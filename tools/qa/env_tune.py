"""Try lip-sync envelope variants on accepted takes and report the resulting mouth-state mix."""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "voice"))
from make_voices import trim_and_level  # noqa: E402

st = json.loads((ROOT / "voice" / "state.json").read_text(encoding="utf-8"))
ids = [k for k in st if k.startswith("ys")][::5][:60]


def env_v2(y, sr, rate=50, span=20.0, att=0.7, rel=0.45):
    hop = sr // rate
    def band(lo, hi):
        b = sosfiltfilt(butter(4, [lo, hi], btype="band", fs=sr, output="sos"), y)
        n = int(np.ceil(len(b) / hop))
        pad = np.pad(b, (0, n * hop - len(b)))
        return np.sqrt((pad.reshape(n, hop) ** 2).mean(axis=1)) + 1e-9
    full = band(180, 3800)
    f1 = band(450, 1150)
    db = 20 * np.log10(full)
    ref = np.percentile(db, 97)
    loud = np.clip((db - (ref - span)) / span, 0, 1)
    ratio = f1 / full
    voiced = loud > 0.2
    if voiced.any():
        lo, hi = np.percentile(ratio[voiced], 15), np.percentile(ratio[voiced], 90)
        openness = np.clip((ratio - lo) / (hi - lo + 1e-9), 0, 1)
    else:
        openness = np.zeros_like(ratio)
    raw = loud * (0.5 + 0.5 * openness)
    out = np.zeros_like(raw)
    v = 0.0
    for i, x in enumerate(raw):
        v = v + (x - v) * (att if x > v else rel)
        out[i] = v
    out[-2:] = 0
    return out


for span in (16.0, 20.0, 24.0):
    allv = []
    for vid in ids:
        y, sr = sf.read(str(ROOT / st[vid]["file"]), dtype="float32", always_2d=True)
        y = trim_and_level(y.mean(axis=1), sr)
        allv.append(env_v2(y, sr, span=span))
    a = np.concatenate(allv)
    closed = np.mean(a <= 0.25)
    m1 = np.mean((a > 0.25) & (a <= 0.55))
    m2 = np.mean(a > 0.55)
    d = np.diff(a)
    mins = np.where((d[:-1] < 0) & (d[1:] > 0) & (a[1:-1] < 0.45))[0]
    print(f"span={span}: closed {closed:.2f}  m1 {m1:.2f}  m2 {m2:.2f}  dips<0.45 per s {len(mins) / (len(a) / 50):.2f}")
