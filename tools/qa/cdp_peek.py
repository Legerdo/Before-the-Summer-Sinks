"""Screenshot + state dump of the Electron page over CDP (port 9333)."""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
name = sys.argv[1] if len(sys.argv) > 1 else "peek"
with sync_playwright() as p:
    port = sys.argv[2] if len(sys.argv) > 2 else "9334"
    b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    page = [pg for c in b.contexts for pg in c.pages if pg.url.startswith("app://")][0]
    page.screenshot(path=str(ROOT / "art_work" / "qa" / f"{name}.png"))
    st = page.evaluate("""() => { const g = window.__vn.game; return {mode: g.mode, menuOpen: g.menuOpen, pc: g.vm.pc,
      running: g.vm.running, label: g.vm.label(g.vm.pc), bg: g.stage.scene.bg, errors: g.errors.slice(-5),
      title: !!document.querySelector('.title-screen'), splash: !!document.querySelector('.splash')}; }""")
    print(json.dumps(st, ensure_ascii=False))
    b.close()
