// Menu screens: splash, title, game menu, save/load, settings, backlog, gallery,
// ending card, credits, confirm dialogs and toasts.

import type { Game } from "../game";
import { sleep } from "../game";

const ENDINGS: { id: string; title: string; hint: string }[] = [
  { id: "true", title: "윤슬", hint: "빛은, 물 위에 남는다." },
  { id: "normal", title: "잔향", hint: "닿지 못한 주파수." },
];

function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls = "", html = ""): HTMLElementTagNameMap[K] {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html) e.innerHTML = html;
  return e;
}

function fmtDate(t: number) {
  const d = new Date(t);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}.${p(d.getMonth() + 1)}.${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

function fmtTime(sec: number) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return `${h}시간 ${String(m).padStart(2, "0")}분`;
}

export class Screens {
  private stack: HTMLElement[] = [];
  private titleEl: HTMLElement | null = null;
  private toastEl: HTMLDivElement;

  constructor(private g: Game) {
    this.toastEl = el("div", "toast");
    g.stage.ui.appendChild(this.toastEl);
  }

  private get ui() {
    return this.g.stage.ui;
  }

  private click(b: HTMLElement, fn: () => void, sound = "ui_click") {
    b.addEventListener("mouseenter", () => this.g.audio.ui("ui_hover", 0.5));
    b.addEventListener("click", (e) => {
      e.stopPropagation();
      this.g.audio.ui(sound);
      fn();
    });
  }

  private open(scr: HTMLElement) {
    scr.classList.add("screen");
    this.ui.appendChild(scr);
    this.stack.push(scr);
    this.g.menuOpen = true;
    requestAnimationFrame(() => scr.classList.add("in"));
    return scr;
  }

  closeTop() {
    const s = this.stack.pop();
    if (s) {
      this.g.audio.ui("ui_cancel", 0.7);
      s.classList.remove("in");
      setTimeout(() => s.remove(), 220);
      (s as HTMLElement & { onClose?: () => void }).onClose?.();
    }
    this.g.menuOpen = this.stack.length > 0;
  }

  closeAll() {
    while (this.stack.length) {
      const s = this.stack.pop()!;
      (s as HTMLElement & { onClose?: () => void }).onClose?.();
      s.remove();
    }
    this.g.menuOpen = false;
  }

  toast(msg: string) {
    this.toastEl.textContent = msg;
    this.toastEl.classList.remove("on");
    void this.toastEl.offsetWidth;
    this.toastEl.classList.add("on");
  }

  private header(title: string, sub: string) {
    const h = el("div", "scr-head", `<div class="scr-title">${title}</div><div class="scr-sub">${sub}</div>`);
    const x = el("button", "scr-close", "돌아가기");
    this.click(x, () => this.closeTop(), "ui_cancel");
    h.appendChild(x);
    return h;
  }

  // ------------------------------------------------------------------ splash + title
  splash(): Promise<void> {
    return new Promise((resolve) => {
      const s = el("div", "splash", `<div class="sp-logo">여름이 가라앉기 전에</div>
        <div class="sp-note">이 작품은 음성과 음악이 함께합니다. 헤드폰 사용을 권장합니다.</div>
        <div class="sp-press">화면을 클릭하거나 아무 키나 누르세요</div>`);
      this.ui.appendChild(s);
      const go = async () => {
        removeEventListener("keydown", go);
        s.removeEventListener("click", go);
        await this.g.audio.unlock();
        s.classList.add("out");
        setTimeout(() => s.remove(), 900);
        resolve();
      };
      s.addEventListener("click", go);
      addEventListener("keydown", go);
    });
  }

