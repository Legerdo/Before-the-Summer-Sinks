"""Interactive smoke test with screenshots (real rendering, audio enabled).

Usage: python shots.py <scenario> [--url http://localhost:5173/] [--out art_work/qa]
Scenarios are small scripts of actions defined below.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
args = sys.argv[1:]
url = "http://localhost:47813/"
out = ROOT / "art_work" / "qa"
if "--url" in args:
    i = args.index("--url")
    url = args[i + 1]
    del args[i:i + 2]
if "--out" in args:
    i = args.index("--out")
    out = Path(args[i + 1])
    del args[i:i + 2]
scenario = args[0] if args else "smoke"
out.mkdir(parents=True, exist_ok=True)


def shot(page, name, small=True):
    p = out / f"{name}.png"
    page.screenshot(path=str(p))
    if small:
        im = Image.open(p).convert("RGB")
        im.resize((1280, 720), Image.LANCZOS).save(out / f"{name}_s.jpg", quality=88)
    print("shot", name, flush=True)


def advance(page, n=1, delay=0.35):
    for _ in range(n):
        page.mouse.click(960, 540)
        time.sleep(delay)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True,
                              args=["--autoplay-policy=no-user-gesture-required", "--mute-audio"])
        ctx = b.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page = ctx.new_page()
        logs = []
        page.on("console", lambda m: logs.append(f"{m.type}: {m.text}"))
        page.on("pageerror", lambda e: logs.append(f"pageerror: {e}"))
        page.goto(url + ("" if scenario != "label" else ""), wait_until="networkidle")
        time.sleep(1.0)
        if scenario == "smoke":
            shot(page, "01_splash")
            page.mouse.click(960, 540)
            time.sleep(2.5)
            shot(page, "02_title")
            page.get_by_text("처음부터").click()
            time.sleep(5.5)
            shot(page, "03_prologue_radio")
            advance(page, 3, 1.2)
            time.sleep(6)
            shot(page, "04_caption")
            time.sleep(4)
            advance(page, 2, 1.0)
            shot(page, "05_busstop")
            for k in range(14):
                advance(page, 1, 0.25)
                advance(page, 1, 0.25)
            time.sleep(3)
            shot(page, "06_after_prologue")
        elif scenario.startswith("label:"):
            label = scenario.split(":", 1)[1]
            page.goto(url + f"?label={label}", wait_until="networkidle")
            time.sleep(0.8)
            page.mouse.click(960, 540)
            time.sleep(3)
            for k in range(int(args[1]) if len(args) > 1 else 6):
                shot(page, f"{label}_{k:02d}")
                advance(page, 1, 1.4)
        errs = page.evaluate("() => window.__vn ? window.__vn.errors : []")
        (out / "console.json").write_text(json.dumps({"logs": logs, "errors": errs}, ensure_ascii=False, indent=1), encoding="utf-8")
        print("console lines:", len(logs), "vn errors:", len(errs))
        for l in logs[-15:]:
            print("  ", l[:200])
        b.close()


if __name__ == "__main__":
    main()
