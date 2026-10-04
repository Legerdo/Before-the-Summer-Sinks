// Canvas weather / atmosphere layer: rain, storm, fireflies, dust motes, water glitter, static,
// and "lightning" (flashes + thunder only, for indoor scenes during a storm).

type Kind = "rain" | "storm" | "fireflies" | "dust" | "glitter" | "static" | "petals" | "lightning";

/** Kinds that belong to the background's space (sky, water surface): hidden while a CG covers the stage. */
const SCENIC: ReadonlySet<Kind> = new Set<Kind>(["rain", "storm", "glitter"]);

interface P {
  x: number;
  y: number;
  vx: number;
  vy: number;
  s: number;
  a: number;
  ph: number;
  life: number;
}

export class FxLayer {
  canvas: HTMLCanvasElement;
  private g: CanvasRenderingContext2D;
  private active = new Map<Kind, { level: number; target: number; ps: P[] }>();
  private last = performance.now();
  private noiseImg: ImageData | null = null;
  onLightning: () => void = () => {};
  private nextBolt = 0;
  flashAlpha = 0;
  /** 0..1: how much a CG currently covers the stage (fades scenic weather out). */
  private cover = 0;
  private coverTarget = 0;

  constructor(parent: HTMLElement) {
    this.canvas = document.createElement("canvas");
    this.canvas.width = 1920;
    this.canvas.height = 1080;
    this.canvas.className = "fx-canvas";
    parent.appendChild(this.canvas);
    this.g = this.canvas.getContext("2d")!;
  }

  set(kind: string, level: number, instant = false) {
    const k = kind as Kind;
    let a = this.active.get(k);
    if (!a) {
      if (level <= 0) return;
      a = { level: instant ? level : 0, target: level, ps: [] };
      this.active.set(k, a);
    }
    a.target = level;
    if (instant) a.level = level;
  }

  clear(instant = false) {
    for (const [k, a] of this.active) {
      a.target = 0;
      if (instant) this.active.delete(k);
    }
  }

  /** A CG is (not) on screen: rain/storm/glitter fade out behind it; lightning flashes stay. */
  setCover(on: boolean, instant = false) {
    this.coverTarget = on ? 1 : 0;
    if (instant) this.cover = this.coverTarget;
  }

  levels(): Record<string, number> {
    const out: Record<string, number> = {};
    for (const [k, a] of this.active) if (a.target > 0) out[k] = a.target;
    return out;
  }

  private spawn(k: Kind): P {
    const r = Math.random;
    switch (k) {
      case "rain":
      case "storm": {
        const storm = k === "storm";
        return { x: r() * 2300 - 200, y: -40 - r() * 400, vx: storm ? -9 - r() * 4 : -2.2, vy: (storm ? 38 : 26) + r() * 10,
          s: storm ? 1.4 + r() : 1 + r() * 0.6, a: 0.18 + r() * 0.3, ph: 0, life: 1 };
      }
      case "fireflies":
        return { x: r() * 1920, y: 260 + r() * 760, vx: (r() - 0.5) * 0.35, vy: (r() - 0.5) * 0.25, s: 2 + r() * 3.2,
          a: 0, ph: r() * Math.PI * 2, life: 0 };
      case "dust":
        return { x: r() * 1920, y: r() * 1080, vx: 0.08 + r() * 0.12, vy: -0.04 - r() * 0.08, s: 0.8 + r() * 2.2,
          a: 0.1 + r() * 0.35, ph: r() * Math.PI * 2, life: 0 };
      case "glitter":
        return { x: r() * 1920, y: 560 + r() * 520, vx: 0, vy: 0, s: 1.5 + r() * 3.5, a: 0, ph: r() * Math.PI * 2, life: 0 };
      case "petals":
        return { x: r() * 2100, y: -30, vx: -0.6 - r() * 0.6, vy: 0.7 + r() * 0.7, s: 3 + r() * 3, a: 0.7, ph: r() * 6, life: 0 };
      default:
        return { x: 0, y: 0, vx: 0, vy: 0, s: 1, a: 1, ph: 0, life: 0 };
    }
  }

  private target(k: Kind, level: number): number {
    const base = { rain: 340, storm: 900, fireflies: 70, dust: 70, glitter: 130, static: 0, petals: 40, lightning: 0 }[k];
    return Math.round(base * level);
  }

  tick(now: number) {
    const dt = Math.min(50, now - this.last) / 16.67;
    this.last = now;
    const g = this.g;
    g.clearRect(0, 0, 1920, 1080);
    if (!this.active.size && this.flashAlpha <= 0) {
      this.canvas.style.display = "none";
      return;
    }
    this.canvas.style.display = "block";
    const step = 0.025 * dt;
    this.cover += Math.max(-step, Math.min(step, this.coverTarget - this.cover));
    for (const [k, a] of [...this.active]) {
      a.level += (a.target - a.level) * Math.min(1, 0.03 * dt);
      if (a.target === 0 && a.level < 0.01) {
        this.active.delete(k);
        continue;
      }
      const want = this.target(k, a.level);
      while (a.ps.length < want) {
        const p = this.spawn(k);
        if (k === "rain" || k === "storm") p.y = Math.random() * 1080;
        a.ps.push(p);
      }
      if (a.ps.length > want) a.ps.length = want;
      const vis = SCENIC.has(k) ? 1 - this.cover : 1;
      this.draw(k, a.ps, a.level * vis, now, dt);
    }
    // lightning: full strength with a heavy storm outside; "lightning" alone = flashes through the windows
    const storm = this.active.get("storm");
    const bolt = this.active.get("lightning");
    const boltLevel = storm && storm.target > 0.5 ? 1 : bolt && bolt.target > 0 ? bolt.level : 0;
    if (boltLevel > 0) {
      const indoor = !(storm && storm.target > 0.5);
      if (!this.nextBolt) this.nextBolt = now + 4000 + Math.random() * 6000;
      if (now > this.nextBolt) {
        this.flashAlpha = (0.55 + Math.random() * 0.3) * boltLevel;
        this.nextBolt = now + (indoor ? 8000 + Math.random() * 12000 : 5000 + Math.random() * 9000);
        this.onLightning();
      }
    } else this.nextBolt = 0;
    if (this.flashAlpha > 0) {
      g.fillStyle = `rgba(220,230,255,${this.flashAlpha})`;
      g.fillRect(0, 0, 1920, 1080);
      this.flashAlpha -= 0.045 * dt * (this.flashAlpha > 0.3 ? 1.4 : 0.8);
    }
  }