  title() {
    this.closeAll();
    this.titleEl?.remove();
    const g = this.g;
    g.mode = "title";
    const cleared = g.store.global.cleared;
    const scr = el("div", "title-screen" + (cleared ? " cleared" : ""));
    const bgId = cleared ? "cg_true_end" : "cg_title";
    scr.innerHTML = `<div class="ts-bg" style="background-image:url('${g.stage.imgUrl("cg", bgId)}')"></div>
      <div class="ts-shade"></div>
      <div class="ts-logo">
        <div class="ts-dial"><span>88.3</span> MHz · 소리실 심야방송</div>
        <h1 class="ts-title"><span>여름이</span><span>가라앉기 전에</span></h1>
        <div class="ts-en">Before the Summer Sinks</div>
      </div>
      <nav class="ts-menu"></nav>
      <div class="ts-foot">${cleared ? "— 다녀와, 그리고 어서 와 —" : "v1.0"}</div>`;
    const menu = scr.querySelector(".ts-menu")!;
    const add = (label: string, fn: () => void, disabled = false) => {
      const b = el("button", "ts-btn" + (disabled ? " disabled" : ""), `<span class="ts-tick"></span>${label}`);
      if (!disabled) this.click(b, fn, "ui_confirm");
      menu.appendChild(b);
    };
    add("처음부터", () => {
      scr.classList.add("out");
      g.audio.stopBgm(1.6);
      setTimeout(() => {
        scr.remove();
        this.titleEl = null;
        void g.newGame();
      }, 1100);
    });
    const latest = g.store.latest();
    add("이어하기", () => {
      if (!latest) return;
      scr.remove();
      this.titleEl = null;
      void g.loadFrom(latest.slot);
    }, !latest);
    add("불러오기", () => this.saveLoad("load", true), !latest);
    add("환경설정", () => this.settings());
    add("추억", () => this.gallery());
    if (window.vnHost) add("종료", () => this.confirm("게임을 종료할까요?", () => window.vnHost!.quit()));
    this.ui.appendChild(scr);
    this.titleEl = scr;
    g.stage.clearAll();
    void g.audio.playBgm("title", 2.5);
    void g.audio.setAmb(["cicada_far"], 3);
  }

  // ------------------------------------------------------------------ in-game menu
  gameMenu() {
    const scr = el("div", "game-menu");
    scr.appendChild(this.header("메뉴", "잠시 멈춤"));
    const list = el("div", "gm-list");
    const add = (label: string, fn: () => void) => {
      const b = el("button", "gm-btn", label);
      this.click(b, fn);
      list.appendChild(b);
    };
    add("게임으로 돌아가기", () => this.closeTop());
    add("저장하기", () => this.saveLoad("save"));
    add("불러오기", () => this.saveLoad("load"));
    add("대사 기록", () => this.backlog());
    add("환경설정", () => this.settings());
    add("타이틀로", () => this.confirm("타이틀 화면으로 돌아갈까요?\n저장하지 않은 진행은 사라집니다.", () => {
      this.closeAll();
      this.g.toTitle();
    }));
    scr.appendChild(list);
    const info = el("div", "gm-info", `총 플레이 시간 ${fmtTime(this.g.store.global.playTime)}`);
    scr.appendChild(info);
    this.open(scr);
  }

  confirm(msg: string, yes: () => void) {
    const scr = el("div", "confirm", `<div class="cf-box"><div class="cf-msg"></div><div class="cf-btns"></div></div>`);
    (scr.querySelector(".cf-msg") as HTMLElement).textContent = msg;
    const btns = scr.querySelector(".cf-btns")!;
    const y = el("button", "cf-btn yes", "예");
    const n = el("button", "cf-btn", "아니요");
    this.click(y, () => {
      this.closeTop();
      yes();
    }, "ui_confirm");
    this.click(n, () => this.closeTop(), "ui_cancel");
    btns.append(y, n);
    this.open(scr);
  }

