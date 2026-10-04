"""Full-route verification in a real Chrome instance (headless) using the in-game QA hooks.

* decodes every audio file and image the game references
* runs the whole story from *start for a set of choice combinations (instant text, no waits)
* checks runtime errors, endings reached, variable logic, and instruction coverage
Usage: python route_check.py [--url http://localhost:47813/] [--all]
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
url = "http://localhost:47813/"
args = sys.argv[1:]
if "--url" in args:
    url = args[args.index("--url") + 1]
ALL = "--all" in args
NO_ASSETS = "--no-assets" in args
FIRST = int(args[args.index("--first") + 1]) if "--first" in args else None  # only combos with this first choice
PART = tuple(int(v) for v in args[args.index("--part") + 1].split("/")) if "--part" in args else None  # k/n split

# choice indices: c1(2) c2(3) c3(2) c4(2) c5(3) c6(3)
if ALL:
    combos = list(itertools.product(range(2), range(3), range(2), range(2), range(3), range(3)))
    if FIRST is not None:
        combos = [c for c in combos if c[0] == FIRST]
    if PART:
        combos = [c for i, c in enumerate(combos) if i % PART[1] == PART[0]]
else:
    combos = [
        (0, 0, 0, 0, 0, 0),  # all warm -> true (다녀와)
        (0, 2, 0, 0, 2, 1),  # true (좋아해), echo=3, shout
        (1, 1, 1, 1, 1, 0),  # cold route: aff 0 -> normal even with 다녀와
        (0, 1, 1, 0, 0, 2),  # 잘 가 -> normal
        (1, 0, 0, 1, 2, 1),  # aff = 2 (c3,c5) -> 좋아해 but normal
        (0, 2, 0, 1, 0, 0),  # aff 3 without honesty -> true
        (1, 2, 1, 0, 1, 1),  # aff 1 -> normal
        (0, 0, 1, 1, 1, 0),  # aff 1 -> normal
        (1, 1, 0, 0, 0, 1),  # aff 3 -> true
    ]


def expected(c):
    aff = (c[0] == 0) + (c[2] == 0) + (c[3] == 0) + (c[4] in (0, 2))
    if c[5] == 2:
        return "normal", aff
    return ("true" if aff >= 3 else "normal"), aff


def main():
    report = {"runs": [], "assets": None, "problems": []}
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True, args=["--autoplay-policy=no-user-gesture-required", "--mute-audio"])
        page = b.new_page(viewport={"width": 1280, "height": 720})
        logs = []
        page.on("console", lambda m: logs.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))
        page.goto(url + "?test=1", wait_until="networkidle")
        page.wait_for_function("() => !!window.__vn", timeout=30000)
        if not NO_ASSETS:
            res = page.evaluate("async () => await window.__vn.verifyAssets()")
            report["assets"] = res
            print(f"assets: audio {res['decoded']}/{res['audio']} decoded, images {res['imgOk']}/{res['images']}, fails {len(res['fails'])}, dur mismatch {len(res['durMismatch'])}")
            for f in res["fails"][:20]:
                print("   FAIL", f)
            for f in res["durMismatch"][:10]:
                print("   DUR", f)
        for c in combos:
            exp, aff = expected(c)
            r = page.evaluate("async (ch) => await window.__vn.run({choices: ch})", list(c))
            got = r.get("ending")
            page.evaluate("() => { window.__vn.errors.length = 0; }")
            ok = (r["vars"].get("aff") == aff) and got == exp
            rec = {"choices": c, "lines": r["lines"], "ms": round(r["ms"]), "aff": r["vars"].get("aff"), "exp_aff": aff,
                   "expected": exp, "ending_new": got, "errors": r["errors"][:10], "ok": ok and not r["errors"]}
            report["runs"].append(rec)
            print(f"{c} lines={r['lines']} aff={rec['aff']}/{aff} expected={exp} got={got} errors={len(r['errors'])} {'OK' if rec['ok'] else 'PROBLEM'}")
            for e in r["errors"][:5]:
                print("    ", e)
        cov = page.evaluate("() => window.__vn.coverage()")
        report["coverage"] = {"total": cov["total"], "visited": cov["visited"], "unvisited": cov["unvisited"][:200]}
        print(f"coverage: {cov['visited']}/{cov['total']} instructions; unvisited {len(cov['unvisited'])}")
        for u in cov["unvisited"][:25]:
            print("   unvisited", u)
        report["console"] = logs[-100:]
        print("console errors/warnings:", len(logs))
        for l in logs[:15]:
            print("   ", l[:220])
        b.close()
    (ROOT / "art_work" / "qa").mkdir(parents=True, exist_ok=True)
    suffix = f"_{FIRST}_{PART[0]}of{PART[1]}" if PART else (f"_{FIRST}" if FIRST is not None else "")
    ok = sum(r["ok"] for r in report["runs"])
    print(f"SUMMARY {ok}/{len(report['runs'])} routes OK")
    (ROOT / "art_work" / "qa" / f"route_report{suffix}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
