// Stage: the fixed 1920x1080 world scaled to the window, with background, CG, character,
// weather and overlay layers. Every visual change goes through here so the scene can be
// rebuilt instantly from a SceneState when loading a save.

import type { AudioEngine } from "./audio";
import { FxLayer } from "./fx";
import { Sprite } from "./sprite";
import type { Assets, CharState, SceneState } from "./types";

export const LIGHTS: Record<string, string> = {
  day: "",
  noon: "brightness(1.02) saturate(1.04)",
  evening: "sepia(0.22) saturate(1.12) brightness(0.95) hue-rotate(-6deg)",
  sunset: "sepia(0.35) saturate(1.25) brightness(0.93) hue-rotate(-10deg)",
  night: "brightness(0.66) saturate(0.78) hue-rotate(8deg) contrast(1.04)",
  lamp: "brightness(0.9) sepia(0.2) saturate(1.06)",
  dawn: "brightness(0.9) saturate(0.88) sepia(0.12) hue-rotate(-4deg)",
  storm: "brightness(0.55) saturate(0.65) contrast(1.06) hue-rotate(10deg)",
  dark: "brightness(0.42) saturate(0.6)",
};

export const POS: Record<string, number> = { left: 0.27, center: 0.5, right: 0.73, farleft: 0.16, farright: 0.84, lc: 0.38, rc: 0.62 };

export function emptyScene(): SceneState {
  return {
    bg: null, bgZoom: 1, bgX: 0, bgY: 0, cg: null, chars: [], bgm: null, bgmVol: 1, amb: [], sfxloop: null, fx: {},
    light: "day", letterbox: false, sepia: false, blur: 0, textbox: true, voicefx: "none",
    camera: { zoom: 1, x: 0, y: 0 }, chapter: "", date: "",
  };
}

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

export class Stage {
  root: HTMLDivElement;
  world: HTMLDivElement;
  private bgLayer: HTMLDivElement;
  private cgLayer: HTMLDivElement;
  private charLayer: HTMLDivElement;
  private tintLayer: HTMLDivElement;
  private overlay: HTMLDivElement;
  private cover: HTMLDivElement;
  private bars: HTMLDivElement;
  private card: HTMLDivElement;
  fx: FxLayer;
  ui: HTMLDivElement;
  sprites = new Map<string, Sprite>();
  scene: SceneState = emptyScene();
  private bgEl: HTMLDivElement | null = null;
  private cgEl: HTMLDivElement | null = null;
  fast = false; // skip mode shortens every transition

