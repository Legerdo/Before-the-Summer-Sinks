"""Export backgrounds/CGs to game-ready WebP (1920x1280, slight sharpen) + CG thumbnails + app icon.
Sources: art_src/bg/<id>.(png|jpg|webp), art_src/cg/<id>.(png|jpg|webp); the file name is the asset id.
A source newer than its WebP is re-exported, so replacing an image = overwrite the source and re-run.
Usage: python export_images.py"""
import json
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
SRC_BG = ROOT / "art_src" / "bg"
SRC_CG = ROOT / "art_src" / "cg"
OUT_BG = ROOT / "public" / "assets" / "bg"
OUT_CG = ROOT / "public" / "assets" / "cg"
EXTS = (".png", ".jpg", ".jpeg", ".webp")
# gallery titles: art_src/cg/titles.json ({"<cg id>": "title"}); the file name is the asset id
CG_TITLES = json.loads((SRC_CG / "titles.json").read_text(encoding="utf-8")) if (SRC_CG / "titles.json").exists() else {}
# app icon: square crop (x0, y0, x1, y1) of the heroine's master sprite
ICON_SRC, ICON_BOX = ROOT / "art_src" / "chars" / "yunseul" / "master.png", (352, 120, 672, 440)


def sources(d: Path):
    return sorted(p for p in d.iterdir() if p.suffix.lower() in EXTS)


def export(src: Path, dst: Path, size=(1920, 1280), q=88):
    im = Image.open(src).convert("RGB")
    im = im.resize(size, Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=1.2, percent=45, threshold=2))
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "WEBP", quality=q, method=6)
    return im


def main():
    meta = {"bg": {}, "cg": {}}
    for p in sources(SRC_BG):
        dst = OUT_BG / f"{p.stem}.webp"
        if not dst.exists() or dst.stat().st_mtime < p.stat().st_mtime:
            export(p, dst)
        meta["bg"][p.stem] = {"src": f"assets/bg/{p.stem}.webp"}
    for p in sources(SRC_CG):
        cid, src = p.stem, p
        dst = OUT_CG / f"{cid}.webp"
        th = OUT_CG / "thumb" / f"{cid}.webp"
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            im = export(src, dst)
            w, h = im.size
            ch = int(w * 9 / 16)
            crop = im.crop((0, (h - ch) // 2, w, (h - ch) // 2 + ch)).resize((480, 270), Image.LANCZOS)
            th.parent.mkdir(parents=True, exist_ok=True)
            crop.save(th, "WEBP", quality=82, method=6)
        meta["cg"][cid] = {"src": f"assets/cg/{cid}.webp", "thumb": f"assets/cg/thumb/{cid}.webp", "title": CG_TITLES.get(cid, cid)}
    # app icon from the heroine's face
    face = Image.open(ICON_SRC).convert("RGBA").crop(ICON_BOX)
    bg = Image.new("RGBA", face.size, (18, 46, 56, 255))
    bg.alpha_composite(face)
    icon = bg.resize((256, 256), Image.LANCZOS)
    icon.save(ROOT / "public" / "icon.png")
    (ROOT / "build").mkdir(exist_ok=True)
    icon.save(ROOT / "build" / "icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    (ROOT / "public" / "data" / "images.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print("bg", len(meta["bg"]), "cg", len(meta["cg"]))


if __name__ == "__main__":
    main()
