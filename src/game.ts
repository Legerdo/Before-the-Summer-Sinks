// Game shell: connects the VM to the dialogue box, voices, lip sync, auto/skip modes,
// saves and the menu screens. Implements the VM Host interface.

import { AudioEngine, type VoiceHandle } from "./engine/audio";
import { SLOT_COUNT, SAVE_VERSION, Store } from "./engine/save";
import { Stage } from "./engine/stage";
import { plain, TextBox } from "./engine/textbox";
import type { Assets, BacklogEntry, ChoiceIns, SaveSlot, SayIns, Story } from "./engine/types";
import { VM, type Host } from "./engine/vm";
import { Screens } from "./ui/screens";

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

export interface HostBridge {
  quit(): void;
  setFullscreen(on: boolean): void;
  isFullscreen(): boolean;
  setWindowSize(w: number, h: number): void;
}

declare global {
  interface Window {
    vnHost?: HostBridge;
    __vn?: unknown;
  }
}

export class Game implements Host {
  audio: AudioEngine;
  stage: Stage;
  text: TextBox;
  vm: VM;
  store = new Store();
  screens: Screens;
  lipsync = new Map<string, Uint8Array>();
  private rawLipsync: Record<string, string> = {};
  mode: "title" | "play" = "title";
  auto = false;
  skip = false;
  hiddenByUser = false;
  menuOpen = false;
  private advance: (() => void) | null = null;
  private waitCancel: (() => void) | null = null;
  private currentLine: SayIns | null = null;
  private playClock = performance.now();
  private quick!: HTMLDivElement;
  private choiceBox!: HTMLDivElement;
  errors: string[] = [];
  lineCount = 0;
  testMode = false;

  constructor(host: HTMLElement, public assets: Assets, public story: Story, public base: string, lipsync: Record<string, string>) {
    this.rawLipsync = lipsync;
    this.audio = new AudioEngine(assets, base);
    this.audio.onError = (m) => this.error(m);
    this.audio.onBgm = (id) => this.store.unlock("bgms", id);
    this.stage = new Stage(host, assets, base, this.audio);
    this.stage.fx.onLightning = () => {
      if (!this.skip) void this.audio.se("thunder", 0.9, 0.35 + Math.random() * 0.6);
    };
    this.text = new TextBox(this.stage.ui);
    this.buildQuickMenu();
    this.choiceBox = document.createElement("div");
    this.choiceBox.className = "choices";
    this.stage.ui.appendChild(this.choiceBox);
    this.vm = new VM(story, this.stage, this.audio, this);
    this.screens = new Screens(this);
    this.applySettings();
    this.bindInput();
    addEventListener("vn-error", (e) => this.error((e as CustomEvent).detail));
    setInterval(() => {
      const now = performance.now();
      if (this.mode === "play") this.store.addPlayTime((now - this.playClock) / 1000);
      this.playClock = now;
    }, 5000);
    this.setTextbox(false);
  }

  error(msg: string) {
    this.errors.push(msg);
    console.error("[vn]", msg);
  }

