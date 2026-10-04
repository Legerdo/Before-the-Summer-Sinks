"""Voice production: Fish TTS (zero-shot clone per character) -> ASR verification -> retries ->
trim + loudness -> Ogg + lip-sync envelope. Incremental: a line is regenerated only when its
text hash changes (voice ids are stable, see tools/story/compile.mjs).

A line is also regenerated when its character's reference voice (story/characters.json "tts") changes.

Usage:
  python make_voices.py gen [--only ys0001,ys0002] [--chars yunseul] [--limit N] [--force]
  python make_voices.py build          # encode + envelopes + manifests from accepted takes
Files:
  story/characters.json "tts": {"ref": wav, "refText": transcript}  reference voice per character
  voice/lines.json      (from the story compiler)
  voice/raw/<id>_<k>.wav  every take
  voice/state.json      accepted take per id with ASR/CER
  public/audio/voice/<id>.ogg, public/data/voice.json, public/data/lipsync.json
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, resample_poly, sosfiltfilt

sys.path.insert(0, str(Path(__file__).parent))
import fish  # noqa: E402
from analyze import cer, norm_text  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
LINES = ROOT / "voice" / "lines.json"
RAW = ROOT / "voice" / "raw"
STATE = ROOT / "voice" / "state.json"
OUT = ROOT / "public" / "audio" / "voice"
# TTS reference per character comes from the character registry (story/characters.json, "tts" block)
CAST = {c["id"]: c["tts"] for c in json.loads((ROOT / "story" / "characters.json").read_text(encoding="utf-8")).values()
        if c.get("tts")}
MAX_TAKES = 3
lock = threading.Lock()


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def save_state(st: dict):
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def ref_for(char: str):
    c = CAST[char]
    return [(ROOT / c["ref"], (ROOT / c["refText"]).read_text(encoding="utf-8").strip())]


_fp_cache: dict[str, str] = {}


def ref_fp(char: str) -> str:
    """Fingerprint of a character's reference voice: replacing the wav/txt re-voices all of its lines."""
    if char not in _fp_cache:
        c = CAST[char]
        h = hashlib.sha1((ROOT / c["ref"]).read_bytes() + (ROOT / c["refText"]).read_bytes())
        _fp_cache[char] = h.hexdigest()[:12]
    return _fp_cache[char]


_asr = None


def asr_model():
    global _asr
    if _asr is None:
        from faster_whisper import WhisperModel
        _asr = WhisperModel("large-v3", device="cuda", compute_type="float16")
    return _asr


def mono16k(path: Path):
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    y = y.mean(axis=1)
    g = gcd(sr, 16000)
    return resample_poly(y, 16000 // g, sr // g).astype(np.float32), y, sr


def transcribe(path: Path, prompt: str) -> str:
    x, _, _ = mono16k(path)
    segs, _ = asr_model().transcribe(x, language="ko", beam_size=5, vad_filter=False, condition_on_previous_text=False,
                                     initial_prompt=None)
    return "".join(s.text for s in segs).strip()


_NATIVE = {"하나": 1, "한": 1, "둘": 2, "두": 2, "셋": 3, "세": 3, "넷": 4, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7,
           "여덟": 8, "아홉": 9}
_TENS = {"열": 10, "스물": 20, "스무": 20, "서른": 30, "마흔": 40, "쉰": 50, "예순": 60, "일흔": 70, "여든": 80, "아흔": 90}
_SINO = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}


def _num_pairs():
    pairs = {}
    for t, tv in _TENS.items():
        pairs[t] = tv
        for u, uv in _NATIVE.items():
            pairs[t + u] = tv + uv
    for u, uv in _NATIVE.items():
        pairs.setdefault(u, uv)
    for t, tv in _SINO.items():
        pairs[t + "십"] = tv * 10
        for u, uv in _SINO.items():
            pairs[t + "십" + u] = tv * 10 + uv
    pairs.update({"십": 10, "백": 100, "천": 1000})
    return sorted(pairs.items(), key=lambda kv: -len(kv[0]))


NUM_PAIRS = _num_pairs()
UNITS = r"(?=\s*(?:시간|시|분|번째|번|개|명|통|대|년|살|밀리|호|째|MHz|메가)|\s+일\b)"


def numerals_to_digits(s: str) -> str:
    """Rewrite spelled Korean numbers that precede a counter into digits (as the recogniser writes them)."""
    for word, val in NUM_PAIRS:
        s = re.sub(re.escape(word) + UNITS, str(val), s)
    # multi-syllable numbers standing alone before punctuation ("쉰다섯." / "열일곱인데")
    for word, val in NUM_PAIRS:
        if len(word) >= 2 and word not in ("하나", "다섯", "여섯", "일곱", "여덟", "아홉"):
            s = re.sub(re.escape(word) + r"(?=\s*(?:[.!?…,]|인데|이야|$))", str(val), s)
    return s


