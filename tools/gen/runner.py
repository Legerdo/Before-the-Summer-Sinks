"""Parallel job runner for Codex CLI image generation.

jobs.json: [{"id": "yunseul_expr_smile", "out": "art_src/chars/yunseul/expr/smile.png",
             "prompt": "...", "images": ["art_src/chars/yunseul/master.png"]}, ...]
Each job runs `codex exec` in its own scratch directory; the agent is told to save
result.png there. On success the file is moved to `out`. Existing outputs are skipped.

Usage: python runner.py jobs.json [--workers 4] [--only id1,id2] [--force]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = ROOT / "art_work" / "jobs"
LOG = ROOT / "art_work" / "runner.log"


def codex_bin() -> str:
    base = Path(r"C:\Users\K\AppData\Local\OpenAI\Codex\bin")
    cands = [d for d in base.iterdir() if d.is_dir() and (d / "codex.exe").exists()] if base.exists() else []
    if cands:
        cands.sort(key=lambda d: d.stat().st_mtime, reverse=True)
        return str(cands[0] / "codex.exe")
    return str(Path(os.environ["APPDATA"]) / "npm" / "codex.cmd")


def log(msg: str) -> None:
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


SUFFIX = ("\n\nSave the final PNG into the current working directory as result.png "
          "(copy it from wherever image_gen stores it). Do not create any other files. "
          "Reply only with the saved path and pixel dimensions.")


def run_job(job: dict, force: bool, timeout: int) -> tuple[str, bool, str]:
    out = ROOT / job["out"]
    if out.exists() and not force:
        return job["id"], True, "exists"
    work = SCRATCH / job["id"]
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    imgs = []
    for i, p in enumerate(job.get("images", [])):
        src = ROOT / p
        dst = work / f"input_{i + 1}{src.suffix}"
        shutil.copy2(src, dst)
        imgs.append(dst.name)
    prompt = job["prompt"].strip() + SUFFIX
    args = [codex_bin(), "exec", "--skip-git-repo-check", "-s", "workspace-write",
            "-c", 'model_reasoning_effort="low"', "-"]
    if imgs:
        args += ["-i", *imgs]
    t0 = time.time()
    with (work / "codex.log").open("w", encoding="utf-8", errors="replace") as lf:
        try:
            proc = subprocess.run(args, input=prompt.encode("utf-8"), cwd=work, stdout=lf,
                                  stderr=subprocess.STDOUT, timeout=timeout)
            code = proc.returncode
        except subprocess.TimeoutExpired:
            code = -999
    res = work / "result.png"
    if not res.exists():
        pngs = [p for p in work.glob("*.png") if not p.name.startswith("input_")]
        if pngs:
            res = max(pngs, key=lambda p: p.stat().st_mtime)
    if res.exists() and res.stat().st_size > 10000:
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(res, out)
        (out.with_suffix(".prompt.txt")).write_text(job["prompt"], encoding="utf-8")
        return job["id"], True, f"ok {time.time() - t0:.0f}s"
    return job["id"], False, f"failed code={code} after {time.time() - t0:.0f}s (see {work / 'codex.log'})"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--retries", type=int, default=1)
    a = ap.parse_args()
    jobs = json.loads(Path(a.jobs).read_text(encoding="utf-8"))
    if a.only:
        keep = set(a.only.split(","))
        jobs = [j for j in jobs if j["id"] in keep]
    log(f"start {len(jobs)} jobs from {a.jobs} workers={a.workers}")
    pending = jobs
    for attempt in range(a.retries + 1):
        failed = []
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            futs = {ex.submit(run_job, j, a.force, a.timeout): j for j in pending}
            for fu in as_completed(futs):
                jid, ok, msg = fu.result()
                log(f"{'OK ' if ok else 'ERR'} {jid}: {msg}")
                if not ok:
                    failed.append(futs[fu])
        if not failed:
            break
        pending = failed
        a.force = False
        log(f"retrying {len(failed)} failed jobs")
    log("done")


if __name__ == "__main__":
    sys.exit(main())
