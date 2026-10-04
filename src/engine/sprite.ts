// Layered character sprite: body + expression face + blink eyes + two mouth shapes.
// Blinks on its own clock, breathes with a CSS idle loop, and drives the mouth from the
// pre-analysed envelope of the voice that is actually playing.

import type { AudioEngine, VoiceHandle } from "./audio";
import type { CharSprites, FaceSet } from "./types";

const ENV_RATE = 50; // lip-sync envelope frames per second

function layer(src: string, rect: [number, number, number, number], w: number, h: number, cls: string, base: string) {
  const img = new Image();
  img.decoding = "async";
  img.draggable = false;
  img.className = "sp-layer " + cls;
  img.src = base + src;
  const [x, y, rw, rh] = rect;
  img.style.left = `${(x / w) * 100}%`;
  img.style.top = `${(y / h) * 100}%`;
  img.style.width = `${(rw / w) * 100}%`;
  img.style.height = `${(rh / h) * 100}%`;
  return img;
}

export class Sprite {
  el: HTMLDivElement;
  private inner: HTMLDivElement;
  private bodyImg: HTMLImageElement;
  private faceWrap: HTMLDivElement | null = null;
  private eyes: HTMLImageElement | null = null;
  private mouths: HTMLImageElement[] = [];
  pose: string;
  expr = "neutral";
  x = 0.5;
  private nextBlink = 0;
  private blinkUntil = 0;
  private doubleBlinkAt = 0;
  private mouthState = 0;
  private mouthHoldUntil = 0;
  private voice: VoiceHandle | null = null;
  private env: Uint8Array | null = null;
  private lightFilter = "";
  private dimmed = false;

  constructor(
    public id: string,
    private data: CharSprites,
    private conf: { scale: number; y: number; defaultPose: string },
    private base: string,
    pose?: string,
  ) {
    this.pose = pose && data.bodies[pose] ? pose : conf.defaultPose;
    this.el = document.createElement("div");
    this.el.className = "sprite";
    this.el.dataset.char = id;
    const w = data.w * conf.scale;
    const h = data.h * conf.scale;
    this.el.style.width = `${w}px`;
    this.el.style.height = `${h}px`;
    this.el.style.top = `${conf.y}px`;
    this.inner = document.createElement("div");
    this.inner.className = "sprite-inner";
    this.inner.style.animationDelay = `${-Math.random() * 4}s`;
    this.el.appendChild(this.inner);
    this.bodyImg = new Image();
    this.bodyImg.className = "sp-layer sp-body";
    this.bodyImg.draggable = false;
    this.bodyImg.src = base + data.bodies[this.pose];
    this.inner.appendChild(this.bodyImg);
    this.setExpr("neutral", false);
    this.scheduleBlink(performance.now());
  }

  /** Every image this sprite may show (for preloading). */
  static urls(data: CharSprites): string[] {
    const out = Object.values(data.bodies);
    for (const f of Object.values(data.faces)) {
      out.push(f.face.src);
      if (f.eyes) out.push(f.eyes.src);
      for (const m of f.mouth) out.push(m.src);
    }
    return out;
  }

  setPose(pose: string) {
    if (!this.data.bodies[pose] || pose === this.pose) return;
    this.pose = pose;
    const next = new Image();
    next.className = "sp-layer sp-body";
    next.draggable = false;
    next.src = this.base + this.data.bodies[pose];
    const old = this.bodyImg;
    next.style.opacity = "0";
    old.after(next);
    this.bodyImg = next;
    const show = () => {
      next.style.transition = "opacity 160ms linear";
      requestAnimationFrame(() => (next.style.opacity = "1"));
      setTimeout(() => old.remove(), 200);
    };
    if (next.complete) show();
    else next.decode().then(show, show);
  }

