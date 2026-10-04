// Story compiler: story/*.vn  ->  public/data/story.json (+ voice/lines.json)
//
// Syntax (one statement per line):
//   // comment
//   *label                                   label
//   @cmd pos1 pos2 key=value key="a b"       command
//   ?(cond) <statement>                      conditional statement
//   @choice [id]                             choice header, followed by option lines:
//   = option text => *target ; var += 1      option (optional ?(cond) prefix)
//   Name(expr)<cue>: text #id                dialogue (Display=Name(...) for a custom name plate)
//   anything else                            narration
// Text markup: {w=0.5} pause, [[cue]] inline TTS cue (hidden), {shown|spoken} alternate TTS reading.
//
// Voice ids (#ys0001) are stamped into the source files for every voiced line that lacks one.
// Existing ids are never changed, so editing a line keeps its id; lines.json carries a text hash
// that the TTS tool uses to detect lines that need regeneration.

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/(\w:)/, "$1")), "..", "..");
const STORY_DIR = path.join(ROOT, "story");
const OUT = path.join(ROOT, "public", "data", "story.json");
const VOICE_OUT = path.join(ROOT, "voice", "lines.json");
const CHARS = JSON.parse(fs.readFileSync(path.join(STORY_DIR, "characters.json"), "utf8"));
const ASSETS_PATH = path.join(ROOT, "public", "data", "assets.json");
const ASSETS = fs.existsSync(ASSETS_PATH) ? JSON.parse(fs.readFileSync(ASSETS_PATH, "utf8")) : null;
const STRICT_ASSETS = process.argv.includes("--strict-assets");

const errors = [];
const warnings = [];
const err = (loc, msg) => errors.push(`${loc}: ${msg}`);
const warn = (loc, msg) => warnings.push(`${loc}: ${msg}`);

const files = fs.readdirSync(STORY_DIR).filter((f) => f.endsWith(".vn")).sort();

// ---------------------------------------------------------------- tokenizing helpers
function parseArgs(s) {
  const pos = [];
  const kv = {};
  const re = /\s*(?:([A-Za-z_][\w.-]*)=("(?:[^"\\]|\\.)*"|\S+)|("(?:[^"\\]|\\.)*")|(\S+))/gy;
  let m;
  while ((m = re.exec(s)) !== null) {
    if (m[0].trim() === "") break;
    if (m[1] !== undefined) kv[m[1]] = coerce(unq(m[2]));
    else if (m[3] !== undefined) pos.push(unq(m[3]));
    else if (m[4] !== undefined) pos.push(coerce(m[4]));
  }
  return { pos, kv };
}
function unq(v) {
  if (typeof v === "string" && v.startsWith('"') && v.endsWith('"')) return v.slice(1, -1).replace(/\\"/g, '"');
  return v;
}
function coerce(v) {
  if (typeof v !== "string") return v;
  if (/^-?\d+(\.\d+)?$/.test(v)) return Number(v);
  if (v === "true") return true;
  if (v === "false") return false;
  return v;
}

// Tiny expression validator (same grammar as runtime evaluator).
function validateExpr(expr, loc) {
  const toks = expr.match(/\s*(>=|<=|==|!=|&&|\|\||[-+*/%()<>!]|%?[A-Za-z_]\w*|\d+(?:\.\d+)?)\s*/g);
  const joined = (toks || []).join("").replace(/\s+/g, "");
  if (joined !== expr.replace(/\s+/g, "")) err(loc, `bad expression: ${expr}`);
}
function parseSet(s, loc) {
  const m = s.trim().match(/^(%?[A-Za-z_]\w*)\s*(=|\+=|-=)\s*(.+)$/);
  if (!m) {
    err(loc, `bad set: ${s}`);
    return null;
  }
  validateExpr(m[3], loc);
  return { v: m[1], op: m[2], e: m[3].trim() };
}

// ---------------------------------------------------------------- text helpers
function displayText(t) {
  return t
    .replace(/\[\[[^\]]*\]\]/g, "")
    .replace(/\{([^{}|]*)\|([^{}]*)\}/g, "$1")
    .replace(/\s{2,}/g, " ")
    .trim();
}
function ttsText(t, cue) {
  let s = t
    .replace(/\{w=[\d.]+\}/g, "")
    .replace(/\[\[([^\]]*)\]\]/g, "[$1]")
    .replace(/\{([^{}|]*)\|([^{}]*)\}/g, "$2")
    .replace(/\s{2,}/g, " ")
    .trim();
  // one natural-language bracket cue (S2 models accept free-form descriptions)
  if (cue) s = `[${cue.trim()}] ` + s;
  return s;
}
const hash = (s) => crypto.createHash("sha1").update(s).digest("hex").slice(0, 10);