  // ------------------------------------------------------------------ save / load
  saveLoad(mode: "save" | "load", fromTitle = false) {
    const g = this.g;
    const scr = el("div", "saveload " + mode);
    scr.appendChild(this.header(mode === "save" ? "저장하기" : "불러오기", mode === "save" ? "기억을 테이프에 남깁니다" : "남겨 둔 테이프를 재생합니다"));
    const tabs = el("div", "sl-tabs");
    const grid = el("div", "sl-grid");
    const pages = mode === "load" ? ["A", "1", "2", "3", "4", "5", "6"] : ["1", "2", "3", "4", "5", "6"];
    let page = mode === "load" ? "A" : "1";
    const render = () => {
      grid.innerHTML = "";
      tabs.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.p === page));
      const slots = page === "A" ? ["auto", "quick"] : Array.from({ length: 6 }, (_, i) => String((Number(page) - 1) * 6 + i + 1));
      for (const slot of slots) {
        const data = g.store.load(slot);
        const card = el("button", "sl-card" + (data ? "" : " empty"));
        const label = slot === "auto" ? "AUTO" : slot === "quick" ? "QUICK" : `No.${slot.padStart(2, "0")}`;
        card.innerHTML = `<div class="sl-thumb" ${data?.thumb ? `style="background-image:url('${data.thumb}')"` : ""}>
            <span class="sl-no">${label}</span></div>
          <div class="sl-meta"><div class="sl-ch">${data ? data.chapter : "비어 있음"}</div>
          <div class="sl-date">${data ? fmtDate(data.time) : ""}</div>
          <div class="sl-text"></div></div>`;
        (card.querySelector(".sl-text") as HTMLElement).textContent = data ? data.text : "";
        this.click(card, () => {
          if (mode === "save") {
            const doSave = () => {
              if (g.saveTo(slot)) {
                g.audio.ui("ui_save");
                render();
                this.toast("저장했습니다");
              }
            };
            if (data) this.confirm("이 슬롯에 덮어쓸까요?", doSave);
            else doSave();
          } else if (data) {
            const doLoad = () => {
              this.titleEl?.remove();
              this.titleEl = null;
              void g.loadFrom(slot);
            };
            if (fromTitle) doLoad();
            else this.confirm("이 기록을 불러올까요?", doLoad);
          }
        });
        grid.appendChild(card);
      }
    };
    for (const p of pages) {
      const b = el("button", "sl-tab", p === "A" ? "자동/퀵" : p);
      b.dataset.p = p;
      this.click(b, () => {
        page = p;
        render();
      });
      tabs.appendChild(b);
    }
    scr.append(tabs, grid);
    render();
    this.open(scr);
  }

  // ------------------------------------------------------------------ settings
  settings() {
    const g = this.g;
    const s = g.store.settings;
    const scr = el("div", "settings");
    scr.appendChild(this.header("환경설정", "주파수 조정"));
    const body = el("div", "st-body");
    const col = (title: string) => {
      const c = el("div", "st-col", `<div class="st-cap">${title}</div>`);
      body.appendChild(c);
      return c;
    };
    const slider = (parent: HTMLElement, label: string, get: () => number, set: (v: number) => void, fmt = (v: number) => `${Math.round(v * 100)}`, preview?: () => void) => {
      const row = el("label", "st-row", `<span class="st-label">${label}</span><input type="range" min="0" max="1" step="0.01"><span class="st-val"></span>`);
      const inp = row.querySelector("input")!;
      const val = row.querySelector(".st-val")!;
      inp.value = String(get());
      val.textContent = fmt(get());
      inp.addEventListener("input", () => {
        set(Number(inp.value));
        val.textContent = fmt(Number(inp.value));
        g.applySettings();
      });
      inp.addEventListener("change", () => {
        g.store.saveSettings();
        preview?.();
      });
      parent.appendChild(row);
    };
    const toggle = (parent: HTMLElement, label: string, get: () => boolean, set: (v: boolean) => void) => {
      const row = el("div", "st-row", `<span class="st-label">${label}</span><div class="st-toggle"><button data-v="1">켜기</button><button data-v="0">끄기</button></div>`);
      const paint = () => row.querySelectorAll("button").forEach((b) => b.classList.toggle("on", (b.dataset.v === "1") === get()));
      row.querySelectorAll("button").forEach((b) => this.click(b, () => {
        set(b.dataset.v === "1");
        g.store.saveSettings();
        paint();
      }));
      paint();
      parent.appendChild(row);
    };
    const snd = col("소리");
    slider(snd, "전체 음량", () => s.master, (v) => (s.master = v));
    slider(snd, "배경음악", () => s.bgm, (v) => (s.bgm = v));
    slider(snd, "음성", () => s.voice, (v) => (s.voice = v), undefined, () => void g.audio.se("ui_confirm", 1, 0, "voice"));
    slider(snd, "환경음", () => s.amb, (v) => (s.amb = v));
    slider(snd, "효과음", () => s.se, (v) => (s.se = v), undefined, () => void g.audio.se("ui_confirm"));
    slider(snd, "시스템음", () => s.sys, (v) => (s.sys = v), undefined, () => g.audio.ui("ui_click"));
    const txt = col("텍스트");
    slider(txt, "텍스트 속도", () => (s.textSpeed <= 0 ? 1 : (s.textSpeed - 12) / 108), (v) => (s.textSpeed = v >= 0.995 ? 0 : Math.round(12 + v * 108)),
      (v) => (v >= 0.995 ? "즉시" : `${Math.round(12 + v * 108)}`));
    slider(txt, "오토 속도", () => s.autoSpeed, (v) => (s.autoSpeed = v));
    slider(txt, "대화창 투명도", () => 1 - s.tbAlpha, (v) => (s.tbAlpha = 1 - v));
    toggle(txt, "읽지 않은 문장도 스킵", () => s.skipUnread, (v) => (s.skipUnread = v));
    toggle(txt, "넘겨도 음성 계속 재생", () => s.voiceContinue, (v) => (s.voiceContinue = v));
    const scrc = col("화면");
    toggle(scrc, "전체 화면", () => this.isFullscreen(), (v) => this.setFullscreen(v));
    if (window.vnHost) {
      const row = el("div", "st-row", `<span class="st-label">창 크기</span><div class="st-sizes"></div>`);
      const box = row.querySelector(".st-sizes")!;
      for (const size of ["1280x720", "1600x900", "1920x1080"]) {
        const b = el("button", "st-size" + (s.windowSize === size ? " on" : ""), size.replace("x", "×"));
        this.click(b, () => {
          s.windowSize = size;
          g.store.saveSettings();
          const [w, h] = size.split("x").map(Number);
          this.setFullscreen(false);
          window.vnHost!.setWindowSize(w, h);
          box.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
        });
        box.appendChild(b);
      }
      scrc.appendChild(row);
    }
    const keys = el("div", "st-keys", `<div class="st-cap">조작</div>
      <p><b>클릭 · Enter · Space</b> 진행 &nbsp; <b>휠 위 · ↑</b> 대사 기록 &nbsp; <b>Ctrl</b> 누르는 동안 스킵</p>
      <p><b>A</b> 오토 &nbsp; <b>S</b> 스킵 &nbsp; <b>H</b> 대화창 숨기기 &nbsp; <b>R</b> 음성 다시 듣기</p>
      <p><b>F5</b> 퀵 세이브 &nbsp; <b>F9</b> 퀵 로드 &nbsp; <b>Esc · 우클릭</b> 메뉴 &nbsp; <b>F11</b> 전체 화면</p>`);
    scrc.appendChild(keys);
    scr.appendChild(body);
    this.open(scr);
  }

  isFullscreen() {
    return window.vnHost ? window.vnHost.isFullscreen() : !!document.fullscreenElement;
  }

  setFullscreen(on: boolean) {
    this.g.store.settings.fullscreen = on;
    this.g.store.saveSettings();
    if (window.vnHost) window.vnHost.setFullscreen(on);
    else if (on && !document.fullscreenElement) void document.documentElement.requestFullscreen().catch(() => {});
    else if (!on && document.fullscreenElement) void document.exitFullscreen();
  }

  toggleFullscreen() {
    this.setFullscreen(!this.isFullscreen());
  }

  // ------------------------------------------------------------------ backlog
  backlog() {
    const g = this.g;
    if (this.stack.some((s) => s.classList.contains("backlog"))) return;
    const scr = el("div", "backlog");
    scr.appendChild(this.header("대사 기록", "지나간 목소리"));
    const list = el("div", "bl-list");
    const items = g.vm.backlog.slice(-200);
    for (const b of items) {
      const row = el("div", "bl-row" + (b.choice ? " choice" : "") + (b.who ? "" : " narr"));
      if (b.choice) row.innerHTML = `<div class="bl-text">▶ <span></span></div>`;
      else row.innerHTML = `<div class="bl-name">${b.name ?? ""}</div><div class="bl-text"><span></span></div>`;
      (row.querySelector(".bl-text span") as HTMLElement).textContent = b.text;
      if (b.voice) {
        const v = el("button", "bl-voice", "▶");
        v.title = "음성 다시 듣기";
        this.click(v, () => void g.audio.playVoice(b.voice!, b.voicefx ?? "none"), "ui_tick");
        row.prepend(v);
      }
      const conf = b.who ? g.assets.charConf[b.who] : undefined;
      if (conf) row.style.setProperty("--name-color", conf.color);
      list.appendChild(row);
    }
    scr.appendChild(list);
    list.addEventListener("wheel", (e) => {
      if (e.deltaY > 0 && list.scrollTop + list.clientHeight >= list.scrollHeight - 2) this.closeTop();
    }, { passive: true });
    this.open(scr);
    requestAnimationFrame(() => (list.scrollTop = list.scrollHeight));
  }

  // ------------------------------------------------------------------ gallery
  gallery() {
    const g = this.g;
    const scr = el("div", "gallery");
    scr.appendChild(this.header("추억", "소리 지도 · 사진 · 테이프"));
    const tabs = el("div", "sl-tabs");
    const body = el("div", "gl-body");
    let musicPlaying = false;
    const restoreTitle = () => {
      if (musicPlaying) void g.audio.playBgm("title", 1.5);
    };
    (scr as HTMLElement & { onClose?: () => void }).onClose = restoreTitle;
    const show = (tab: string) => {
      tabs.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.t === tab));
      body.innerHTML = "";
      if (tab === "cg") {
        const grid = el("div", "gl-grid");
        for (const [id, meta] of Object.entries(g.assets.cg)) {
          if (id === "cg_title") continue;
          const open = g.store.global.cgs.includes(id);
          const c = el("button", "gl-cg" + (open ? "" : " locked"));
          if (open) c.style.backgroundImage = `url('${g.base}${meta.thumb ?? meta.src}')`;
          c.innerHTML = `<span>${open ? meta.title ?? "" : "? ? ?"}</span>`;
          if (open) this.click(c, () => {
            const v = el("div", "gl-view");
            v.style.backgroundImage = `url('${g.base}${meta.src}')`;
            v.addEventListener("click", (e) => {
              e.stopPropagation();
              this.closeTop();
            });
            this.open(v);
          });
          grid.appendChild(c);
        }
        const total = Object.keys(g.assets.cg).length - 1;
        const got = g.store.global.cgs.filter((i) => i !== "cg_title").length;
        body.append(el("div", "gl-count", `${got} / ${total}`), grid);
      } else if (tab === "music") {
        const list = el("div", "gl-music");
        for (const [id, meta] of Object.entries(g.assets.bgm)) {
          const open = g.store.global.bgms.includes(id) || id === "title";
          const r = el("button", "gl-track" + (open ? "" : " locked"), `<span class="gl-play">▶</span><span class="gl-tt">${open ? meta.title : "? ? ?"}</span><span class="gl-dur">${open ? `${Math.floor(meta.duration / 60)}:${String(Math.round(meta.duration % 60)).padStart(2, "0")}` : ""}</span>`);
          if (open) this.click(r, () => {
            musicPlaying = true;
            void g.audio.playBgm(id, 0.8);
            list.querySelectorAll(".gl-track").forEach((x) => x.classList.toggle("now", x === r));
          });
          list.appendChild(r);
        }
        body.appendChild(list);
      } else {
        const list = el("div", "gl-endings");
        ENDINGS.forEach((e, i) => {
          const got = g.store.global.endings.includes(e.id);
          list.appendChild(el("div", "gl-end" + (got ? "" : " locked"), `<div class="ge-no">ENDING ${String(i + 1).padStart(2, "0")}</div>
            <div class="ge-title">${got ? e.title : "? ? ?"}</div><div class="ge-hint">${got ? e.hint : "아직 듣지 못한 이야기"}</div>`));
        });
        body.appendChild(list);
      }
    };
    for (const [t, label] of [["cg", "이벤트 CG"], ["music", "음악"], ["end", "엔딩"]]) {
      const b = el("button", "sl-tab", label);
      b.dataset.t = t;
      this.click(b, () => show(t));
      tabs.appendChild(b);
    }
    scr.append(tabs, body);
    show("cg");
    this.open(scr);
  }

  // ------------------------------------------------------------------ endings + credits
  async endingCard(id: string, title: string) {
    const idx = ENDINGS.findIndex((e) => e.id === id) + 1;
    const c = el("div", "ending-card", `<div class="ec-no">ENDING ${String(idx).padStart(2, "0")}</div><div class="ec-title">${title}</div>`);
    this.ui.appendChild(c);
    c.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 1600, fill: "forwards" });
    await sleep(4200);
    c.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 1200, fill: "forwards" });
    await sleep(1250);
    c.remove();
  }

  async credits(song: string, variant: string) {
    const g = this.g;
    const c = el("div", "credits " + variant);
    const roll = el("div", "cr-roll");
    // credit text is data (story/credits.json): update it whenever a resource is replaced
    const cr = g.assets.credits;
    const esc = (s: string) => s.replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[ch]!);
    const sec = (title: string, lines: string[]) => `<div class="cr-sec"><div class="cr-h">${esc(title)}</div>${lines.map((l) => `<div class="cr-l">${esc(l)}</div>`).join("")}</div>`;
    roll.innerHTML = `<div class="cr-logo">${esc(cr.title)}</div><div class="cr-en">${esc(cr.subtitle)}</div>` +
      cr.sections.map((s) => sec(s.h, s.lines)).join("") +
      sec("", cr.outro) +
      `<div class="cr-end">— 끝 —</div>`;
    c.appendChild(roll);
    this.ui.appendChild(c);
    await g.audio.playBgm(song, 1.5);
    const dur = Math.min(140, Math.max(40, (g.assets.bgm[song]?.duration ?? 90) - 6));
    requestAnimationFrame(() => {
      roll.style.transition = `transform ${dur}s linear`;
      roll.style.transform = `translateY(calc(-100% - 200px))`;
    });
    let skip = false;
    const onKey = (e: Event) => {
      if (e instanceof KeyboardEvent && e.key !== "Escape") return;
      if (g.store.global.endings.length > 1 || g.store.global.cleared) skip = true;
    };
    addEventListener("keydown", onKey);
    c.addEventListener("dblclick", onKey);
    const t0 = performance.now();
    while (!skip && performance.now() - t0 < dur * 1000 + 2500) await sleep(200);
    removeEventListener("keydown", onKey);
    g.audio.stopBgm(3);
    c.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 2000, fill: "forwards" });
    await sleep(2100);
    c.remove();
  }
}
