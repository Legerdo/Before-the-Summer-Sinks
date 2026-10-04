"""Estimate play time per route by walking the compiled story like the VM does.

Time model (seconds):
  say     max(text reveal at 45 cps + inline waits, reading time, voice length) + reaction
  choice  6 s to read and decide
  staging the awaited durations the VM really waits for (scene/bg/cg/show/hide/move/camera/wait,
          chapter & caption cards, ending card, credits roll)
Reading speed presets are Korean syllables (incl. spaces/punctuation) per second.
Usage: python playtime.py [--all]
"""
from __future__ import annotations

import itertools
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
story = json.loads((ROOT / "public/data/story.json").read_text(encoding="utf-8"))
assets = json.loads((ROOT / "public/data/assets.json").read_text(encoding="utf-8"))
voice = assets["voice"]
bgm = assets["bgm"]
code, labels = story["code"], story["labels"]

READERS = {"fast": 11.0, "typical": 8.0, "slow": 6.0}
REVEAL_CPS = 45.0
REACTION = 0.6
CHOICE = 6.0


def lex(s: str):
    return re.findall(r"\s*(>=|<=|==|!=|&&|\|\||[-+*/%()<>!]|%?[A-Za-z_]\w*|\d+(?:\.\d+)?)", s)


def evaluate(expr: str, vars_: dict) -> float:
    toks = [t.strip() for t in lex(expr)]
    i = 0
    prec = {"||": 1, "&&": 2, "==": 3, "!=": 3, "<": 4, ">": 4, "<=": 4, ">=": 4, "+": 5, "-": 5, "*": 6, "/": 6, "%": 6}

    def unary():
        nonlocal i
        if i >= len(toks):
            return 0
        t = toks[i]
        i += 1
        if re.match(r"^\d", t):
            return float(t)
        if re.match(r"^%?[A-Za-z_]", t):
            return 1 if t == "true" else 0 if t == "false" else vars_.get(t, 0)
        if t == "(":
            v = binop(0)
            i += 1
            return v
        if t == "!":
            return 0 if unary() else 1
        if t == "-":
            return -unary()
        return 0

    def binop(min_p):
        nonlocal i
        l = unary()
        while i < len(toks) and toks[i] in prec and prec[toks[i]] >= min_p:
            op = toks[i]
            i += 1
            r = binop(prec[op] + 1)
            l = {"||": lambda: 1 if (l or r) else 0, "&&": lambda: 1 if (l and r) else 0,
                 "==": lambda: 1 if l == r else 0, "!=": lambda: 1 if l != r else 0,
                 "<": lambda: 1 if l < r else 0, ">": lambda: 1 if l > r else 0,
                 "<=": lambda: 1 if l <= r else 0, ">=": lambda: 1 if l >= r else 0,
                 "+": lambda: l + r, "-": lambda: l - r, "*": lambda: l * r,
                 "/": lambda: l / r if r else 0, "%": lambda: l % r if r else 0}[op]()
        return l

    return binop(0)


def plain(text: str):
    waits = sum(float(w) for w in re.findall(r"\{w=([\d.]+)\}", text))
    return re.sub(r"\{[^}]*\}", "", text), waits


def num(v, d):
    return d if v in (None, "") else float(v)


