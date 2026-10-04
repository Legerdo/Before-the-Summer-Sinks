// Dialogue box with a smooth per-character reveal, inline pauses ({w=0.4}) and a wait marker.

interface Piece {
  ch?: string;
  br?: boolean;
  wait?: number;
}

function parse(text: string): Piece[] {
  const out: Piece[] = [];
  const re = /\{w=([\d.]+)\}|\\n|([\s\S])/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) {
    if (m[1] !== undefined) out.push({ wait: Number(m[1]) });
    else if (m[0] === "\\n") out.push({ br: true });
    else out.push({ ch: m[2] });
  }
  return out;
}

export function plain(text: string) {
  return text.replace(/\{w=[\d.]+\}/g, "").replace(/\\n/g, " ");
}

export class TextBox {
  el: HTMLDivElement;
  private nameEl: HTMLDivElement;
  private textEl: HTMLDivElement;
  private waitEl: HTMLDivElement;
  private spans: HTMLSpanElement[] = [];
  private pieces: Piece[] = [];
  private raf = 0;
  private resolveDone: (() => void) | null = null;
  revealing = false;
  visible = true;

  constructor(parent: HTMLElement) {
    this.el = document.createElement("div");
    this.el.className = "textbox";
    this.el.innerHTML = `<div class="tb-glass"></div><div class="tb-shimmer"></div>
      <div class="tb-name"><span class="tb-name-text"></span></div>
      <div class="tb-text" aria-live="polite"></div><div class="tb-wait"></div>`;
    parent.appendChild(this.el);
    this.nameEl = this.el.querySelector(".tb-name")!;
    this.textEl = this.el.querySelector(".tb-text")!;
    this.waitEl = this.el.querySelector(".tb-wait")!;
  }

  setOpacity(v: number) {
    this.el.style.setProperty("--tb-alpha", String(v));
  }

  show(visible: boolean) {
    this.visible = visible;
    this.el.classList.toggle("hidden", !visible);
  }

  clear() {
    cancelAnimationFrame(this.raf);
    this.textEl.innerHTML = "";
    this.nameEl.classList.remove("on");
    this.waitEl.classList.remove("on");
    this.revealing = false;
    this.resolveDone?.();
    this.resolveDone = null;
  }

  /** Displays a line; resolves when the whole line is visible. */
  say(name: string | undefined, color: string | undefined, text: string, cps: number, narration: boolean): Promise<void> {
    cancelAnimationFrame(this.raf);
    this.resolveDone?.();
    this.waitEl.classList.remove("on");
    const nameText = this.nameEl.querySelector(".tb-name-text") as HTMLSpanElement;
    if (name) {
      nameText.textContent = name;
      this.nameEl.style.setProperty("--name-color", color ?? "#fff");
      this.nameEl.classList.add("on");
    } else this.nameEl.classList.remove("on");
    this.textEl.classList.toggle("narration", narration);
    this.textEl.innerHTML = "";
    this.pieces = parse(text);
    this.spans = [];
    const frag = document.createDocumentFragment();
    // group by words so the browser keeps Korean words intact (word-break: keep-all)
    let word: HTMLSpanElement | null = null;
    for (const p of this.pieces) {
      if (p.br) {
        frag.appendChild(document.createElement("br"));
        word = null;
        continue;
      }
      if (p.ch === undefined) continue;
      if (p.ch === " ") {
        const sp = document.createElement("span");
        sp.className = "ch sp";
        sp.textContent = " ";
        frag.appendChild(sp);
        this.spans.push(sp);
        word = null;
        continue;
      }
      if (!word) {
        word = document.createElement("span");
        word.className = "w";
        frag.appendChild(word);
      }
      const s = document.createElement("span");
      s.className = "ch";
      s.textContent = p.ch;
      word.appendChild(s);
      this.spans.push(s);
    }
    this.textEl.appendChild(frag);
    return new Promise<void>((resolve) => {
      this.resolveDone = resolve;
      if (cps <= 0 || cps >= 1000) {
        this.finish();
        return;
      }
      this.revealing = true;
      let shown = 0;
      let pi = 0;
      let budget = 0;
      let last = performance.now();
      let pause = 0;
      const step = (now: number) => {
        const dt = (now - last) / 1000;
        last = now;
        if (pause > 0) pause -= dt;
        else budget += dt * cps;
        while (budget >= 1 && pi < this.pieces.length && pause <= 0) {
          const p = this.pieces[pi++];
          if (p.wait) {
            pause = p.wait;
            break;
          }
          if (p.br || p.ch === undefined) continue;
          this.spans[shown++]?.classList.add("on");
          budget -= 1;
          // small natural pause after punctuation
          if (p.ch && /[.,!?…。、~]/.test(p.ch) && pi < this.pieces.length) budget -= p.ch === "," ? 2 : 3.2;
        }
        if (pi >= this.pieces.length && pause <= 0) {
          this.finish();
          return;
        }
        this.raf = requestAnimationFrame(step);
      };
      this.raf = requestAnimationFrame(step);
    });
  }

  /** Reveal everything immediately. */
  finish() {
    cancelAnimationFrame(this.raf);
    for (const s of this.spans) s.classList.add("on", "instant");
    this.revealing = false;
    this.waitEl.classList.add("on");
    const r = this.resolveDone;
    this.resolveDone = null;
    r?.();
  }
}
