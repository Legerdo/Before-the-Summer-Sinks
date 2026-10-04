// Story virtual machine: walks the compiled instruction list, evaluates conditions and
// variables, drives the stage/audio and hands dialogue + choices to the host (the game UI).

import type { AudioEngine } from "./audio";
import { POS, type Stage } from "./stage";
import type { ArgVal, BacklogEntry, ChoiceIns, CmdIns, RawIns, SayIns, Snapshot, Story } from "./types";

export interface Host {
  say(ins: SayIns): Promise<void>;
  choose(ins: ChoiceIns, options: { text: string; index: number }[]): Promise<number>;
  wait(sec: number): Promise<void>;
  ending(id: string, title: string): Promise<void>;
  credits(song: string, variant: string): Promise<void>;
  toTitle(): void;
  autosave(label: string): void;
  unlockCg(id: string): void;
  isSkipping(): boolean;
  setTextbox(visible: boolean): void;
  onChapter(num: string, title: string): void;
}

// ------------------------------------------------------------------ expressions
type Tok = { t: "num"; v: number } | { t: "id"; v: string } | { t: "op"; v: string };

function lex(s: string): Tok[] {
  const out: Tok[] = [];
  const re = /\s*(>=|<=|==|!=|&&|\|\||[-+*/%()<>!]|%?[A-Za-z_]\w*|\d+(?:\.\d+)?)/y;
  let m: RegExpExecArray | null;
  while (re.lastIndex < s.length && (m = re.exec(s)) !== null) {
    const x = m[1];
    if (/^\d/.test(x)) out.push({ t: "num", v: Number(x) });
    else if (/^%?[A-Za-z_]/.test(x)) out.push({ t: "id", v: x });
    else out.push({ t: "op", v: x });
  }
  return out;
}

export function evaluate(expr: string, vars: Record<string, number>): number {
  const toks = lex(expr);
  let i = 0;
  const peek = () => toks[i];
  const eat = () => toks[i++];
  const prec: Record<string, number> = { "||": 1, "&&": 2, "==": 3, "!=": 3, "<": 4, ">": 4, "<=": 4, ">=": 4, "+": 5, "-": 5, "*": 6, "/": 6, "%": 6 };
  const unary = (): number => {
    const t = eat();
    if (!t) return 0;
    if (t.t === "num") return t.v;
    if (t.t === "id") return t.v === "true" ? 1 : t.v === "false" ? 0 : vars[t.v] ?? 0;
    if (t.v === "(") {
      const v = bin(0);
      eat();
      return v;
    }
    if (t.v === "!") return unary() ? 0 : 1;
    if (t.v === "-") return -unary();
    return 0;
  };
  const bin = (minP: number): number => {
    let l = unary();
    for (;;) {
      const t = peek();
      if (!t || t.t !== "op" || prec[t.v] === undefined || prec[t.v] < minP) return l;
      eat();
      const r = bin(prec[t.v] + 1);
      switch (t.v) {
        case "||": l = l || r ? 1 : 0; break;
        case "&&": l = l && r ? 1 : 0; break;
        case "==": l = l === r ? 1 : 0; break;
        case "!=": l = l !== r ? 1 : 0; break;
        case "<": l = l < r ? 1 : 0; break;
        case ">": l = l > r ? 1 : 0; break;
        case "<=": l = l <= r ? 1 : 0; break;
        case ">=": l = l >= r ? 1 : 0; break;
        case "+": l = l + r; break;
        case "-": l = l - r; break;
        case "*": l = l * r; break;
        case "/": l = r ? l / r : 0; break;
        case "%": l = r ? l % r : 0; break;
      }
    }
  };
  return bin(0);
}

// ------------------------------------------------------------------ VM
const num = (v: ArgVal | undefined, d: number) => (v === undefined || v === "" ? d : Number(v));
const str = (v: ArgVal | undefined, d = "") => (v === undefined ? d : String(v));

