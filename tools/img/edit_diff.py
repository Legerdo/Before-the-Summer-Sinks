"""Measure how an image edit differs from the base: global alignment + diff map + face crops.

Usage: python edit_diff.py base.png edit1.png [edit2.png ...] --crop x0 y0 x1 y1 --out sheet.jpg
"""
import sys

import cv2
import numpy as np
from PIL import Image

args = sys.argv[1:]
crop = None
out = "diff_sheet.jpg"
if "--crop" in args:
    i = args.index("--crop")
    crop = tuple(int(v) for v in args[i + 1:i + 5])
    del args[i:i + 5]
if "--out" in args:
    i = args.index("--out")
    out = args[i + 1]
    del args[i:i + 2]
base_p, edits = args[0], args[1:]


def load(p):
    im = Image.open(p).convert("RGBA")
    a = np.array(im).astype(np.float32) / 255.0
    return a


base = load(base_p)
H, W = base.shape[:2]
gray_b = cv2.cvtColor((base[..., :3] * base[..., 3:4] * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
tiles = []
x0, y0, x1, y1 = crop if crop else (0, 0, W, H)


def to_tile(a):
    rgb = a[..., :3] * a[..., 3:4] + 0.5 * (1 - a[..., 3:4])
    return (np.clip(rgb, 0, 1) * 255).astype(np.uint8)


tiles.append(to_tile(base)[y0:y1, x0:x1])
for p in edits:
    e = load(p)
    if e.shape != base.shape:
        e = np.array(Image.fromarray((e * 255).astype(np.uint8)).resize((W, H), Image.LANCZOS)).astype(np.float32) / 255
    gray_e = cv2.cvtColor((e[..., :3] * e[..., 3:4] * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    warp = np.eye(2, 3, dtype=np.float32)
    try:
        cc, warp = cv2.findTransformECC(gray_b.astype(np.float32), gray_e.astype(np.float32), warp,
                                        cv2.MOTION_AFFINE,
                                        (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), None, 5)
    except cv2.error as ex:
        cc = float("nan")
    aligned = cv2.warpAffine(e, warp, (W, H), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP)
    d_raw = np.abs(e[..., :3] - base[..., :3]).mean(axis=2) * np.maximum(e[..., 3], base[..., 3])
    d_al = np.abs(aligned[..., :3] - base[..., :3]).mean(axis=2) * np.maximum(aligned[..., 3], base[..., 3])
    print(f"{p}: ecc={cc:.4f} warp={np.round(warp, 4).tolist()} meanDiffRaw={d_raw.mean():.4f} "
          f"meanDiffAligned={d_al.mean():.4f} alphaDiff={np.abs(e[..., 3] - base[..., 3]).mean():.4f}")
    tiles.append(to_tile(e)[y0:y1, x0:x1])
    heat = cv2.applyColorMap(np.clip(d_al * 4 * 255, 0, 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
    tiles.append(cv2.cvtColor(heat, cv2.COLOR_BGR2RGB)[y0:y1, x0:x1])
row = np.concatenate([np.pad(t, ((4, 4), (4, 4), (0, 0)), constant_values=40) for t in tiles], axis=1)
img = Image.fromarray(row)
s = min(1.0, 1900 / img.width, 1900 / img.height)
if s < 1:
    img = img.resize((int(img.width * s), int(img.height * s)), Image.LANCZOS)
img.save(out, quality=90)
print("sheet", out, img.size)
