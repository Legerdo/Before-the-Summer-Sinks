"""Capture README media (screenshots + GIFs) from the real game running on the dev server (:47813).

Output: docs/media/*.jpg (1280x720) and docs/media/*.gif
Usage: python readme_media.py [name ...]
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "media"
URL = "http://localhost:47813/?qa=1"
WARM = [0, 0, 0, 0, 0, 0]


def loc(f: str, marker: str) -> str:
    lines = (ROOT / "story" / f).read_text(encoding="utf-8").splitlines()
    idx = next(i for i, l in enumerate(lines) if marker in l)
    return f"{f}:{idx + 1}"


def seek(page, f, marker, choices=WARM, settle=2.6):
    page.goto(URL, wait_until="networkidle")
    page.wait_for_function("() => !!window.__vn", timeout=30000)
    page.evaluate("() => { window.__seekDone = false; addEventListener('vn-seek-done', () => window.__seekDone = true); }")
    page.evaluate("(a) => window.__vn.seek({loc: a[0], choices: a[1]})", [loc(f, marker), choices])
    page.wait_for_function("() => window.__seekDone === true", timeout=120000)
    time.sleep(settle)


def shot(page, name, clip=None):
    b = page.screenshot(type="png", clip=clip)
    im = Image.open(io.BytesIO(b)).convert("RGB")
    if im.width > 1280:
        im = im.resize((1280, int(im.height * 1280 / im.width)), Image.LANCZOS)
    im.save(OUT / f"{name}.jpg", quality=88)
    print("shot", name, im.size, flush=True)


def gif(page, name, seconds, width, clip=None, fps=12, before_frame=None, colors=192):
    frames, stamps = [], []
    t0 = time.perf_counter()
    k = 0
    while time.perf_counter() - t0 < seconds:
        if before_frame:
            before_frame(k)
        b = page.screenshot(type="jpeg", quality=90, clip=clip)
        stamps.append(time.perf_counter())
        im = Image.open(io.BytesIO(b)).convert("RGB")
        frames.append(im.resize((width, int(im.height * width / im.width)), Image.LANCZOS))
        k += 1
        wait = t0 + k / fps - time.perf_counter()
        if wait > 0:
            time.sleep(wait)
    durs = [max(40, int((stamps[i + 1] - stamps[i]) * 1000)) for i in range(len(stamps) - 1)] + [80]
    pal = [f.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG) for f in frames]
    pal[0].save(OUT / f"{name}.gif", save_all=True, append_images=pal[1:], duration=durs, loop=0, optimize=True)
    kb = (OUT / f"{name}.gif").stat().st_size // 1024
    print("gif", name, len(frames), "frames", frames[0].size, f"{kb} KB", flush=True)


def main():
    only = set(sys.argv[1:])
    want = lambda n: not only or n in only
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True, args=["--autoplay-policy=no-user-gesture-required", "--mute-audio"])
        page = b.new_page(viewport={"width": 1280, "height": 720})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # -------- scenes
        scenes = [
            ("scene_store", "01_ch1.vn", "@show bongsun default neutral"),
            ("scene_stream", "01_ch1.vn", "@show yunseul uniform_b pout"),
            ("scene_bcroom", "02_ch2.vn", "@show yunseul uniform_c gentle"),
            ("cg_fireflies", "04_ch4.vn", "@cg cg_fireflies"),
            ("scene_father", "05_ch5.vn", "@show father casual smile"),
            ("scene_storm_room", "06_ch6.vn", "@show yunseul casual_b surprised"),
            ("cg_storm", "06_ch6.vn", "@cg cg_storm"),
            ("cg_true_end", "08_end.vn", "@cg cg_true_end"),
        ]
        for name, f, marker in scenes:
            if want(name):
                seek(page, f, marker)
                shot(page, name)
                if name == "scene_bcroom":
                    page.evaluate("() => window.__vn.game.saveTo('1')")
                if name == "cg_fireflies":
                    page.evaluate("() => window.__vn.game.saveTo('2')")
                if name == "scene_storm_room":
                    page.evaluate("() => window.__vn.game.saveTo('3')")

        if want("choice"):
            seek(page, "01_ch1.vn", "너, 내일부터 내 조수야", settle=1.5)
            for _ in range(6):
                if page.evaluate("() => !!document.querySelector('.choices button')"):
                    break
                page.mouse.click(640, 300)
                time.sleep(1.8)
            time.sleep(1.2)
            shot(page, "choice")

        if any(want(n) for n in ("backlog", "settings", "saveload")):
            if want("saveload"):  # a few filled slots for the save screen
                for slot, (f, marker) in {"1": ("02_ch2.vn", "@show yunseul uniform_c gentle"),
                                          "2": ("04_ch4.vn", "@cg cg_fireflies"),
                                          "3": ("06_ch6.vn", "@show yunseul casual_b surprised")}.items():
                    seek(page, f, marker, settle=1.0)
                    page.evaluate("(s) => window.__vn.game.saveTo(s)", slot)
            seek(page, "02_ch2.vn", "@cg cg_echo", settle=1.0)
            for _ in range(5):
                page.mouse.click(640, 300)
                time.sleep(1.2)
            if want("backlog"):
                page.evaluate("() => window.__vn.game.screens.backlog()")
                time.sleep(1.2)
                shot(page, "backlog")
                page.evaluate("() => window.__vn.game.screens.closeAll()")
                time.sleep(0.6)
            if want("settings"):
                page.evaluate("() => window.__vn.game.screens.settings()")
                time.sleep(1.2)
                shot(page, "settings")
                page.evaluate("() => window.__vn.game.screens.closeAll()")
                time.sleep(0.6)
            if want("saveload"):
                page.evaluate("() => window.__vn.game.screens.saveLoad('save')")
                time.sleep(1.5)
                shot(page, "saveload")

        if want("title") or want("gallery"):
            page.goto(URL, wait_until="networkidle")
            page.wait_for_function("() => !!window.__vn", timeout=30000)
            page.evaluate("""() => { const g = window.__vn.game;
                for (const id of Object.keys(window.__vn.assets.cg)) g.store.unlock('cgs', id);
                g.store.unlock('endings', 'true'); g.store.unlock('endings', 'normal'); g.screens.title(); }""")
            time.sleep(4)
            if want("title"):
                shot(page, "title")
            if want("gallery"):
                page.evaluate("() => window.__vn.game.screens.gallery()")
                time.sleep(1.8)
                shot(page, "gallery")

        # -------- GIFs
        if want("lipsync"):
            # the QA probe plays a real voice line on the sprite; the mouth layers follow the audio envelope
            page.goto(URL, wait_until="networkidle")
            page.wait_for_function("() => !!window.__vn", timeout=30000)
            page.evaluate("() => { window.__probe = window.__vn.lipsyncProbe('ys0030', 'yunseul', 'smile'); }")
            page.wait_for_function("() => !!document.querySelector('.sprite[data-char=\"yunseul\"] .sp-mouth1')", timeout=20000)
            time.sleep(0.25)
            r = page.evaluate("""() => { const b = document.querySelector('.sprite[data-char="yunseul"] .sp-mouth1').getBoundingClientRect();
                return {x: b.x + b.width / 2, y: b.y + b.height / 2}; }""")
            clip = {"x": max(0, r["x"] - 130), "y": max(0, r["y"] - 170), "width": 260, "height": 260}
            states: list[int] = []
            probe = lambda k: states.append(page.evaluate("""() => { const q = (c) => document.querySelector('.sprite[data-char="yunseul"] ' + c);
                return q('.sp-mouth2')?.style.opacity === '1' ? 2 : q('.sp-mouth1')?.style.opacity === '1' ? 1 : 0; }"""))
            gif(page, "lipsync", 4.0, 240, clip=clip, fps=12, before_frame=probe, colors=128)
            print("  mouth states per frame:", "".join(map(str, states)))
            page.evaluate("async () => await window.__probe")

        if want("storm"):
            seek(page, "06_ch6.vn", "옥상은 바람의 한가운데였다", settle=1.2)

            def bolt(k):
                if k == 12:
                    page.evaluate("() => { window.__vn.game.stage.fx.nextBolt = performance.now() - 1; }")
            page.mouse.click(640, 300)
            gif(page, "storm", 3.0, 480, fps=10, before_frame=bolt, colors=96)

        if want("fireflies"):
            seek(page, "04_ch4.vn", "@fx fireflies 0.9", settle=3.0)
            gif(page, "fireflies", 3.5, 480, fps=10, colors=128)

        errs = page.evaluate("() => window.__vn.errors.slice()")
        b.close()
    print("runtime errors:", errs[:5], "page errors:", errors[:5])


if __name__ == "__main__":
    main()
