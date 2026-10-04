"""Build layered VN sprites from generated full-body edits.

For every character:
  * all images are aligned to the master with ECC (affine, head-region mask)
  * zones: eyes (from the neutral blink diff), mouth (from the neutral open-mouth diff),
    face (union of expression diffs) -> feathered elliptical masks
  * outputs body_<pose>.webp, face_<expr>.webp, eyes_<expr>.webp, mouth_<expr>_{1,2}.webp
    plus public/data/chars.json describing the layer rectangles in canvas pixels
  * patches are colour-matched to their base on the feather ring to avoid halos

Usage: python build_sprites.py [char ...] [--preview]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "art_src" / "chars"
OUT = ROOT / "public" / "assets" / "chars"
MANIFEST = ROOT / "public" / "data" / "chars.json"
WORK = ROOT / "art_work" / "sprites"

REGISTRY = ROOT / "story" / "characters.json"


def load_chars() -> dict:
    """Sprite settings come from the character registry (story/characters.json, "sprite" block).
    Source images live in art_src/chars/<id>/: master.png, body/<pose>.png, expr/<expr>.png,
    var/<expr>_{blink,m1,m2}.png (see docs/RESOURCES.md)."""
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    out = {}
    for ch in reg.values():
        sp = ch.get("sprite")
        if not sp:
            continue
        cfg = {"bodies": sp["bodies"], "exprs": sp["exprs"], "noblink": sp.get("noblink", []),
               "head_box": tuple(sp["headBox"])}
        if sp.get("eyesBox"):
            cfg["eyes_box"] = tuple(sp["eyesBox"])
        out[ch["id"]] = cfg
    return out


CHARS = load_chars()


def load(p: Path) -> np.ndarray:
    return np.asarray(Image.open(p).convert("RGBA")).astype(np.float32) / 255.0


def gray(a: np.ndarray) -> np.ndarray:
    rgb = a[..., :3] * a[..., 3:4] + 0.5 * (1 - a[..., 3:4])
    return cv2.cvtColor((rgb * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)


def align(img: np.ndarray, ref: np.ndarray, mask: np.ndarray | None) -> tuple[np.ndarray, float, np.ndarray]:
    H, W = ref.shape[:2]
    if img.shape[:2] != (H, W):
        img = cv2.resize(img, (W, H), interpolation=cv2.INTER_LANCZOS4)
    warp = np.eye(2, 3, dtype=np.float32)
    m8 = None if mask is None else (mask > 0).astype(np.uint8) * 255
    try:
        cc, warp = cv2.findTransformECC(gray(ref), gray(img), warp, cv2.MOTION_AFFINE,
                                        (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 300, 1e-7), m8, 5)
    except cv2.error:
        cc = float("nan")
    out = cv2.warpAffine(img, warp, (W, H), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    return out, cc, warp


def diffmap(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    d = np.abs(a[..., :3] - b[..., :3]).max(axis=2) * np.maximum(a[..., 3], b[..., 3])
    return cv2.GaussianBlur(d, (0, 0), 2.5)


def bbox(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def main_components(mask: np.ndarray, min_area: int) -> np.ndarray:
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    keep = np.zeros_like(mask, dtype=bool)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            keep |= lab == i
    return keep


def ellipse_mask(shape, box, feather: float) -> np.ndarray:
    H, W = shape
    x0, y0, x1, y1 = box
    m = np.zeros((H, W), np.float32)
    cv2.ellipse(m, ((float(x0 + x1) / 2, float(y0 + y1) / 2), (float(x1 - x0), float(y1 - y0)), 0.0), 1.0, -1)
    if feather > 0:
        m = cv2.GaussianBlur(m, (0, 0), feather)
    return m


def expand(box, l, t, r, b, W, H):
    x0, y0, x1, y1 = box
    return max(0, x0 - l), max(0, y0 - t), min(W, x1 + r), min(H, y1 + b)


def color_match(patch: np.ndarray, base: np.ndarray, ring: np.ndarray) -> np.ndarray:
    """Per-channel gain/offset so the patch matches the base on the ring."""
    sel = ring > 0.5
    if sel.sum() < 200:
        return patch
    out = patch.copy()
    for c in range(3):
        p = patch[..., c][sel]
        q = base[..., c][sel]
        sp, sq = p.std() + 1e-4, q.std() + 1e-4
        g = float(np.clip(sq / sp, 0.9, 1.1))
        o = float(q.mean() - g * p.mean())
        out[..., c] = np.clip(patch[..., c] * g + o, 0, 1)
    return out


def crop_layer(img: np.ndarray, mask: np.ndarray, pad: int = 2):
    a = img[..., 3] * mask
    ys, xs = np.where(a > 0.004)
    x0, y0 = max(0, xs.min() - pad), max(0, ys.min() - pad)
    x1, y1 = min(img.shape[1], xs.max() + pad + 1), min(img.shape[0], ys.max() + pad + 1)
    out = img[y0:y1, x0:x1].copy()
    out[..., 3] = a[y0:y1, x0:x1]
    return out, (int(x0), int(y0), int(x1 - x0), int(y1 - y0))


def save_webp(a: np.ndarray, p: Path, quality: int = 92):
    p.parent.mkdir(parents=True, exist_ok=True)
    im = Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")
    im.save(p, "WEBP", quality=quality, method=6, alpha_quality=100)


def build(name: str, preview: bool) -> dict:
    cfg = CHARS[name]
    base_dir = SRC / name
    master = load(base_dir / "master.png")
    H, W = master.shape[:2]
    exprs = cfg["exprs"]
    src_of = lambda e: base_dir / ("master.png" if e == "neutral" else f"expr/{e}.png")
    var_of = lambda e, v: base_dir / "var" / f"{e}_{v}.png"

    # ---- zones from neutral variants, searched only inside the configured head box
    hx0, hy0, hx1, hy1 = cfg["head_box"]
    hb = np.zeros((H, W), np.float32)
    hb[hy0:hy1, hx0:hx1] = 1
    nb, _, _ = align(load(var_of("neutral", "blink")), master, hb)
    nm, _, _ = align(load(var_of("neutral", "m2")), master, hb)
    if "eyes_box" in cfg:
        eb = tuple(cfg["eyes_box"])
        eye_raw = np.zeros((H, W), bool)
        eye_raw[eb[1]:eb[3], eb[0]:eb[2]] = True
    else:
        eye_raw = main_components((diffmap(nb, master) * hb) > 0.10, 60)
        eb = bbox(eye_raw)
    # the mouth must sit below the eyes and inside their horizontal span
    mzone = np.zeros((H, W), np.float32)
    ew = eb[2] - eb[0]
    mzone[eb[3] - int(ew * 0.1):min(H, eb[3] + int(ew * 0.65)), eb[0]:eb[2]] = 1
    mouth_raw = main_components((diffmap(nm, master) * hb * mzone) > 0.10, 40)
    mb = bbox(mouth_raw)
    # the eye diff can catch stray hair; restrict to the band around the largest components
    ex0, ey0, ex1, ey1 = eb
    mx0, my0, mx1, my1 = mb
    face_w = ex1 - ex0
    head_roi = expand((ex0, ey0, ex1, my1), int(face_w * 0.45), int(face_w * 0.55), int(face_w * 0.45), int(face_w * 0.35), W, H)
    roi_mask = np.zeros((H, W), np.float32)
    roi_mask[head_roi[1]:head_roi[3], head_roi[0]:head_roi[2]] = 1
    # alignment mask: head ROI minus eyes and mouth
    al_mask = roi_mask.copy()
    ebx = expand(eb, 12, 12, 12, 12, W, H)
    mbx = expand(mb, 14, 14, 14, 14, W, H)
    al_mask[ebx[1]:ebx[3], ebx[0]:ebx[2]] = 0
    al_mask[mbx[1]:mbx[3], mbx[0]:mbx[2]] = 0

    # ---- align expressions and measure the face zone as the union of expression diffs
    aligned = {"neutral": master}
    report = {}
    for e in exprs:
        if e == "neutral":
            continue
        a, cc, _ = align(load(src_of(e)), master, al_mask)
        aligned[e] = a
        report[e] = round(float(cc), 4)
    union = np.zeros((H, W), bool)
    for e, a in aligned.items():
        if e == "neutral":
            continue
        d = diffmap(a, master) * roi_mask * hb
        union |= main_components(d > 0.09, 120)
    fb = bbox(union | eye_raw | mouth_raw)
    # clamp the face zone to the facial features (brows..chin, eye span) so hair edits stay out
    fb = (max(fb[0], int(eb[0] - 0.10 * ew)), max(fb[1], int(eb[1] - 0.42 * ew)),
          min(fb[2], int(eb[2] + 0.10 * ew)), min(fb[3], int(mb[3] + 0.28 * ew)))
    fbox = expand(fb, 16, 10, 16, 14, W, H)
    face_m = ellipse_mask((H, W), fbox, 9)
    eye_box = expand(eb, 14, 10, 14, 12, W, H)
    eye_m = ellipse_mask((H, W), eye_box, 5)
    mouth_box = expand(mb, 16, 12, 16, 14, W, H)
    mouth_m = ellipse_mask((H, W), mouth_box, 4)
    ring = lambda m: ((m > 0.08) & (m < 0.7)).astype(np.float32)

    out_dir = OUT / name
    man = {"w": W, "h": H, "bodies": {}, "faces": {},
           "zones": {"face": fbox, "eyes": eye_box, "mouth": mouth_box}}

    # ---- bodies aligned to master on the head region
    body_cc = {}
    body_imgs = []
    for pose, rel in cfg["bodies"].items():
        img = load(base_dir / rel)
        if rel != "master.png":
            img, cc, _ = align(img, master, roi_mask)
            body_cc[pose] = round(float(cc), 4)
        body_imgs.append(img)
        save_webp(img, out_dir / f"body_{pose}.webp", 90)
        man["bodies"][pose] = f"assets/chars/{name}/body_{pose}.webp"
    # face layers are shared by every body: never paint where a body is transparent but the master
    # is not (e.g. the master's shirt collar must not show up beside a T-shirt body's neck)
    if len(body_imgs) > 1:
        min_a = np.minimum.reduce([b[..., 3] for b in body_imgs])
        ma = master[..., 3]
        # ratio, not difference: faint antialiased strokes (collar outlines) must vanish too
        support = np.where(ma > 0.02, np.clip(min_a / np.maximum(ma, 1e-3), 0, 1), 1.0).astype(np.float32)
        support = cv2.GaussianBlur(cv2.erode(support, np.ones((3, 3), np.uint8)), (0, 0), 1.0)
        face_m = face_m * support

    # ---- faces / eyes / mouths
    var_cc = {}
    for e in exprs:
        base = aligned[e]
        fl = color_match(base, master, ring(face_m)) if e != "neutral" else base
        face_img, frect = crop_layer(fl, face_m)
        save_webp(face_img, out_dir / f"face_{e}.webp")
        entry = {"face": {"src": f"assets/chars/{name}/face_{e}.webp", "rect": frect}, "eyes": None, "mouth": []}
        # variant alignment mask: head ROI minus the zone being changed
        if e not in cfg["noblink"] and var_of(e, "blink").exists():
            am = roi_mask * (1 - (eye_m > 0.02))
            v, cc, _ = align(load(var_of(e, "blink")), base, am)
            var_cc[f"{e}_blink"] = round(float(cc), 4)
            v = color_match(v, base, ring(eye_m))
            img, rect = crop_layer(v, eye_m)
            save_webp(img, out_dir / f"eyes_{e}.webp")
            entry["eyes"] = {"src": f"assets/chars/{name}/eyes_{e}.webp", "rect": rect}
        for k, tag in ((1, "m1"), (2, "m2")):
            p = var_of(e, tag)
            if not p.exists():
                continue
            am = roi_mask * (1 - (mouth_m > 0.02))
            v, cc, _ = align(load(p), base, am)
            var_cc[f"{e}_{tag}"] = round(float(cc), 4)
            v = color_match(v, base, ring(mouth_m))
            img, rect = crop_layer(v, mouth_m)
            save_webp(img, out_dir / f"mouth_{e}_{k}.webp")
            entry["mouth"].append({"src": f"assets/chars/{name}/mouth_{e}_{k}.webp", "rect": rect})
        man["faces"][e] = entry

    print(name, "zones", man["zones"], flush=True)
    print("  expr ecc", report, flush=True)
    print("  body ecc", body_cc, flush=True)
    low = {k: v for k, v in {**report, **var_cc, **body_cc}.items() if not (v > 0.95)}
    if low:
        print("  low-correlation alignments:", low, flush=True)

    if preview:
        WORK.mkdir(parents=True, exist_ok=True)
        combos = []
        poses = list(cfg["bodies"].keys())
        for i, e in enumerate(exprs):
            pose = poses[i % len(poses)]
            for state in ("open", "blink", "m1", "m2"):
                combos.append((pose, e, state))
        tiles = []
        for pose, e, state in combos:
            canvas = load(base_dir / cfg["bodies"][pose]) if cfg["bodies"][pose] == "master.png" else None
            body = np.asarray(Image.open(out_dir / f"body_{pose}.webp").convert("RGBA")).astype(np.float32) / 255
            c = body.copy()

            def over(layer):
                src = np.asarray(Image.open(ROOT / "public" / layer["src"]).convert("RGBA")).astype(np.float32) / 255
                x, y, w, h = layer["rect"]
                dst = c[y:y + h, x:x + w]
                a = src[..., 3:4]
                dst[..., :3] = src[..., :3] * a + dst[..., :3] * (1 - a)
                dst[..., 3:4] = a + dst[..., 3:4] * (1 - a)

            f = man["faces"][e]
            over(f["face"])
            if state == "blink" and f["eyes"]:
                over(f["eyes"])
            if state in ("m1", "m2") and len(f["mouth"]) >= (1 if state == "m1" else 2):
                over(f["mouth"][0 if state == "m1" else 1])
            x0, y0, x1, y1 = expand(man["zones"]["face"], 40, 60, 40, 50, W, H)
            t = c[y0:y1, x0:x1]
            rgb = t[..., :3] * t[..., 3:4] + 0.45 * (1 - t[..., 3:4])
            tiles.append(((rgb * 255).astype(np.uint8), f"{e}/{state}"))
        th = 190
        cells = []
        for img, lab in tiles:
            s = th / img.shape[0]
            cells.append(cv2.resize(img, (int(img.shape[1] * s), th), interpolation=cv2.INTER_AREA))
        cols = 8
        cw = max(c.shape[1] for c in cells)
        rows = (len(cells) + cols - 1) // cols
        sheet = np.full((rows * (th + 4), cols * (cw + 4), 3), 40, np.uint8)
        for k, cimg in enumerate(cells):
            r, q = divmod(k, cols)
            sheet[r * (th + 4):r * (th + 4) + th, q * (cw + 4):q * (cw + 4) + cimg.shape[1]] = cimg
        Image.fromarray(sheet).save(WORK / f"preview_{name}.jpg", quality=90)
        print("  preview", WORK / f"preview_{name}.jpg", sheet.shape[1], "x", sheet.shape[0])
        # full-resolution seam check on a few demanding combinations
        detail = []
        picks = [(poses[-1], exprs[min(7, len(exprs) - 1)], "m2"), (poses[len(poses) // 2], exprs[-2], "blink"),
                 (poses[1 % len(poses)], exprs[len(exprs) // 2], "m1"), (poses[0], exprs[1], "m2")]
        for pose, e, state in picks:
            body = np.asarray(Image.open(out_dir / f"body_{pose}.webp").convert("RGBA")).astype(np.float32) / 255
            c = body.copy()
            f = man["faces"][e]
            layers = [f["face"]]
            if state == "blink" and f["eyes"]:
                layers.append(f["eyes"])
            if state in ("m1", "m2") and f["mouth"]:
                layers.append(f["mouth"][min(len(f["mouth"]) - 1, 0 if state == "m1" else 1)])
            for layer in layers:
                src = np.asarray(Image.open(ROOT / "public" / layer["src"]).convert("RGBA")).astype(np.float32) / 255
                x, y, w, h = layer["rect"]
                dst = c[y:y + h, x:x + w]
                a = src[..., 3:4]
                dst[..., :3] = src[..., :3] * a + dst[..., :3] * (1 - a)
                dst[..., 3:4] = a + dst[..., 3:4] * (1 - a)
            x0, y0, x1, y1 = expand(man["zones"]["face"], 30, 40, 30, 40, W, H)
            t = c[y0:y1, x0:x1]
            detail.append(((t[..., :3] * t[..., 3:4] + 0.45 * (1 - t[..., 3:4])) * 255).astype(np.uint8))
        hmax = max(d.shape[0] for d in detail)
        row = np.concatenate([np.pad(d, ((0, hmax - d.shape[0]), (2, 2), (0, 0)), constant_values=30) for d in detail], axis=1)
        s = min(1.0, 1900 / row.shape[1])
        img = Image.fromarray(row)
        if s < 1:
            img = img.resize((int(row.shape[1] * s), int(row.shape[0] * s)), Image.LANCZOS)
        img.save(WORK / f"detail_{name}.jpg", quality=92)
        print("  detail", WORK / f"detail_{name}.jpg", img.size, [f"{p}/{e}/{s_}" for p, e, s_ in picks])
    return man


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    preview = "--preview" in sys.argv
    names = args or list(CHARS.keys())
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    for n in names:
        manifest[n] = build(n, preview)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print("manifest ->", MANIFEST)
