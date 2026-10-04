"""List public Fish Audio voice models for a language, showing provenance fields.

Usage: python list_voices.py <language> [pages] [title_filter]
Writes art_work/voice_lib_<lang>.json with the raw summaries.
"""
import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
import fish  # noqa: E402

lang = sys.argv[1] if len(sys.argv) > 1 else "ko"
pages = int(sys.argv[2]) if len(sys.argv) > 2 else 3
title = sys.argv[3] if len(sys.argv) > 3 else None
rows = []
for page in range(1, pages + 1):
    params = {"page_size": 50, "page_number": page, "language": lang, "sort_by": "task_count"}
    if title:
        params["title"] = title
    r = requests.get(f"{fish.API}/model", headers=fish._headers(), params=params, timeout=60)
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        break
    for it in items:
        rows.append({
            "id": it.get("_id"), "title": it.get("title"), "source": it.get("source"),
            "tags": it.get("tags"), "languages": it.get("languages"), "task_count": it.get("task_count"),
            "licensed": it.get("licensed"), "visibility": it.get("visibility"),
            "description": (it.get("description") or "")[:160],
            "author": (it.get("author") or {}).get("nickname"),
            "samples": [s.get("audio") for s in (it.get("samples") or [])][:1],
        })
out = Path("art_work") / f"voice_lib_{lang}{'_' + title if title else ''}.json"
out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(rows), "rows ->", out)
srcs = {}
for r_ in rows:
    srcs[r_["source"]] = srcs.get(r_["source"], 0) + 1
print("sources:", srcs)
for r_ in rows:
    if r_["source"] not in (None, "", "user_upload"):
        print(r_["id"], r_["source"], r_["task_count"], r_["title"], r_["tags"])
