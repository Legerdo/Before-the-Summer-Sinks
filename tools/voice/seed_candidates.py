"""Generate unconditioned (no reference) TTS candidates on the free model to find an
original synthetic voice. Each request samples a new synthetic speaker.

Usage: python seed_candidates.py <out_dir> <count> <prefix> <text_file>
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fish  # noqa: E402

out_dir = Path(sys.argv[1])
count = int(sys.argv[2])
prefix = sys.argv[3]
text = Path(sys.argv[4]).read_text(encoding="utf-8").strip()
out_dir.mkdir(parents=True, exist_ok=True)


def one(i: int) -> str:
    p = out_dir / f"{prefix}_{i:02d}.wav"
    if p.exists():
        return f"skip {p.name}"
    fish.tts(text, p, fmt="wav", sample_rate=44100, temperature=0.8, top_p=0.8)
    return f"ok {p.name} {p.stat().st_size}"


with ThreadPoolExecutor(max_workers=4) as ex:
    for res in ex.map(one, range(count)):
        print(res, flush=True)