def walk(choices, rate):
    vars_, stack, pc = {}, [], labels["start"]
    t = {"text": 0.0, "voice_wait": 0.0, "staging": 0.0, "choice": 0.0, "credits": 0.0}
    chars = lines = voiced = 0
    ch = list(choices)
    ending = None
    cond = lambda c: (not c) or bool(evaluate(c, vars_))
    steps = 0
    while pc < len(code):
        steps += 1
        if steps > 200000:
            raise RuntimeError("loop")
        ins = code[pc]
        pc += 1
        op = ins["op"]
        if op == "say":
            if not cond(ins.get("cond")):
                continue
            text, waits = plain(ins["text"])
            n = len(text)
            chars += n
            lines += 1
            reveal = n / REVEAL_CPS + waits
            read = n / rate + waits
            vd = voice.get(ins.get("voice") or "", {}).get("dur", 0.0)
            if vd:
                voiced += 1
            base = max(reveal, read)
            t["text"] += base + REACTION
            if vd > base:
                t["voice_wait"] += vd - base
            continue
        if op == "choice":
            if not cond(ins.get("cond")):
                continue
            opts = [k for k, o in enumerate(ins["options"]) if cond(o.get("cond"))]
            want = ch.pop(0) if ch else opts[0]
            pick = want if want in opts else opts[0]
            o = ins["options"][pick]
            for s in o["set"]:
                val = evaluate(s["e"], vars_)
                vars_[s["v"]] = vars_.get(s["v"], 0) + val if s["op"] == "+=" else vars_.get(s["v"], 0) - val if s["op"] == "-=" else val
            t["choice"] += CHOICE
            pc = labels[o["target"]]
            continue
        if op in ("jump", "call"):
            if cond(ins.get("cond")):
                if op == "call":
                    stack.append(pc)
                pc = labels[ins["target"]]
            continue
        if op == "if":
            if evaluate(ins["cond"], vars_):
                pc = labels[ins["target"]]
            continue
        if op == "set":
            if cond(ins.get("cond")):
                val = evaluate(ins["e"], vars_)
                v = ins["v"]
                vars_[v] = vars_.get(v, 0) + val if ins["sop"] == "+=" else vars_.get(v, 0) - val if ins["sop"] == "-=" else val
            continue
        if not cond(ins.get("cond")):
            continue
        kv, pos = ins.get("kv", {}), ins.get("pos", [])
        nowait = kv.get("nowait") is True or kv.get("async") is True
        dt = 0.0
        if op == "scene":
            dt = 0.3 + 0.4 + num(kv.get("t"), 1.2)
        elif op in ("bg", "cg"):
            dt = 0 if nowait else num(kv.get("t"), 1)
        elif op == "show":
            dt = 0 if nowait else num(kv.get("t"), 0.45)
        elif op in ("hide", "hideall", "clear"):
            dt = 0 if nowait else num(kv.get("t"), 0.4)
        elif op == "move":
            dt = 0 if nowait else num(kv.get("t"), 0.6)
        elif op == "camera":
            dt = 0 if nowait else num(kv.get("t"), 1.2)
        elif op == "flash":
            dt = 0 if nowait else num(kv.get("t"), 0.35)
        elif op == "wait":
            dt = num(pos[0] if pos else None, 1)
        elif op == "chapter":
            dt = num(kv.get("hold"), 2.6) + 0.72
        elif op == "caption":
            dt = num(kv.get("hold"), 2.4) + 0.82
        elif op == "ending":
            # the compiler turns bare true/false into booleans; the VM stringifies them
            ending = (str(pos[0]).lower() if isinstance(pos[0], bool) else str(pos[0])) if pos else None
            dt = 4.2 + 1.25
        elif op == "credits":
            song = pos[0] if pos else "theme_song"
            d = min(140, max(40, bgm.get(song, {}).get("duration", 90) - 6))
            t["credits"] += d + 2.5 + 2.1
        elif op == "return":
            if stack:
                pc = stack.pop()
        elif op == "title":
            break
        t["staging"] += dt
    total = sum(t.values())
    return {"total_min": total / 60, "parts": {k: round(v / 60, 1) for k, v in t.items()}, "chars": chars,
            "lines": lines, "voiced": voiced, "ending": ending, "vars": vars_}


def main():
    all_combos = list(itertools.product(range(2), range(3), range(2), range(2), range(3), range(3)))
    res = {name: [walk(c, rate) for c in all_combos] for name, rate in READERS.items()}
    typ = res["typical"]
    by_end = {}
    for c, r in zip(all_combos, typ):
        by_end.setdefault(r["ending"], []).append((r["total_min"], c, r))
    print(f"{len(all_combos)} choice combinations walked; endings: { {k: len(v) for k, v in by_end.items()} }")
    for name in READERS:
        mins = [r["total_min"] for r in res[name]]
        print(f"  {name:8s} reader ({READERS[name]:.0f} syl/s): one route {min(mins):.1f}-{max(mins):.1f} min")
    for e, rows in by_end.items():
        rows.sort()
        lo, hi = rows[0], rows[-1]
        print(f"  ending {e}: typical {lo[0]:.1f}-{hi[0]:.1f} min; e.g. {hi[1]} parts {hi[2]['parts']} "
              f"lines {hi[2]['lines']} voiced {hi[2]['voiced']} chars {hi[2]['chars']}")
    # both endings back to back (second run re-reads shared text quickly with skip-read)
    true_r = max((r for r in typ if r["ending"] == "true"), key=lambda r: r["total_min"])
    norm_r = max((r for r in typ if r["ending"] == "normal"), key=lambda r: r["total_min"])
    print(f"  first route (true) {true_r['total_min']:.1f} min + second route (normal, fresh read) {norm_r['total_min']:.1f} min")
    vtotal = sum(v["dur"] for v in voice.values())
    print(f"  total recorded voice {vtotal / 60:.1f} min across {len(voice)} clips")


if __name__ == "__main__":
    main()