export class VM {
  pc = 0;
  vars: Record<string, number> = {};
  callStack: number[] = [];
  backlog: BacklogEntry[] = [];
  running = false;
  private gen = 0;
  lastSnap: Snapshot | null = null;
  currentLabel = "";
  /** QA coverage: instruction indices executed (only allocated by the test harness). */
  visited: Set<number> | null = null;
  /** QA hook called before each instruction. */
  onStep: ((pc: number, ins: RawIns) => void) | null = null;

  constructor(private story: Story, private stage: Stage, private audio: AudioEngine, private host: Host) {}

  label(pc: number): string {
    let best = "";
    let bestPc = -1;
    for (const [k, v] of Object.entries(this.story.labels)) if (v <= pc && v > bestPc) { best = k; bestPc = v; }
    return best;
  }

  snapshot(pc = this.pc): Snapshot {
    return {
      pc,
      vars: { ...this.vars },
      scene: JSON.parse(JSON.stringify(this.stage.scene)),
      backlog: this.backlog.slice(-120),
      callStack: [...this.callStack],
    };
  }

  stop() {
    this.running = false;
    this.gen++;
  }

  async start(label: string, vars: Record<string, number> = {}) {
    this.stop();
    this.vars = { ...vars };
    this.callStack = [];
    this.backlog = [];
    const pc = this.story.labels[label];
    if (pc === undefined) throw new Error(`no label ${label}`);
    this.pc = pc;
    await this.run();
  }

  async resume(s: Snapshot) {
    this.stop();
    this.vars = { ...s.vars };
    this.callStack = [...s.callStack];
    this.backlog = s.backlog.slice();
    this.pc = s.pc;
    await this.stage.restore(s.scene);
    await this.audio.playBgm(s.scene.bgm, 1.2, s.scene.bgmVol);
    await this.audio.setAmb(s.scene.amb, 1.2);
    await this.audio.setSfxLoop(s.scene.sfxloop, 0.5);
    this.host.setTextbox(s.scene.textbox);
    await this.run();
  }

  private cond(c: string | undefined) {
    return !c || !!evaluate(c, this.vars);
  }

  private async run() {
    const my = ++this.gen;
    this.running = true;
    const code = this.story.code;
    while (this.running && my === this.gen && this.pc < code.length) {
      const at = this.pc;
      const ins = code[this.pc++] as RawIns;
      this.visited?.add(at);
      this.onStep?.(at, ins);
      try {
        await this.exec(ins, at);
      } catch (e) {
        const msg = `runtime error at ${this.story.srcmap[at]}: ${(e as Error).message}`;
        console.error(msg);
        window.dispatchEvent(new CustomEvent("vn-error", { detail: msg }));
      }
      if (my !== this.gen) return;
    }
    this.running = false;
  }

  private jump(target: string) {
    const pc = this.story.labels[target];
    if (pc === undefined) throw new Error(`unknown label ${target}`);
    this.pc = pc;
    this.currentLabel = target;
  }

  private async exec(raw: RawIns, at: number) {
    const op = raw.op;
    if (op === "say") {
      const ins = raw as unknown as SayIns;
      if (!this.cond(ins.cond)) return;
      if (ins.who && ins.expr) this.stage.setExpr(ins.who, ins.expr);
      this.stage.focusSpeaker(ins.who);
      this.lastSnap = this.snapshot(at);
      await this.host.say(ins);
      return;
    }
    if (op === "choice") {
      const ins = raw as unknown as ChoiceIns;
      if (!this.cond(ins.cond)) return;
      this.lastSnap = this.snapshot(at);
      const opts = ins.options.map((o, index) => ({ o, index })).filter(({ o }) => this.cond(o.cond));
      const pick = await this.host.choose(ins, opts.map(({ o, index }) => ({ text: o.text, index })));
      const chosen = ins.options[pick];
      for (const s of chosen.set) this.applySet(s.v, s.op, s.e);
      this.backlog.push({ text: chosen.text, choice: true });
      this.jump(chosen.target);
      return;
    }
    if (op === "jump") {
      if (this.cond(raw.cond as string | undefined)) this.jump(raw.target as string);
      return;
    }
    if (op === "call") {
      if (this.cond(raw.cond as string | undefined)) {
        this.callStack.push(this.pc);
        this.jump(raw.target as string);
      }
      return;
    }
    if (op === "if") {
      if (evaluate(raw.cond as string, this.vars)) this.jump(raw.target as string);
      return;
    }
    if (op === "set") {
      if (this.cond(raw.cond as string | undefined)) this.applySet(raw.v as string, raw.sop as string, raw.e as string);
      return;
    }
    await this.cmd(raw as unknown as CmdIns);
  }