// ---------------------------------------------------------------- pass 1: collect existing voice ids
const usedIds = new Set();
const maxN = {};
for (const f of files) {
  const src = fs.readFileSync(path.join(STORY_DIR, f), "utf8");
  for (const m of src.matchAll(/#([a-z]{2})(\d{4})\b/g)) {
    const id = m[1] + m[2];
    usedIds.add(id);
    maxN[m[1]] = Math.max(maxN[m[1]] || 0, Number(m[2]));
  }
}
// A voice id may appear more than once only for an intentional replay of the identical line.
const voiceText = new Map();
function nextId(prefix) {
  maxN[prefix] = (maxN[prefix] || 0) + 1;
  return prefix + String(maxN[prefix]).padStart(4, "0");
}

// ---------------------------------------------------------------- pass 2: parse
const code = [];
const labels = {};
const labelOrder = [];
const voiceLines = [];
const lineIdCount = {};
let stamped = 0;
const KNOWN_CMDS = new Set([
  "bg", "cg", "cgvar", "show", "hide", "expr", "pose", "move", "bgm", "amb", "se", "voicefx", "wait", "shake",
  "flash", "camera", "fx", "light", "chapter", "choice", "jump", "if", "set", "textbox", "ending", "credits",
  "title", "scene", "clear", "hideall", "fade", "unlock", "stopvoice", "nvl", "mono", "date", "sfxloop",
  "autosave", "lock", "unlock_input", "note", "caption", "letterbox", "blur", "shakeloop", "sepia", "call", "return",
  "react", "pan", "cgpan", "tint",
]);

for (const f of files) {
  const p = path.join(STORY_DIR, f);
  const lines = fs.readFileSync(p, "utf8").replace(/\r\n/g, "\n").split("\n");
  let currentLabel = null;
  let pendingChoice = null;
  let changed = false;
  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const loc = `${f}:${i + 1}`;
    let s = raw.trim();
    if (!s || s.startsWith("//")) {
      if (pendingChoice && s === "") continue;
      continue;
    }
    let cond = null;
    const cm = s.match(/^\?\((.+?)\)\s+(.*)$/);
    if (cm) {
      cond = cm[1].trim();
      validateExpr(cond, loc);
      s = cm[2].trim();
    }
    // choice options
    if (s.startsWith("= ")) {
      if (!pendingChoice) {
        err(loc, "option outside @choice");
        continue;
      }
      const om = s.slice(2).match(/^(.*?)\s*=>\s*\*([\w.]+)\s*(?:;(.*))?$/);
      if (!om) {
        err(loc, `bad option: ${s}`);
        continue;
      }
      const sets = (om[3] || "").split(";").map((x) => x.trim()).filter(Boolean).map((x) => parseSet(x, loc)).filter(Boolean);
      pendingChoice.options.push({ text: om[1].trim(), target: om[2], set: sets, cond, loc });
      continue;
    }
    pendingChoice = null;

    if (s.startsWith("*")) {
      const name = s.slice(1).trim();
      if (!/^[\w.]+$/.test(name)) err(loc, `bad label ${name}`);
      if (labels[name] !== undefined) err(loc, `duplicate label ${name}`);
      labels[name] = code.length;
      labelOrder.push(name);
      currentLabel = name;
      continue;
    }
    if (s.startsWith("@")) {
      const sp = s.indexOf(" ");
      const cmd = (sp < 0 ? s.slice(1) : s.slice(1, sp)).trim();
      const rest = sp < 0 ? "" : s.slice(sp + 1);
      if (!KNOWN_CMDS.has(cmd)) err(loc, `unknown command @${cmd}`);
      if (cmd === "choice") {
        const { pos } = parseArgs(rest);
        const id = `${currentLabel || "top"}:choice:${pos[0] || code.length}`;
        pendingChoice = { op: "choice", id, options: [], loc };
        if (cond) pendingChoice.cond = cond;
        code.push(pendingChoice);
        continue;
      }
      if (cmd === "jump" || cmd === "call") {
        const t = rest.trim().replace(/^\*/, "");
        const ins = { op: cmd, target: t, loc };
        if (cond) ins.cond = cond;
        code.push(ins);
        continue;
      }
      if (cmd === "if") {
        const im = rest.match(/^(.*?)\s*=>\s*\*([\w.]+)\s*$/);
        if (!im) {
          err(loc, `bad @if: ${rest}`);
          continue;
        }
        validateExpr(im[1], loc);
        code.push({ op: "if", cond: im[1].trim(), target: im[2], loc });
        continue;
      }
      if (cmd === "set") {
        const st = parseSet(rest, loc);
        if (st) code.push({ op: "set", v: st.v, sop: st.op, e: st.e, ...(cond ? { cond } : {}), loc });
        continue;
      }
      const { pos, kv } = parseArgs(rest);
      const ins = { op: cmd, pos, kv, loc };
      if (cond) ins.cond = cond;
      code.push(ins);
      continue;
    }

    // dialogue?
    const dm = s.match(/^(?:([^\s:=()<>#]{1,14})=)?([^\s:=()<>#]{1,14})(?:\(([a-z_]+)\))?(?:<([^>]*)>)?:\s*(.*)$/);
    let who = null, disp = null, expr = null, cue = null, text = s;
    if (dm && (CHARS[dm[2]] || dm[1])) {
      disp = dm[1] || null;
      who = dm[2];
      expr = dm[3] || null;
      cue = dm[4] || null;
      text = dm[5];
      if (!CHARS[who]) err(loc, `unknown character ${who}`);
    } else if (dm && !CHARS[dm[2]] && /^[^\s]{1,14}(\([a-z_]+\))?:\s/.test(s) && !/^https?:/.test(s)) {
      warn(loc, `possible unknown speaker "${dm[2]}" treated as narration`);
    }
    let vid = null;
    const idm = text.match(/\s+#([a-z]{2}\d{4})\s*$/);
    if (idm) {
      vid = idm[1];
      text = text.slice(0, idm.index).trimEnd();
    }
    const ch = who ? CHARS[who] : null;
    const voiced = ch && ch.voice && ch.voice !== false;
    if (voiced && !vid) {
      vid = nextId(ch.voicePrefix);
      lines[i] = raw.replace(/\s*$/, "") + ` #${vid}`;
      changed = true;
      stamped++;
    }
    if (!voiced && vid) warn(loc, `voice id on unvoiced line (${who || "narration"})`);
    const shown = displayText(text);
    if (!shown) err(loc, "empty text");
    const baseId = `${currentLabel || "top"}:${hash((who || "") + "|" + shown)}`;
    lineIdCount[baseId] = (lineIdCount[baseId] || 0) + 1;
    const lineId = lineIdCount[baseId] > 1 ? `${baseId}.${lineIdCount[baseId]}` : baseId;
    const ins = { op: "say", id: lineId, text: shown, loc };
    if (who) {
      ins.who = ch ? ch.id : who;
      ins.name = disp || (ch ? ch.name : who);
    }
    if (expr) ins.expr = expr;
    if (vid && voiced) {
      ins.voice = vid;
      const tts = ttsText(text, cue);
      const prev = voiceText.get(vid);
      if (prev === undefined) {
        voiceText.set(vid, tts);
        voiceLines.push({ id: vid, char: ch.id, text: shown, tts, hash: hash(ch.id + "|" + tts), label: currentLabel, loc });
      } else if (prev !== tts) err(loc, `voice id ${vid} reused for a different line`);
    }
    if (cond) ins.cond = cond;
    code.push(ins);
  }
  if (changed) fs.writeFileSync(p, lines.join("\n"), "utf8");
}

// ---------------------------------------------------------------- validation
for (const ins of code) {
  const loc = ins.loc;
  if (ins.op === "jump" || ins.op === "if" || ins.op === "call") {
    if (labels[ins.target] === undefined) err(loc, `unknown label *${ins.target}`);
  }
  if (ins.op === "choice") {
    if (ins.options.length < 2) err(loc, "choice needs >= 2 options");
    for (const o of ins.options) if (labels[o.target] === undefined) err(o.loc, `unknown label *${o.target}`);
  }
  if (ASSETS) {
    const need = (kind, id) => {
      if (id === undefined || id === null || id === "off" || id === "stop" || id === "none" || id === "black" || id === "white") return;
      const table = ASSETS[kind] || {};
      if (!table[id]) (STRICT_ASSETS ? err : warn)(loc, `missing ${kind} asset "${id}"`);
    };
    if (ins.op === "bg") need("bg", ins.pos[0]);
    if (ins.op === "cg" || ins.op === "cgvar") need("cg", ins.pos[0]);
    if (ins.op === "bgm") need("bgm", ins.pos[0]);
    if (ins.op === "amb") need("amb", ins.pos[0]);
    if (ins.op === "se") need("se", ins.pos[0]);
    if (ins.op === "sfxloop" && !(ASSETS.amb || {})[ins.pos[0]]) need("se", ins.pos[0]);
    if (ins.op === "amb") for (const a of ins.pos) need("amb", a);
    if (ins.op === "show" || ins.op === "expr" || ins.op === "pose") {
      const who = ins.pos[0];
      const ch = Object.values(CHARS).find((c) => c.id === who || c.key === who);
      if (!ch) err(loc, `unknown character in @${ins.op}: ${who}`);
      const sprites = ASSETS.chars && ASSETS.chars[ch ? ch.id : who];
      if (!sprites) (STRICT_ASSETS ? err : warn)(loc, `no sprite set for ${who}`);
      else {
        const expr = ins.op === "expr" ? ins.pos[1] : ins.kv.expr || (ins.op === "show" ? ins.pos[2] : null);
        const pose = ins.op === "pose" ? ins.pos[1] : ins.kv.pose || (ins.op === "show" ? ins.pos[1] : null);
        if (expr && !sprites.faces[expr]) (STRICT_ASSETS ? err : warn)(loc, `unknown expression ${expr} for ${who}`);
        if (pose && !sprites.bodies[pose]) (STRICT_ASSETS ? err : warn)(loc, `unknown pose ${pose} for ${who}`);
      }
    }
  }
  if (ins.op === "say" && ins.expr && ASSETS && ASSETS.chars) {
    const sprites = ASSETS.chars[ins.who];
    if (sprites && !sprites.faces[ins.expr]) (STRICT_ASSETS ? err : warn)(loc, `unknown expression ${ins.expr} for ${ins.who}`);
  }
}
const firstLabel = labelOrder[0];
if (labels.start === undefined) err("story", "missing *start label");

// strip loc for output size, keep a compact source map
const srcmap = code.map((c) => c.loc);
for (const c of code) {
  delete c.loc;
  if (c.options) for (const o of c.options) delete o.loc;
}

// statistics
let sayCount = 0, chars = 0, voiced = 0;
const perChar = {};
for (const c of code) {
  if (c.op !== "say") continue;
  sayCount++;
  chars += c.text.length;
  if (c.voice) voiced++;
  perChar[c.who || "(narration)"] = (perChar[c.who || "(narration)"] || 0) + 1;
}

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify({ labels, code, srcmap, first: firstLabel }), "utf8");
fs.mkdirSync(path.dirname(VOICE_OUT), { recursive: true });
fs.writeFileSync(VOICE_OUT, JSON.stringify(voiceLines, null, 1), "utf8");

for (const w of warnings) console.warn("warn  " + w);
for (const e of errors) console.error("ERROR " + e);
console.log(
  `story: ${files.length} files, ${code.length} instructions, ${Object.keys(labels).length} labels, ` +
    `${sayCount} lines (${chars} chars), ${voiced} voiced, stamped ${stamped} new voice ids`
);
console.log("lines per speaker:", JSON.stringify(perChar));
if (errors.length) process.exit(1);
