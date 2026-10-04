"""Draw boxes (x0 y0 x1 y1) over an image crop with a 20px grid for coordinate checks.
Usage: python draw_boxes.py img.png out.jpg cx0 cy0 cx1 cy1 [x0,y0,x1,y1 ...] [--scale 2]"""
import sys

from PIL import Image, ImageDraw

args = sys.argv[1:]
scale = 2
if "--scale" in args:
    i = args.index("--scale")
    scale = float(args[i + 1])
    del args[i:i + 2]
src, out = args[0], args[1]
cx0, cy0, cx1, cy1 = (int(v) for v in args[2:6])
boxes = [tuple(int(v) for v in b.split(",")) for b in args[6:]]
im = Image.open(src).convert("RGBA")
bg = Image.new("RGBA", im.size, (128, 128, 128, 255))
bg.alpha_composite(im)
c = bg.crop((cx0, cy0, cx1, cy1)).resize((int((cx1 - cx0) * scale), int((cy1 - cy0) * scale)), Image.LANCZOS)
d = ImageDraw.Draw(c)
for gx in range(cx0 - cx0 % 20, cx1, 20):
    x = (gx - cx0) * scale
    d.line([(x, 0), (x, c.height)], fill=(255, 255, 255, 60) if gx % 100 else (255, 255, 0, 140))
    if gx % 100 == 0:
        d.text((x + 2, 2), str(gx), fill=(255, 255, 0, 255))
for gy in range(cy0 - cy0 % 20, cy1, 20):
    y = (gy - cy0) * scale
    d.line([(0, y), (c.width, y)], fill=(255, 255, 255, 60) if gy % 100 else (255, 255, 0, 140))
    if gy % 100 == 0:
        d.text((2, y + 2), str(gy), fill=(255, 255, 0, 255))
cols = [(255, 60, 60, 255), (60, 255, 60, 255), (60, 160, 255, 255), (255, 0, 255, 255)]
for k, (x0, y0, x1, y1) in enumerate(boxes):
    d.rectangle([(x0 - cx0) * scale, (y0 - cy0) * scale, (x1 - cx0) * scale, (y1 - cy0) * scale],
                outline=cols[k % len(cols)], width=2)
c.convert("RGB").save(out, quality=90)
print(out, c.size)