  private applySet(v: string, op: string, e: string) {
    const val = evaluate(e, this.vars);
    if (op === "+=") this.vars[v] = (this.vars[v] ?? 0) + val;
    else if (op === "-=") this.vars[v] = (this.vars[v] ?? 0) - val;
    else this.vars[v] = val;
  }

  private async cmd(c: CmdIns) {
    if (!this.cond(c.cond)) return;
    const { pos, kv } = c;
    const st = this.stage;
    const nowait = kv.nowait === true || kv.async === true;
    const run = async (p: Promise<unknown>) => {
      if (nowait) void p;
      else await p;
    };
    const skipping = this.host.isSkipping();
    switch (c.op) {
      case "bg":
        await run(st.setBg(str(pos[0]), str(kv.fx, "cross"), num(kv.t, 1), num(kv.zoom, 1), num(kv.x, 0), num(kv.y, 0)));
        if (kv.light !== undefined) st.setLight(str(kv.light));
        break;
      case "cg": {
        const id = str(pos[0]);
        if (id !== "off") this.host.unlockCg(id);
        await run(st.setCg(id, num(kv.t, 1), str(kv.fx, "cross")));
        break;
      }
      case "scene": {
        // @scene <bg> light=.. weather=storm:0.9,lightning:0.5 : clear characters + cg + weather and switch
        // background in one go; the new weather is already there when the scene is revealed
        const trans = str(kv.fx, "black");
        const covered = trans === "black" || trans === "white";
        st.setFx("off", 0);
        await st.hideAll(0.3);
        if (st.scene.cg) await st.setCg(null, 0.4);
        if (kv.tint === undefined && st.scene.tint && st.scene.tint !== "none") st.setTint("none", 0.8);
        await st.setBg(str(pos[0]), trans, num(kv.t, 1.2), num(kv.zoom, 1), num(kv.x, 0), num(kv.y, 0), () => {
          st.setFx("off", 0, covered);
          for (const w of str(kv.weather).split(",").filter(Boolean)) {
            const [kind, lvl] = w.split(":");
            st.setFx(kind.trim(), lvl === undefined ? 1 : Number(lvl), covered);
          }
        });
        st.setLight(str(kv.light, "day"));
        if (kv.tint !== undefined) st.setTint(str(kv.tint), 0);
        break;
      }
      case "show": {
        const id = str(pos[0]);
        const x = kv.at !== undefined ? (POS[str(kv.at)] ?? num(kv.at, 0.5)) : (st.scene.chars.find((ch) => ch.id === id)?.x ?? 0.5);
        await run(st.show(id, pos[1] !== undefined ? str(pos[1]) : (kv.pose as string | undefined),
          pos[2] !== undefined ? str(pos[2]) : (kv.expr as string | undefined), x, num(kv.t, 0.45), str(kv.from, "none")));
        break;
      }
      case "hide":
        await run(st.hide(str(pos[0]), num(kv.t, 0.4), str(kv.to, "none")));
        break;
      case "hideall":
      case "clear":
        await run(st.hideAll(num(kv.t, 0.4)));
        break;
      case "expr":
        st.setExpr(str(pos[0]), str(pos[1]));
        break;
      case "pose":
        st.setPose(str(pos[0]), str(pos[1]));
        break;
      case "move":
        await run(st.move(str(pos[0]), POS[str(kv.at)] ?? num(kv.at, 0.5), num(kv.t, 0.6)));
        break;
      case "react":
        st.react(str(pos[0]), str(pos[1], "hop"));
        break;
      case "bgm": {
        const id = str(pos[0]);
        st.scene.bgm = id === "stop" || id === "off" ? null : id;
        st.scene.bgmVol = num(kv.vol, 1);
        await this.audio.playBgm(st.scene.bgm, num(kv.t, 2), st.scene.bgmVol);
        break;
      }
      case "amb": {
        const ids = pos.map((p) => str(p)).filter((p) => p !== "stop" && p !== "off");
        st.scene.amb = ids;
        await this.audio.setAmb(ids, num(kv.t, 2));
        break;
      }
      case "sfxloop": {
        const id = str(pos[0]);
        st.scene.sfxloop = id === "stop" || id === "off" ? null : id;
        await this.audio.setSfxLoop(st.scene.sfxloop, num(kv.t, 0.6));
        break;
      }
      case "se":
        if (!skipping || kv.always) void this.audio.se(str(pos[0]), num(kv.vol, 1), num(kv.delay, 0));
        break;
      case "voicefx":
        st.scene.voicefx = str(pos[0], "none");
        break;
      case "stopvoice":
        this.audio.stopVoice();
        break;
      case "wait":
        await this.host.wait(num(pos[0], 1));
        break;
      case "shake":
        st.shake(num(kv.amp, 12), num(kv.t, 0.5));
        break;
      case "flash":
        await run(st.flash(str(kv.color, "white"), num(kv.t, 0.35)));
        break;
      case "camera":
        await run(st.camera(num(kv.zoom, 1), num(kv.x, 0), num(kv.y, 0), num(kv.t, 1.2)));
        break;
      case "pan":
        st.panBg(num(kv.zoom, 1), num(kv.x, 0), num(kv.y, 0), num(kv.t, 8));
        break;
      case "cgpan":
        st.panCg(num(kv.zoom, 1), num(kv.x, 0), num(kv.y, 0), num(kv.t, 8));
        break;
      case "fx": {
        const kind = str(pos[0]);
        const lvl = pos[1] === "off" ? 0 : num(pos[1], 1);
        st.setFx(kind, lvl, kv.instant === true);
        break;
      }
      case "light":
        st.setLight(str(pos[0], "day"));
        break;
      case "tint":
        st.setTint(str(pos[0], "none"), num(kv.t, 1.5));
        break;
      case "letterbox":
        st.setLetterbox(str(pos[0], "on") === "on");
        break;
      case "sepia":
        st.setFilters(str(pos[0], "on") === "on", st.scene.blur);
        break;
      case "blur":
        st.setFilters(st.scene.sepia, num(pos[0], 0));
        break;
      case "textbox": {
        const v = str(pos[0], "show") !== "hide";
        st.scene.textbox = v;
        this.host.setTextbox(v);
        break;
      }
      case "chapter": {
        st.scene.chapter = `${str(pos[0])} ${str(pos[1])}`.trim();
        this.host.onChapter(str(pos[0]), str(pos[1]));
        this.host.setTextbox(false);
        await st.chapterCard(str(pos[0]), str(pos[1]), str(pos[2]), num(kv.hold, 2.6));
        this.host.setTextbox(st.scene.textbox);
        this.host.autosave(st.scene.chapter);
        break;
      }
      case "date":
        void st.dateCard(str(pos[0]));
        break;
      case "caption":
        this.host.setTextbox(false);
        await st.caption(str(pos[0]), num(kv.hold, 2.4));
        this.host.setTextbox(st.scene.textbox);
        break;
      case "autosave":
        this.host.autosave(st.scene.chapter);
        break;
      case "unlock":
        this.host.unlockCg(str(pos[0]));
        break;
      case "ending":
        await this.host.ending(str(pos[0]), str(pos[1]));
        break;
      case "credits":
        await this.host.credits(str(pos[0], "theme_song"), str(pos[1], ""));
        break;
      case "title":
        this.stop();
        this.host.toTitle();
        break;
      case "return": {
        const r = this.callStack.pop();
        if (r !== undefined) this.pc = r;
        break;
      }
      case "note":
      case "mono":
      case "nvl":
      case "lock":
      case "unlock_input":
      case "cgvar":
      case "fade":
      case "shakeloop":
        break;
      default:
        throw new Error(`unknown command @${c.op}`);
    }
  }
}
