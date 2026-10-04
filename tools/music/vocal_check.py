"""Rough vocal-presence check for generated BGM (instrumental tracks should have none).

Uses the Silero VAD bundled with faster-whisper on a centre-channel-emphasised mono mix,
then transcribes the flagged regions with whisper to see whether they carry words.
Usage: python vocal_check.py <track_dir> [...]
"""
import json
import sys
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def to16k(path: Path) -> np.ndarray:
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    mid = y.mean(axis=1)
    g = gcd(sr, 16000)
    return resample_poly(mid, 16000 // g, sr // g).astype(np.float32)


def main():
    from faster_whisper import WhisperModel
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    for a in sys.argv[1:]:
        d = Path(a)
        x = to16k(d / "source.wav")
        ts = get_speech_timestamps(x, VadOptions(threshold=0.6, min_speech_duration_ms=400))
        speech = sum(t["end"] - t["start"] for t in ts) / 16000
        dur = len(x) / 16000
        segs, info = model.transcribe(x, beam_size=5, vad_filter=True,
                                      vad_parameters={"threshold": 0.6, "min_speech_duration_ms": 400},
                                      condition_on_previous_text=False)
        segs = list(segs)
        words = [(round(s.start, 1), round(s.end, 1), s.text.strip(), round(s.avg_logprob, 2), round(s.no_speech_prob, 2))
                 for s in segs]
        confident = [w for w in words if w[3] > -0.6 and w[4] < 0.5 and len(w[2]) > 3]
        res = {"track": d.name, "dur": round(dur, 1), "vad_speech_s": round(speech, 1),
               "vad_ratio": round(speech / dur, 3), "lang": info.language, "lang_p": round(info.language_probability, 2),
               "n_segments": len(words), "confident_segments": len(confident), "sample": words[:6]}
        (d / "vocal_check.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(res, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