def ref_text(text: str) -> str:
    t = re.sub(r"\{w=[\d.]+\}", "", text)
    return t


def judge(line: dict, path: Path) -> dict:
    hyp = transcribe(path, line["text"])
    ref = ref_text(line["text"])
    c = cer(ref, hyp)
    # tolerate numerals written as digits by the recogniser ("쉰여섯 번째" -> "56번째")
    alt = numerals_to_digits(ref)
    c = min(c, cer(alt, hyp), cer(ref, re.sub(r"(\d)\s+(?=\d)", r"\1", hyp)))
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    dur = len(y) / sr
    n = len(norm_text(ref))
    rate = n / max(dur, 0.1)
    emotional = bool(re.search(r"laugh|cry|sob|tear|scream|shout|whisper|breathless|sleepy|murmur", line["tts"], re.I))
    limit = 0.34 if n <= 6 else (0.25 if emotional else 0.16)
    ok = c <= limit and 0.8 <= rate <= 16 and dur < max(4.0, n * 0.5 + 4)
    if n <= 3 and 0.2 < dur < 3.5:  # interjections ("흐응.", "야…!!") are not reliably transcribed
        ok = True
    return {"asr": hyp, "cer": round(c, 3), "dur": round(dur, 2), "rate": round(rate, 2), "ok": bool(ok), "limit": limit}


def cmd_accept(a):
    """Manually accept reviewed takes whose ASR mismatch is a recogniser artefact (liaison, elongation)."""
    st = load_state()
    for vid in a.only or []:
        if vid in st:
            st[vid]["ok"] = True
            st[vid]["manual"] = "accepted after review: " + st[vid].get("asr", "")
            print("accepted", vid, st[vid]["asr"])
    save_state(st)


def cmd_rejudge(a):
    lines = {l["id"]: l for l in json.loads(LINES.read_text(encoding="utf-8"))}
    st = load_state()
    for vid, l in lines.items():
        if a.only and vid not in a.only:
            continue
        takes = sorted(RAW.glob(f"{vid}_[0-9].wav"))
        if not takes:
            continue
        best = None
        for p in takes:
            j = judge(l, p)
            cand = {"hash": l["hash"], "char": l["char"], "ref": ref_fp(l["char"]), "take": int(p.stem.split("_")[-1]),
                    "file": str(p.relative_to(ROOT)), **j}
            if best is None or (cand["ok"] and not best["ok"]) or (cand["ok"] == best["ok"] and cand["cer"] < best["cer"]):
                best = cand
        st[vid] = best
        print(f"  {vid} best take{best['take']} cer={best['cer']} ok={best['ok']}", flush=True)
    save_state(st)


def take_path(vid: str, k: int) -> Path:
    return RAW / f"{vid}_{k}.wav"


def gen_take(line: dict, k: int) -> Path:
    p = take_path(line["id"], k)
    if not p.exists():
        temp = 0.7 if k == 1 else 0.62 if k == 2 else 0.75
        fish.tts_clone(line["tts"], p, ref_for(line["char"]), temperature=temp, top_p=0.7)
    return p


def cmd_gen(a):
    lines = json.loads(LINES.read_text(encoding="utf-8"))
    st = load_state()
    todo = []
    adopted = 0
    for l in lines:
        if a.only and l["id"] not in a.only:
            continue
        if a.chars and l["char"] not in a.chars:
            continue
        s = st.get(l["id"])
        fp = ref_fp(l["char"])
        if s and "ref" not in s:  # takes made before fingerprints were tracked belong to the current voice
            s["ref"] = fp
            adopted += 1
        new_voice = bool(s) and s.get("ref") != fp
        if s and s.get("hash") == l["hash"] and s.get("ok") and not a.force and not new_voice:
            continue
        if s and (s.get("hash") != l["hash"] or new_voice or a.force):
            for f in RAW.glob(f"{l['id']}_*.wav"):
                f.unlink()
            del st[l["id"]]
        todo.append(l)
    if adopted:
        save_state(st)
    if a.limit:
        todo = todo[: a.limit]
    print(f"{len(todo)} lines to generate", flush=True)
    RAW.mkdir(parents=True, exist_ok=True)
    pending = todo
    for k in range(1, MAX_TAKES + 1):
        if not pending:
            break
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(gen_take, l, k): l for l in pending}
            for f, l in futs.items():
                try:
                    f.result()
                except Exception as e:  # noqa: BLE001
                    print("  gen error", l["id"], e, flush=True)
        retry = []
        for l in pending:
            p = take_path(l["id"], k)
            if not p.exists():
                retry.append(l)
                continue
            j = judge(l, p)
            prev = st.get(l["id"])
            cand = {"hash": l["hash"], "char": l["char"], "ref": ref_fp(l["char"]), "take": k,
                    "file": str(p.relative_to(ROOT)), **j}
            # keep the best take seen so far for this hash
            if not prev or prev.get("hash") != l["hash"] or (not prev.get("ok") and (j["ok"] or j["cer"] < prev.get("cer", 9))):
                st[l["id"]] = cand
            if not st[l["id"]]["ok"]:
                retry.append(l)
            print(f"  {l['id']} take{k} cer={j['cer']} ok={j['ok']} | {l['text'][:28]} -> {j['asr'][:28]}", flush=True)
        with lock:
            save_state(st)
        pending = retry
    bad = [i for i, s in st.items() if not s.get("ok")]
    print(f"done. accepted-with-issues: {len(bad)} {bad[:30]}", flush=True)


