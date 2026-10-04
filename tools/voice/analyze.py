"""Analyze voice clips: duration, silence, loudness, pitch stats and ASR character error rate.

Usage:
  python analyze.py --files a.wav b.wav --text-file expected.txt [--json out.json]
  python analyze.py --manifest manifest.json [--only-missing] [--json out.json]

Manifest format: [{"id":..., "file":..., "text":...}, ...]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

CUE_RE = re.compile(r"\[[^\]]*\]")
KEEP_RE = re.compile(r"[^0-9A-Za-z\uac00-\ud7a3]")


def norm_text(s: str) -> str:
    s = CUE_RE.sub("", s)
    return KEEP_RE.sub("", s).lower()


def cer(ref: str, hyp: str) -> float:
    r, h = norm_text(ref), norm_text(hyp)
    if not r:
        return 0.0 if not h else 1.0
    prev = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        cur = [i] + [0] * len(h)
        for j, hc in enumerate(h, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc))
        prev = cur
    return prev[-1] / len(r)


def load_mono(path: Path, sr_target: int = 16000):
    from math import gcd

    from scipy.signal import resample_poly
    y, sr = sf.read(str(path), always_2d=False)
    if y.ndim > 1:
        y = y.mean(axis=1)
    y = y.astype(np.float32)
    if sr != sr_target:
        g = gcd(sr, sr_target)
        y16 = resample_poly(y, sr_target // g, sr // g).astype(np.float32)
    else:
        y16 = y
    return y, sr, y16


def frame_rms(y: np.ndarray, frame: int, hop: int) -> np.ndarray:
    if len(y) < frame:
        y = np.pad(y, (0, frame - len(y)))
    n = 1 + (len(y) - frame) // hop
    idx = np.arange(frame)[None, :] + hop * np.arange(n)[:, None]
    return np.sqrt(np.mean(y[idx] ** 2, axis=1))


def yin_f0(y: np.ndarray, sr: int, fmin: float = 70, fmax: float = 700, hop_s: float = 0.01,
           thresh: float = 0.15) -> np.ndarray:
    """Simple YIN pitch tracker. Returns f0 per frame with NaN for unvoiced frames."""
    w = int(sr / fmin) * 2
    hop = int(sr * hop_s)
    tau_min, tau_max = int(sr / fmax), int(sr / fmin)
    if len(y) < w + tau_max:
        return np.array([])
    n = 1 + (len(y) - w - tau_max) // hop
    out = np.full(n, np.nan)
    global LAST_APER
    LAST_APER = np.full(n, np.nan)
    rms_all = frame_rms(y, w, hop)
    gate = rms_all.max() * 0.03 if len(rms_all) else 0
    for i in range(n):
        s = i * hop
        x = y[s:s + w + tau_max].astype(np.float64)
        if np.sqrt(np.mean(x[:w] ** 2)) < gate:
            continue
        # difference function via FFT
        fx = np.fft.rfft(x, 2 * len(x))
        ac = np.fft.irfft(fx * np.conj(np.fft.rfft(x[:w], 2 * len(x))))[:tau_max + 1]
        e = np.cumsum(x ** 2)
        e0 = e[w - 1]
        et = e[w - 1:w + tau_max] - np.concatenate(([0.0], e[:tau_max]))
        d = e0 + et - 2 * ac
        d[0] = 0
        cmnd = np.ones_like(d)
        cs = np.cumsum(d[1:])
        cmnd[1:] = d[1:] * np.arange(1, len(d)) / np.maximum(cs, 1e-12)
        cand = np.where(cmnd[tau_min:tau_max] < thresh)[0]
        if len(cand) == 0:
            continue
        t = cand[0] + tau_min
        while t + 1 < tau_max and cmnd[t + 1] < cmnd[t]:
            t += 1
        if 1 <= t < tau_max:
            a, b, c = cmnd[t - 1], cmnd[t], cmnd[t + 1]
            den = a - 2 * b + c
            shift = 0.5 * (a - c) / den if abs(den) > 1e-12 else 0
            out[i] = sr / (t + shift)
            LAST_APER[i] = b
    return out


LAST_APER = np.array([])


def spectral_centroid(y: np.ndarray, sr: int) -> float:
    frame, hop = 1024, 256
    if len(y) < frame:
        return 0.0
    n = 1 + (len(y) - frame) // hop
    idx = np.arange(frame)[None, :] + hop * np.arange(n)[:, None]
    fr = y[idx] * np.hanning(frame)[None, :]
    mag = np.abs(np.fft.rfft(fr, axis=1))
    freqs = np.fft.rfftfreq(frame, 1 / sr)
    e = mag.sum(axis=1)
    keep = e > e.max() * 0.05
    cent = (mag[keep] * freqs[None, :]).sum(axis=1) / np.maximum(e[keep], 1e-9)
    return float(np.median(cent)) if len(cent) else 0.0


def acoustic(y: np.ndarray, sr: int) -> dict:
    dur = len(y) / sr
    frame = int(sr * 0.02)
    hop = int(sr * 0.01)
    rms = frame_rms(y, frame, hop)
    db = 20 * np.log10(rms + 1e-9)
    thr = db.max() - 40
    voiced_idx = np.where(db > thr)[0]
    lead = voiced_idx[0] * hop / sr if len(voiced_idx) else dur
    trail = (len(db) - 1 - voiced_idx[-1]) * hop / sr if len(voiced_idx) else dur
    # longest internal silence
    active = db > thr
    longest = 0
    run = 0
    started = False
    for a in active:
        if a:
            started = True
            longest = max(longest, run)
            run = 0
        elif started:
            run += 1
    from math import gcd

    from scipy.signal import resample_poly
    g = gcd(sr, 16000)
    y16 = resample_poly(y, 16000 // g, sr // g) if sr != 16000 else y
    f0 = yin_f0(y16, 16000)
    f0v = f0[~np.isnan(f0)] if len(f0) else np.array([])
    if len(f0v) > 10:
        med = float(np.median(f0v))
        semis = 12 * np.log2(f0v / med)
        iqr = float(np.percentile(semis, 75) - np.percentile(semis, 25))
        p10, p90 = float(np.percentile(f0v, 10)), float(np.percentile(f0v, 90))
    else:
        med, iqr, p10, p90 = 0.0, 0.0, 0.0, 0.0
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    end_rms_db = float(db[-5:].mean()) if len(db) > 5 else -120.0
    aper = LAST_APER[~np.isnan(LAST_APER)] if len(LAST_APER) else np.array([])
    return {"dur": round(dur, 2), "lead_sil": round(lead, 2), "trail_sil": round(trail, 2),
            "max_gap": round(longest * hop / sr, 2), "peak": round(peak, 3),
            "f0_med": round(med, 1), "f0_p10": round(p10, 1), "f0_p90": round(p90, 1),
            "f0_iqr_st": round(iqr, 2), "end_db": round(end_rms_db, 1),
            "aper": round(float(np.median(aper)), 3) if len(aper) else None,
            "centroid": round(spectral_centroid(y16, 16000), 0),
            "voiced_ratio": round(float(np.mean(~np.isnan(f0))) if len(f0) else 0.0, 2)}


_model = None


def asr(y16: np.ndarray) -> str:
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel("large-v3", device="cuda", compute_type="float16")
    segs, _info = _model.transcribe(y16, language="ko", beam_size=5, vad_filter=False,
                                    condition_on_previous_text=False)
    return "".join(s.text for s in segs).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--text-file")
    ap.add_argument("--manifest")
    ap.add_argument("--json")
    ap.add_argument("--no-asr", action="store_true")
    ap.add_argument("--no-pitch", action="store_true")
    args = ap.parse_args()

    items = []
    if args.manifest:
        items = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    else:
        text = Path(args.text_file).read_text(encoding="utf-8").strip() if args.text_file else ""
        items = [{"id": Path(f).stem, "file": f, "text": text} for f in args.files]

    results = []
    for it in items:
        p = Path(it["file"])
        if not p.exists():
            results.append({"id": it["id"], "error": "missing"})
            continue
        y, sr, y16 = load_mono(p)
        row = {"id": it["id"], "file": str(p)}
        if not args.no_pitch:
            row.update(acoustic(y, sr))
        else:
            row["dur"] = round(len(y) / sr, 2)
        if not args.no_asr:
            hyp = asr(y16)
            row["asr"] = hyp
            row["cer"] = round(cer(it.get("text", ""), hyp), 3)
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    if args.json:
        Path(args.json).write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
