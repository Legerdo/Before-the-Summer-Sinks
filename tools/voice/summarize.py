"""Print a compact table from an analyze.py JSON report. Usage: python summarize.py report.json [sort_key]"""
import json
import sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))
key = sys.argv[2] if len(sys.argv) > 2 else "f0_med"
cols = ["id", "dur", "f0_med", "f0_p10", "f0_p90", "f0_iqr_st", "aper", "centroid", "voiced_ratio", "max_gap", "cer"]
print(" ".join(f"{c:>9}" for c in cols))
for r in sorted(rows, key=lambda r: (r.get(key) is None, r.get(key))):
    print(" ".join(f"{str(r.get(c, '')):>9}" for c in cols))