  env(id: string): Uint8Array | null {
    let e = this.lipsync.get(id);
    if (!e) {
      const raw = this.rawLipsync[id];
      if (!raw) return null;
      const bin = atob(raw);
      e = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) e[i] = bin.charCodeAt(i);
      this.lipsync.set(id, e);
    }
    return e;
  }

  applySettings() {
    const s = this.store.settings;
    this.audio.setVolumes({ master: s.master, bgm: s.bgm, amb: s.amb, se: s.se, voice: s.voice, sys: s.sys });
    this.text.setOpacity(s.tbAlpha);
  }

  // ------------------------------------------------------------------ quick menu + input
  private buildQuickMenu() {
    this.quick = document.createElement("div");
    this.quick.className = "quickmenu";
    const items: [string, string][] = [
      ["log", "로그"], ["auto", "오토"], ["skip", "스킵"], ["save", "저장"], ["load", "불러오기"],
      ["qsave", "Q.저장"], ["qload", "Q.불러오기"], ["config", "설정"], ["hide", "숨기기"], ["menu", "메뉴"],
    ];
    for (const [k, label] of items) {
      const b = document.createElement("button");
      b.className = "qm-btn";
      b.dataset.k = k;
      b.textContent = label;
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        this.audio.ui("ui_click");
        this.quickAction(k);
      });
      b.addEventListener("mouseenter", () => this.audio.ui("ui_hover", 0.5));
      this.quick.appendChild(b);
    }
    this.text.el.appendChild(this.quick);
  }

  quickAction(k: string) {
    switch (k) {
      case "log": this.screens.backlog(); break;
      case "auto": this.setAuto(!this.auto); break;
      case "skip": this.setSkip(!this.skip); break;
      case "save": this.screens.saveLoad("save"); break;
      case "load": this.screens.saveLoad("load"); break;
      case "qsave": this.quickSave(); break;
      case "qload": this.quickLoad(); break;
      case "config": this.screens.settings(); break;
      case "hide": this.toggleHide(true); break;
      case "menu": this.screens.gameMenu(); break;
    }
  }

  setAuto(on: boolean) {
    this.auto = on;
    if (on) this.skip = false;
    this.refreshQuick();
    if (on && !this.text.revealing && !this.audio.speaking) this.kickAuto();
  }

  setSkip(on: boolean) {
    this.skip = on;
    if (on) this.auto = false;
    this.stage.fast = on;
    this.refreshQuick();
    if (on) {
      this.audio.stopVoice();
      this.advance?.();
    }
  }

  private refreshQuick() {
    this.quick.querySelector('[data-k="auto"]')?.classList.toggle("on", this.auto);
    this.quick.querySelector('[data-k="skip"]')?.classList.toggle("on", this.skip);
    document.body.classList.toggle("skipping", this.skip);
  }

  toggleHide(on: boolean) {
    this.hiddenByUser = on;
    this.text.el.classList.toggle("user-hidden", on);
    this.choiceBox.classList.toggle("user-hidden", on);
  }

  private bindInput() {
    const stageEl = this.stage.root;
    stageEl.addEventListener("click", (e) => {
      if (this.mode !== "play" || this.menuOpen) return;
      if ((e.target as HTMLElement).closest("button, .screen, .choices")) return;
      if (this.hiddenByUser) return this.toggleHide(false);
      this.userAdvance();
    });
    stageEl.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      if (this.mode !== "play") return;
      if (this.menuOpen) this.screens.closeTop();
      else if (this.hiddenByUser) this.toggleHide(false);
      else this.screens.gameMenu();
    });
    stageEl.addEventListener("wheel", (e) => {
      if (this.mode !== "play" || this.menuOpen) return;
      if (e.deltaY < 0) this.screens.backlog();
      else if (e.deltaY > 0 && !this.hiddenByUser) this.userAdvance();
    }, { passive: true });
    addEventListener("keydown", (e) => {
      if (e.key === "F11" || (e.key === "Enter" && e.altKey)) {
        e.preventDefault();
        this.screens.toggleFullscreen();
        return;
      }
      if (this.mode !== "play") return;
      if (this.menuOpen) {
        if (e.key === "Escape") this.screens.closeTop();
        return;
      }
      if (e.key === "Control" && !e.repeat) {
        this.ctrlSkip = true;
        this.setSkip(true);
        return;
      }
      switch (e.key) {
        case "Enter":
        case " ":
        case "ArrowDown":
        case "PageDown":
          e.preventDefault();
          if (this.hiddenByUser) this.toggleHide(false);
          else if (!e.repeat || this.text.revealing === false) this.userAdvance();
          break;
        case "Escape": this.screens.gameMenu(); break;
        case "PageUp":
        case "ArrowUp":
        case "l":
        case "L": this.screens.backlog(); break;
        case "a":
        case "A": this.setAuto(!this.auto); break;
        case "s":
        case "S": this.setSkip(!this.skip); break;
        case "h":
        case "H": this.toggleHide(!this.hiddenByUser); break;
        case "r":
        case "R": this.replayVoice(); break;
        case "F5": e.preventDefault(); this.quickSave(); break;
        case "F9": e.preventDefault(); this.quickLoad(); break;
      }
    });
    addEventListener("keyup", (e) => {
      if (e.key === "Control" && this.ctrlSkip) {
        this.ctrlSkip = false;
        this.setSkip(false);
      }
    });
    addEventListener("blur", () => {
      if (this.ctrlSkip) {
        this.ctrlSkip = false;
        this.setSkip(false);
      }
    });
  }

  private ctrlSkip = false;

  userAdvance() {
    if (this.skip && !this.ctrlSkip) this.setSkip(false);
    if (this.auto) this.setAuto(false);
    if (this.waitCancel) {
      this.waitCancel();
      return;
    }
    if (this.text.revealing) {
      this.text.finish();
      return;
    }
    this.advance?.();
  }

  replayVoice() {
    const l = this.currentLine;
    if (l?.voice) void this.playLineVoice(l);
  }

  // ------------------------------------------------------------------ Host: dialogue
  private kickAuto() {
    /* the say() loop polls auto state; nothing to do here */
  }

  async playLineVoice(ins: SayIns, fxOverride?: string) {
    if (!ins.voice) return null;
    const h = await this.audio.playVoice(ins.voice, fxOverride ?? this.stage.scene.voicefx);
    const spr = ins.who ? this.stage.sprites.get(ins.who) : undefined;
    if (spr && h) spr.speak(h, this.env(ins.voice));
    return h;
  }

  async say(ins: SayIns): Promise<void> {
    this.lineCount++;
    this.currentLine = ins;
    if (this.testMode) {
      if (ins.voice && !this.assets.voice[ins.voice]) this.error(`missing voice ${ins.voice} at ${ins.id}`);
      if (ins.voice && !this.env(ins.voice)) this.error(`missing lipsync ${ins.voice}`);
      if (ins.who && ins.expr && this.assets.chars[ins.who] && !this.assets.chars[ins.who].faces[ins.expr]) this.error(`unknown expr ${ins.who}/${ins.expr}`);
    }
    const read = this.store.isRead(ins.id);
    if (this.skip && !read && !this.store.settings.skipUnread && !this.ctrlSkip) this.setSkip(false);
    const skipping = this.skip;
    if (this.stage.scene.textbox) this.setTextbox(true);
    const conf = ins.who ? this.assets.charConf[ins.who] : undefined;
    const cps = skipping || this.testMode ? 0 : this.store.settings.textSpeed;
    const shown = this.text.say(ins.name, conf?.color, ins.text, cps, !ins.who);
    this.vm.backlog.push({ name: ins.name, who: ins.who, text: plain(ins.text), voice: ins.voice, voicefx: this.stage.scene.voicefx });
    if (this.vm.backlog.length > 400) this.vm.backlog.splice(0, this.vm.backlog.length - 400);
    let voice: VoiceHandle | null = null;
    if (ins.voice && !skipping && !this.testMode) voice = await this.playLineVoice(ins);
    await shown;
    this.store.markRead(ins.id);
    if (this.skip) {
      await sleep(this.testMode ? 0 : 35);
      this.audio.stopVoice();
      return;
    }
    // wait for the player (or auto mode)
    await new Promise<void>((resolve) => {
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        this.advance = null;
        resolve();
      };
      this.advance = finish;
      if (this.testMode) {
        finish();
        return;
      }
      const autoLoop = async () => {
        while (!done) {
          if (this.auto && !this.menuOpen) {
            if (voice && !voice.ended) await Promise.race([voice.done, sleep(250)]);
            else {
              const chars = plain(ins.text).length;
              const k = 1.6 - this.store.settings.autoSpeed * 1.2; // 0.4 .. 1.6
              const delay = (voice ? 650 : 900 + chars * 38) * k;
              const t0 = performance.now();
              while (!done && this.auto && !this.menuOpen && performance.now() - t0 < delay) await sleep(60);
              if (!done && this.auto && !this.menuOpen) finish();
            }
          } else await sleep(120);
        }
      };
      void autoLoop();
    });
    if (!this.store.settings.voiceContinue) this.audio.stopVoice();
  }

  async choose(_ins: ChoiceIns, options: { text: string; index: number }[]): Promise<number> {
    if (this.skip && !this.ctrlSkip) this.setSkip(false);
    if (this.testMode && this.testChoices) {
      const want = this.testChoices.shift();
      const pick = options.find((o) => o.index === want) ?? options[0];
      return pick.index;
    }
    this.setTextbox(true);
    return new Promise<number>((resolve) => {
      this.choiceBox.innerHTML = "";
      this.choiceBox.classList.add("on");
      options.forEach((o, k) => {
        const b = document.createElement("button");
        b.className = "choice";
        b.innerHTML = `<span class="ch-freq">${(88.1 + k * 0.2).toFixed(1)}</span><span class="ch-text"></span>`;
        (b.querySelector(".ch-text") as HTMLElement).textContent = o.text;
        b.style.animationDelay = `${k * 90}ms`;
        b.addEventListener("mouseenter", () => this.audio.ui("ui_hover", 0.6));
        b.addEventListener("click", (e) => {
          e.stopPropagation();
          this.audio.ui("ui_choice");
          this.choiceBox.classList.remove("on");
          this.choiceBox.innerHTML = "";
          resolve(o.index);
        });
        this.choiceBox.appendChild(b);
      });
      (this.choiceBox.firstElementChild as HTMLElement | null)?.focus();
    });
  }

  testChoices: number[] | null = null;

  async wait(sec: number) {
    if (this.skip || this.testMode) return;
    await new Promise<void>((resolve) => {
      const t = setTimeout(() => {
        this.waitCancel = null;
        resolve();
      }, sec * 1000);
      this.waitCancel = () => {
        clearTimeout(t);
        this.waitCancel = null;
        resolve();
      };
    });
  }

  isSkipping() {
    return this.skip || this.testMode;
  }

  setTextbox(visible: boolean) {
    this.text.show(visible && this.mode === "play");
    if (!visible) this.text.clear();
  }

  onChapter(_num: string, _title: string) {
    this.audio.stopVoice();
  }

  unlockCg(id: string) {
    this.store.unlock("cgs", id);
  }

  lastEnding: string | null = null;

  async ending(id: string, title: string) {
    this.lastEnding = id;
    this.store.unlock("endings", id);
    if (id === "true") this.store.setCleared();
    this.setSkip(false);
    this.setAuto(false);
    this.setTextbox(false);
    if (this.testMode) return;
    await this.screens.endingCard(id, title);
  }

  async credits(song: string, variant: string) {
    this.setSkip(false);
    this.setTextbox(false);
    if (this.testMode) return;
    await this.screens.credits(song, variant);
  }

  toTitle() {
    this.mode = "title";
    this.vm.stop();
    this.audio.stopAll(1.2);
    this.setTextbox(false);
    this.stage.clearAll();
    this.setSkip(false);
    this.setAuto(false);
    this.screens.title();
  }

  // ------------------------------------------------------------------ flow
  async newGame() {
    this.mode = "play";
    this.stage.clearAll();
    this.audio.stopAll(0.8);
    this.playClock = performance.now();
    await this.vm.start("start");
  }

  makeSave(): SaveSlot | null {
    const snap = this.vm.lastSnap;
    if (!snap) return null;
    const sc = snap.scene;
    const last = [...snap.backlog].reverse().find((b: BacklogEntry) => !b.choice);
    return {
      version: SAVE_VERSION,
      time: Date.now(),
      chapter: sc.chapter || "프롤로그",
      text: last ? (last.name ? `${last.name}: ` : "") + last.text : "",
      thumb: sc.cg ? this.stage.imgUrl("cg", sc.cg) : sc.bg ? this.stage.imgUrl("bg", sc.bg) : null,
      snap,
      playTime: this.store.global.playTime,
    };
  }

  saveTo(slot: string) {
    const s = this.makeSave();
    if (!s) return false;
    this.store.write(slot, s);
    return true;
  }

  async loadFrom(slot: string) {
    const s = this.store.load(slot);
    if (!s) return false;
    this.screens.closeAll();
    this.mode = "play";
    this.setSkip(false);
    this.setAuto(false);
    this.audio.stopAll(0.4);
    this.choiceBox.classList.remove("on");
    this.choiceBox.innerHTML = "";
    this.text.clear();
    this.advance = null;
    this.waitCancel = null;
    await this.stage.coverTo("black", 0.35);
    void this.vm.resume(s.snap);
    await sleep(250);
    await this.stage.coverFrom(0.5);
    return true;
  }

  autosave(_label: string) {
    if (this.testMode) return;
    const snap = this.vm.snapshot();
    const sc = snap.scene;
    this.store.write("auto", {
      version: SAVE_VERSION, time: Date.now(), chapter: sc.chapter || "프롤로그", text: "— 자동 저장 —",
      thumb: sc.cg ? this.stage.imgUrl("cg", sc.cg) : sc.bg ? this.stage.imgUrl("bg", sc.bg) : null,
      snap, playTime: this.store.global.playTime,
    });
  }

  quickSave() {
    if (this.saveTo("quick")) this.screens.toast("퀵 세이브 완료");
  }

  quickLoad() {
    if (!this.store.load("quick")) {
      this.screens.toast("퀵 세이브 데이터가 없습니다");
      return;
    }
    void this.loadFrom("quick");
  }

  hasSaves() {
    return this.store.latest() !== null;
  }

  slots() {
    return Array.from({ length: SLOT_COUNT }, (_, i) => String(i + 1));
  }
}

export { sleep };
