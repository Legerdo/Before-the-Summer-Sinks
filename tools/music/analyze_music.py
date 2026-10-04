"""Objective review of generated music (I can't listen, so measure and look).

For each source.wav:
  * format (sr/channels/duration), peak, clipping ratio, DC offset
  * integrated loudness / true peak / LRA via ffmpeg loudnorm
  * tempo estimate from onset autocorrelation
  * loudness envelope + log-mel spectrogram rendered to review.png (<= 1900 px wide)
  * glitch scan: frames whose spectral flux is an extreme outlier
  * leading/trailing silence, abrupt ending check
Writes analysis.json next to the source.

Usage: python analyze_music.py <track_dir> [<track_dir> ...]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw, ImageFont


def loudnorm(path: Path) -> dict:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af",
                        "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S)
    if not m:
        return {}
    j = json.loads(m.group(0))
    return {"lufs": float(j["input_i"]), "true_peak": float(j["input_tp"]), "lra": float(j["input_lra"])}


def stft_mag(x: np.ndarray, n_fft: int, hop: int) -> np.ndarray:
    if len(x) < n_fft:
        x = np.pad(x, (0, n_fft - len(x)))
    n = 1 + (len(x) - n_fft) // hop
    win = np.hanning(n_fft).astype(np.float32)
    out = np.empty((n, n_fft // 2 + 1), dtype=np.float32)
    for s in range(0, n, 512):
        e = min(n, s + 512)
        idx = np.arange(n_fft)[None, :] + hop * np.arange(s, e)[:, None]
        out[s:e] = np.abs(np.fft.rfft(x[idx] * win[None, :], axis=1))
    return out


def mel_fb(sr: int, n_fft: int, n_mels: int, fmin=30.0, fmax=None) -> np.ndarray:
    fmax = fmax or sr / 2
    hz2mel = lambda f: 2595 * np.log10(1 + f / 700)
    mel2hz = lambda m: 700 * (10 ** (m / 2595) - 1)
    mels = np.linspace(hz2mel(fmin), hz2mel(fmax), n_mels + 2)
    hz = mel2hz(mels)
    bins = np.fft.rfftfreq(n_fft, 1 / sr)
    fb = np.zeros((n_mels, len(bins)), dtype=np.float32)
    for i in range(n_mels):
        l, c, r = hz[i], hz[i + 1], hz[i + 2]
        fb[i] = np.clip(np.minimum((bins - l) / (c - l + 1e-9), (r - bins) / (r - c + 1e-9)), 0, None)
    return fb


def tempo(onset: np.ndarray, fps: float) -> tuple[float, float]:
    o = onset - onset.mean()
    ac = np.correlate(o, o, mode="full")[len(o) - 1:]
    ac /= ac[0] + 1e-9
    lags = np.arange(len(ac)) / fps
    bpm = 60 / np.maximum(lags, 1e-9)
    mask = (bpm >= 55) & (bpm <= 180)
    # weight toward ~100 bpm to reduce octave errors
    w = np.exp(-0.5 * (np.log2(bpm / 100) / 0.9) ** 2)
    score = np.where(mask, ac * w, -1)
    k = int(np.argmax(score))
    return float(bpm[k]), float(ac[k])


def colormap(v: np.ndarray) -> np.ndarray:
    v = np.clip(v, 0, 1)
    r = np.clip(1.6 * v - 0.2, 0, 1)
    g = np.clip(1.8 * v - 0.8, 0, 1)
    b = np.clip(np.sin(np.pi * v) * 0.9 + 0.15 * v, 0, 1)
    return (np.stack([r, g, b], -1) * 255).astype(np.uint8)


def analyze(dir_: Path) -> dict:
    src = dir_ / "source.wav"
    info = sf.info(str(src))
    y, sr = sf.read(str(src), dtype="float32", always_2d=True)
    mono = y.mean(axis=1)
    dur = len(mono) / sr
    peak = float(np.abs(y).max())
    clip = float(np.mean(np.abs(y) > 0.999))
    dc = float(mono.mean())
    side = (y[:, 0] - y[:, 1]) / 2 if y.shape[1] == 2 else np.zeros(1)
    width = float(np.sqrt(np.mean(side ** 2)) / (np.sqrt(np.mean(mono ** 2)) + 1e-9))
    res = {"file": str(src), "sr": sr, "channels": info.channels, "subtype": info.subtype, "dur": round(dur, 2),
           "peak": round(peak, 3), "clip_ratio": round(clip, 6), "dc": round(dc, 5), "stereo_width": round(width, 3)}
    res.update(loudnorm(src))

    # features at 22.05k-ish resolution
    step = max(1, sr // 22050)
    x = mono[::step]
    fs = sr / step
    n_fft, hop = 2048, 512
    S = stft_mag(x, n_fft, hop)
    fps = fs / hop
    fb = mel_fb(int(fs), n_fft, 96)
    M = np.log10(S @ fb.T + 1e-6)
    flux = np.maximum(0, np.diff(M, axis=0)).sum(axis=1)
    flux = np.concatenate([[0], flux])
    bpm, conf = tempo(flux, fps)
    res["bpm_est"] = round(bpm, 1)
    res["bpm_conf"] = round(conf, 3)
    rms = np.sqrt(np.mean(S ** 2, axis=1)) + 1e-9
    db = 20 * np.log10(rms / rms.max())
    act = np.where(db > -45)[0]
    res["lead_silence"] = round(float(act[0] / fps) if len(act) else dur, 2)
    res["trail_silence"] = round(float((len(db) - 1 - act[-1]) / fps) if len(act) else dur, 2)
    last2 = db[-int(2 * fps):]
    res["end_level_db"] = round(float(np.median(last2)), 1)
    res["abrupt_end"] = bool(np.median(last2) > -20)
    # glitch scan: flux outliers relative to local median
    med = np.median(flux)
    mad = np.median(np.abs(flux - med)) + 1e-9
    z = (flux - med) / mad
    spikes = np.where(z > 25)[0]
    res["flux_spikes"] = [round(float(t / fps), 2) for t in spikes[:20]]
    # section energy profile (per 5s)
    seg = int(5 * fps)
    prof = [round(float(np.mean(db[i:i + seg])), 1) for i in range(0, len(db), seg)]
    res["energy_5s"] = prof

    # render review image
    W, Hs, He = 1800, 300, 120
    img = Image.new("RGB", (W, Hs + He + 40), (18, 18, 22))
    Mn = (M - np.percentile(M, 5)) / (np.percentile(M, 99.5) - np.percentile(M, 5) + 1e-9)
    col = colormap(Mn[:, ::-1].T)  # mels x frames (flip for low at bottom)
    spec = Image.fromarray(col).resize((W, Hs), Image.BILINEAR)
    img.paste(spec, (0, 0))
    d = ImageDraw.Draw(img)
    # envelope
    env = np.interp(np.linspace(0, len(db) - 1, W), np.arange(len(db)), db)
    pts = [(i, Hs + 10 + int((-min(0, max(-60, v)) / 60) * He)) for i, v in enumerate(env)]
    d.line(pts, fill=(120, 220, 160), width=1)
    try:
        font = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    for t in range(0, int(dur) + 1, 10):
        xpx = int(t / dur * (W - 1))
        d.line([(xpx, Hs), (xpx, Hs + 8)], fill=(200, 200, 200))
        d.text((xpx + 2, Hs + He + 14), f"{t}s", fill=(200, 200, 200), font=font)
    for t in res["flux_spikes"]:
        xpx = int(t / dur * (W - 1))
        d.line([(xpx, 0), (xpx, Hs)], fill=(255, 60, 60))
    d.text((6, 4), f"{dir_.name}  {dur:.1f}s  {res.get('lufs', 0):.1f} LUFS  ~{bpm:.0f} bpm", fill=(255, 255, 255), font=font)
    img.save(dir_ / "review.png")
    (dir_ / "analysis.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


if __name__ == "__main__":
    for a in sys.argv[1:]:
        r = analyze(Path(a))
        short = {k: v for k, v in r.items() if k not in ("energy_5s", "file")}
        print(json.dumps(short, ensure_ascii=False))
