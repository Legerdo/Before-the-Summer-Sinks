"""Visual tour: fast-forward to key moments of the story and capture real renders.

Each stop = (name, "file.vn:line", choices, shots, gap_seconds). Screens are saved as 1280x720 JPEGs and
combined into contact sheets (<= 1900 px) for review.
Usage: python tour.py [stop-name ...]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "art_work" / "qa" / "tour"
URL = "http://localhost:47813/?qa=1"
WARM = [0, 0, 0, 0, 0, 0]

COLD = [1, 1, 1, 1, 1, 2]
# (name, file, marker text on a line, choices, shots, gap) -> seek to the first dialogue line after the marker
STOPS_SPEC = [
    ("p_coldopen", "00_prologue.vn", "@voicefx radio", WARM, 1, 0),
    ("c1_store", "01_ch1.vn", "@show bongsun default neutral", WARM, 2, 2.2),
    ("c1_radio", "01_ch1.vn", "@se radio_tune", WARM, 1, 0),
    ("c1_meet", "01_ch1.vn", "@cg cg_meet", WARM, 2, 2.0),
    ("c1_stream", "01_ch1.vn", "@show yunseul uniform_b pout", WARM, 2, 2.0),
    ("c1_broadcast", "01_ch1.vn", "@cg cg_broadcast", WARM, 1, 0),
    ("c1_accident", "01_ch1.vn", "@show yunseul casual_b angry", WARM, 2, 1.8),
    ("c1_choice", "01_ch1.vn", "너, 내일부터 내 조수야", WARM, 2, 3.0),
    ("c2_map", "02_ch2.vn", "@show yunseul uniform_c gentle", WARM, 2, 2.0),
    ("c2_echo", "02_ch2.vn", "@cg cg_echo", WARM, 1, 0),
    ("c2_choice", "02_ch2.vn", "편집으로 더 부끄럽게", WARM, 2, 3.0),
    ("c2_path", "02_ch2.vn", "@fx fireflies 0.25", WARM, 1, 0),
    ("c3_repair", "03_ch3.vn", "@cg cg_tape_repair", WARM, 1, 0),
    ("c3_mothertape", "03_ch3.vn", "이건 뭐지. 이름이 없네", WARM, 2, 3.5),
    ("c3_stream", "03_ch3.vn", "@show yunseul uniform_c sad", WARM, 2, 2.0),
    ("c3_bongsun", "03_ch3.vn", "@cg cg_bongsun_radio", WARM, 2, 3.0),
    ("c3_farewell", "03_ch3.vn", "@show bongsun default surprised at=left", WARM, 2, 2.5),
    ("c4_radios", "04_ch4.vn", "@show yunseul uniform_b smile", WARM, 1, 0),
    ("c4_phone", "04_ch4.vn", "@voicefx phone", WARM, 1, 0),
    ("c4_fireflies", "04_ch4.vn", "@cg cg_fireflies", WARM, 2, 2.0),
    ("c4_choice", "04_ch4.vn", "아빠는 무슨 일 하셔", WARM, 2, 3.0),
    ("c4_hall", "04_ch4.vn", "@show father default serious", WARM, 2, 2.0),
    ("c4_betray", "04_ch4.vn", "*c4_betray", [0, 0, 0, 1, 0, 0], 2, 2.0),
    ("c5_demolish", "05_ch5.vn", "@shake amp=6", WARM, 1, 0),
    ("c5_album", "05_ch5.vn", "@cg cg_father_album", WARM, 1, 0),
    ("c5_father_sad", "05_ch5.vn", "@show father casual sad", WARM, 1, 0),
    ("c5_father", "05_ch5.vn", "@show father casual smile", WARM, 1, 0),
    ("c5_echo", "05_ch5.vn", "@show yunseul uniform_c sad", WARM, 1, 0),
    ("c6_storm", "06_ch6.vn", "@se power_down", WARM, 1, 0),
    ("c6_bcroom", "06_ch6.vn", "@show yunseul casual_b surprised", WARM, 2, 2.0),
    ("c6_father", "06_ch6.vn", "@show father default serious", WARM, 1, 0),
    ("c6_roof", "06_ch6.vn", "@cg cg_storm", WARM, 2, 2.5),
    ("c6_evac", "06_ch6.vn", "@show yunseul casual_c cry", WARM, 1, 0),
    ("c6_dawn", "06_ch6.vn", "@cg cg_dawn", WARM, 1, 0),
    ("c7_ceremony", "07_ch7.vn", "@show yunseul uniform_a laugh at=right", WARM, 2, 2.0),
    ("c7_broadcast", "07_ch7.vn", "@cg cg_last_broadcast", WARM, 1, 0),
    ("c7_mother", "07_ch7.vn", "@cg cg_mother_tape", WARM, 1, 0),
    ("c7_cry", "07_ch7.vn", "@show yunseul uniform_c cry", WARM, 1, 0),
    ("c7_choice", "07_ch7.vn", "녹음기의 빨간 불이 켜졌다", WARM, 2, 3.0),
    ("e_true_bus", "08_end.vn", "@show yunseul uniform_a gentle", WARM, 1, 0),
    ("e_true_lake", "08_end.vn", "@fx glitter 0.8", WARM, 1, 0),
    ("e_true_cg", "08_end.vn", "@cg cg_true_end", WARM, 1, 0),
    ("e_normal_city", "08_end.vn", "@bg city_night", COLD, 1, 0),
    ("e_normal_cg", "08_end.vn", "@cg cg_normal_end", COLD, 1, 0),
]


def resolve_stops():
    stops = []
    for name, f, marker, ch, n, gap in STOPS_SPEC:
        lines = (ROOT / "story" / f).read_text(encoding="utf-8").splitlines()
        idx = next((i for i, l in enumerate(lines) if marker in l), None)
        if idx is None:
            print("marker not found:", name, marker)
            continue
        stops.append((name, f"{f}:{idx + 1}", ch, n, gap))
    return stops


STOPS = resolve_stops()


def main():
    only = set(sys.argv[1:])
    OUT.mkdir(parents=True, exist_ok=True)
    shots = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True, args=["--autoplay-policy=no-user-gesture-required", "--mute-audio"])
        page = b.new_page(viewport={"width": 1920, "height": 1080})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        for name, loc, choices, n, gap in STOPS:
            if only and name not in only:
                continue
            page.goto(URL, wait_until="networkidle")
            page.wait_for_function("() => !!window.__vn", timeout=30000)
            page.evaluate("() => { window.__seekDone = false; addEventListener('vn-seek-done', () => window.__seekDone = true); }")
            page.evaluate("(a) => window.__vn.seek({loc: a[0], choices: a[1]})", [loc, choices])
            page.wait_for_function("() => window.__seekDone === true", timeout=120000)
            time.sleep(2.6)
            for k in range(n):
                path = OUT / f"{name}_{k}.png"
                page.screenshot(path=str(path))
                im = Image.open(path).convert("RGB").resize((1280, 720), Image.LANCZOS)
                im.save(OUT / f"{name}_{k}.jpg", quality=86)
                path.unlink()
                shots.append(OUT / f"{name}_{k}.jpg")
                if k + 1 < n:
                    page.mouse.click(960, 400)
                    time.sleep(gap)
            errs = page.evaluate("() => window.__vn.errors.slice()")
            print(name, "ok" if not errs else errs[:3], flush=True)
        b.close()
    if errors:
        print("page errors:", errors[:5])
    # contact sheets of 6
    for i in range(0, len(shots), 6):
        grp = shots[i:i + 6]
        cells = [Image.open(s) for s in grp]
        W, H = 633, 356
        sheet = Image.new("RGB", (3 * W + 8, ((len(cells) + 2) // 3) * (H + 4) + 4), (30, 30, 34))
        for k, c in enumerate(cells):
            r, q = divmod(k, 3)
            sheet.paste(c.resize((W, H), Image.LANCZOS), (2 + q * (W + 2), 2 + r * (H + 4)))
        sheet.save(OUT / f"sheet_{i // 6:02d}.jpg", quality=88)
        print("sheet", OUT / f"sheet_{i // 6:02d}.jpg", [s.stem for s in grp])


if __name__ == "__main__":
    main()
