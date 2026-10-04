"""Attach to a running Electron build (started with VN_DEBUG_PORT=9333) and verify the desktop shell:
app:// loading, assets, window API (fullscreen + window size), persistence of saves across restarts.

Usage: python electron_check.py <phase>   phase = "first" | "second"
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
phase = sys.argv[1] if len(sys.argv) > 1 else "first"
out = ROOT / "art_work" / "qa"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9334")
    page = None
    for _ in range(40):
        for c in b.contexts:
            for pg in c.pages:
                if pg.url.startswith("app://"):
                    page = pg
        if page:
            break
        time.sleep(0.5)
    assert page, "no app:// page"
    page.wait_for_function("() => !!window.__vn", timeout=30000)
    info = page.evaluate("""() => ({url: location.href, host: !!window.vnHost, fs: window.vnHost ? window.vnHost.isFullscreen() : null,
        inner: [innerWidth, innerHeight], errors: window.__vn.errors.slice(), saves: Object.keys(localStorage).filter(k => k.startsWith('sws1.save.'))})""")
    print("info", json.dumps(info, ensure_ascii=False))
    if phase == "first":
        # get through the splash, start a game, advance a few lines, save to slot 1
        page.mouse.click(700, 400)
        time.sleep(2.5)
        page.screenshot(path=str(out / "electron_title.png"))
        page.get_by_text("처음부터").click()
        time.sleep(4)
        for _ in range(8):
            page.mouse.click(700, 300)
            time.sleep(0.6)
        time.sleep(1)
        ok = page.evaluate("() => window.__vn.game.saveTo('1')")
        print("saved slot 1:", ok)
        page.evaluate("() => window.vnHost.setWindowSize(1280, 720)")
        time.sleep(1.0)
        print("after resize inner:", page.evaluate("() => [innerWidth, innerHeight]"))
        page.evaluate("() => window.vnHost.setFullscreen(true)")
        time.sleep(1.5)
        print("fullscreen:", page.evaluate("() => window.vnHost.isFullscreen()"), page.evaluate("() => [innerWidth, innerHeight]"))
        page.screenshot(path=str(out / "electron_fullscreen.png"))
        page.evaluate("() => window.vnHost.setFullscreen(false)")
        time.sleep(1.0)
        print("fullscreen off:", page.evaluate("() => window.vnHost.isFullscreen()"))
    else:
        d = page.evaluate("() => { const s = window.__vn.game.store.load('1'); return s ? {chapter: s.chapter, text: s.text, pc: s.snap.pc} : null; }")
        print("slot 1 after restart:", json.dumps(d, ensure_ascii=False))
        page.mouse.click(700, 400)
        time.sleep(2.5)
        page.evaluate("async () => { await window.__vn.game.loadFrom('1'); }")
        time.sleep(3)
        page.screenshot(path=str(out / "electron_loaded.png"))
        st = page.evaluate("() => ({bg: window.__vn.game.stage.scene.bg, bgm: window.__vn.game.audio.bgmId, line: window.__vn.game.vm.pc, chars: window.__vn.game.stage.scene.chars.map(c => c.id)})")
        print("restored state:", json.dumps(st, ensure_ascii=False))
    b.close()
