"""Transcribe a vocal track in Korean and compare with the intended lyrics (character error rate).
Usage: python lyrics_check.py <track_dir>"""
import json
import re
import sys
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "voice"))
from analyze import cer  # noqa: E402

d = Path(sys.argv[1])
song = json.loads((d / "song.json").read_text(encoding="utf-8"))
lyr = "\n".join(l for l in song["lyrics"].splitlines() if l.strip() and not re.match(r"^\[.*\]$", l.strip()))
y, sr = sf.read(str(d / "source.wav"), dtype="float32", always_2d=True)
x = y.mean(axis=1)
g = gcd(sr, 16000)
x = resample_poly(x, 16000 // g, sr // g).astype(np.float32)
from faster_whisper import WhisperModel  # noqa: E402

m = WhisperModel("large-v3", device="cuda", compute_type="float16")
segs, info = m.transcribe(x, language="ko", beam_size=5, vad_filter=True, condition_on_previous_text=False)
segs = list(segs)
hyp = " ".join(s.text.strip() for s in segs)
for s in segs:
    print(f"{s.start:6.1f}-{s.end:6.1f}  {s.text.strip()}")
print("CER vs lyrics:", round(cer(lyr, hyp), 3))
(d / "lyrics_check.json").write_text(json.dumps({"hyp": hyp, "cer": cer(lyr, hyp),
                                                 "segments": [[s.start, s.end, s.text] for s in segs]},
                                                ensure_ascii=False, indent=1), encoding="utf-8")
