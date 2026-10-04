"""Thin Fish Audio API client (TTS, voice design, model creation).

The API key is read from the FISH_API_KEY environment variable and never printed.
"""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

import requests

API = "https://api.fish.audio"


def _key() -> str:
    key = os.environ.get("FISH_API_KEY", "")
    if not key:
        raise SystemExit("FISH_API_KEY is not set")
    return key


def _headers(extra: dict | None = None) -> dict:
    h = {"Authorization": f"Bearer {_key()}"}
    if extra:
        h.update(extra)
    return h


def tts(text: str, out: Path, *, reference_id: str | None = None, model: str = "s2.1-pro-free",
        fmt: str = "wav", sample_rate: int | None = 44100, speed: float | None = None,
        temperature: float | None = None, top_p: float | None = None,
        latency: str = "normal", retries: int = 4, timeout: int = 180) -> Path:
    body: dict = {"text": text, "format": fmt, "latency": latency, "normalize": True}
    if reference_id:
        body["reference_id"] = reference_id
    if fmt == "wav" and sample_rate:
        body["sample_rate"] = sample_rate
    if fmt == "mp3":
        body["mp3_bitrate"] = 192
    if speed is not None:
        body["prosody"] = {"speed": speed}
    if temperature is not None:
        body["temperature"] = temperature
    if top_p is not None:
        body["top_p"] = top_p
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(f"{API}/v1/tts", headers=_headers({"Content-Type": "application/json", "model": model}),
                              data=json.dumps(body, ensure_ascii=False).encode("utf-8"), timeout=timeout)
            if r.status_code == 200 and len(r.content) > 1000 and not r.content.lstrip().startswith(b"{"):
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(r.content)
                return out
            last = f"HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code in (400, 401, 402, 403, 422):
                break
        except requests.RequestException as e:  # network hiccup
            last = str(e)
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"TTS failed for {out.name}: {last}")


def tts_clone(text: str, out: Path, refs: list[tuple[Path, str]], *, model: str = "s2.1-pro-free",
              fmt: str = "wav", sample_rate: int = 44100, temperature: float = 0.7, top_p: float = 0.7,
              speed: float | None = None, retries: int = 4, timeout: int = 240) -> Path:
    """Zero-shot cloning: reference audio is attached inline (MessagePack body)."""
    import msgpack
    body: dict = {"text": text, "format": fmt, "latency": "normal", "normalize": True,
                  "temperature": temperature, "top_p": top_p,
                  "references": [{"audio": p.read_bytes(), "text": t} for p, t in refs]}
    if fmt == "wav":
        body["sample_rate"] = sample_rate
    if speed is not None:
        body["prosody"] = {"speed": speed}
    packed = msgpack.packb(body, use_bin_type=True)
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(f"{API}/v1/tts", headers=_headers({"Content-Type": "application/msgpack", "model": model}),
                              data=packed, timeout=timeout)
            if r.status_code == 200 and len(r.content) > 1000 and not r.content.lstrip().startswith(b"{"):
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(r.content)
                return out
            last = f"HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code in (400, 401, 402, 403, 422):
                break
        except requests.RequestException as e:
            last = str(e)
        time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"clone TTS failed for {out.name}: {last}")


def voice_design(instruction: str, reference_text: str | None, *, language: str = "ko", n: int = 4,
                 seed: int | None = None, speed: float = 1.0, guidance_scale: float = 2.0,
                 num_step: int = 32) -> list[dict]:
    body: dict = {"instruction": instruction, "language": language, "n": n, "speed": speed,
                  "guidance_scale": guidance_scale, "num_step": num_step}
    if reference_text:
        body["reference_text"] = reference_text
    if seed is not None:
        body["seed"] = seed
    r = requests.post(f"{API}/v1/voice-design",
                      headers=_headers({"Content-Type": "application/json", "model": "voice-design-1"}),
                      data=json.dumps(body, ensure_ascii=False).encode("utf-8"), timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"voice-design HTTP {r.status_code}: {r.text[:500]}")
    return r.json()["candidates"]


def save_candidates(cands: list[dict], out_dir: Path, prefix: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    meta = []
    for c in cands:
        p = out_dir / f"{prefix}_{c.get('index', len(paths))}.wav"
        p.write_bytes(base64.b64decode(c["audio_base64"]))
        paths.append(p)
        m = {k: v for k, v in c.items() if k != "audio_base64"}
        m["file"] = p.name
        meta.append(m)
    (out_dir / f"{prefix}_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return paths


def create_model(title: str, files: list[Path], texts: list[str] | None = None, *,
                 signatures: list[str] | None = None, enhance: bool = False,
                 description: str = "") -> dict:
    data = [("type", "tts"), ("title", title), ("train_mode", "fast"), ("visibility", "private"),
            ("enhance_audio_quality", "true" if enhance else "false"), ("description", description)]
    for t in texts or []:
        data.append(("texts", t))
    for s in signatures or []:
        data.append(("voice_design_signatures", s))
    fh = [("voices", (f.name, f.read_bytes(), "audio/wav")) for f in files]
    r = requests.post(f"{API}/model", headers=_headers(), data=data, files=fh, timeout=300)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"create model HTTP {r.status_code}: {r.text[:500]}")
    return r.json()


def get_model(model_id: str) -> dict:
    r = requests.get(f"{API}/model/{model_id}", headers=_headers(), timeout=60)
    r.raise_for_status()
    return r.json()


def package_balance() -> dict:
    r = requests.get(f"{API}/wallet/self/package", headers=_headers(), timeout=60)
    r.raise_for_status()
    j = r.json()
    return {"total": j.get("total"), "balance": j.get("balance"), "type": j.get("type")}
