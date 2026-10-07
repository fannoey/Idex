#!/usr/bin/env python3
"""Generate the "VLONE hoodie + chain cargo pants" Minecraft Bedrock add-on.

Everything (geometry, textures, attachables, items, recipes, icons, preview
renders and the .mcaddon) is produced from the part list in this file, so the
model and its texture atlas always stay in sync.

Run:  python3 tools/build_outfit.py
"""
import json
import math
import os
import shutil
import uuid
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "vlone_outfit")
RP = os.path.join(OUT, "Vlone_Outfit_RP")
BP = os.path.join(OUT, "Vlone_Outfit_BP")
DIST = os.path.join(ROOT, "dist")
PREVIEW = os.path.join(ROOT, "preview")

NS = "idex"
PX = 8            # texture pixels per model unit (8x vanilla detail)
ATLAS_W = 64      # atlas width in model units (image = ATLAS_W * PX)

# Player skeleton (Bedrock humanoid). Attachable bones with these names follow
# the wearer's bones automatically.
PLAYER_BONES = {
    "body": dict(pivot=[0, 24, 0], parent=None),
    "head": dict(pivot=[0, 24, 0], parent="body"),
    "rightArm": dict(pivot=[-5, 22, 0], parent="body"),
    "leftArm": dict(pivot=[5, 22, 0], parent="body"),
    "rightLeg": dict(pivot=[-1.9, 12, 0], parent=None),
    "leftLeg": dict(pivot=[1.9, 12, 0], parent=None),
}


class Part:
    """One box-UV cube. size must be integers (box UV); inflate adds thickness."""

    def __init__(self, name, bone, origin, size, inflate=0.0, painter=None, **kw):
        self.name, self.bone = name, bone
        self.origin, self.size, self.inflate = list(origin), list(size), inflate
        self.painter = painter
        self.kw = kw
        self.uv = None

    @property
    def region(self):
        w, h, d = self.size
        return 2 * (w + d), d + h

    def faces_px(self):
        """Texture rectangle (x, y, w, h) in pixels for each face."""
        u, v = self.uv
        w, h, d = self.size
        r = {
            "top": (u + d, v, w, d),
            "bottom": (u + d + w, v, w, d),
            "right": (u, v + d, d, h),          # player's right side (-X)
            "front": (u + d, v + d, w, h),      # -Z
            "left": (u + d + w, v + d, d, h),   # +X
            "back": (u + 2 * d + w, v + d, w, h),
        }
        return {k: tuple(int(round(c * PX)) for c in val) for k, val in r.items()}

    def bounds(self):
        i = self.inflate
        lo = [self.origin[k] - i for k in range(3)]
        hi = [self.origin[k] + self.size[k] + i for k in range(3)]
        return lo, hi

    def faces_3d(self):
        """(name, P0, U, V, normal): P0 = texel (0,0) corner, U along columns, V along rows."""
        (x0, y0, z0), (x1, y1, z1) = self.bounds()
        W, H, D = x1 - x0, y1 - y0, z1 - z0
        A = np.array
        return [
            ("front", A([x0, y1, z0]), A([W, 0, 0]), A([0, -H, 0]), A([0, 0, -1])),
            ("back", A([x1, y1, z1]), A([-W, 0, 0]), A([0, -H, 0]), A([0, 0, 1])),
            ("right", A([x0, y1, z1]), A([0, 0, -D]), A([0, -H, 0]), A([-1, 0, 0])),
            ("left", A([x1, y1, z0]), A([0, 0, D]), A([0, -H, 0]), A([1, 0, 0])),
            ("top", A([x0, y1, z1]), A([W, 0, 0]), A([0, 0, -D]), A([0, 1, 0])),
            ("bottom", A([x0, y0, z0]), A([W, 0, 0]), A([0, 0, D]), A([0, -1, 0])),
        ]

    def cube_json(self):
        c = {"origin": [round(o, 4) for o in self.origin], "size": self.size,
             "uv": [int(self.uv[0]), int(self.uv[1])]}
        if self.inflate:
            c["inflate"] = self.inflate
        return c


def pack(parts, width=ATLAS_W, pad=1):
    """Shelf-pack box-UV regions; returns atlas height (power of two, units)."""
    order = sorted(parts, key=lambda p: (-p.region[1], -p.region[0]))
    x = y = shelf = 0
    for p in order:
        w, h = p.region
        if x + w > width:
            x, y, shelf = 0, y + shelf + pad, 0
        p.uv = (x, y)
        x += w + pad
        shelf = max(shelf, h)
    used = y + shelf
    height = 16
    while height < used:
        height *= 2
    return height


# --------------------------------------------------------------------------
# painting helpers (atlas = float RGBA numpy array)
# --------------------------------------------------------------------------
rng = np.random.default_rng(20261007)


def fill(a, r, base, noise=3.0, alpha=255):
    x, y, w, h = r
    if w <= 0 or h <= 0:
        return
    a[y:y + h, x:x + w, :3] = np.clip(np.array(base, float) + rng.normal(0, noise, (h, w, 1)), 0, 255)
    a[y:y + h, x:x + w, 3] = alpha


def clear(a, r):
    x, y, w, h = r
    a[y:y + h, x:x + w] = 0


