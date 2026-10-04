"""Clone-stability test: synthesize a few emotional lines with each candidate as reference.

Usage: python clone_test.py <out_dir> <ref_transcript_file> cand1.wav [cand2.wav ...]
Writes <out_dir>/<cand>__<k>.wav and manifest.json for analyze.py.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fish  # noqa: E402

LINES = [
    "[happy] 진짜? 그럼 내일 아침 일곱 시에 정류장 앞에서 봐. 늦으면 두고 간다!",
    "[sad][soft tone] 엄마가 그랬어. 소리는… 사라지지 않는다고. 누군가 기억하는 한.",
    "[angry] 그러니까 처음부터 알고 있었던 거잖아. 왜 말 안 했어?",
    "[whispering] 쉿. 지금부터 방송 시작이야. 숨소리도 다 들어가니까, 조용히 해.",
]

out_dir = Path(sys.argv[1])
ref_text = Path(sys.argv[2]).read_text(encoding="utf-8").strip()
cands = [Path(p) for p in sys.argv[3:]]
jobs = []
manifest = []
for c in cands:
    for k, line in enumerate(LINES):
        p = out_dir / f"{c.stem}__{k}.wav"
        jobs.append((c, line, p))
        manifest.append({"id": p.stem, "file": str(p), "text": line})


def run(job):
    c, line, p = job
    if not p.exists():
        fish.tts_clone(line, p, [(c, ref_text)])
    return p.name


with ThreadPoolExecutor(max_workers=4) as ex:
    for name in ex.map(run, jobs):
        print("ok", name, flush=True)
(out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