  constructor(host: HTMLElement, private assets: Assets, private base: string, private audio: AudioEngine) {
    this.root = document.createElement("div");
    this.root.id = "stage";
    host.appendChild(this.root);
    this.world = this.div("world", this.root);
    this.bgLayer = this.div("bg-layer", this.world);
    this.charLayer = this.div("char-layer", this.world);
    this.tintLayer = this.div("tint-layer", this.world);
    this.cgLayer = this.div("cg-layer", this.world);
    this.fx = new FxLayer(this.world);
    this.overlay = this.div("overlay", this.root);
    this.bars = this.div("letterbox", this.root);
    this.bars.innerHTML = '<div class="bar top"></div><div class="bar bottom"></div>';
    this.ui = this.div("ui-layer", this.root);
    this.card = this.div("card-layer", this.root);
    this.cover = this.div("cover", this.root);
    this.fit();
    addEventListener("resize", () => this.fit());
    const loop = (now: number) => {
      for (const s of this.sprites.values()) s.tick(now, this.audio);
      this.fx.tick(now);
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  private div(cls: string, parent: HTMLElement) {
    const d = document.createElement("div");
    d.className = cls;
    parent.appendChild(d);
    return d;
  }

  fit() {
    const s = Math.min(innerWidth / 1920, innerHeight / 1080);
    this.root.style.transform = `translate(-50%, -50%) scale(${s})`;
    document.documentElement.style.setProperty("--ui-scale", String(s));
  }

  private t(sec: number) {
    return this.fast ? Math.min(sec, 0.05) : sec;
  }

  imgUrl(kind: "bg" | "cg", id: string) {
    const m = kind === "bg" ? this.assets.bg[id] : this.assets.cg[id];
    return m ? this.base + m.src : "";
  }

  // ------------------------------------------------------------------ background
  /** `onSwap` runs at the moment the new background replaces the old one (under the cover for black/white). */
  async setBg(id: string | null, fx = "cross", t = 1, zoom = 1, x = 0, y = 0, onSwap?: () => void) {
    this.scene.bg = id;
    this.scene.bgZoom = zoom;
    this.scene.bgX = x;
    this.scene.bgY = y;
    const dur = this.t(t);
    if (fx === "black" || fx === "white") {
      await this.coverTo(fx, dur / 2);
      onSwap?.();
      this.swapBg(id, 0, zoom, x, y);
      await sleep(this.fast ? 0 : 120);
      await this.coverFrom(dur / 2);
      return;
    }
    onSwap?.();
    await this.swapBg(id, fx === "none" ? 0 : dur, zoom, x, y, fx === "wipe");
  }

  private async swapBg(id: string | null, dur: number, zoom: number, x: number, y: number, wipe = false) {
    const el = document.createElement("div");
    el.className = "bg-img";
    if (id && id !== "black" && id !== "white") {
      const url = this.imgUrl("bg", id);
      el.style.backgroundImage = `url("${url}")`;
      await this.decode(url);
    } else el.style.background = id === "white" ? "#f4f1ea" : "#000";
    this.applyKen(el, zoom, x, y, 0);
    el.style.opacity = "0";
    this.bgLayer.appendChild(el);
    const old = this.bgEl;
    this.bgEl = el;
    await this.fadeIn(el, dur, wipe);
    if (old) old.remove();
  }

  private applyKen(el: HTMLElement, zoom: number, x: number, y: number, dur: number) {
    el.style.transition = dur > 0 ? `transform ${dur}s cubic-bezier(.35,.05,.25,1)` : "none";
    el.style.transform = `translate(${x}px, ${y}px) scale(${zoom})`;
  }

  /** Slow push/pan on the current background (Ken Burns). */
  panBg(zoom: number, x: number, y: number, t: number) {
    this.scene.bgZoom = zoom;
    this.scene.bgX = x;
    this.scene.bgY = y;
    if (this.bgEl) this.applyKen(this.bgEl, zoom, x, y, this.t(t));
  }

  private async fadeIn(el: HTMLElement, dur: number, wipe = false) {
    if (dur <= 0) {
      el.style.opacity = "1";
      return;
    }
    if (wipe) {
      el.style.opacity = "1";
      el.animate(
        [{ clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)" }],
        { duration: dur * 1000, easing: "cubic-bezier(.5,0,.2,1)", fill: "forwards" },
      );
    } else {
      el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: dur * 1000, easing: "ease-in-out", fill: "forwards" });
    }
    await sleep(dur * 1000);
    el.style.opacity = "1";
  }

  private decoded = new Set<string>();
  async decode(url: string) {
    if (!url || this.decoded.has(url)) return;
    const img = new Image();
    img.src = url;
    try {
      await img.decode();
      this.decoded.add(url);
    } catch {
      console.error("image failed", url);
      window.dispatchEvent(new CustomEvent("vn-error", { detail: `image failed: ${url}` }));
    }
  }

  preloadImages(urls: string[]) {
    for (const u of urls) void this.decode(u);
  }

  // ------------------------------------------------------------------ CG
  async setCg(id: string | null, t = 1, fx = "cross") {
    this.scene.cg = id && id !== "off" ? id : null;
    const dur = this.t(t);
    this.fx.setCover(!!this.scene.cg, this.fast);
    if (!this.scene.cg) {
      if (this.cgEl) {
        const el = this.cgEl;
        this.cgEl = null;
        el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: Math.max(1, dur * 1000), fill: "forwards" });
        await sleep(dur * 1000);
        el.remove();
      }
      return;
    }
    const el = document.createElement("div");
    el.className = "cg-img";
    const url = this.imgUrl("cg", this.scene.cg);
    el.style.backgroundImage = `url("${url}")`;
    await this.decode(url);
    el.style.opacity = "0";
    this.cgLayer.appendChild(el);
    const old = this.cgEl;
    this.cgEl = el;
    if (fx === "black" || fx === "white") {
      await this.coverTo(fx, dur / 2);
      el.style.opacity = "1";
      if (old) old.remove();
      await this.coverFrom(dur / 2);
      return;
    }
    await this.fadeIn(el, dur);
    if (old) old.remove();
  }

  panCg(zoom: number, x: number, y: number, t: number) {
    if (this.cgEl) this.applyKen(this.cgEl, zoom, x, y, this.t(t));
  }

  // ------------------------------------------------------------------ characters
  private makeSprite(c: CharState) {
    const data = this.assets.chars[c.id];
    const conf = this.assets.charConf[c.id];
    if (!data || !conf) throw new Error(`no sprite data for ${c.id}`);
    const s = new Sprite(c.id, data, conf, this.base, c.pose);
    s.setExpr(c.expr, false);
    s.setLight(LIGHTS[this.scene.light] ?? "");
    s.el.style.zIndex = String(10 + c.z);
    this.charLayer.appendChild(s.el);
    this.sprites.set(c.id, s);
    return s;
  }

  async show(id: string, pose: string | undefined, expr: string | undefined, x: number, t = 0.45, from = "none") {
    const dur = this.t(t);
    let st = this.scene.chars.find((c) => c.id === id);
    const existing = this.sprites.get(id);
    if (st && existing) {
      if (pose) this.setPose(id, pose);
      if (expr) this.setExpr(id, expr);
      if (Math.abs(existing.x - x) > 1e-3) await this.move(id, x, t);
      return;
    }
    const conf = this.assets.charConf[id];
    st = { id, pose: pose || conf.defaultPose, expr: expr || "neutral", x, z: this.scene.chars.length };
    this.scene.chars.push(st);
    const s = this.makeSprite(st);
    const dx = from === "left" ? -90 : from === "right" ? 90 : 0;
    const dy = from === "bottom" ? 60 : 0;
    s.place(x, 0);
    s.el.style.opacity = "0";
    await this.decodeSprite(s);
    if (dur <= 0) {
      s.el.style.opacity = "1";
      return;
    }
    s.el.animate(
      [{ opacity: 0, transform: `translate(${dx}px, ${dy + 12}px)` }, { opacity: 1, transform: "translate(0,0)" }],
      { duration: dur * 1000, easing: "cubic-bezier(.2,.7,.2,1)", fill: "none" },
    );
    s.el.style.opacity = "1";
    await sleep(dur * 1000);
  }

  private async decodeSprite(s: Sprite) {
    const imgs = Array.from(s.el.querySelectorAll("img"));
    await Promise.all(imgs.map((i) => i.decode().catch(() => {})));
  }

  async hide(id: string, t = 0.4, to = "none") {
    const dur = this.t(t);
    this.scene.chars = this.scene.chars.filter((c) => c.id !== id);
    const s = this.sprites.get(id);
    if (!s) return;
    this.sprites.delete(id);
    const dx = to === "left" ? -90 : to === "right" ? 90 : 0;
    if (dur > 0) {
      s.el.animate([{ opacity: 1, transform: "translate(0,0)" }, { opacity: 0, transform: `translate(${dx}px, 8px)` }],
        { duration: dur * 1000, easing: "ease-in", fill: "forwards" });
      await sleep(dur * 1000);
    }
    s.el.remove();
  }

  async hideAll(t = 0.4) {
    await Promise.all([...this.sprites.keys()].map((id) => this.hide(id, t)));
  }

  setExpr(id: string, expr: string) {
    const st = this.scene.chars.find((c) => c.id === id);
    const s = this.sprites.get(id);
    if (!st || !s) return;
    st.expr = expr;
    s.setExpr(expr, !this.fast);
  }

  setPose(id: string, pose: string) {
    const st = this.scene.chars.find((c) => c.id === id);
    const s = this.sprites.get(id);
    if (!st || !s) return;
    st.pose = pose;
    s.setPose(pose);
  }

  async move(id: string, x: number, t = 0.6) {
    const st = this.scene.chars.find((c) => c.id === id);
    const s = this.sprites.get(id);
    if (!st || !s) return;
    st.x = x;
    const dur = this.t(t);
    s.place(x, dur);
    await sleep(dur * 1000);
  }

  /** Hop / nod / shiver reaction on a sprite. */
  react(id: string, kind: string) {
    const s = this.sprites.get(id);
    if (!s || this.fast) return;
    const k: Record<string, Keyframe[]> = {
      hop: [{ transform: "translateY(0)" }, { transform: "translateY(-26px)" }, { transform: "translateY(0)" }],
      nod: [{ transform: "translateY(0)" }, { transform: "translateY(10px)" }, { transform: "translateY(0)" }],
      shake: [{ transform: "translateX(0)" }, { transform: "translateX(-10px)" }, { transform: "translateX(9px)" },
        { transform: "translateX(-6px)" }, { transform: "translateX(0)" }],
      lean: [{ transform: "translate(0,0)" }, { transform: "translate(-18px, 6px)" }],
      back: [{ transform: "translate(0,0) scale(1)" }, { transform: "translate(0, 10px) scale(0.985)" }, { transform: "translate(0,0) scale(1)" }],
    };
    s.el.animate(k[kind] ?? k.hop, { duration: kind === "shake" ? 380 : 420, easing: "ease-out" });
  }

  focusSpeaker(who: string | undefined) {
    const many = this.sprites.size > 1;
    for (const [id, s] of this.sprites) s.setDim(many && !!who && id !== who && this.sprites.has(who));
  }

  // ------------------------------------------------------------------ look
  setLight(name: string) {
    this.scene.light = name;
    for (const s of this.sprites.values()) s.setLight(LIGHTS[name] ?? "");
  }

  /** Colour grade over background + characters (for re-using a day painting at dawn/dusk). */
  setTint(name: string, t = 1.5) {
    this.scene.tint = name;
    const TINTS: Record<string, string> = {
      dawn: "rgba(92, 118, 184, 0.52)",
      dusk: "rgba(255, 146, 86, 0.36)",
      night: "rgba(38, 56, 118, 0.62)",
      gray: "rgba(120, 130, 140, 0.4)",
    };
    const c = TINTS[name];
    this.tintLayer.style.transition = `opacity ${this.t(t)}s ease`;
    if (c) this.tintLayer.style.background = c;
    this.tintLayer.style.opacity = c ? "1" : "0";
  }

  setLetterbox(on: boolean) {
    this.scene.letterbox = on;
    this.bars.classList.toggle("on", on);
  }

  setFilters(sepia: boolean, blur: number) {
    this.scene.sepia = sepia;
    this.scene.blur = blur;
    const parts: string[] = [];
    if (sepia) parts.push("sepia(0.55) saturate(0.8) contrast(0.96) brightness(1.02)");
    if (blur > 0) parts.push(`blur(${blur}px)`);
    this.bgLayer.style.filter = parts.join(" ") || "none";
    this.charLayer.style.filter = sepia ? "sepia(0.55) saturate(0.8)" : "none";
    this.cgLayer.style.filter = sepia ? "sepia(0.5) saturate(0.85)" : "none";
  }

  setFx(kind: string, level: number, instant = false) {
    if (kind === "none" || kind === "off") {
      this.scene.fx = {};
      this.fx.clear(instant);
      return;
    }
    if (level > 0) this.scene.fx[kind] = level;
    else delete this.scene.fx[kind];
    this.fx.set(kind, level, instant);
  }

  async camera(zoom: number, x: number, y: number, t: number, ease = "cubic-bezier(.4,0,.2,1)") {
    this.scene.camera = { zoom, x, y };
    const dur = this.t(t);
    this.world.style.transition = dur > 0 ? `transform ${dur}s ${ease}` : "none";
    this.world.style.transform = `scale(${zoom}) translate(${x}px, ${y}px)`;
    if (dur > 0) await sleep(dur * 1000);
  }

  shake(amp = 12, t = 0.5) {
    if (this.fast) return;
    const n = Math.max(4, Math.round(t * 30));
    const frames: Keyframe[] = [];
    for (let i = 0; i <= n; i++) {
      const k = 1 - i / n;
      frames.push({ translate: `${(Math.random() * 2 - 1) * amp * k}px ${(Math.random() * 2 - 1) * amp * k * 0.7}px` });
    }
    this.root.querySelector<HTMLElement>(".world")!.animate(frames, { duration: t * 1000, easing: "linear" });
  }

  async flash(color = "white", t = 0.35) {
    if (this.fast) return;
    const f = document.createElement("div");
    f.className = "flash";
    f.style.background = color === "white" ? "#fff" : color;
    this.overlay.appendChild(f);
    f.animate([{ opacity: 0.95 }, { opacity: 0 }], { duration: t * 1000, easing: "ease-out", fill: "forwards" });
    await sleep(t * 1000);
    f.remove();
  }

  async coverTo(color: string, t: number) {
    this.cover.style.background = color === "white" ? "#f6f3ec" : "#000";
    this.cover.style.transition = `opacity ${this.t(t)}s ease-in-out`;
    this.cover.style.pointerEvents = "auto";
    this.cover.style.opacity = "1";
    await sleep(this.t(t) * 1000);
  }

  async coverFrom(t: number) {
    this.cover.style.transition = `opacity ${this.t(t)}s ease-in-out`;
    this.cover.style.opacity = "0";
    this.cover.style.pointerEvents = "none";
    await sleep(this.t(t) * 1000);
  }

  // ------------------------------------------------------------------ cards
  async chapterCard(num: string, title: string, sub: string, hold = 2.6) {
    this.card.innerHTML = `<div class="chapter-card"><div class="cc-freq"><span class="cc-num">${num}</span></div>
      <div class="cc-title">${title}</div><div class="cc-sub">${sub}</div><div class="cc-wave"></div></div>`;
    const el = this.card.firstElementChild as HTMLElement;
    if (this.fast) {
      await sleep(60);
      this.card.innerHTML = "";
      return;
    }
    el.animate([{ opacity: 0, filter: "blur(6px)" }, { opacity: 1, filter: "blur(0)" }], { duration: 900, fill: "forwards", easing: "ease-out" });
    await sleep(hold * 1000);
    el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 700, fill: "forwards" });
    await sleep(720);
    this.card.innerHTML = "";
  }

  async dateCard(text: string) {
    this.scene.date = text;
    if (this.fast) return;
    const el = document.createElement("div");
    el.className = "date-card";
    el.innerHTML = `<span class="dc-line"></span><span class="dc-text">${text}</span>`;
    this.card.appendChild(el);
    el.animate([{ opacity: 0, transform: "translateX(-20px)" }, { opacity: 1, transform: "translateX(0)" }], { duration: 600, fill: "forwards", easing: "ease-out" });
    setTimeout(() => {
      el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 900, fill: "forwards" });
      setTimeout(() => el.remove(), 950);
    }, 3200);
  }

  async caption(text: string, hold = 2.4) {
    const el = document.createElement("div");
    el.className = "caption-card";
    el.textContent = text;
    this.card.appendChild(el);
    if (this.fast) {
      await sleep(40);
      el.remove();
      return;
    }
    el.animate([{ opacity: 0, letterSpacing: "0.5em" }, { opacity: 1, letterSpacing: "0.32em" }], { duration: 1100, fill: "forwards", easing: "ease-out" });
    await sleep(hold * 1000);
    el.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 800, fill: "forwards" });
    await sleep(820);
    el.remove();
  }

  // ------------------------------------------------------------------ restore
  async restore(sc: SceneState) {
    for (const s of this.sprites.values()) s.el.remove();
    this.sprites.clear();
    this.scene = JSON.parse(JSON.stringify(sc));
    this.bgLayer.innerHTML = "";
    this.cgLayer.innerHTML = "";
    this.bgEl = null;
    this.cgEl = null;
    await this.swapBg(sc.bg, 0, sc.bgZoom, sc.bgX, sc.bgY);
    if (sc.cg) {
      const el = document.createElement("div");
      el.className = "cg-img";
      const url = this.imgUrl("cg", sc.cg);
      el.style.backgroundImage = `url("${url}")`;
      await this.decode(url);
      this.cgLayer.appendChild(el);
      this.cgEl = el;
    }
    for (const c of this.scene.chars) {
      const s = this.makeSprite(c);
      s.place(c.x, 0);
      await this.decodeSprite(s);
    }
    this.setLight(sc.light);
    this.setTint(sc.tint ?? "none", 0);
    this.setLetterbox(sc.letterbox);
    this.setFilters(sc.sepia, sc.blur);
    this.fx.clear(true);
    for (const [k, v] of Object.entries(sc.fx)) this.fx.set(k, v, true);
    this.fx.setCover(!!sc.cg, true);
    this.world.style.transition = "none";
    this.world.style.transform = `scale(${sc.camera.zoom}) translate(${sc.camera.x}px, ${sc.camera.y}px)`;
    this.cover.style.transition = "none";
    this.cover.style.opacity = "0";
    this.cover.style.pointerEvents = "none";
    this.card.innerHTML = "";
  }

  clearAll() {
    for (const s of this.sprites.values()) s.el.remove();
    this.sprites.clear();
    this.bgLayer.innerHTML = "";
    this.cgLayer.innerHTML = "";
    this.bgEl = null;
    this.cgEl = null;
    this.fx.clear(true);
    this.fx.setCover(false, true);
    this.card.innerHTML = "";
    this.scene = emptyScene();
    this.setTint("none", 0);
    this.setLetterbox(false);
    this.setFilters(false, 0);
    this.world.style.transform = "none";
  }
}
