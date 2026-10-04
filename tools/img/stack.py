"""Stack images vertically into one review image, scaled to fit within --max (default 1900).
Usage: python stack.py out.jpg img1 img2 ... [--max 1900]"""
import sys

from PIL import Image

args = sys.argv[1:]
mx = 1900
if "--max" in args:
    i = args.index("--max")
    mx = int(args[i + 1])
    del args[i:i + 2]
out, files = args[0], args[1:]
ims = [Image.open(f).convert("RGB") for f in files]
W = max(im.width for im in ims)
H = sum(im.height for im in ims) + 6 * (len(ims) - 1)
sheet = Image.new("RGB", (W, H), (40, 40, 44))
y = 0
for im in ims:
    sheet.paste(im, (0, y))
    y += im.height + 6
s = min(1.0, mx / W, mx / H)
if s < 1:
    sheet = sheet.resize((int(W * s), int(H * s)), Image.LANCZOS)
sheet.save(out, quality=88)
print(out, sheet.size)
