import sys
from PIL import Image, ImageDraw
d = sys.argv[1]  # dir holding raw_front.png from blockbench_render.mjs
REF = sys.argv[2] if len(sys.argv) > 2 else 'reference.jpg'
def on_white(path, h):
    im = Image.open(path).convert('RGBA')
    bg = Image.new('RGBA', im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
    bg = bg.convert('RGB')
    return bg.resize((round(bg.width * h / bg.height), h), Image.LANCZOS)
ref = Image.open(REF).convert('RGB')
# crop reference to its content bbox (same as autocrop)
import numpy as np
a = np.array(ref.convert('L')) < 200
ys, xs = np.where(a); ref = ref.crop((xs.min(), ys.min(), xs.max()+1, ys.max()+1))
H = 800
r = ref.resize((round(ref.width * H / ref.height), H), Image.LANCZOS)
f = on_white(d + '/raw_front.png', H)
out = Image.new('RGB', (r.width + f.width + 30, H), 'white')
out.paste(r, (0, 0)); out.paste(f, (r.width + 30, 0))
out.save(d + '/compare.png')
# overlay: reference in red, model in blue
f2 = f.resize(r.size, Image.LANCZOS)
ra = np.array(r.convert('L')) < 150; fa = np.array(f2.convert('L')) < 150
ov = np.full(ra.shape + (3,), 255, np.uint8)
ov[ra & ~fa] = (230, 60, 60); ov[fa & ~ra] = (60, 90, 230); ov[ra & fa] = (40, 40, 40)
Image.fromarray(ov).save(d + '/overlay.png')