def ribbed(a, r, c1=(17, 17, 19), c2=(29, 29, 32), period=2):
    x, y, w, h = r
    if w <= 0 or h <= 0:
        return
    stripe = ((np.arange(w) // period) % 2).astype(bool)
    base = np.where(stripe[None, :, None], np.array(c1, float), np.array(c2, float))
    a[y:y + h, x:x + w, :3] = np.clip(base + rng.normal(0, 1.5, (h, w, 1)), 0, 255)
    a[y:y + h, x:x + w, 3] = 255
    shade(a, (x, y, w, 1), -6)
    shade(a, (x, y + h - 1, w, 1), -6)


def shade(a, r, amt):
    x, y, w, h = r
    if w <= 0 or h <= 0:
        return
    a[y:y + h, x:x + w, :3] = np.clip(a[y:y + h, x:x + w, :3] + amt, 0, 255)


def put(a, x, y, col):
    if 0 <= y < a.shape[0] and 0 <= x < a.shape[1]:
        a[y, x, :3] = col
        a[y, x, 3] = 255


def stitch_h(a, x0, x1, y, col=(135, 135, 140), on=2, off=1):
    for i, x in enumerate(range(x0, x1)):
        if i % (on + off) < on:
            put(a, x, y, col)


def stitch_v(a, x, y0, y1, col=(135, 135, 140), on=2, off=1):
    for i, y in enumerate(range(y0, y1)):
        if i % (on + off) < on:
            put(a, x, y, col)


def denim(a, r, base=(50, 50, 55), fade=None, creases=0):
    x, y, w, h = r
    if w <= 0 or h <= 0:
        return
    yy, xx = np.mgrid[0:h, 0:w]
    c = np.array(base, float)[None, None, :] + rng.normal(0, 4.5, (h, w, 1))
    c += (((xx + yy) % 4) == 0)[..., None] * 5.0                       # twill
    c += rng.normal(0, 3.0, (1, w, 1))                                   # vertical wash streaks
    if fade:
        cx, cy, sx, sy, amt = fade
        g = amt * np.exp(-(((xx / max(w, 1) - cx) / sx) ** 2 + ((yy / max(h, 1) - cy) / sy) ** 2))
        c += g[..., None]
    for _ in range(creases):                                             # bunched folds
        cy0 = rng.integers(0, h)
        cx0 = rng.integers(0, max(w - 6, 1))
        ln = rng.integers(4, max(w // 2, 5))
        c[cy0, cx0:cx0 + ln] -= 14
        if cy0 + 1 < h:
            c[cy0 + 1, cx0:cx0 + ln] += 7
    a[y:y + h, x:x + w, :3] = np.clip(c, 0, 255)
    a[y:y + h, x:x + w, 3] = 255


SILVER = (196, 198, 204)
SILVER_DK = (92, 94, 100)


def eyelet(a, cx, cy):
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            d = dx * dx + dy * dy
            if d <= 5:
                put(a, cx + dx, cy + dy, SILVER if d >= 2 else (20, 20, 22))
    put(a, cx - 1, cy - 2, (240, 240, 245))


def overlay_pil(a, r, draw_fn, ss=4, binary=True):
    """Draw with PIL (supersampled) into region r, alpha-composited over a."""
    x, y, w, h = r
    if w <= 0 or h <= 0:
        return
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im), ss)
    im = np.asarray(im.resize((w, h), Image.BOX)).astype(float)   # Pillow returns straight alpha
    al = im[..., 3:4] / 255.0
    if binary:
        al = (al >= 0.45).astype(float)
    rgb = im[..., :3]
    dst = a[y:y + h, x:x + w]
    dst[..., :3] = rgb * al + dst[..., :3] * (1 - al)
    dst[..., 3:4] = np.maximum(dst[..., 3:4], al * 255)


def mirror_plane_back(a, f):
    """Zero-depth planes: back face = mirrored front so both sides match."""
    x, y, w, h = f["front"]
    bx, by, _, _ = f["back"]
    a[by:by + h, bx:bx + w] = a[y:y + h, x:x + w][:, ::-1]


# --------------------------------------------------------------------------
# HOODIE painters
# --------------------------------------------------------------------------
BLACK = (22, 22, 25)


def letter_polys(ch):
    def R(x0, y0, x1, y1):
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if ch == "V":
        return [[(0.6, 0), (4.3, 0), (6.5, 34), (4.8, 34)], [(7.8, 0), (9.6, 0), (6.5, 34), (5.8, 34)],
                R(0, 0, 5.1, 1.3), R(7.0, 0, 10.8, 1.3)]
    if ch == "L":
        return [R(1.6, 0, 4.6, 34), R(0, 0, 6.2, 1.3), R(0, 32.6, 10.8, 34), R(9.6, 27.5, 10.8, 34)]
    if ch == "N":
        return [R(1.0, 0, 2.4, 34), R(8.4, 0, 9.8, 34), [(1.0, 0), (4.3, 0), (9.8, 34), (6.6, 34)],
                R(0, 0, 4.3, 1.3), R(7.2, 0, 11, 1.3), R(0, 32.7, 3.4, 34)]
    if ch == "E":
        return [R(1.6, 0, 4.6, 34), R(0, 0, 10.6, 1.6), R(4.6, 16.2, 8.4, 17.9), R(0, 32.4, 10.8, 34),
                R(9.5, 0, 10.6, 6.5), R(9.6, 27.5, 10.8, 34), R(7.8, 13.5, 8.6, 20.5)]
    return []


def paint_front_logo(a, r):
    """Tall serif "VLONE" in reflective grey-blue (bright V L, darker O N E)."""
    x, y, w, h = r
    colors = [(178, 193, 203), (166, 180, 190), (112, 118, 125), (98, 103, 110), (90, 95, 102)]
    top = int(h * 0.42)

    def draw(d, s):
        cx = 2.1
        for ch, col in zip("VLONE", colors):
            if ch == "O":
                d.ellipse([(cx + 0.2) * s, top * s, (cx + 10.8) * s, (top + 34) * s], fill=col + (255,))
                d.ellipse([(cx + 3.4) * s, (top + 2.2) * s, (cx + 7.6) * s, (top + 31.8) * s], fill=(0, 0, 0, 0))
            else:
                for poly in letter_polys(ch):
                    d.polygon([((cx + px) * s, (top + py) * s) for px, py in poly], fill=col + (255,))
            cx += 11.0 + 1.2
    al, rgb = pil_layer(w, h, draw)
    rgb += rng.normal(0, 6, rgb.shape)                                    # print grain
    dst = a[y:y + h, x:x + w]
    dst[..., :3] = np.clip(rgb * al + dst[..., :3] * (1 - al), 0, 255)


def pil_layer(w, h, draw_fn, ss=4):
    """Antialiased PIL drawing -> (alpha[h,w,1], straight rgb[h,w,3])."""
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im), ss)
    im = np.asarray(im.resize((w, h), Image.BOX)).astype(float)
    return im[..., 3:4] / 255.0, im[..., :3].copy()


def paint_back_v(a, r):
    """Big distressed "V" on the back."""
    x, y, w, h = r
    top, left = int(h * 0.44), 10
    col = (200, 214, 223)

    def draw(d, s):
        polys = [[(3, 2), (16, 2), (25.5, 40), (19, 40)], [(29, 2), (37, 2), (24.5, 40), (21.5, 40)],
                 [(0, 0), (19, 0), (19, 3.2), (0, 3.2)], [(26.5, 0), (42, 0), (42, 3.2), (26.5, 3.2)]]
        for p in polys:
            d.polygon([((left + px) * s, (top + py) * s) for px, py in p], fill=col + (255,))
        # cracks / torn paint
        for _ in range(9):
            px, py = left + rng.uniform(4, 36), top + rng.uniform(4, 36)
            pts = [(px * s, py * s)]
            for _ in range(4):
                px += rng.uniform(-3, 3)
                py += rng.uniform(-1, 3)
                pts.append((px * s, py * s))
            d.line(pts, fill=BLACK + (255,), width=int(s * 0.9))
    al, rgb = pil_layer(w, h, draw)
    edge_noise = rng.random(al.shape) < 0.25
    al = np.where((al > 0.05) & (al < 0.95) & edge_noise, 0, al)            # ragged edges
    speck = rng.random(al.shape) < 0.07
    al = np.where(speck & (al > 0.5), 0.15, al)                              # worn specks
    rgb += rng.normal(0, 7, rgb.shape)
    rgb[..., 2] += 6                                                          # slight blue cast
    dst = a[y:y + h, x:x + w]
    dst[..., :3] = np.clip(rgb * al + dst[..., :3] * (1 - al), 0, 255)