  setExpr(expr: string, animate = true) {
    const fs: FaceSet | undefined = this.data.faces[expr] ?? this.data.faces["neutral"];
    if (!fs) return;
    if (expr === this.expr && this.faceWrap) return;
    this.expr = this.data.faces[expr] ? expr : "neutral";
    const { w, h } = this.data;
    const wrap = document.createElement("div");
    wrap.className = "sp-face";
    wrap.appendChild(layer(fs.face.src, fs.face.rect, w, h, "sp-facebase", this.base));
    const eyes = fs.eyes ? layer(fs.eyes.src, fs.eyes.rect, w, h, "sp-eyes", this.base) : null;
    if (eyes) wrap.appendChild(eyes);
    const mouths = fs.mouth.map((m, i) => layer(m.src, m.rect, w, h, `sp-mouth sp-mouth${i + 1}`, this.base));
    for (const m of mouths) wrap.appendChild(m);
    const old = this.faceWrap;
    this.inner.appendChild(wrap);
    this.faceWrap = wrap;
    this.eyes = eyes;
    this.mouths = mouths;
    this.applyMouth(this.mouthState);
    this.applyEyes(performance.now() < this.blinkUntil);
    if (old) {
      if (animate) {
        wrap.style.opacity = "0";
        const imgs = Array.from(wrap.querySelectorAll("img"));
        Promise.all(imgs.map((i) => i.decode().catch(() => {}))).then(() => {
          wrap.style.transition = "opacity 140ms linear";
          wrap.style.opacity = "1";
          setTimeout(() => old.remove(), 170);
        });
      } else old.remove();
    }
  }

  setLight(filter: string) {
    this.lightFilter = filter;
    this.applyFilter();
  }

  setDim(d: boolean) {
    if (d === this.dimmed) return;
    this.dimmed = d;
    this.applyFilter();
  }

  private applyFilter() {
    const f = `${this.lightFilter} ${this.dimmed ? "brightness(0.8) saturate(0.9)" : ""}`.trim();
    this.el.style.filter = f || "none";
  }

  place(x: number, animate: number) {
    this.x = x;
    const w = this.data.w * this.conf.scale;
    this.el.style.transition = animate > 0 ? `left ${animate}s cubic-bezier(.4,.1,.2,1), opacity .35s` : "none";
    this.el.style.left = `${x * 1920 - w / 2}px`;
  }

  speak(h: VoiceHandle | null, env: Uint8Array | null) {
    this.voice = h;
    this.env = env;
  }

  private scheduleBlink(now: number) {
    this.nextBlink = now + 2200 + Math.random() * 4200;
  }

  private applyEyes(closed: boolean) {
    if (this.eyes) this.eyes.style.opacity = closed ? "1" : "0";
  }

  private applyMouth(s: number) {
    this.mouths.forEach((m, i) => (m.style.opacity = s === i + 1 ? "1" : "0"));
  }

  /** Per-frame update: blink + lip sync. */
  tick(now: number, audio: AudioEngine) {
    // --- blink
    if (this.eyes) {
      if (now >= this.nextBlink && now >= this.blinkUntil) {
        this.blinkUntil = now + 95 + Math.random() * 45;
        this.doubleBlinkAt = Math.random() < 0.16 ? this.blinkUntil + 150 : 0;
        this.scheduleBlink(now);
      }
      if (this.doubleBlinkAt && now >= this.doubleBlinkAt) {
        this.blinkUntil = now + 90;
        this.doubleBlinkAt = 0;
      }
      this.applyEyes(now < this.blinkUntil);
    }
    // --- mouth from the real playback position of the voice
    let target = 0;
    const v = this.voice;
    if (v && !v.ended && this.env && this.mouths.length) {
      const t = audio.voiceTime(v);
      if (t >= 0 && t < v.duration) {
        const i = Math.min(this.env.length - 1, Math.floor(t * ENV_RATE));
        const lvl = this.env[i] / 255;
        const nxt = this.env[Math.min(this.env.length - 1, i + 1)] / 255;
        const level = Math.max(lvl, nxt * 0.6);
        const hasM2 = this.mouths.length > 1;
        // thresholds match the envelope built by tools/voice/make_voices.py (with hysteresis)
        if (level > (this.mouthState === 2 ? 0.48 : 0.56) && hasM2) target = 2;
        else if (level > (this.mouthState >= 1 ? 0.2 : 0.26)) target = 1;
      }
    } else if (v && v.ended) {
      this.voice = null;
    }
    if (target !== this.mouthState) {
      // hold each shape briefly so it never flickers faster than ~16 fps
      if (now >= this.mouthHoldUntil || target === 0) {
        this.mouthState = target;
        this.mouthHoldUntil = now + 55;
        this.applyMouth(target);
      }
    }
  }
}
