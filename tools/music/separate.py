"""Run Demucs (isolated venv) on generated tracks and measure the vocal stem over time.

For each track dir: art_work/stems/<dir>/htdemucs/source/{vocals,no_vocals}.wav
Reports seconds where the vocal stem is within 18 dB of the full mix (= audible vocals),
and the contiguous vocal regions. Writes <dir>/vocals.json.
Usage: python separate.py <track_dir> [...]
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
VENV_PY = ROOT / ".venv-audio" / "Scripts" / "python.exe"


def rms_db(x: np.ndarray, sr: int, win: float = 1.0) -> np.ndarray:
    n = int(sr * win)
    k = len(x) // n
    x = x[: k * n].reshape(k, n, -1)
    return 20 * np.log10(np.sqrt((x ** 2).mean(axis=(1, 2))) + 1e-9)


def regions(mask: np.ndarray, min_len: int = 2, gap: int = 2):
    out = []
    i = 0
    while i < len(mask):
        if mask[i]:
            j = i
            while j < len(mask) and (mask[j] or (j + gap < len(mask) and mask[j:j + gap + 1].any())):
                j += 1
            if j - i >= min_len:
                out.append((i, j))
            i = j
        else:
            i += 1
    return out


for a in sys.argv[1:]:
    d = Path(a).resolve()
    out_root = ROOT / "art_work" / "stems" / d.name
    stem_dir = out_root / "htdemucs" / "source"
    if not (stem_dir / "no_vocals.wav").exists():
        subprocess.run([str(VENV_PY), "-m", "demucs", "--two-stems", "vocals", "-n", "htdemucs",
                        "-o", str(out_root), str(d / "source.wav")], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    voc, sr = sf.read(str(stem_dir / "vocals.wav"), dtype="float32", always_2d=True)
    acc, _ = sf.read(str(stem_dir / "no_vocals.wav"), dtype="float32", always_2d=True)
    mix = voc + acc
    v = rms_db(voc, sr)
    m = rms_db(mix, sr)
    rel = v - m
    audible = (rel > -18) & (v > -45)
    regs = regions(audible)
    res = {"track": d.name, "sr": sr, "vocal_seconds": int(audible.sum()), "dur": round(len(mix) / sr, 1),
           "regions": regs, "max_rel_db": round(float(rel.max()), 1),
           "no_vocals": str(stem_dir / "no_vocals.wav")}
    (d / "vocals.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res), flush=True)
