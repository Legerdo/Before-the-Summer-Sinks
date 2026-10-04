"""Distribution of lip-sync envelope levels across all voice lines (to tune mouth thresholds)."""
import base64
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
lips = json.loads((ROOT / "public" / "data" / "lipsync.json").read_text(encoding="utf-8"))
allv = np.concatenate([np.frombuffer(base64.b64decode(v), dtype=np.uint8) / 255 for k, v in lips.items() if k.startswith("ys")])
print("frames", len(allv))
for q in (10, 20, 30, 40, 50, 60, 70, 80, 90):
    print(f"p{q}: {np.percentile(allv, q):.3f}")
for th in (0.13, 0.19, 0.25, 0.3, 0.35, 0.4, 0.46, 0.56, 0.62, 0.7):
    print(f"> {th}: {np.mean(allv > th):.2f}")
# syllable-like dips: fraction of frames that are local minima with depth > 0.15
d = np.diff(allv)
mins = np.where((d[:-1] < 0) & (d[1:] > 0))[0] + 1
print("local minima per second:", round(len(mins) / (len(allv) / 50), 2))
