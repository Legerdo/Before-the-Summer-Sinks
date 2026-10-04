"""Check weather state at key story points: @scene resets, indoor lightning, CG covering scenic weather,
and save/restore of the cover state. Needs the dev server (npx vite) on :47813.
Usage: python fx_check.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
URL = "http://localhost:47813/?qa=1"
WARM = [0, 0, 0, 0, 0, 0]
COLD = [1, 1, 1, 1, 1, 2]
# (name, file, marker, choices, expected scene.fx, expected cover)
CHECKS = [
    ("ch2 echo rock after dusty room", "02_ch2.vn", "@scene echo_sunset", WARM, {}, 0),
    ("ch3 stream after dusty room", "03_ch3.vn", "@scene stream_day", WARM, {}, 0),
    ("ch5 rainy room (indoor)", "05_ch5.vn", "19일 밤, 방에서 라디오를 켰다", WARM, {}, 0),
    ("ch6 school yard storm", "06_ch6.vn", "분교 이 층 창문에서", WARM, {"storm": 0.9}, 0),
    ("ch6 broadcast room (power out)", "06_ch6.vn", "@show yunseul casual_b surprised", WARM, {"lightning": 0.6}, 0),
    ("ch6 rooftop", "06_ch6.vn", "옥상은 바람의 한가운데였다", WARM, {"storm": 1}, 0),
    ("ch6 storm CG", "06_ch6.vn", "@cg cg_storm", WARM, {"storm": 1}, 1),
    ("ch6 rooftop after CG", "06_ch6.vn", "번개가 바로 옆 산등성이에", WARM, {"storm": 1}, 0),
    ("ch6 evacuation", "06_ch6.vn", "그로부터 한 시간 반", WARM, {"lightning": 0.5}, 0),
    ("true end lake", "08_end.vn", "물은 정말로 사 년 만에", WARM, {"glitter": 0.8}, 0),
    ("true end CG", "08_end.vn", "@cg cg_true_end", WARM, {"glitter": 0.8}, 1),
    ("normal end city room", "08_end.vn", "@bg city_night", COLD, {}, 0),
]


def loc(f: str, marker: str) -> str:
    lines = (ROOT / "story" / f).read_text(encoding="utf-8").splitlines()
    idx = next(i for i, l in enumerate(lines) if marker in l)
    return f"{f}:{idx + 1}"


def main():
    bad = 0
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True, args=["--autoplay-policy=no-user-gesture-required", "--mute-audio"])
        page = b.new_page(viewport={"width": 1280, "height": 720})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for name, f, marker, ch, want_fx, want_cover in CHECKS:
            page.goto(URL, wait_until="networkidle")
            page.wait_for_function("() => !!window.__vn", timeout=30000)
            page.evaluate("() => { window.__seekDone = false; addEventListener('vn-seek-done', () => window.__seekDone = true); }")
            page.evaluate("(a) => window.__vn.seek({loc: a[0], choices: a[1]})", [loc(f, marker), ch])
            page.wait_for_function("() => window.__seekDone === true", timeout=120000)
            time.sleep(1.5)
            st = page.evaluate("""() => { const s = window.__vn.game.stage;
                return { fx: s.scene.fx, live: s.fx.levels(), cover: s.fx.coverTarget, cg: s.scene.cg, bg: s.scene.bg }; }""")
            ok = st["fx"] == want_fx and st["live"] == want_fx and st["cover"] == want_cover
            if name == "ch6 storm CG":
                # a save made here must restore the covered state
                st2 = page.evaluate("""async () => { const g = window.__vn.game; const snap = g.vm.lastSnap;
                    g.stage.clearAll(); await g.stage.restore(snap.scene);
                    return { fx: g.stage.scene.fx, cover: g.stage.fx.coverTarget, coverNow: g.stage.fx.cover }; }""")
                ok = ok and st2["fx"] == want_fx and st2["cover"] == 1 and st2["coverNow"] == 1
                st["restored"] = st2
            bad += not ok
            print(f"{'OK ' if ok else 'BAD'} {name}: {json.dumps(st, ensure_ascii=False)}", flush=True)
        errs = page.evaluate("() => window.__vn.errors.slice()")
        b.close()
    print("runtime errors:", errs[:5], "page errors:", errors[:5])
    print("RESULT", "PASS" if bad == 0 and not errs and not errors else f"FAIL ({bad})")


if __name__ == "__main__":
    main()