def p_torso(a, f, part):
    for k in ("right", "left", "front", "back", "top"):
        fill(a, f[k], BLACK)
    fill(a, f["bottom"], (8, 8, 9), 1)
    # side seams + soft folds
    for k in ("right", "left"):
        x, y, w, h = f[k]
        stitch_v(a, x + w // 2, y, y + h, (34, 34, 38), 3, 1)
    for k in ("front", "back"):
        x, y, w, h = f[k]
        for _ in range(10):
            fy, fx = y + rng.integers(4, h - 4), x + rng.integers(0, w - 10)
            shade(a, (fx, fy, int(rng.integers(5, 12)), 1), -7)
            shade(a, (fx, fy + 1, int(rng.integers(5, 12)), 1), 4)
    paint_front_logo(a, f["front"])
    paint_back_v(a, f["back"])
    # neck opening on top
    x, y, w, h = f["top"]

    def neck(d, s):
        d.ellipse([w * 0.18 * s, h * 0.12 * s, w * 0.82 * s, h * 0.95 * s], fill=(10, 10, 11, 255))
        d.ellipse([w * 0.14 * s, h * 0.05 * s, w * 0.86 * s, h * 1.0 * s], outline=(34, 34, 38, 255), width=s)
    overlay_pil(a, f["top"], neck)


def p_rib(a, f, part):
    for k in ("right", "left", "front", "back"):
        ribbed(a, f[k])
    fill(a, f["top"], (12, 12, 13), 1)
    fill(a, f["bottom"], (8, 8, 9), 1)


def p_sleeve(a, f, part):
    for k in ("right", "left", "front", "back", "top"):
        fill(a, f[k], BLACK)
        x, y, w, h = f[k]
        for _ in range(6):                                                   # bunched folds
            fy, fx = y + rng.integers(h // 2, h - 2), x + rng.integers(0, max(w - 8, 1))
            shade(a, (fx, fy, int(rng.integers(4, 9)), 1), -8)
            shade(a, (fx, fy - 1, int(rng.integers(4, 9)), 1), 5)
    fill(a, f["bottom"], (8, 8, 9), 1)
    # shoulder seam
    x, y, w, h = f["right" if part.bone == "rightArm" else "left"]
    stitch_h(a, x, x + w, y + 6, (36, 36, 40), 3, 1)


def p_hood_shell(a, f, part):
    for k in ("right", "left", "back", "top"):
        fill(a, f[k], BLACK)
    # centre seam running over top and back
    x, y, w, h = f["top"]
    stitch_v(a, x + w // 2, y, y + h, (38, 38, 42), 3, 1)
    shade(a, (x + w // 2 - 1, y, 1, h), -6)
    x, y, w, h = f["back"]
    stitch_v(a, x + w // 2, y, y + h, (38, 38, 42), 3, 1)
    shade(a, (x + w // 2 - 1, y, 1, h), -6)
    # face opening + open bottom are see-through
    clear(a, f["front"])
    clear(a, f["bottom"])


def p_hood_rim(a, f, part):
    for k in f:
        fill(a, f[k], (27, 27, 31))
    x, y, w, h = f["front"]
    if w >= h:
        stitch_h(a, x + 1, x + w - 1, y + h - 3, (44, 44, 50), 3, 1)
    else:
        stitch_v(a, x + w // 2, y + 1, y + h - 1, (44, 44, 50), 3, 1)


def p_hood_down(a, f, part):
    for k in ("right", "left", "front", "back"):
        fill(a, f[k], BLACK)
    x, y, w, h = f["back"]
    stitch_v(a, x + w // 2, y, y + h, (38, 38, 42), 3, 1)
    shade(a, (x + w // 2 - 1, y, 1, h), -6)
    shade(a, (x, y + h - 2, w, 2), -5)                                       # rounded lower edge
    fill(a, f["top"], (11, 11, 12), 1)
    fill(a, f["bottom"], (14, 14, 16), 1)


def p_hood_roll(a, f, part):
    for k in ("right", "left", "front", "back"):
        fill(a, f[k], (25, 25, 29))
        x, y, w, h = f[k]
        stitch_h(a, x, x + w, y + 2, (40, 40, 46), 3, 1)
    fill(a, f["top"], (10, 10, 11), 1)                                       # hood opening
    fill(a, f["bottom"], (14, 14, 16), 1)


def p_drawstring(a, f, part):
    for k in f:
        clear(a, f[k])
    x, y, w, h = f["front"]
    cx = x + w // 2 - 1
    for yy in range(y, y + h - 7):
        put(a, cx, yy, (58, 58, 64))
        put(a, cx + 1, yy, (44, 44, 49))
    for yy in range(y + h - 7, y + h):                                        # metal aglet
        put(a, cx, yy, (215, 215, 220))
        put(a, cx + 1, yy, (150, 150, 158))
    mirror_plane_back(a, f)


# --------------------------------------------------------------------------
# PANTS painters
# --------------------------------------------------------------------------
STRAP = (24, 24, 27)


def outer_cols(f_rect, bone, width):
    """x range of the outer edge on a front/back face for this leg."""
    x, y, w, h = f_rect
    return (x, x + width) if bone == "rightLeg" else (x + w - width, x + w)


def p_waistband(a, f, part):
    for k in ("right", "left", "front", "back"):
        x, y, w, h = f[k]
        denim(a, f[k], (40, 40, 44))
        for cx in range(x + 1, x + w, 3):                                    # gathered elastic
            shade(a, (cx, y + 2, 1, h - 4), -10)
        stitch_h(a, x, x + w, y + 1)
        stitch_h(a, x, x + w, y + h - 2)
    fill(a, f["top"], (14, 14, 16), 1)
    fill(a, f["bottom"], (14, 14, 16), 1)
    # strap loops + buckles at the front hips
    x, y, w, h = f["front"]
    for sx in (x + 3, x + w - 9):
        fill(a, (sx, y, 6, h), STRAP, 2)
        fill(a, (sx - 1, y + 5, 8, 6), SILVER, 4)
        fill(a, (sx + 1, y + 7, 4, 2), SILVER_DK, 2)


def p_thigh(a, f, part):
    side = "right" if part.bone == "rightLeg" else "left"
    inner = "left" if side == "right" else "right"
    for k in ("front", "back", side, inner):
        fl = (0.5, 0.45, 0.35, 0.6, 22) if k in ("front", "back") else None
        denim(a, f[k], fade=fl)
    fill(a, f["top"], (14, 14, 16), 1)
    fill(a, f["bottom"], (14, 14, 16), 1)
    # outer side seam
    x, y, w, h = f[side]
    stitch_v(a, x + w // 2, y, y + h)
    # front: vertical grommet strap on the outer edge + front-pocket curve
    x, y, w, h = f["front"]
    sx0, _ = outer_cols(f["front"], part.bone, 7)
    fill(a, (sx0, y, 6, h - 10), STRAP, 2)
    for ey in range(y + 6, y + h - 12, 8):
        eyelet(a, sx0 + 3, ey)
    fill(a, (sx0 - 1, y + 1, 8, 4), SILVER, 4)                                # buckle
    pocket_x = x + w - 12 if part.bone == "rightLeg" else x + 1
    for i in range(10):
        put(a, pocket_x + (i if part.bone == "rightLeg" else 10 - i), y + 2 + int(i * 0.9), (130, 130, 136))
    # back: yoke + back pocket
    x, y, w, h = f["back"]
    stitch_h(a, x, x + w, y + 3)
    px0 = x + 7
    stitch_h(a, px0, px0 + 18, y + 8)
    stitch_v(a, px0, y + 8, y + 24)
    stitch_v(a, px0 + 17, y + 8, y + 24)
    stitch_h(a, px0, px0 + 18, y + 24)


def p_lower(a, f, part):
    side = "right" if part.bone == "rightLeg" else "left"
    for k in ("front", "back", "right", "left"):
        fl = (0.5, 0.35, 0.4, 0.5, 18) if k == "front" else None
        denim(a, f[k], fade=fl, creases=5)
        x, y, w, h = f[k]
        stitch_h(a, x, x + w, y + 1)                                          # knee seam
        shade(a, (x, y, w, 1), -10)
    fill(a, f["top"], (40, 40, 44), 2)
    fill(a, f["bottom"], (14, 14, 16), 1)
    x, y, w, h = f[side]
    stitch_v(a, x + w // 2, y, y + h)


def p_hem(a, f, part):
    for k in ("front", "back", "right", "left"):
        denim(a, f[k], (46, 46, 51), creases=3)
        x, y, w, h = f[k]
        for cx in range(x, x + w, 4):                                         # cinched gathers
            shade(a, (cx, y, 1, h), -12)
        stitch_h(a, x, x + w, y + h - 2)
    fill(a, f["top"], (40, 40, 44), 2)
    fill(a, f["bottom"], (10, 10, 11), 1)                                      # leg opening


def p_pocket(a, f, part):
    for k in ("front", "back", "right", "left"):
        denim(a, f[k], (52, 52, 57))
        x, y, w, h = f[k]
        stitch_h(a, x + 1, x + w - 1, y + h - 2)
        stitch_v(a, x + 1, y, y + h - 1)
        stitch_v(a, x + w - 2, y, y + h - 1)
    fill(a, f["top"], (30, 30, 33), 1)
    fill(a, f["bottom"], (30, 30, 33), 1)
    # front: strap with grommets and a D-ring
    x, y, w, h = f["front"]
    fill(a, (x + 5, y + 2, 6, h - 10), STRAP, 2)
    eyelet(a, x + 8, y + 7)

    def ring(d, s):
        d.ellipse([4 * s, (h - 10) * s, 12 * s, (h - 2) * s], outline=SILVER + (255,), width=int(1.6 * s))
        d.line([4.5 * s, (h - 7.5) * s, 11.5 * s, (h - 7.5) * s], fill=SILVER + (255,), width=int(1.4 * s))
    overlay_pil(a, f["front"], ring)
    # outer face: same strap detail
    x, y, w, h = f["right" if part.bone == "rightLeg" else "left"]
    fill(a, (x + w // 2 - 3, y + 2, 6, h - 6), STRAP, 2)
    eyelet(a, x + w // 2, y + 7)
    eyelet(a, x + w // 2, y + 15)


def p_flap(a, f, part):
    for k in f:
        denim(a, f[k], (58, 58, 63))
    for k in ("front", "right", "left"):
        x, y, w, h = f[k]
        stitch_h(a, x, x + w, y + h - 2)
    x, y, w, h = f["front"]
    eyelet(a, x + w // 2, y + h // 2)


def p_strap(a, f, part):
    for k in f:
        fill(a, f[k], STRAP, 2)
        x, y, w, h = f[k]
        shade(a, (x, y, w, 1), 10)
        shade(a, (x, y + h - 1, w, 1), -6)
    for k in ("front", "right", "left"):
        x, y, w, h = f[k]
        if w >= 8:
            eyelet(a, x + 3, y + h // 2)
            eyelet(a, x + w - 4, y + h // 2)


def p_ring(a, f, part):
    for k in f:
        clear(a, f[k])
    x, y, w, h = f["front"]

    def ring(d, s):
        d.line([1 * s, 1 * s, 7 * s, 1 * s], fill=SILVER + (255,), width=int(1.5 * s))
        d.arc([1 * s, -2.5 * s, 7 * s, 7 * s], 0, 180, fill=SILVER + (255,), width=int(1.5 * s))
    overlay_pil(a, f["front"], ring)
    mirror_plane_back(a, f)


def p_toggle(a, f, part):
    for k in f:
        clear(a, f[k])

    def tog(d, s):
        d.line([4 * s, 0, 4 * s, 4 * s], fill=(30, 30, 33, 255), width=int(1.2 * s))
        d.rectangle([2.5 * s, 3.5 * s, 5.5 * s, 7.5 * s], fill=(14, 14, 15, 255))
        d.point([3.2 * s, 4.3 * s], fill=(70, 70, 76, 255))
    overlay_pil(a, f["front"], tog)
    mirror_plane_back(a, f)


def p_bow(a, f, part):
    for k in f:
        clear(a, f[k])

    def bow(d, s):
        c = (16, 16, 18, 255)
        d.ellipse([2 * s, 1 * s, 8 * s, 6 * s], outline=c, width=int(1.3 * s))
        d.ellipse([8 * s, 1 * s, 14 * s, 6 * s], outline=c, width=int(1.3 * s))
        d.line([7 * s, 5 * s, 5 * s, 22 * s], fill=c, width=int(1.3 * s))
        d.line([9 * s, 5 * s, 11 * s, 20 * s], fill=c, width=int(1.3 * s))
        d.rectangle([4.2 * s, 20 * s, 5.8 * s, 24 * s], fill=SILVER + (255,))
        d.rectangle([10.2 * s, 18 * s, 11.8 * s, 22 * s], fill=SILVER + (255,))
    overlay_pil(a, f["front"], bow)
    mirror_plane_back(a, f)


def p_chain(a, f, part):
    for k in f:
        clear(a, f[k])
    x, y, w, h = f["front"]

    def chains(d, s):
        for x0, x1, sag in ((2, w - 2, 23), (3, w - 4, 36)):
            pts = []
            for i in range(400):
                t = i / 399
                px = x0 + (x1 - x0) * t
                py = 2 + sag * (1 - (2 * t - 1) ** 2)
                pts.append((px, py))
            # walk along arc length placing links
            acc, k = 0.0, 0
            for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                acc += math.hypot(bx - ax, by - ay)
                if acc < 2.6:
                    continue
                acc = 0.0
                ang = math.atan2(by - ay, bx - ax)
                ca, sa = math.cos(ang), math.sin(ang)
                if k % 2 == 0:   # link seen flat (oval)
                    poly = [((bx + 1.9 * ca * math.cos(q) - 1.2 * sa * math.sin(q)) * s,
                             (by + 1.9 * sa * math.cos(q) + 1.2 * ca * math.sin(q)) * s)
                            for q in np.linspace(0, 2 * math.pi, 14)]
                    d.polygon(poly, outline=SILVER_DK + (255,), fill=SILVER + (255,))
                    d.ellipse([(bx - 0.5) * s, (by - 0.5) * s, (bx + 0.5) * s, (by + 0.5) * s],
                              fill=(0, 0, 0, 0))
                else:            # link seen edge-on (bar)
                    d.line([(bx - 1.6 * ca) * s, (by - 1.6 * sa) * s, (bx + 1.6 * ca) * s, (by + 1.6 * sa) * s],
                           fill=(230, 230, 236, 255), width=int(0.9 * s))
                k += 1
    overlay_pil(a, f["front"], chains)
    mirror_plane_back(a, f)


# --------------------------------------------------------------------------
# Part lists
# --------------------------------------------------------------------------
def hoodie_common():
    return [
        Part("torso", "body", [-4, 12, -2], [8, 12, 4], 0.85, p_torso),
        Part("hem", "body", [-4, 11, -2], [8, 2, 4], 1.0, p_rib),
        Part("sleeve_r", "rightArm", [-8, 12, -2], [4, 12, 4], 0.7, p_sleeve),
        Part("sleeve_l", "leftArm", [4, 12, -2], [4, 12, 4], 0.7, p_sleeve),
        Part("cuff_r", "rightArm", [-8, 12, -2], [4, 2, 4], 0.85, p_rib),
        Part("cuff_l", "leftArm", [4, 12, -2], [4, 2, 4], 0.85, p_rib),
        Part("string_r", "body", [-2.2, 17, -2.95], [1, 7, 0], 0, p_drawstring),
        Part("string_l", "body", [1.2, 16.5, -2.95], [1, 7, 0], 0, p_drawstring),
    ]


def hoodie_hood_down():
    return [
        Part("hood_flap", "body", [-4, 20, 2], [8, 4, 2], 0.7, p_hood_down),
        Part("hood_roll", "body", [-4, 23, 1], [8, 2, 4], 0.65, p_hood_roll),
    ]


def hoodie_hood_up():
    return [
        Part("hood", "head", [-4, 24, -4], [8, 8, 8], 1.1, p_hood_shell),
        Part("hood_rim_top", "head", [-5, 31, -6], [10, 2, 1], 0.1, p_hood_rim),
        Part("hood_rim_r", "head", [-5, 23, -6], [1, 8, 1], 0.1, p_hood_rim),
        Part("hood_rim_l", "head", [4, 23, -6], [1, 8, 1], 0.1, p_hood_rim),
        Part("hood_drape", "body", [-4, 20, 1], [8, 4, 3], 0.9, p_hood_down),
    ]


def pants_parts():
    parts = [
        Part("waistband", "body", [-4, 11, -2], [8, 2, 4], 0.65, p_waistband),
        Part("drawstring_bow", "body", [-1, 9.6, -2.7], [2, 3, 0], 0, p_bow),
    ]
    for bone, s in (("rightLeg", -1), ("leftLeg", 1)):
        def X(xr, w):
            """mirror an x-range given for the right leg onto the left leg."""
            return xr if s < 0 else -(xr + w)
        tag = "r" if s < 0 else "l"
        parts += [
            Part(f"thigh_{tag}", bone, [X(-3.9, 4), 6, -2], [4, 6, 4], 0.5, p_thigh),
            Part(f"lower_{tag}", bone, [X(-3.9, 4), 2, -2], [4, 4, 4], 0.8, p_lower),
            Part(f"hem_{tag}", bone, [X(-3.9, 4), 1.5, -2], [4, 1, 4], 0.95, p_hem),
            # pocket + flap end at y=10, exactly where the hoodie hem stops -> nothing pokes through
            Part(f"pocket_{tag}", bone, [X(-5.2, 2), 6, -2.9], [2, 3, 3], 0, p_pocket),
            Part(f"flap_{tag}", bone, [X(-5.4, 2), 9, -3.1], [2, 1, 3], 0, p_flap),
            Part(f"strap1_{tag}", bone, [X(-5.0, 2), 2.9, -3.0], [2, 1, 3], 0, p_strap),
            Part(f"strap2_{tag}", bone, [X(-5.0, 2), 3.95, -3.0], [2, 1, 3], 0, p_strap),
            Part(f"dring_{tag}", bone, [X(-4.6, 1), 1.9, -3.08], [1, 1, 0], 0, p_ring),
            Part(f"toggle_{tag}", bone, [X(-4.8, 1), 0.0, -3.0], [1, 1, 0], 0, p_toggle),
            # chains start under the hoodie hem and loop down in front of the knee
            Part(f"chain_{tag}", bone, [X(-3.4, 3), 5, -2.86], [3, 6, 0], 0, p_chain),
        ]
    return parts


def mannequin_parts():
    """Plain 'Steve'-like player used only for previews."""
    def p_head(a, f, part):
        for k in f:
            fill(a, f[k], (196, 146, 112), 2)
        for k in ("right", "left", "back", "top"):
            x, y, w, h = f[k]
            fill(a, (x, y, w, h if k in ("top", "back") else 20), (58, 38, 26), 3)
        x, y, w, h = f["front"]
        fill(a, (x, y, w, 14), (58, 38, 26), 3)
        fill(a, (x + 8, y + 32, 8, 8), (240, 240, 240), 1)
        fill(a, (x + 12, y + 32, 4, 8), (58, 92, 170), 1)
        fill(a, (x + 48, y + 32, 8, 8), (240, 240, 240), 1)
        fill(a, (x + 48, y + 32, 4, 8), (58, 92, 170), 1)
        fill(a, (x + 24, y + 48, 16, 4), (150, 100, 76), 1)
        fill(a, (x + 20, y + 52, 24, 4), (118, 70, 52), 1)

    def p_skin(a, f, part):
        for k in f:
            fill(a, f[k], (196, 146, 112), 2)

    def p_shirt(a, f, part):
        for k in f:
            fill(a, f[k], (220, 220, 224), 2)

    def p_leg(a, f, part):
        for k in f:
            fill(a, f[k], (60, 70, 120), 3)
        for k in ("front", "back", "right", "left"):
            x, y, w, h = f[k]
            fill(a, (x, y + h - 10, w, 10), (235, 235, 238), 2)               # sneakers
            fill(a, (x, y + h - 3, w, 3), (120, 120, 126), 2)
        fill(a, f["bottom"], (120, 120, 126), 2)

    return [
        Part("head", "head", [-4, 24, -4], [8, 8, 8], 0, p_head),
        Part("body", "body", [-4, 12, -2], [8, 12, 4], 0, p_shirt),
        Part("rarm", "rightArm", [-8, 12, -2], [4, 12, 4], 0, p_skin),
        Part("larm", "leftArm", [4, 12, -2], [4, 12, 4], 0, p_skin),
        Part("rleg", "rightLeg", [-3.9, 0, -2], [4, 12, 4], 0, p_leg),
        Part("lleg", "leftLeg", [-0.1, 0, -2], [4, 12, 4], 0, p_leg),
    ]


def build_atlas(parts):
    h_units = pack(parts)
    a = np.zeros((h_units * PX, ATLAS_W * PX, 4), float)
    for p in parts:
        if p.painter:
            p.painter(a, p.faces_px(), p)
    return a, h_units


def to_image(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


# --------------------------------------------------------------------------
# Geometry JSON
# --------------------------------------------------------------------------
def geometry_json(identifier, parts, tex_h, prefix):
    used = {p.bone for p in parts}
    needed = set(used)
    for b in list(used):                      # include parents so the chain binds
        while PLAYER_BONES[b]["parent"]:
            b = PLAYER_BONES[b]["parent"]
            needed.add(b)
    bones = []
    for name, info in PLAYER_BONES.items():
        if name not in needed:
            continue
        bone = {"name": name, "pivot": info["pivot"]}
        if info["parent"]:
            bone["parent"] = info["parent"]
        bones.append(bone)
    for name, info in PLAYER_BONES.items():
        cubes = [p.cube_json() for p in parts if p.bone == name]
        if cubes:
            bones.append({"name": f"{prefix}_{name}", "parent": name, "pivot": info["pivot"], "cubes": cubes})
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {
                "identifier": identifier,
                "texture_width": ATLAS_W,
                "texture_height": tex_h,
                "visible_bounds_width": 3,
                "visible_bounds_height": 3.5,
                "visible_bounds_offset": [0, 1.5, 0],
            },
            "bones": bones,
        }],
    }


# --------------------------------------------------------------------------
# Software renderer (orthographic, z-buffered) for previews and icons
# --------------------------------------------------------------------------
def rot_x(d):
    t = math.radians(d)
    return np.array([[1, 0, 0], [0, math.cos(t), -math.sin(t)], [0, math.sin(t), math.cos(t)]])


def rot_y(d):
    t = math.radians(d)
    return np.array([[math.cos(t), 0, math.sin(t)], [0, 1, 0], [-math.sin(t), 0, math.cos(t)]])


def bone_matrix(bone, pose):
    """Return (R, pivot) chain for a bone in the given pose {bone: x_degrees}."""
    chain = []
    b = bone
    while b:
        chain.append(b)
        b = PLAYER_BONES[b]["parent"]
    return [(rot_x(pose.get(c, 0.0)), np.array(PLAYER_BONES[c]["pivot"], float)) for c in chain]


def render(layers, yaw=0.0, pitch=0.0, pose=None, scale=14, size=(420, 560), center_y=16.5, ss=2,
           bg=(236, 236, 240)):
    pose = pose or {}
    W, H = size[0] * ss, size[1] * ss
    sc = scale * ss
    col = np.zeros((H, W, 3)) + np.array(bg, float)
    alpha_mask = np.zeros((H, W))
    zb = np.full((H, W), np.inf)
    V = rot_x(pitch) @ rot_y(yaw)
    L = np.array([-0.35, 0.85, -0.55])
    L /= np.linalg.norm(L)
    for parts, img in layers:
        tex = np.asarray(img).astype(float)
        th, tw = tex.shape[:2]
        for p in parts:
            fpx = p.faces_px()
            mats = bone_matrix(p.bone, pose)
            for name, P0, U, Vv, N in p.faces_3d():
                tx, ty, tw_, th_ = fpx[name]
                if tw_ <= 0 or th_ <= 0 or np.linalg.norm(U) < 1e-6 or np.linalg.norm(Vv) < 1e-6:
                    continue
                P, Uw, Vw, Nw = P0.astype(float), U.astype(float), Vv.astype(float), N.astype(float)
                for R, piv in mats:
                    P = R @ (P - piv) + piv
                    Uw, Vw, Nw = R @ Uw, R @ Vw, R @ Nw
                p0, u, v, n = V @ P, V @ Uw, V @ Vw, V @ Nw
                # screen: x right, y down
                s0 = np.array([W / 2 + p0[0] * sc, H / 2 - (p0[1] - center_y) * sc])
                us, vs = np.array([u[0] * sc, -u[1] * sc]), np.array([v[0] * sc, -v[1] * sc])
                M = np.array([[us[0], vs[0]], [us[1], vs[1]]])
                det = np.linalg.det(M)
                if abs(det) < 1e-6:
                    continue
                Minv = np.linalg.inv(M)
                corners = np.array([s0, s0 + us, s0 + vs, s0 + us + vs])
                x0, y0 = np.floor(corners.min(0)).astype(int)
                x1, y1 = np.ceil(corners.max(0)).astype(int)
                x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
                if x1 <= x0 or y1 <= y0:
                    continue
                gy, gx = np.mgrid[y0:y1, x0:x1]
                d = np.stack([gx + 0.5 - s0[0], gy + 0.5 - s0[1]], -1)
                st = d @ Minv.T
                s_, t_ = st[..., 0], st[..., 1]
                inside = (s_ >= 0) & (s_ < 1) & (t_ >= 0) & (t_ < 1)
                if not inside.any():
                    continue
                cx = np.clip(tx + np.floor(s_ * tw_).astype(int), 0, tw - 1)
                cy = np.clip(ty + np.floor(t_ * th_).astype(int), 0, th - 1)
                texel = tex[cy, cx]
                inside &= texel[..., 3] >= 128
                depth = p0[2] + s_ * u[2] + t_ * v[2]
                sub_z = zb[y0:y1, x0:x1]
                win = inside & (depth < sub_z - 1e-4)
                if not win.any():
                    continue
                nn = Nw / np.linalg.norm(Nw)
                if n[2] > 0:                       # seen from behind (two-sided planes / interiors)
                    nn = -nn
                b = 0.58 + 0.42 * max(0.0, float(nn @ L))
                sub_c = col[y0:y1, x0:x1]
                sub_c[win] = texel[..., :3][win] * b
                sub_z[win] = depth[win]
                alpha_mask[y0:y1, x0:x1][win] = 1
    out = np.dstack([col, alpha_mask * 255])
    im = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGBA")
    return im.resize(size, Image.LANCZOS)


def icon_from(layers, out_size=32, yaw=0, pitch=0, center_y=16.5, scale=10):
    im = render(layers, yaw=yaw, pitch=pitch, scale=scale, size=(320, 400), center_y=center_y, ss=2,
                bg=(0, 0, 0))
    a = np.asarray(im).copy()
    a[..., 3] = np.where(a[..., 3] > 100, 255, 0)
    im = Image.fromarray(a, "RGBA")
    bbox = im.getbbox()
    im = im.crop(bbox)
    w, h = im.size
    side = max(w, h)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, ((side - w) // 2, (side - h) // 2))
    sq = sq.resize((out_size, out_size), Image.BOX)
    a = np.asarray(sq).copy()
    a[..., 3] = np.where(a[..., 3] > 110, 255, 0)
    # 1px dark outline so the icon reads in the inventory
    solid = a[..., 3] > 0
    ring = np.zeros_like(solid)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ring |= np.roll(np.roll(solid, dy, 0), dx, 1)
    ring &= ~solid
    a[ring] = (12, 12, 14, 255)
    return Image.fromarray(a, "RGBA")


def font(sz):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, sz)
    return ImageFont.load_default()


# --------------------------------------------------------------------------
# Add-on files
# --------------------------------------------------------------------------
def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def uid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"idex/vlone_outfit/{name}"))


def attachable(identifier, geo, tex, layer_var, slot):
    return {
        "format_version": "1.10.0",
        "minecraft:attachable": {
            "description": {
                "identifier": identifier,
                "materials": {"default": "entity_alphatest", "enchanted": "entity_alphatest_glint"},
                "textures": {"default": tex, "enchanted": "textures/misc/enchanted_item_glint"},
                "geometry": {"default": geo},
                "scripts": {"parent_setup": f"variable.{layer_var} = 0.0;"},
                # hide the 3D outfit while the item is only held in a hand
                "render_controllers": [
                    {"controller.render.armor": "c.item_slot != 'main_hand' && c.item_slot != 'off_hand'"}
                ],
            }
        },
    }


def item(identifier, name, icon, slot, ench_slot, protection, durability):
    return {
        "format_version": "1.21.40",
        "minecraft:item": {
            "description": {"identifier": identifier, "menu_category": {"category": "equipment"}},
            "components": {
                "minecraft:icon": icon,
                "minecraft:display_name": {"value": name},
                "minecraft:max_stack_size": 1,
                "minecraft:wearable": {"slot": slot, "protection": protection},
                "minecraft:durability": {"max_durability": durability},
                "minecraft:enchantable": {"slot": ench_slot, "value": 15},
            },
        },
    }


def shaped(identifier, pattern, key, result):
    return {"format_version": "1.20.10", "minecraft:recipe_shaped": {
        "description": {"identifier": identifier}, "tags": ["crafting_table"],
        "pattern": pattern, "key": {k: {"item": v} for k, v in key.items()},
        "result": {"item": result}}}


def shapeless(identifier, ingredient, result):
    return {"format_version": "1.20.10", "minecraft:recipe_shapeless": {
        "description": {"identifier": identifier}, "tags": ["crafting_table"],
        "ingredients": [{"item": ingredient}], "result": {"item": result}}}


def main():
    for d in (OUT, PREVIEW):
        if os.path.isdir(d):
            shutil.rmtree(d)
    os.makedirs(DIST, exist_ok=True)
    os.makedirs(PREVIEW, exist_ok=True)

    # ---- build part lists + atlases
    common, down, up = hoodie_common(), hoodie_hood_down(), hoodie_hood_up()
    hoodie_all = common + down + up
    hoodie_arr, hoodie_h = build_atlas(hoodie_all)
    hoodie_img = to_image(hoodie_arr)

    pants = pants_parts()
    pants_arr, pants_h = build_atlas(pants)
    pants_img = to_image(pants_arr)

    man = mannequin_parts()
    man_arr, _ = build_atlas(man)
    man_img = to_image(man_arr)

    # ---- resource pack
    hoodie_tex = "textures/models/armor/vlone_hoodie"
    pants_tex = "textures/models/armor/vlone_cargo_pants"
    os.makedirs(os.path.join(RP, "textures/models/armor"), exist_ok=True)
    hoodie_img.save(os.path.join(RP, hoodie_tex + ".png"))
    pants_img.save(os.path.join(RP, pants_tex + ".png"))

    geo_down, geo_up, geo_pants = (f"geometry.{NS}.vlone_hoodie", f"geometry.{NS}.vlone_hoodie_up",
                                   f"geometry.{NS}.vlone_cargo_pants")
    write_json(os.path.join(RP, "models/entity/vlone_hoodie.geo.json"),
               geometry_json(geo_down, common + down, hoodie_h, "hoodie"))
    write_json(os.path.join(RP, "models/entity/vlone_hoodie_up.geo.json"),
               geometry_json(geo_up, common + up, hoodie_h, "hoodie"))
    write_json(os.path.join(RP, "models/entity/vlone_cargo_pants.geo.json"),
               geometry_json(geo_pants, pants, pants_h, "pants"))

    ids = {"down": f"{NS}:vlone_hoodie", "up": f"{NS}:vlone_hoodie_up", "pants": f"{NS}:vlone_cargo_pants"}
    write_json(os.path.join(RP, "attachables/vlone_hoodie.json"),
               attachable(ids["down"], geo_down, hoodie_tex, "chest_layer_visible", "torso"))
    write_json(os.path.join(RP, "attachables/vlone_hoodie_up.json"),
               attachable(ids["up"], geo_up, hoodie_tex, "chest_layer_visible", "torso"))
    write_json(os.path.join(RP, "attachables/vlone_cargo_pants.json"),
               attachable(ids["pants"], geo_pants, pants_tex, "leg_layer_visible", "legs"))

    # icons
    icons = {
        "vlone_hoodie": icon_from([(common + down, hoodie_img)], center_y=18),
        "vlone_hoodie_up": icon_from([(common + up, hoodie_img)], center_y=21),
        "vlone_cargo_pants": icon_from([(pants, pants_img)], center_y=6),
    }
    os.makedirs(os.path.join(RP, "textures/items"), exist_ok=True)
    tex_data = {}
    for k, im in icons.items():
        im.save(os.path.join(RP, f"textures/items/{k}.png"))
        tex_data[f"{NS}_{k}"] = {"textures": f"textures/items/{k}"}
    write_json(os.path.join(RP, "textures/item_texture.json"),
               {"resource_pack_name": "vlone_outfit", "texture_name": "atlas.items", "texture_data": tex_data})

    # ---- previews
    full_down = [(man, man_img), (common + down, hoodie_img), (pants, pants_img)]
    full_up = [(man, man_img), (common + up, hoodie_img), (pants, pants_img)]
    walk = {"rightArm": 30, "leftArm": -30, "rightLeg": -28, "leftLeg": 28}
    views = [
        ("Hood down - front", render(full_down, 0, -6)),
        ("Hood down - back", render(full_down, 180, -6)),
        ("Hood up - 3/4", render(full_up, -32, -10)),
        ("Hood up - back 3/4", render(full_up, 148, -10)),
        ("Walking - side", render(full_down, -90, -4, pose=walk)),
    ]
    pad, lab = 16, 34
    tw = sum(v.width for _, v in views) + pad * (len(views) + 1)
    th = views[0][1].height + lab + pad * 2
    sheet = Image.new("RGB", (tw, th), (236, 236, 240))
    dr = ImageDraw.Draw(sheet)
    x = pad
    for label, im in views:
        sheet.paste(im, (x, pad + lab), im)
        dr.text((x + 6, pad), label, fill=(30, 30, 34), font=font(20))
        x += im.width + pad
    sheet.save(os.path.join(PREVIEW, "outfit_preview.png"))

    pieces = [
        ("Hoodie (hood down)", render([(common + down, hoodie_img)], -25, -10)),
        ("Hoodie (hood up)", render([(common + up, hoodie_img)], -25, -10)),
        ("Cargo pants", render([(pants, pants_img)], -25, -10, center_y=10)),
    ]
    tw = sum(v.width for _, v in pieces) + pad * (len(pieces) + 1)
    sheet = Image.new("RGB", (tw, th), (236, 236, 240))
    dr = ImageDraw.Draw(sheet)
    x = pad
    for label, im in pieces:
        sheet.paste(im, (x, pad + lab), im)
        dr.text((x + 6, pad), label, fill=(30, 30, 34), font=font(20))
        x += im.width + pad
    sheet.save(os.path.join(PREVIEW, "pieces_preview.png"))
    hoodie_img.resize((hoodie_img.width, hoodie_img.height), Image.NEAREST).save(
        os.path.join(PREVIEW, "hoodie_texture.png"))
    pants_img.save(os.path.join(PREVIEW, "pants_texture.png"))

    pack_icon = render(full_down, -30, -8, scale=7, size=(256, 256), center_y=16.5)
    bg = Image.new("RGBA", pack_icon.size, (40, 40, 46, 255))
    bg.alpha_composite(pack_icon)
    pack_icon = bg.convert("RGB")
    pack_icon.save(os.path.join(RP, "pack_icon.png"))

    version = [1, 0, 0]
    write_json(os.path.join(RP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": "VLONE Outfit (RP)", "description": "Hoodie (hood up / down) + chain cargo pants",
                   "uuid": uid("rp"), "version": version, "min_engine_version": [1, 21, 40]},
        "modules": [{"type": "resources", "uuid": uid("rp-mod"), "version": version}],
    })

    # ---- behavior pack
    write_json(os.path.join(BP, "items/vlone_hoodie.json"),
               item(ids["down"], "VLONE Hoodie", f"{NS}_vlone_hoodie", "slot.armor.chest", "armor_torso", 3, 240))
    write_json(os.path.join(BP, "items/vlone_hoodie_up.json"),
               item(ids["up"], "VLONE Hoodie (Hood Up)", f"{NS}_vlone_hoodie_up", "slot.armor.chest",
                    "armor_torso", 3, 240))
    write_json(os.path.join(BP, "items/vlone_cargo_pants.json"),
               item(ids["pants"], "Chain Cargo Pants", f"{NS}_vlone_cargo_pants", "slot.armor.legs",
                    "armor_legs", 2, 225))
    write_json(os.path.join(BP, "recipes/vlone_hoodie.json"),
               shaped(ids["down"], ["W W", "WWW", "WWW"], {"W": "minecraft:black_wool"}, ids["down"]))
    write_json(os.path.join(BP, "recipes/vlone_cargo_pants.json"),
               shaped(ids["pants"], ["WCW", "W W", "W W"],
                      {"W": "minecraft:black_wool", "C": "minecraft:chain"}, ids["pants"]))
    write_json(os.path.join(BP, "recipes/vlone_hood_up.json"),
               shapeless(f"{NS}:vlone_hood_up_toggle", ids["down"], ids["up"]))
    write_json(os.path.join(BP, "recipes/vlone_hood_down.json"),
               shapeless(f"{NS}:vlone_hood_down_toggle", ids["up"], ids["down"]))
    os.makedirs(os.path.join(BP, "functions"), exist_ok=True)
    with open(os.path.join(BP, "functions/hood_up.mcfunction"), "w") as fh:
        fh.write(f"replaceitem entity @s[hasitem={{item={ids['down']},location=slot.armor.chest}}] "
                 f"slot.armor.chest 0 {ids['up']}\n")
    with open(os.path.join(BP, "functions/hood_down.mcfunction"), "w") as fh:
        fh.write(f"replaceitem entity @s[hasitem={{item={ids['up']},location=slot.armor.chest}}] "
                 f"slot.armor.chest 0 {ids['down']}\n")
    pack_icon.save(os.path.join(BP, "pack_icon.png"))
    write_json(os.path.join(BP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": "VLONE Outfit (BP)", "description": "Hoodie (hood up / down) + chain cargo pants",
                   "uuid": uid("bp"), "version": version, "min_engine_version": [1, 21, 40]},
        "modules": [{"type": "data", "uuid": uid("bp-mod"), "version": version}],
        "dependencies": [{"uuid": uid("rp"), "version": version}],
    })

    # ---- package
    out = os.path.join(DIST, "Vlone_Outfit.mcaddon")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for base in (RP, BP):
            for dp, _, files in os.walk(base):
                for fn in sorted(files):
                    full = os.path.join(dp, fn)
                    z.write(full, os.path.relpath(full, OUT))
    print("atlas heights:", hoodie_h, pants_h)
    print("wrote", out)


if __name__ == "__main__":
    main()
