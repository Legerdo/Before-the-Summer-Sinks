"""Build a labeled contact sheet from images (keeps the sheet within max_w x max_h).

Usage: python contact.py out.png cols cell_h img1 [img2 ...] [--bg gray|check|white|black] [--max 1900]
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

args = sys.argv[1:]
bg_mode = "gray"
max_side = 1900
crop_box = None
if "--crop" in args:
    i = args.index("--crop")
    crop_box = tuple(int(v) for v in args[i + 1:i + 5])
    del args[i:i + 5]
if "--bg" in args:
    i = args.index("--bg")
    bg_mode = args[i + 1]
    del args[i:i + 2]
if "--max" in args:
    i = args.index("--max")
    max_side = int(args[i + 1])
    del args[i:i + 2]
out, cols, cell_h, files = args[0], int(args[1]), int(args[2]), args[3:]
ims = [Image.open(f).convert("RGBA") for f in files]
if crop_box:
    ims = [im.crop(crop_box) for im in ims]
cells = []
for im in ims:
    s = cell_h / im.height
    cells.append(im.resize((max(1, int(im.width * s)), cell_h), Image.LANCZOS))
cell_w = max(c.width for c in cells)
rows = (len(cells) + cols - 1) // cols
pad, label_h = 8, 22
W = cols * (cell_w + pad) + pad
H = rows * (cell_h + pad + label_h) + pad
sheet = Image.new("RGBA", (W, H), (60, 60, 64, 255))
try:
    font = ImageFont.truetype("arial.ttf", 15)
except OSError:
    font = ImageFont.load_default()
d = ImageDraw.Draw(sheet)
for k, (c, f) in enumerate(zip(cells, files)):
    r, q = divmod(k, cols)
    x = pad + q * (cell_w + pad)
    y = pad + r * (cell_h + pad + label_h)
    if bg_mode == "check":
        tile = Image.new("RGBA", (cell_w, cell_h), (200, 200, 200, 255))
        td = ImageDraw.Draw(tile)
        for yy in range(0, cell_h, 16):
            for xx in range(0, cell_w, 16):
                if (xx // 16 + yy // 16) % 2:
                    td.rectangle([xx, yy, xx + 15, yy + 15], fill=(235, 235, 235, 255))
    else:
        col = {"gray": (128, 128, 128, 255), "white": (255, 255, 255, 255), "black": (0, 0, 0, 255),
               "green": (0, 177, 64, 255)}.get(bg_mode, (128, 128, 128, 255))
        tile = Image.new("RGBA", (cell_w, cell_h), col)
    tile.alpha_composite(c, ((cell_w - c.width) // 2, 0))
    sheet.alpha_composite(tile, (x, y))
    d.text((x + 2, y + cell_h + 3), Path(f).stem[:40], fill=(240, 240, 240, 255), font=font)
scale = min(1.0, max_side / max(W, H))
if scale < 1.0:
    sheet = sheet.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
sheet.convert("RGB").save(out, quality=90)
print(out, sheet.size)
