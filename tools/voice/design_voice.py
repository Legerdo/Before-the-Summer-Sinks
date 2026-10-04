"""Generate voice-design candidates for a character and save them with metadata.

Usage: python design_voice.py <config.json> <out_dir> [seed]
config.json: {"prefix": str, "instruction": str, "reference_text": str, "n": 4}
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fish  # noqa: E402

cfg = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
out_dir = Path(sys.argv[2])
seed = int(sys.argv[3]) if len(sys.argv) > 3 else None
before = fish.package_balance()
cands = fish.voice_design(cfg["instruction"], cfg.get("reference_text"), language=cfg.get("language", "ko"),
                          n=cfg.get("n", 4), seed=seed, guidance_scale=cfg.get("guidance_scale", 2.0),
                          num_step=cfg.get("num_step", 32))
paths = fish.save_candidates(cands, out_dir, cfg["prefix"] + (f"_s{seed}" if seed is not None else ""))
after = fish.package_balance()
print("saved:", [p.name for p in paths])
print("keys in candidate:", sorted(k for k in cands[0].keys() if k != "audio_base64"))
print("balance before/after:", before.get("balance"), after.get("balance"))