# ------------------------------------------------------------------ build
def trim_and_level(y: np.ndarray, sr: int) -> np.ndarray:
    a = np.abs(y)
    win = int(0.01 * sr)
    env = np.convolve(a, np.ones(win) / win, mode="same")
    thr = env.max() * 10 ** (-42 / 20)
    idx = np.where(env > thr)[0]
    if len(idx):
        s = max(0, idx[0] - int(0.05 * sr))
        e = min(len(y), idx[-1] + int(0.16 * sr))
        y = y[s:e]
    # loudness-ish normalisation on active speech (RMS of frames above -35 dB)
    frame = int(0.02 * sr)
    n = len(y) // frame
    if n > 0:
        fr = y[: n * frame].reshape(n, frame)
        r = np.sqrt((fr ** 2).mean(axis=1)) + 1e-9
        act = r[r > r.max() * 10 ** (-35 / 20)]
        rms = np.sqrt((act ** 2).mean()) if len(act) else r.mean()
        y = y * (10 ** (-19 / 20) / rms)
    pk = np.abs(y).max()
    if pk > 0.93:
        y = y * (0.93 / pk)
    f = min(len(y), int(0.012 * sr))
    y[:f] *= np.linspace(0, 1, f)
    y[-f:] *= np.linspace(1, 0, f)
    return y.astype(np.float32)


def envelope(y: np.ndarray, sr: int, rate: int = 50, span: float = 20.0) -> bytes:
    """Mouth-opening curve at 50 fps: loudness in the top `span` dB of the line, scaled by how
    much energy sits in the first-formant band (open vowels like 아/어 open wider than 이/우)."""
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
        v = v + (x - v) * (0.7 if x > v else 0.45)
        out[i] = v
    out[-2:] = 0
    return (np.clip(out, 0, 1) * 255).astype(np.uint8).tobytes()


def cmd_build(a):
    lines = {l["id"]: l for l in json.loads(LINES.read_text(encoding="utf-8"))}
    st = load_state()
    OUT.mkdir(parents=True, exist_ok=True)
    manifest, lips, missing = {}, {}, []
    for vid, l in lines.items():
        s = st.get(vid)
        if not s or s.get("hash") != l["hash"]:
            missing.append(vid)
            continue
        src = ROOT / s["file"]
        y, sr = sf.read(str(src), dtype="float32", always_2d=True)
        y = trim_and_level(y.mean(axis=1), sr)
        ogg = OUT / f"{vid}.ogg"
        stamp = ROOT / "voice" / "stamps" / f"{vid}.src"
        stamp.parent.mkdir(parents=True, exist_ok=True)
        if not ogg.exists() or not stamp.exists() or stamp.read_text() != s["file"]:
            tmp = RAW / f"_{vid}_proc.wav"
            sf.write(str(tmp), y, sr, subtype="PCM_16")
            subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(tmp), "-ac", "1", "-c:a", "libvorbis",
                            "-q:a", "5", str(ogg)], check=True)
            tmp.unlink()
            stamp.write_text(s["file"])
        manifest[vid] = {"src": f"audio/voice/{vid}.ogg", "dur": round(len(y) / sr, 3)}
        lips[vid] = base64.b64encode(envelope(y, sr)).decode()
    (ROOT / "public" / "data" / "voice.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (ROOT / "public" / "data" / "lipsync.json").write_text(json.dumps(lips), encoding="utf-8")
    print(f"built {len(manifest)} voices; missing {len(missing)}: {missing[:20]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gen", "build", "rejudge", "accept"])
    ap.add_argument("--only", type=lambda s: set(s.split(",")), default=None)
    ap.add_argument("--chars", type=lambda s: set(s.split(",")), default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    {"gen": cmd_gen, "build": cmd_build, "rejudge": cmd_rejudge, "accept": cmd_accept}[a.cmd](a)
