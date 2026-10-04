"""Turn selected generated tracks into game-ready BGM: trim, loudness-normalise, find a seamless
loop (feature self-similarity + waveform alignment), bake a short crossfade into the loop end,
encode Ogg Vorbis and write public/data/bgm.json with sample-accurate loop points.

Selection lives in tools/music/bgm_select.json (the BGM registry; ids are what the story uses in @bgm):
  {"<id>": {"dir": "<track dir>", "stem": "no_vocals"|"source",   # generated track (session dir)
            "file": "audio_src/bgm/<id>.wav",                      # OR any wav/flac/ogg (replacement)
            "loop": true, "mode": "full",                          # full = the whole piece loops
            "loopStart": 12.5, "loopEnd": 98.0,                    # optional manual loop points (s)
            "title": "...", "min_body": 60, "lufs": -18}}
Usage: python make_loops.py [id ...]
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SESSION = ROOT / "music-20260930-200500"
OUT_DIR = ROOT / "public" / "audio" / "bgm"
META = ROOT / "public" / "data" / "bgm.json"
REVIEW = ROOT / "art_work" / "loops"
sys.path.insert(0, str(Path(__file__).parent))
from analyze_music import colormap, mel_fb, stft_mag  # noqa: E402


def lufs_of(path: Path) -> float:
    from analyze_music import loudnorm
    return loudnorm(path).get("lufs", -18.0)


def features(y: np.ndarray, sr: int, hop_s: float = 0.1) -> tuple[np.ndarray, float]:
    """Log-mel + chroma-ish features at hop_s resolution, z-normalised per dim."""
    x = y.mean(axis=1)
    n_fft = 4096
    hop = int(sr * hop_s)
    S = stft_mag(x, n_fft, hop)
    fb = mel_fb(sr, n_fft, 48, 40, 8000)
    M = np.log10(S @ fb.T + 1e-5)
    freqs = np.fft.rfftfreq(n_fft, 1 / sr)
    valid = (freqs > 60) & (freqs < 4000)
    pc = np.round(12 * np.log2(freqs[valid] / 440.0)) % 12
    C = np.zeros((S.shape[0], 12), np.float32)
    for k in range(12):
        C[:, k] = S[:, valid][:, pc == k].sum(axis=1)
    C = C / (C.sum(axis=1, keepdims=True) + 1e-9)
    F = np.concatenate([M, 3 * C], axis=1)
    F = (F - F.mean(axis=0)) / (F.std(axis=0) + 1e-6)
    return F.astype(np.float32), hop / sr


def find_loop(y: np.ndarray, sr: int, min_body: float, tail_guard: float):
    F, dt = features(y, sr)
    n = len(F)
    w = int(3.0 / dt)  # +-3 s context
    dur = len(y) / sr
    # energy to locate the fade-out
    rms = np.sqrt((y.mean(axis=1)[: n * int(sr * dt)].reshape(n, -1) ** 2).mean(axis=1)) + 1e-9
    db = 20 * np.log10(rms / np.median(rms))
    last_loud = n - 1
    while last_loud > 0 and db[last_loud] < -10:
        last_loud -= 1
    e_max = min(last_loud - w, n - int(tail_guard / dt) - w)
    s_min = int(4.0 / dt) + w
    best = (-1e9, None, None)
    # window vectors: concatenated context (subsampled) for cosine similarity
    def ctx(i):
        seg = F[i - w:i + w:2]
        v = seg.reshape(-1)
        return v / (np.linalg.norm(v) + 1e-9)
    ends = range(max(s_min + int(min_body / dt), int(0.45 * n)), e_max, 2)
    starts_all = list(range(s_min, n, 2))
    cache = {}
    for e in ends:
        ve = cache.setdefault(e, ctx(e))
        for s in starts_all:
            if e - s < int(min_body / dt):
                break
            vs = cache.setdefault(s, ctx(s))
            sim = float(ve @ vs)
            # prefer longer bodies and later ends slightly
            score = sim + 0.02 * ((e - s) * dt / dur) + 0.01 * (e / n)
            if score > best[0]:
                best = (score, s, e, sim)
    _, s, e, sim = best
    s_smp, e_smp = int(s * dt * sr), int(e * dt * sr)
    # refine: align e to s using onset-envelope then waveform cross-correlation (+-250 ms, then +-10 ms)
    x = y.mean(axis=1)

    def xcorr_shift(a_center, b_center, radius, win):
        a = x[a_center - win:a_center + win]
        best_k, best_v = 0, -1e9
        for k in range(-radius, radius + 1, max(1, radius // 250)):
            b = x[b_center + k - win:b_center + k + win]
            if len(b) != len(a):
                continue
            v = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
            if v > best_v:
                best_v, best_k = v, k
        return best_k, best_v

    k1, v1 = xcorr_shift(s_smp, e_smp, int(0.25 * sr), int(0.5 * sr))
    e_smp += k1
    k2, v2 = xcorr_shift(s_smp, e_smp, int(0.01 * sr), int(0.05 * sr))
    e_smp += k2
    return s_smp, e_smp, sim, v2


def bake(y: np.ndarray, s: int, e: int, sr: int, xf: float = 0.5) -> np.ndarray:
    """Replace [e-X, e) with an equal-power blend of itself and [s-X, s) so that e continues into s."""
    X = int(xf * sr)
    X = min(X, s)
    out = y[:e].copy()
    t = np.linspace(0, 1, X, dtype=np.float32)[:, None]
    fade_out = np.cos(t * np.pi / 2)
    fade_in = np.sin(t * np.pi / 2)
    out[e - X:e] = y[e - X:e] * fade_out + y[s - X:s] * fade_in
    return out


def seam_image(y: np.ndarray, s: int, e: int, sr: int, path: Path, title: str):
    """Spectrogram of 8 s before the loop end followed by 8 s after the loop start (what the player hears)."""
    a = y[max(0, e - 8 * sr):e].mean(axis=1)
    b = y[s:s + 8 * sr].mean(axis=1)
    x = np.concatenate([a, b])
    S = stft_mag(x, 2048, 256)
    M = np.log10(S @ mel_fb(sr, 2048, 96).T + 1e-6)
    Mn = (M - np.percentile(M, 5)) / (np.percentile(M, 99.5) - np.percentile(M, 5) + 1e-9)
    img = Image.fromarray(colormap(Mn[:, ::-1].T)).resize((900, 220), Image.BILINEAR)
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    xs = int(len(a) / len(x) * 900)
    d.line([(xs, 0), (xs, 12)], fill=(255, 255, 255), width=2)
    d.line([(xs, 208), (xs, 220)], fill=(255, 255, 255), width=2)
    d.text((6, 4), title, fill=(255, 255, 255))
    img.save(path)


def main():
    sel = json.loads((Path(__file__).parent / "bgm_select.json").read_text(encoding="utf-8"))
    only = set(sys.argv[1:])
    meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW.mkdir(parents=True, exist_ok=True)
    for bid, cfg in sel.items():
        if only and bid not in only:
            continue
        if cfg.get("file"):
            src = ROOT / cfg["file"]
        elif cfg.get("stem", "no_vocals") == "no_vocals":
            src = ROOT / "art_work" / "stems" / cfg["dir"] / "htdemucs" / "source" / "no_vocals.wav"
        else:
            src = SESSION / cfg["dir"] / "source.wav"
        if not src.exists():
            raise SystemExit(f"{bid}: source not found: {src}")
        y, sr = sf.read(str(src), dtype="float32", always_2d=True)
        # trim leading silence
        env = np.abs(y).max(axis=1)
        first = int(np.argmax(env > 0.003))
        y = y[max(0, first - int(0.02 * sr)):]
        # loudness normalise (linear gain) with a soft ceiling
        tmp = REVIEW / f"{bid}_tmp.wav"
        sf.write(str(tmp), y, sr, subtype="FLOAT")
        L = lufs_of(tmp)
        target = cfg.get("lufs", -18.0)
        y = y * (10 ** ((target - L) / 20))
        peak = float(np.abs(y).max())
        if peak > 0.89:
            # gentle tanh knee above -1 dBFS
            k = 0.89
            over = np.abs(y) > k
            y[over] = np.sign(y[over]) * (k + (1 - k) * np.tanh((np.abs(y[over]) - k) / (1 - k)))
        entry = {"title": cfg.get("title", bid), "src": f"audio/bgm/{bid}.ogg", "sr": sr, "lufs": target}
        if cfg.get("loop", True) and cfg.get("mode") == "full":
            # whole piece loops: keep its natural ending, make sure it fades, add a breath of silence
            tail = y.copy()
            env_db = 20 * np.log10(np.abs(tail).max(axis=1) + 1e-9)
            last = len(tail) - 1
            while last > 0 and env_db[last] < -50:
                last -= 1
            tail = tail[:last + 1]
            end_db = 20 * np.log10(np.sqrt((tail[-int(0.5 * sr):] ** 2).mean()) + 1e-9)
            if end_db > -38:  # abrupt ending -> 3 s fade
                f = int(3 * sr)
                tail[-f:] *= np.cos(np.linspace(0, np.pi / 2, f))[:, None] ** 2
            out = np.concatenate([tail, np.zeros((int(1.2 * sr), tail.shape[1]), np.float32)])
            entry.update({"loopStart": 0.0, "loopEnd": round(len(out) / sr, 5), "loop": True, "mode": "full"})
        elif cfg.get("loop", True):
            if "loopStart" in cfg and "loopEnd" in cfg:  # hand-picked loop points (seconds, after trimming)
                s, e, sim, fine = int(cfg["loopStart"] * sr), int(cfg["loopEnd"] * sr), 1.0, 1.0
            else:
                s, e, sim, fine = find_loop(y, sr, cfg.get("min_body", 60), cfg.get("tail_guard", 3))
            out = bake(y, s, e, sr)
            entry.update({"loopStart": round(s / sr, 5), "loopEnd": round(e / sr, 5), "loop": True,
                          "similarity": round(sim, 3), "phase": round(fine, 3)})
            seam_image(y, s, e, sr, REVIEW / f"{bid}_seam.png",
                       f"{bid} loop {s / sr:.2f}-{e / sr:.2f}s sim={sim:.3f} xc={fine:.3f}")
        else:
            out = y
            # short fade at the very end for safety
            f = min(len(out), int(0.05 * sr))
            out[-f:] *= np.linspace(1, 0, f)[:, None]
            entry.update({"loop": False})
        entry["duration"] = round(len(out) / sr, 3)
        wav = REVIEW / f"{bid}.wav"
        sf.write(str(wav), out, sr, subtype="PCM_16")
        ogg = OUT_DIR / f"{bid}.ogg"
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(wav), "-c:a", "libvorbis",
                        "-q:a", "5", str(ogg)], check=True)
        tmp.unlink(missing_ok=True)
        meta[bid] = entry
        print(bid, json.dumps(entry), flush=True)
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
