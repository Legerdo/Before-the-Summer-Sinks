"""Measure lip-sync against the real playing voice in Chrome (frame-by-frame DOM sampling).

For each voice id: plays it on the on-stage sprite, samples mouth/eye layers every animation frame
together with the audio clock, and compares with the analysed envelope.
Usage: python lipsync_probe.py ys0030 ys0045 ...
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
url = "http://localhost:47813/?test=1"
ids = sys.argv[1:] or ["ys0030", "ys0045", "ys0060", "ys0100", "ys0150"]
out = ROOT / "art_work" / "qa"
out.mkdir(parents=True, exist_ok=True)


def analyse(vid, r):
    s = r["samples"]
    env = np.array(r["env"], dtype=float) / 255
    dur = r["dur"]
    t = np.array([x["t"] for x in s])
    m = np.array([x["mouth"] for x in s])
    inside = (t >= 0.02) & (t < dur - 0.02)
    idx = np.clip((t[inside] * 50).astype(int), 0, len(env) - 1)
    exp_open = env[idx] > 0.26
    act_open = m[inside] > 0
    agree = float((exp_open == act_open).mean()) if inside.any() else 0
    after = t > dur + 0.06
    stuck_open = int((m[after] > 0).sum())
    before = t < -0.01
    early_open = int((m[before] > 0).sum())
    # lag estimate: shift expected curve and find best agreement
    best = (0, agree)
    for lag_ms in range(-120, 121, 20):
        idx2 = np.clip(((t[inside] - lag_ms / 1000) * 50).astype(int), 0, len(env) - 1)
        a2 = float(((env[idx2] > 0.26) == act_open).mean())
        if a2 > best[1] + 1e-9:
            best = (lag_ms, a2)
    # silent gaps: runs of env < 0.08 longer than 160 ms must show a closed mouth in the middle
    gaps, closed_ok = 0, 0
    low = env < 0.08
    i = 0
    while i < len(low):
        if low[i]:
            j = i
            while j < len(low) and low[j]:
                j += 1
            if (j - i) * 20 >= 160 and i > 0 and j < len(low):
                gaps += 1
                mid = (i + j) / 2 / 50
                near = np.abs(t - mid) < 0.03
                if near.any() and (m[near] == 0).all():
                    closed_ok += 1
            i = j
        else:
            i += 1
    changes = int((np.diff(m) != 0).sum())
    blinks = int(((np.diff(np.array([x["eyes"] for x in s])) == 1)).sum())
    frames = len(s)
    fps = frames / max(0.001, s[-1]["wall"] / 1000)
    return {"id": vid, "dur": round(dur, 2), "frames": frames, "fps": round(fps, 1), "agree": round(agree, 3),
            "best_lag_ms": best[0], "agree_at_best": round(best[1], 3), "open_after_end": stuck_open,
            "open_before_start": early_open, "silent_gaps": gaps, "gaps_closed": closed_ok,
            "mouth_changes": changes, "blinks": blinks, "open_ratio": round(float(act_open.mean()) if inside.any() else 0, 2)}


def main():
    rows = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True, args=["--autoplay-policy=no-user-gesture-required"])
        page = b.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(url, wait_until="networkidle")
        page.wait_for_function("() => !!window.__vn", timeout=30000)
        for vid in ids:
            r = page.evaluate("async (v) => await window.__vn.lipsyncProbe(v, 'yunseul', 'smile')", vid)
            if "error" in r:
                print(vid, r)
                continue
            a = analyse(vid, r)
            rows.append(a)
            print(json.dumps(a, ensure_ascii=False), flush=True)
        # visual: capture open / closed mouth frames on one line
        page.evaluate("() => { window.__shots = []; }")
        page.evaluate("async () => { const p = window.__vn.lipsyncProbe('ys0030', 'yunseul', 'smile'); window.__probe = p; }")
        for k, dt in enumerate([0.35, 0.5, 0.2, 0.25]):
            time.sleep(dt)
            page.screenshot(path=str(out / f"lip_{k}.png"), clip={"x": 760, "y": 120, "width": 400, "height": 400})
        page.evaluate("async () => await window.__probe")
        b.close()
    (out / "lipsync_report.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
