"""Transcribe the isolated Demucs vocal stem of each track; confident words => real sung lyrics.
Usage: python stem_words.py <track_dir> [...]"""
import json
import sys
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[2]


def main():
    from faster_whisper import WhisperModel
    model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    for a in sys.argv[1:]:
        d = Path(a)
        import os
        stem = os.environ.get("STEM", "vocals")
        f = ROOT / "art_work" / "stems" / d.name / "htdemucs" / "source" / f"{stem}.wav"
        y, sr = sf.read(str(f), dtype="float32", always_2d=True)
        x = y.mean(axis=1)
        g = gcd(sr, 16000)
        x = resample_poly(x, 16000 // g, sr // g).astype(np.float32)
        segs, info = model.transcribe(x, beam_size=5, vad_filter=True, condition_on_previous_text=False,
                                      vad_parameters={"threshold": 0.5, "min_speech_duration_ms": 300})
        segs = list(segs)
        conf = [s for s in segs if s.avg_logprob > -0.7 and s.no_speech_prob < 0.6 and len(s.text.strip()) > 2]
        words_s = sum(s.end - s.start for s in conf)
        res = {"track": d.name, "lang": info.language, "lang_p": round(info.language_probability, 2),
               "segments": len(segs), "confident": len(conf), "confident_seconds": round(words_s, 1),
               "ranges": [[round(s.start, 1), round(s.end, 1)] for s in conf],
               "text": " / ".join(s.text.strip() for s in conf)[:240]}
        res["stem"] = stem
        (d / f"stem_words_{stem}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(res, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