  private draw(k: Kind, ps: P[], level: number, now: number, dt: number) {
    const g = this.g;
    if (k === "rain" || k === "storm") {
      g.strokeStyle = k === "storm" ? "rgba(190,205,230,0.9)" : "rgba(200,215,235,0.9)";
      g.lineCap = "round";
      for (const p of ps) {
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        if (p.y > 1100) Object.assign(p, this.spawn(k), { y: -20 });
        g.globalAlpha = p.a * Math.min(1, level * 1.4);
        g.lineWidth = p.s;
        g.beginPath();
        g.moveTo(p.x, p.y);
        g.lineTo(p.x - p.vx * 1.6, p.y - p.vy * 1.6);
        g.stroke();
      }
      g.globalAlpha = 1;
      if (k === "storm") {
        g.fillStyle = `rgba(20,30,48,${0.16 * level})`;
        g.fillRect(0, 0, 1920, 1080);
      }
      return;
    }
    if (k === "fireflies" || k === "glitter" || k === "dust") {
      g.globalCompositeOperation = "lighter";
      for (const p of ps) {
        p.ph += (k === "glitter" ? 0.09 : 0.03) * dt;
        if (k === "fireflies") {
          p.vx += (Math.random() - 0.5) * 0.02 * dt;
          p.vy += (Math.random() - 0.5) * 0.02 * dt;
          p.vx *= 0.99;
          p.vy *= 0.99;
          p.life = Math.min(1, p.life + 0.01 * dt);
        }
        if (k === "dust") p.life = Math.min(1, p.life + 0.004 * dt);
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        if (p.x < -40 || p.x > 1960 || p.y < -40 || p.y > 1120) Object.assign(p, this.spawn(k));
        let alpha: number;
        let col: string;
        let rad: number;
        if (k === "fireflies") {
          alpha = (0.35 + 0.65 * Math.max(0, Math.sin(p.ph))) * p.life * level;
          col = "255,236,140";
          rad = p.s * 6;
        } else if (k === "glitter") {
          const tw = Math.max(0, Math.sin(p.ph)) ** 6;
          alpha = tw * level;
          col = "255,250,230";
          rad = p.s * 4;
          if (tw < 0.02 && Math.random() < 0.01) Object.assign(p, this.spawn(k));
        } else {
          alpha = p.a * p.life * level * (0.6 + 0.4 * Math.sin(p.ph));
          col = "255,240,210";
          rad = p.s * 2.5;
        }
        const grd = g.createRadialGradient(p.x, p.y, 0, p.x, p.y, rad);
        grd.addColorStop(0, `rgba(${col},${alpha})`);
        grd.addColorStop(0.35, `rgba(${col},${alpha * 0.35})`);
        grd.addColorStop(1, `rgba(${col},0)`);
        g.fillStyle = grd;
        g.fillRect(p.x - rad, p.y - rad, rad * 2, rad * 2);
        if (k === "glitter" && alpha > 0.3) {
          g.fillStyle = `rgba(255,255,255,${alpha * 0.8})`;
          g.fillRect(p.x - rad * 1.4, p.y - 0.6, rad * 2.8, 1.2);
          g.fillRect(p.x - 0.6, p.y - rad * 1.1, 1.2, rad * 2.2);
        }
      }
      g.globalCompositeOperation = "source-over";
      return;
    }
    if (k === "petals") {
      g.fillStyle = "rgba(120,170,90,0.8)";
      for (const p of ps) {
        p.ph += 0.03 * dt;
        p.x += (p.vx + Math.sin(p.ph) * 0.6) * dt;
        p.y += p.vy * dt;
        if (p.y > 1100) Object.assign(p, this.spawn(k));
        g.save();
        g.translate(p.x, p.y);
        g.rotate(p.ph);
        g.globalAlpha = p.a * level;
        g.beginPath();
        g.ellipse(0, 0, p.s * 1.6, p.s * 0.8, 0, 0, Math.PI * 2);
        g.fill();
        g.restore();
      }
      g.globalAlpha = 1;
      return;
    }
    if (k === "static") {
      const w = 480, h = 270;
      if (!this.noiseImg) this.noiseImg = g.createImageData(w, h);
      const d = this.noiseImg.data;
      for (let i = 0; i < d.length; i += 4) {
        const v = (Math.random() * 255) | 0;
        d[i] = d[i + 1] = d[i + 2] = v;
        d[i + 3] = (level * 150) | 0;
      }
      const tmp = document.createElement("canvas");
      tmp.width = w;
      tmp.height = h;
      tmp.getContext("2d")!.putImageData(this.noiseImg, 0, 0);
      g.imageSmoothingEnabled = false;
      g.drawImage(tmp, 0, 0, 1920, 1080);
      g.imageSmoothingEnabled = true;
    }
  }
}
