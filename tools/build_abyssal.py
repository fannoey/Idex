#!/usr/bin/env python3
"""Generate the "Abyssal Inferno" Minecraft Bedrock add-on.

Produces every data file of the add-on except the Script API code (which lives
hand-written in Abyssal_Inferno_BP/scripts/):

  * particle textures (flame / smoke / slash flipbooks, sigils, cracks, ...)
  * particle definitions (RP/particles/*.particle.json)
  * player skill animations (RP/animations/abyss_player.animation.json)
  * dummy entities (BP + RP), weapon item, recipe, manifests, icons
  * preview contact sheet and dist/Abyssal_Inferno.mcaddon

Run:  python3 tools/build_abyssal.py
"""
import json
import math
import os
import shutil
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "abyssal_inferno")
BP = os.path.join(OUT, "Abyssal_Inferno_BP")
RP = os.path.join(OUT, "Abyssal_Inferno_RP")
DIST = os.path.join(ROOT, "dist")
PREVIEW = os.path.join(ROOT, "preview")

NS = "abyss"
ITEM = f"{NS}:abyssal_inferno"
TEX_DIR = "textures/particle/abyss"
VERSION = [1, 0, 0]
MIN_ENGINE = [1, 21, 60]

UUID_BP_HEADER = "fb97fc7c-1639-4f7c-baa4-a322ab1598df"
UUID_BP_DATA = "494c21bb-f1e1-464f-9ad6-9f78fe444d08"
UUID_BP_SCRIPT = "6bf4891c-288a-4045-a32e-5c4bb916862d"
UUID_RP_HEADER = "90b7b39e-80ce-4f0a-97c2-d45aae2e2bfb"
UUID_RP_RES = "58be05f7-0307-4fbf-883b-66771c9dc414"


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def value_noise(h, w, cells_y, cells_x, rng):
    """Smooth value noise in [0,1], tileable horizontally is not needed here."""
    g = rng.random((cells_y + 2, cells_x + 2))
    ys = np.linspace(0, cells_y, h, endpoint=False)
    xs = np.linspace(0, cells_x, w, endpoint=False)
    y0 = ys.astype(int)
    x0 = xs.astype(int)
    ty = ys - y0
    tx = xs - x0
    ty = ty * ty * (3 - 2 * ty)
    tx = tx * tx * (3 - 2 * tx)
    a = g[y0][:, x0]
    b = g[y0][:, x0 + 1]
    c = g[y0 + 1][:, x0]
    d = g[y0 + 1][:, x0 + 1]
    top = a + (b - a) * tx[None, :]
    bot = c + (d - c) * tx[None, :]
    return top + (bot - top) * ty[:, None]


def fbm(h, w, seed, base=3, octaves=4):
    rng = np.random.default_rng(seed)
    total = np.zeros((h, w))
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        c = base * (2 ** o)
        total += amp * value_noise(h, w, c, c, rng)
        norm += amp
        amp *= 0.5
    return total / norm


def to_img(alpha, lum=None, rgb=None):
    """alpha/lum: float arrays 0..1. rgb: (h,w,3) float array (overrides lum)."""
    h, w = alpha.shape
    out = np.zeros((h, w, 4))
    if rgb is not None:
        out[..., :3] = rgb
    else:
        l = np.ones((h, w)) if lum is None else lum
        out[..., 0] = out[..., 1] = out[..., 2] = l
    out[..., 3] = alpha
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), "RGBA")


def grid(h, w):
    """Normalised coordinates: x,y in [-1,1] (y up)."""
    ys, xs = np.mgrid[0:h, 0:w]
    x = (xs + 0.5) / w * 2 - 1
    y = 1 - (ys + 0.5) / h * 2
    return x, y


def glow_composite(img, radius, strength=0.6):
    """Add a soft bloom around a white-on-transparent line drawing."""
    a = np.asarray(img).astype(float) / 255.0
    alpha = a[..., 3]
    blur = Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius))
    b = np.asarray(blur).astype(float) / 255.0
    new_a = np.clip(np.maximum(alpha, b * strength * 1.6), 0, 1)
    lum = np.clip(0.55 + 0.45 * alpha / np.maximum(new_a, 1e-4), 0, 1)
    return to_img(new_a, lum)


# --------------------------------------------------------------------------
# textures
# --------------------------------------------------------------------------
TEXTURES = {}


def tex(name, img):
    TEXTURES[name] = img


def make_flame_sheet():
    fw, fh, n = 32, 64, 8
    sheet = Image.new("RGBA", (fw * n, fh))
    big = fbm(fh * 4, fw, seed=11, base=3)
    ero = fbm(fh * 4, fw, seed=12, base=4)
    x, y = grid(fh, fw)
    v = (y + 1) / 2  # 0 bottom .. 1 top
    for f in range(n):
        t = f / (n - 1)
        off = int(f * fh * 0.35)
        nz = big[off:off + fh]
        ez = ero[off:off + fh]
        hs = 1.0 - 0.38 * t
        vs = v / hs
        # teardrop width profile
        w = np.where(vs < 0.25,
                     0.62 * np.sqrt(np.clip(1 - ((0.25 - vs) / 0.25) ** 2, 0, 1)),
                     0.62 * np.clip((1 - vs) / 0.75, 0, 1) ** 0.85)
        w = w * (1 - 0.35 * t)
        u = x + (nz - 0.5) * 1.5 * np.clip(vs, 0, 1.2) ** 1.3
        d = np.abs(u) / np.maximum(w, 1e-3)
        inside = (1 - smoothstep(0.55, 1.0, d)) * (vs <= 1.0)
        inside *= smoothstep(t * 0.55, t * 0.55 + 0.3, ez + (1 - vs) * 0.3)
        alpha = inside * (1 - 0.35 * t)
        lum = 0.72 + 0.28 * np.clip(1 - d, 0, 1)
        sheet.paste(to_img(alpha, lum), (f * fw, 0))
    tex("flame_sheet", sheet)


def make_smoke_sheet():
    fs, n = 32, 8
    sheet = Image.new("RGBA", (fs * n, fs))
    x, y = grid(fs, fs)
    r = np.sqrt(x * x + y * y)
    for f in range(n):
        t = f / (n - 1)
        nz = fbm(fs, fs, seed=40 + f, base=3)
        ez = fbm(fs, fs, seed=80 + f, base=5)
        rb = 0.5 + 0.38 * t
        dens = smoothstep(rb, rb - 0.4, r + (nz - 0.5) * 0.55)
        dens *= smoothstep(t * 0.5, t * 0.5 + 0.35, ez)
        alpha = dens * (0.95 - 0.45 * t)
        lum = 0.55 + 0.35 * nz + 0.1 * y
        sheet.paste(to_img(alpha, lum), (f * fs, 0))
    tex("smoke_sheet", sheet)


def make_crescent_sheet():
    fs, n = 64, 6
    sheet = Image.new("RGBA", (fs * n, fs))
    x, y = grid(fs, fs)
    r = np.sqrt(x * x + y * y)
    phi = np.arctan2(x, y)  # 0 = straight up
    erosion = fbm(fs, fs, seed=5, base=6)
    spans = [55, 80, 86, 86, 86, 86]
    thick = [0.20, 0.26, 0.24, 0.16, 0.10, 0.06]
    for f in range(n):
        A = math.radians(spans[f])
        R = 0.86
        rel = np.clip(np.abs(phi) / A, 0, 1)
        th = thick[f] * np.cos(rel * math.pi / 2) ** 0.8
        band = (r <= R) & (r >= R - th) & (np.abs(phi) <= A)
        edge = np.exp(-((R - r) / np.maximum(th * 0.35, 1e-3)) ** 2)
        inner = smoothstep(R - th - 0.04, R - th + 0.06, r) * (r <= R + 0.02)
        a = np.clip(edge + 0.55 * inner, 0, 1) * (np.abs(phi) <= A)
        a *= np.clip(1 - rel ** 4, 0, 1)
        a *= (r <= R + 0.05)
        if f >= 3:
            a *= smoothstep((f - 2) * 0.2, (f - 2) * 0.2 + 0.25, erosion)
        lum = 0.6 + 0.4 * edge
        _ = band
        sheet.paste(to_img(np.clip(a, 0, 1), lum), (f * fs, 0))
    tex("crescent_sheet", sheet)


def make_glow():
    x, y = grid(64, 64)
    r = np.sqrt(x * x + y * y)
    a = np.exp(-(r ** 2) * 4.5) * np.clip(1 - r, 0, 1) ** 0.6
    tex("glow", to_img(a))


def make_spark():
    x, y = grid(16, 16)
    r = np.sqrt(x * x + y * y)
    a = np.exp(-r * 5) + 0.9 * np.exp(-np.abs(x) * 14) * np.exp(-np.abs(y) * 2.5) \
        + 0.9 * np.exp(-np.abs(y) * 14) * np.exp(-np.abs(x) * 2.5)
    a *= np.clip(1 - r, 0, 1)
    tex("spark", to_img(np.clip(a, 0, 1)))


def make_streak():
    x, y = grid(8, 64)
    a = np.exp(-(y / 0.45) ** 2) * np.clip(1 - np.abs(x), 0, 1) ** 1.1
    a *= 0.4 + 0.6 * smoothstep(-1, 0.6, x)  # brighter head (+x)
    tex("streak", to_img(np.clip(a * 1.3, 0, 1)))


def make_ring():
    x, y = grid(128, 128)
    r = np.sqrt(x * x + y * y)
    a = np.exp(-((r - 0.86) / 0.04) ** 2) + 0.35 * np.exp(-((r - 0.86) / 0.16) ** 2) * (r < 0.86)
    tex("ring", to_img(np.clip(a, 0, 1)))


def make_ring_shatter():
    x, y = grid(128, 128)
    r = np.sqrt(x * x + y * y)
    ang = np.arctan2(y, x)
    rng = np.random.default_rng(3)
    seg = np.zeros_like(r)
    cuts = np.sort(rng.random(14) * 2 * math.pi - math.pi)
    a01 = (ang + math.pi)
    idx = np.searchsorted(np.sort(cuts + math.pi), a01)
    jag = (idx % 3) * 0.025 - 0.025
    gap = np.zeros_like(r, dtype=bool)
    for c in cuts:
        dang = np.abs(np.angle(np.exp(1j * (ang - c))))
        gap |= dang < 0.06
    rr = 0.84 + jag
    seg = np.exp(-((r - rr) / 0.05) ** 2) * (~gap)
    seg += 0.5 * np.exp(-((r - rr + 0.09) / 0.03) ** 2) * (~gap) * (idx % 2 == 0)
    tex("ring_shatter", to_img(np.clip(seg, 0, 1)))


def glyph_strokes(rng):
    strokes = []
    for _ in range(rng.integers(2, 5)):
        pts = []
        p = rng.random(2) * 1.4 - 0.7
        for _ in range(rng.integers(2, 4)):
            pts.append(tuple(p))
            p = np.clip(p + (rng.random(2) - 0.5) * 1.3, -0.85, 0.85)
        pts.append(tuple(p))
        strokes.append(pts)
    return strokes


def make_runes_sheet():
    s, n, ss = 16, 8, 8
    sheet = Image.new("RGBA", (s * n, s))
    rng = np.random.default_rng(21)
    for i in range(n):
        im = Image.new("L", (s * ss, s * ss), 0)
        d = ImageDraw.Draw(im)
        for st in glyph_strokes(rng):
            pts = [((px + 1) / 2 * s * ss, (1 - (py + 1) / 2) * s * ss) for px, py in st]
            d.line(pts, fill=255, width=int(1.6 * ss), joint="curve")
        im = im.resize((s, s), Image.LANCZOS)
        a = np.asarray(im).astype(float) / 255
        sheet.paste(glow_composite(to_img(a), 1.0, 0.5), (i * s, 0))
    tex("runes_sheet", sheet)


def make_sigil():
    S = 1024
    im = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(im)
    c = S / 2

    def circ(r, w):
        d.ellipse([c - r, c - r, c + r, c + r], outline=255, width=w)

    circ(496, 12)
    circ(468, 5)
    circ(398, 7)
    circ(232, 6)
    circ(214, 3)
    # rune band
    rng = np.random.default_rng(7)
    for k in range(30):
        th = k / 30 * 2 * math.pi
        cx, cy = c + math.cos(th) * 433, c + math.sin(th) * 433
        rot = th + math.pi / 2
        for st in glyph_strokes(rng):
            pts = []
            for px, py in st:
                X, Y = px * 20, -py * 20
                pts.append((cx + X * math.cos(rot) - Y * math.sin(rot),
                            cy + X * math.sin(rot) + Y * math.cos(rot)))
            d.line(pts, fill=255, width=5, joint="curve")
    # hexagram + vertex rings
    for off in (0, math.pi):
        pts = [(c + math.cos(off + math.pi / 2 + k * 2 * math.pi / 3) * 398,
                c + math.sin(off + math.pi / 2 + k * 2 * math.pi / 3) * 398) for k in range(3)]
        d.line(pts + [pts[0]], fill=255, width=7, joint="curve")
    for k in range(6):
        a = math.pi / 2 + k * math.pi / 3
        x, y = c + math.cos(a) * 398, c + math.sin(a) * 398
        d.ellipse([x - 26, y - 26, x + 26, y + 26], fill=0, outline=255, width=6)
        d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=255)
    # ticks between inner circles
    for k in range(72):
        a = k / 72 * 2 * math.pi
        r0, r1 = (240, 270) if k % 6 else (240, 300)
        d.line([(c + math.cos(a) * r0, c + math.sin(a) * r0), (c + math.cos(a) * r1, c + math.sin(a) * r1)],
               fill=255, width=4)
    # abyssal eye
    ew, eh = 170, 82
    top = [(c + ew * math.cos(t), c - eh * math.sin(t)) for t in np.linspace(0, math.pi, 40)]
    bot = [(c + ew * math.cos(t), c + eh * math.sin(t)) for t in np.linspace(math.pi, 2 * math.pi, 40)]
    d.line(top + bot[1:] + [top[0]], fill=255, width=8, joint="curve")
    d.ellipse([c - 52, c - 52, c + 52, c + 52], outline=255, width=6)
    d.ellipse([c - 14, c - 46, c + 14, c + 46], fill=255)
    # crescents at cardinal points of inner ring
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        x, y = c + math.cos(a) * 318, c + math.sin(a) * 318
        d.ellipse([x - 30, y - 30, x + 30, y + 30], fill=255)
        x2, y2 = c + math.cos(a) * 304, c + math.sin(a) * 304
        d.ellipse([x2 - 27, y2 - 27, x2 + 27, y2 + 27], fill=0)
    im = im.resize((256, 256), Image.LANCZOS)
    a = np.asarray(im).astype(float) / 255
    tex("sigil", glow_composite(to_img(a), 3.0, 0.55))


def make_crack():
    S = 512
    im = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(9)

    def branch(x, y, ang, length, width, depth):
        steps = int(length / 14)
        for i in range(steps):
            ang += rng.normal(0, 0.22)
            nx, ny = x + math.cos(ang) * 14, y + math.sin(ang) * 14
            w = max(1, int(width * (1 - i / steps)))
            d.line([(x, y), (nx, ny)], fill=255, width=w)
            if depth < 2 and rng.random() < 0.16:
                branch(nx, ny, ang + rng.choice([-1, 1]) * rng.uniform(0.5, 1.1),
                       length * rng.uniform(0.3, 0.5), w * 0.7, depth + 1)
            x, y = nx, ny

    for k in range(6):
        a = k / 6 * 2 * math.pi + rng.uniform(-0.3, 0.3)
        branch(S / 2, S / 2, a, rng.uniform(210, 250), 12, 0)
    d.ellipse([S / 2 - 18, S / 2 - 18, S / 2 + 18, S / 2 + 18], fill=255)
    im = im.resize((128, 128), Image.LANCZOS)
    a = np.asarray(im).astype(float) / 255
    tex("crack", glow_composite(to_img(a), 2.0, 0.6))


def make_rift():
    W, H, ss = 32, 128, 4
    im = Image.new("L", (W * ss, H * ss), 0)
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(13)
    n = 26
    left, right = [], []
    cx = 0.0
    for i in range(n + 1):
        t = i / n
        cx = np.clip(cx + rng.normal(0, 0.12), -0.35, 0.35)
        w = 0.42 * math.sin(math.pi * t) ** 0.75 * rng.uniform(0.7, 1.15)
        yy = (1 - t) * H * ss
        left.append(((0.5 + (cx - w) / 2) * W * ss, yy))
        right.append(((0.5 + (cx + w) / 2) * W * ss, yy))
    d.polygon(left + right[::-1], fill=255)
    im = im.resize((W, H), Image.LANCZOS)
    a = np.asarray(im).astype(float) / 255
    tex("rift", glow_composite(to_img(a), 2.0, 0.7))


def make_spear():
    W, H, ss = 128, 32, 4
    im = Image.new("L", (W * ss, H * ss), 0)
    d = ImageDraw.Draw(im)
    cy = H * ss / 2
    s = ss
    # shaft (tapering towards the tail)
    d.polygon([(4 * s, cy - 1 * s), (86 * s, cy - 2.4 * s), (86 * s, cy + 2.4 * s), (4 * s, cy + 1 * s)], fill=255)
    # head
    d.polygon([(80 * s, cy), (92 * s, cy - 11 * s), (127 * s, cy), (92 * s, cy + 11 * s)], fill=255)
    # barbs
    d.polygon([(84 * s, cy - 5 * s), (74 * s, cy - 13 * s), (90 * s, cy - 6 * s)], fill=255)
    d.polygon([(84 * s, cy + 5 * s), (74 * s, cy + 13 * s), (90 * s, cy + 6 * s)], fill=255)
    # tail fins
    d.polygon([(4 * s, cy), (0, cy - 7 * s), (14 * s, cy)], fill=255)
    d.polygon([(4 * s, cy), (0, cy + 7 * s), (14 * s, cy)], fill=255)
    im = im.resize((W, H), Image.LANCZOS)
    a = np.asarray(im).astype(float) / 255
    tex("spear", glow_composite(to_img(a), 2.5, 0.7))


def make_shard():
    s, ss = 16, 8
    im = Image.new("L", (s * ss, s * ss), 0)
    d = ImageDraw.Draw(im)
    d.polygon([(8 * ss, 0.5 * ss), (12.5 * ss, 9 * ss), (8.5 * ss, 15.5 * ss), (4 * ss, 8 * ss)], fill=255)
    im = im.resize((s, s), Image.LANCZOS)
    tex("shard", to_img(np.asarray(im).astype(float) / 255))


def make_orb(name, rim_rgb, swirl_rgb):
    S = 64
    x, y = grid(S, S)
    r = np.sqrt(x * x + y * y)
    ang = np.arctan2(y, x)
    disc = 1 - smoothstep(0.70, 0.76, r)
    rim = np.exp(-((r - 0.76) / 0.05) ** 2)
    halo = np.exp(-((r - 0.78) / 0.14) ** 2) * (r > 0.76)
    swirl = (0.5 + 0.5 * np.sin(ang * 3 + r * 9)) * smoothstep(0.75, 0.2, r) * 0.22
    rgb = np.zeros((S, S, 3))
    for k in range(3):
        rgb[..., k] = 0.02 + swirl * swirl_rgb[k] + rim * rim_rgb[k]
    rgb = np.clip(rgb, 0, 1)
    a = np.clip(disc + rim * 0.95 + halo * 0.45, 0, 1)
    tex(name, to_img(a, rgb=rgb))


def make_mark_sheet():
    s, n, ss = 32, 5, 8
    sheet = Image.new("RGBA", (s * n, s))
    for k in range(n):
        im = Image.new("L", (s * ss, s * ss), 0)
        d = ImageDraw.Draw(im)
        c = s * ss / 2
        R = 11 * ss
        d.ellipse([c - R, c - R, c + R, c + R], outline=255, width=int(1.4 * ss))
        # inverted triangle (abyss rune)
        tr = 6.5 * ss
        pts = [(c + math.cos(a) * tr, c + math.sin(a) * tr) for a in (math.pi / 2 + i * 2 * math.pi / 3 for i in range(3))]
        d.line(pts + [pts[0]], fill=255, width=int(1.2 * ss), joint="curve")
        d.ellipse([c - 1.6 * ss, c - 1.6 * ss, c + 1.6 * ss, c + 1.6 * ss], fill=255)
        # pips (one per stack) on the outer rim, spread across the top arc
        stacks = k + 1
        for i in range(stacks):
            a = -math.pi / 2 + (i - (stacks - 1) / 2) * 0.62
            px, py = c + math.cos(a) * 14 * ss, c + math.sin(a) * 14 * ss
            q = 1.9 * ss
            d.polygon([(px, py - q), (px + q, py), (px, py + q), (px - q, py)], fill=255)
        im = im.resize((s, s), Image.LANCZOS)
        a = np.asarray(im).astype(float) / 255
        sheet.paste(glow_composite(to_img(a), 1.2, 0.5), (k * s, 0))
    tex("mark_sheet", sheet)


def make_blank():
    tex("blank", Image.new("RGBA", (16, 16), (0, 0, 0, 0)))


def make_item_icon():
    S = 32
    img = np.zeros((S, S, 4), dtype=np.uint8)
    start = np.array([5.0, 26.0])
    dvec = np.array([1.0, -1.0]) / math.sqrt(2)
    nvec = np.array([1.0, 1.0]) / math.sqrt(2)
    rng = np.random.default_rng(4)
    shape = np.zeros((S, S), dtype=bool)
    for yy in range(S):
        for xx in range(S):
            p = np.array([xx + 0.5, yy + 0.5]) - start
            s = p @ dvec
            q = p @ nvec
            col = None
            if 7.0 <= s <= 30.0:
                wb = 1.9 if s < 26 else 1.9 * (30.0 - s) / 4.0
                if abs(q) <= wb:
                    if abs(q) > wb - 0.75:
                        col = (226, 34, 58) if q > 0 else (150, 16, 46)
                    elif abs(q) < 0.45 and s < 27:
                        col = (150, 70, 235)
                    else:
                        col = (24, 6, 34)
            if 5.4 <= s < 7.0 and abs(q) <= 4.2:
                col = (110, 36, 170) if abs(q) > 1.1 else (255, 60, 80)
            if 1.0 <= s < 5.4 and abs(q) <= 0.95:
                col = (52, 24, 40) if int(s * 1.6) % 2 else (86, 34, 62)
            if -0.6 <= s < 1.0 and abs(q) <= 1.5:
                col = (240, 52, 76)
            if col:
                img[yy, xx, :3] = col
                img[yy, xx, 3] = 255
                shape[yy, xx] = True
    # outline
    out = np.zeros_like(shape)
    for yy in range(S):
        for xx in range(S):
            if shape[yy, xx]:
                continue
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                y2, x2 = yy + dy, xx + dx
                if 0 <= y2 < S and 0 <= x2 < S and shape[y2, x2]:
                    out[yy, xx] = True
    img[out] = (14, 2, 20, 255)
    # flame licks along the blade
    for _ in range(14):
        s = rng.uniform(9, 27)
        side = rng.choice([-1, 1])
        p = start + dvec * s + nvec * side * rng.uniform(3.2, 4.4)
        xx, yy = int(p[0]), int(p[1])
        if 0 <= xx < S and 0 <= yy < S and img[yy, xx, 3] == 0:
            img[yy, xx] = (200, 40, 70, 210) if rng.random() < 0.5 else (140, 60, 230, 190)
    tex("icon", Image.fromarray(img, "RGBA"))


def make_pack_icon():
    S = 256
    x, y = grid(S, S)
    r = np.sqrt(x * x + y * y)
    rgb = np.zeros((S, S, 3))
    rgb[..., 0] = 0.10 * np.exp(-r * 1.6) + 0.02
    rgb[..., 1] = 0.0
    rgb[..., 2] = 0.16 * np.exp(-r * 1.4) + 0.03
    base = to_img(np.ones((S, S)), rgb=rgb)
    sig = TEXTURES["sigil"].resize((240, 240), Image.LANCZOS)
    sa = np.asarray(sig).astype(float) / 255
    tint = np.zeros((240, 240, 4))
    tint[..., 0] = 0.65
    tint[..., 1] = 0.25
    tint[..., 2] = 1.0
    tint[..., 3] = sa[..., 3] * 0.55
    base.alpha_composite(Image.fromarray((tint * 255).astype(np.uint8), "RGBA"), (8, 8))
    gl = np.exp(-(r ** 2) * 6)
    glow = np.zeros((S, S, 4))
    glow[..., 0] = 1.0
    glow[..., 1] = 0.15
    glow[..., 2] = 0.25
    glow[..., 3] = gl * 0.55
    base.alpha_composite(Image.fromarray((glow * 255).astype(np.uint8), "RGBA"))
    icon = TEXTURES["icon"].resize((192, 192), Image.NEAREST)
    base.alpha_composite(icon, (32, 32))
    tex("pack_icon", base)


def build_textures():
    make_flame_sheet()
    make_smoke_sheet()
    make_crescent_sheet()
    make_glow()
    make_spark()
    make_streak()
    make_ring()
    make_ring_shatter()
    make_runes_sheet()
    make_sigil()
    make_crack()
    make_rift()
    make_spear()
    make_shard()
    make_orb("sun_core", rim_rgb=(0.85, 0.05, 0.12), swirl_rgb=(0.55, 0.05, 0.25))
    make_orb("void_core", rim_rgb=(0.62, 0.22, 1.0), swirl_rgb=(0.45, 0.12, 0.85))
    make_mark_sheet()
    make_blank()
    make_item_icon()
    make_pack_icon()
    pdir = os.path.join(RP, TEX_DIR)
    os.makedirs(pdir, exist_ok=True)
    for name, img in TEXTURES.items():
        if name in ("icon", "pack_icon", "blank"):
            continue
        img.save(os.path.join(pdir, f"{name}.png"))
    os.makedirs(os.path.join(RP, "textures/items"), exist_ok=True)
    os.makedirs(os.path.join(RP, "textures/entity"), exist_ok=True)
    TEXTURES["icon"].save(os.path.join(RP, "textures/items/abyssal_inferno.png"))
    TEXTURES["blank"].save(os.path.join(RP, "textures/entity/abyss_blank.png"))
    TEXTURES["pack_icon"].save(os.path.join(RP, "pack_icon.png"))
    TEXTURES["pack_icon"].save(os.path.join(BP, "pack_icon.png"))


# --------------------------------------------------------------------------
# particles
# --------------------------------------------------------------------------
PARTICLES = {}

# gradients are #AARRGGBB
G_CRIMSON = {"0.0": "#00FFD6A0", "0.08": "#FFFFB070", "0.3": "#FFFF3B1F", "0.6": "#FFB0102E",
             "0.85": "#AA4A0A5A", "1.0": "#00200028"}
G_VOID = {"0.0": "#00F0D0FF", "0.08": "#FFD7A8FF", "0.3": "#FF9A4DFF", "0.6": "#FF5A12C8",
          "0.85": "#AA2A0670", "1.0": "#00100030"}
G_ABYSS = {"0.0": "#00FFFFFF", "0.06": "#FFFFC4D0", "0.25": "#FFFF2A3A", "0.55": "#FFB21CC8",
           "0.85": "#AA4A0A80", "1.0": "#00000000"}
G_BLACK = {"0.0": "#00000000", "0.1": "#F0140612", "0.6": "#E00A020C", "1.0": "#00000000"}
G_SMOKE = {"0.0": "#00000000", "0.15": "#C01A0C1E", "0.6": "#8012081A", "1.0": "#00000000"}
G_EMBER = {"0.0": "#FFFFE0B0", "0.2": "#FFFF5A2A", "0.6": "#FFC01A9A", "1.0": "#00400050"}
G_SPARK = {"0.0": "#FFFFFFFF", "0.25": "#FFFF5070", "0.6": "#FFA020E0", "1.0": "#00300050"}
G_RING_VOID = {"0.0": "#FFFFE0FF", "0.2": "#FFD070FF", "0.5": "#FFB0207A", "1.0": "#00300030"}
G_RING_RED = {"0.0": "#FFFFE6C0", "0.2": "#FFFF6A3A", "0.5": "#FFC0182E", "1.0": "#00300010"}
G_RING_DARK = {"0.0": "#00000000", "0.1": "#C00A0010", "0.6": "#90080008", "1.0": "#00000000"}
G_SIGIL_VOID = {"0.0": "#00FFFFFF", "0.08": "#FFE6B3FF", "0.25": "#FFA347FF", "0.75": "#FF7A1FCC", "1.0": "#00300040"}
G_SIGIL_RED = {"0.0": "#00FFFFFF", "0.08": "#FFFFC0B0", "0.25": "#FFFF3A3A", "0.75": "#FFB0102E", "1.0": "#00300010"}
G_SHADOW = {"0.0": "#00000000", "0.12": "#B0050008", "0.85": "#A0050008", "1.0": "#00000000"}
G_MIST = {"0.0": "#00000000", "0.2": "#90200838", "0.7": "#70100620", "1.0": "#00000000"}
G_CRACK = {"0.0": "#FFFFFFFF", "0.1": "#FFC070FF", "0.55": "#FF7A20C0", "1.0": "#00200040"}

AGE = "v.particle_age / v.particle_lifetime"

UV_FLAME = {"texture_width": 256, "texture_height": 64,
            "flipbook": {"base_UV": [0, 0], "size_UV": [32, 64], "step_UV": [32, 0], "frames_per_second": 16,
                         "max_frame": 8, "stretch_to_lifetime": True, "loop": False}}
UV_SMOKE = {"texture_width": 256, "texture_height": 32,
            "flipbook": {"base_UV": [0, 0], "size_UV": [32, 32], "step_UV": [32, 0], "frames_per_second": 8,
                         "max_frame": 8, "stretch_to_lifetime": True, "loop": False}}
UV_CRESCENT = {"texture_width": 384, "texture_height": 64,
               "flipbook": {"base_UV": [0, 0], "size_UV": [64, 64], "step_UV": [64, 0], "frames_per_second": 24,
                            "max_frame": 6, "stretch_to_lifetime": True, "loop": False}}


def uv_full(w, h):
    return {"texture_width": w, "texture_height": h, "uv": [0, 0], "uv_size": [w, h]}


def particle(name, texture, material, comps):
    PARTICLES[name] = {
        "format_version": "1.10.0",
        "particle_effect": {
            "description": {
                "identifier": f"{NS}:{name}",
                "basic_render_parameters": {"material": material, "texture": f"{TEX_DIR}/{texture}"},
            },
            "components": comps,
        },
    }


def tint(grad):
    return {"minecraft:particle_appearance_tinting": {"color": {"interpolant": AGE, "gradient": grad}}}


def billboard(size, facing, uv, extra=None):
    b = {"size": size, "facing_camera_mode": facing, "uv": uv}
    if extra:
        b.update(extra)
    return {"minecraft:particle_appearance_billboard": b}


def instant(n, life=0.05):
    return {"minecraft:emitter_rate_instant": {"num_particles": n},
            "minecraft:emitter_lifetime_once": {"active_time": life}}


def steady(rate, maxp, active):
    return {"minecraft:emitter_rate_steady": {"spawn_rate": rate, "max_particles": maxp},
            "minecraft:emitter_lifetime_once": {"active_time": active}}


def init(expr):
    return {"minecraft:emitter_initialization": {"creation_expression": expr}}


def lifetime(expr):
    return {"minecraft:particle_lifetime_expression": {"max_lifetime": expr}}


def dyn(acc=(0, 0, 0), drag=0):
    return {"minecraft:particle_motion_dynamic": {"linear_acceleration": list(acc), "linear_drag_coefficient": drag}}


def merge(*ds):
    out = {}
    for d in ds:
        out.update(d)
    return out


def flame_particle(name, material, grad, n=3, scale=1.0, radius=0.25):
    particle(name, "flame_sheet", material, merge(
        instant(n),
        {"minecraft:emitter_shape_sphere": {"radius": radius, "direction": "outwards"}},
        lifetime("math.random(0.45, 0.75)"),
        {"minecraft:particle_initial_speed": "math.random(0.2, 0.6)"},
        dyn((0, 2.2, 0), 2.0),
        billboard([f"({0.28 * scale} + v.particle_random_1 * {0.22 * scale}) * (1 - 0.35 * {AGE})",
                   f"({0.56 * scale} + v.particle_random_1 * {0.44 * scale}) * (1 - 0.35 * {AGE})"],
                  "lookat_y", UV_FLAME),
        tint(grad),
    ))


def explosion_particle(name, material, grad, n):
    particle(name, "flame_sheet", material, merge(
        init("v.rad = v.radius > 0 ? v.radius : 3;"),
        instant(n),
        {"minecraft:emitter_shape_sphere": {"radius": 0.4, "direction": "outwards"}},
        lifetime("math.random(0.55, 0.95)"),
        {"minecraft:particle_initial_speed": "v.rad * math.random(2.0, 3.0)"},
        dyn((0, 1.5, 0), 3.2),
        billboard([f"(0.7 + v.particle_random_1 * 0.6) * (1 - 0.4 * {AGE})",
                   f"(1.2 + v.particle_random_1 * 0.9) * (1 - 0.4 * {AGE})"], "lookat_y", UV_FLAME),
        tint(grad),
    ))


def flat_decal(name, texture, material, grad, size_expr, default_life, spin_rate=0.0, w=128, h=128,
               default_radius=3.0, y=0.06, random_spin=True):
    particle(name, texture, material, merge(
        init(f"v.rad = v.radius > 0 ? v.radius : {default_radius}; v.lf = v.life > 0 ? v.life : {default_life};"),
        instant(1),
        {"minecraft:emitter_shape_point": {"offset": [0, y, 0]}},
        lifetime("v.lf"),
        {"minecraft:particle_initial_spin": {"rotation": "math.random(0, 360)" if random_spin else 0,
                                             "rotation_rate": spin_rate}},
        {"minecraft:particle_initial_speed": 0},
        dyn(),
        billboard([size_expr, size_expr], "emitter_transform_xz", uv_full(w, h)),
        tint(grad),
    ))


def orbit_ring(name, texture, uv, grad, radius, tilt_deg, yaw_deg, speed_deg, rate, active, collapse_at,
               collapse_len, size, material="particles_add", grow=0.35):
    t = math.radians(tilt_deg)
    yw = math.radians(yaw_deg)
    th = f"(v.particle_random_1 * 360 + v.particle_age * {speed_deg})"
    R = (f"({radius} * (v.emitter_age > {collapse_at} ? math.max(0.08, 1 - (v.emitter_age - {collapse_at}) / {collapse_len})"
         f" : math.min(1, v.emitter_age / {grow})))")
    # point on a circle in plane spanned by X and (0, sin t, cos t), then yawed
    px = f"(math.cos({th}) * {R})"
    pz = f"(math.sin({th}) * {R} * {math.cos(t):.4f})"
    py = f"(math.sin({th}) * {R} * {math.sin(t):.4f})"
    rx = f"({px} * {math.cos(yw):.4f} - {pz} * {math.sin(yw):.4f})"
    rz = f"({px} * {math.sin(yw):.4f} + {pz} * {math.cos(yw):.4f})"
    particle(name, texture, material, merge(
        steady(rate, rate * 2, active),
        {"minecraft:emitter_shape_point": {}},
        lifetime("math.random(0.45, 0.7)"),
        {"minecraft:particle_motion_parametric": {"relative_position": [rx, py, rz]}},
        billboard([f"{size} * (1 - 0.5 * {AGE})", f"{size} * (1 - 0.5 * {AGE})"] if uv is not UV_FLAME else
                  [f"{size * 0.6} * (1 - 0.4 * {AGE})", f"{size} * (1 - 0.4 * {AGE})"],
                  "lookat_xyz", uv),
        tint(grad),
    ))


def build_particles():
    # ---- primitives -------------------------------------------------------
    flame_particle("black_flame", "particles_blend", G_BLACK, n=3)
    flame_particle("crimson_flame", "particles_add", G_CRIMSON, n=3, scale=1.15)
    flame_particle("void_flame", "particles_add", G_VOID, n=3, scale=1.1)

    particle("dark_smoke", "smoke_sheet", "particles_blend", merge(
        instant(2),
        {"minecraft:emitter_shape_sphere": {"radius": 0.3, "direction": "outwards"}},
        lifetime("math.random(1.0, 1.6)"),
        {"minecraft:particle_initial_speed": "math.random(0.2, 0.5)"},
        {"minecraft:particle_initial_spin": {"rotation": "math.random(0, 360)", "rotation_rate": "math.random(-30, 30)"}},
        dyn((0, 0.6, 0), 1.2),
        billboard([f"0.5 + {AGE} * 0.9 + v.particle_random_1 * 0.3", f"0.5 + {AGE} * 0.9 + v.particle_random_1 * 0.3"],
                  "rotate_xyz", UV_SMOKE),
        tint(G_SMOKE),
    ))

    particle("ember", "spark", "particles_add", merge(
        instant(6),
        {"minecraft:emitter_shape_sphere": {"radius": 0.5, "direction": "outwards"}},
        lifetime("math.random(0.7, 1.3)"),
        {"minecraft:particle_initial_speed": "math.random(0.4, 1.4)"},
        dyn((0, 1.0, 0), 1.5),
        billboard([f"(0.06 + v.particle_random_2 * 0.05) * (1 - 0.6 * {AGE})"] * 2, "lookat_xyz", uv_full(16, 16)),
        tint(G_EMBER),
    ))

    particle("void_mote", "glow", "particles_add", merge(
        instant(4),
        {"minecraft:emitter_shape_sphere": {"radius": 0.6, "direction": "outwards"}},
        lifetime("math.random(0.8, 1.4)"),
        {"minecraft:particle_initial_speed": "math.random(0.1, 0.4)"},
        dyn((0, 0.5, 0), 1.0),
        billboard([f"(0.08 + v.particle_random_2 * 0.08) * (1 - 0.5 * {AGE})"] * 2, "lookat_xyz", uv_full(64, 64)),
        tint(G_VOID),
    ))

    # ---- hits ---------------------------------------------------------------
    particle("hit_spark", "streak", "particles_add", merge(
        instant(14),
        {"minecraft:emitter_shape_sphere": {"radius": 0.15, "direction": "outwards"}},
        lifetime("math.random(0.16, 0.3)"),
        {"minecraft:particle_initial_speed": "math.random(5, 10)"},
        dyn((0, -2, 0), 7),
        billboard([f"0.55 * (1 - {AGE})", 0.06], "lookat_direction", uv_full(64, 8)),
        tint(G_SPARK),
    ))
    particle("hit_flash", "glow", "particles_add", merge(
        instant(1),
        {"minecraft:emitter_shape_point": {}},
        lifetime(0.16),
        {"minecraft:particle_initial_speed": 0},
        dyn(),
        billboard([f"1.4 * (1 - {AGE})"] * 2, "lookat_xyz", uv_full(64, 64)),
        tint({"0.0": "#FFFFFFFF", "0.4": "#FFFF4A6A", "1.0": "#00800090"}),
    ))
    slash_size = "(v.size > 0 ? v.size : 2.2)"
    particle("slash", "crescent_sheet", "particles_add", merge(
        instant(1),
        {"minecraft:emitter_shape_point": {}},
        lifetime(0.24),
        {"minecraft:particle_initial_speed": 0},
        {"minecraft:particle_initial_spin": {"rotation": "v.angle + math.random(-6, 6)", "rotation_rate": 0}},
        dyn(),
        billboard([slash_size, slash_size], "lookat_xyz", UV_CRESCENT),
        tint(G_ABYSS),
    ))
    particle("slash_dark", "crescent_sheet", "particles_blend", merge(
        instant(1),
        {"minecraft:emitter_shape_point": {}},
        lifetime(0.32),
        {"minecraft:particle_initial_speed": 0},
        {"minecraft:particle_initial_spin": {"rotation": "v.angle + 4", "rotation_rate": 0}},
        dyn(),
        billboard([f"{slash_size} * 1.12", f"{slash_size} * 1.12"], "lookat_xyz", UV_CRESCENT),
        tint({"0.0": "#00000000", "0.1": "#E0100010", "0.7": "#A0080008", "1.0": "#00000000"}),
    ))

    # ---- flat ground shapes ---------------------------------------------------
    ease_out = f"(1 - math.pow(1 - {AGE}, 3))"
    flat_decal("ring_wave", "ring", "particles_add", G_RING_VOID, f"v.rad * 2.33 * {ease_out}", 0.4)
    flat_decal("ring_wave_red", "ring", "particles_add", G_RING_RED, f"v.rad * 2.33 * {ease_out}", 0.4)
    flat_decal("ring_wave_dark", "ring", "particles_blend", G_RING_DARK, f"v.rad * 2.33 * {ease_out}", 0.55)
    flat_decal("ring_contract", "ring", "particles_add", G_RING_VOID,
               f"math.max(0.2, v.rad * 2.33 * (1 - math.pow({AGE}, 2)))", 0.45, default_radius=5)
    flat_decal("ring_shatter", "ring_shatter", "particles_add", G_RING_VOID, f"v.rad * 2.38 * {ease_out}", 0.55,
               spin_rate=40)
    flat_decal("sigil", "sigil", "particles_add", G_SIGIL_VOID,
               f"v.rad * 2 * (0.82 + 0.18 * math.min(1, v.particle_age * 5))", 1.2, spin_rate=24, w=256, h=256)
    flat_decal("sigil_red", "sigil", "particles_add", G_SIGIL_RED,
               f"v.rad * 2 * (0.82 + 0.18 * math.min(1, v.particle_age * 5))", 1.2, spin_rate=-18, w=256, h=256)
    flat_decal("ground_shadow", "glow", "particles_blend", G_SHADOW, "v.rad * 2.4", 1.2, w=64, h=64, y=0.04)
    flat_decal("crack", "crack", "particles_add", G_CRACK, "v.rad * 2", 1.4, default_radius=1.3, y=0.07)
    flat_decal("crack_dark", "crack", "particles_blend",
               {"0.0": "#00000000", "0.05": "#F0080008", "0.7": "#D0080008", "1.0": "#00000000"},
               "v.rad * 2.1", 1.6, default_radius=1.3, y=0.065)

    # ---- columns, rifts, spears ---------------------------------------------
    for name, grad in (("pillar", G_CRIMSON), ("pillar_void", G_VOID)):
        particle(name, "flame_sheet", "particles_add", merge(
            init("v.h = v.height > 0 ? v.height : 2.6;"),
            instant(1),
            {"minecraft:emitter_shape_point": {"offset": [0, "v.h * 0.4", 0]}},
            lifetime("math.random(0.5, 0.65)"),
            {"minecraft:particle_initial_speed": 0},
            dyn((0, 3, 0), 2),
            billboard(["v.h * 0.32 * (1 - 0.5 * " + AGE + ")", f"v.h * math.min(1, {AGE} * 6)"], "lookat_y", UV_FLAME),
            tint(grad),
        ))
    particle("pillar_dark", "flame_sheet", "particles_blend", merge(
        init("v.h = v.height > 0 ? v.height : 2.6;"),
        instant(1),
        {"minecraft:emitter_shape_point": {"offset": [0, "v.h * 0.4", 0]}},
        lifetime("math.random(0.55, 0.7)"),
        {"minecraft:particle_initial_speed": 0},
        dyn((0, 3, 0), 2),
        billboard([f"v.h * 0.2 * (1 - 0.5 * {AGE})", f"v.h * 0.85 * math.min(1, {AGE} * 6)"], "lookat_y", UV_FLAME),
        tint(G_BLACK),
    ))
    particle("rift", "rift", "particles_add", merge(
        instant(1),
        {"minecraft:emitter_shape_point": {"offset": [0, 1.2, 0]}},
        lifetime(0.8),
        {"minecraft:particle_initial_speed": 0},
        dyn(),
        billboard([f"0.75 * (1 - 0.6 * {AGE})", f"2.8 * math.min(1, {AGE} * 8)"], "lookat_y", uv_full(32, 128)),
        tint(G_VOID),
    ))
    particle("rift_dark", "rift", "particles_blend", merge(
        instant(1),
        {"minecraft:emitter_shape_point": {"offset": [0, 1.2, 0]}},
        lifetime(0.9),
        {"minecraft:particle_initial_speed": 0},
        dyn(),
        billboard([f"0.34 * (1 - 0.6 * {AGE})", f"2.5 * math.min(1, {AGE} * 8)"], "lookat_y", uv_full(32, 128)),
        tint({"0.0": "#FF000000", "0.7": "#F0080008", "1.0": "#00000000"}),
    ))
    direction = ["v.dx", "v.dy", "v.dz"]
    particle("spear_head", "spear", "particles_add", merge(
        instant(1),
        {"minecraft:emitter_shape_point": {"direction": direction}},
        lifetime(0.1),
        {"minecraft:particle_initial_speed": 0.05},
        dyn(),
        billboard([1.8, 0.45], "lookat_direction", uv_full(128, 32)),
        tint({"0.0": "#FFF0D8FF", "1.0": "#C0A040FF"}),
    ))
    particle("spear_dark", "spear", "particles_blend", merge(
        instant(1),
        {"minecraft:emitter_shape_point": {"direction": direction}},
        lifetime(0.1),
        {"minecraft:particle_initial_speed": 0.05},
        dyn(),
        billboard([1.35, 0.24], "lookat_direction", uv_full(128, 32)),
        tint({"0.0": "#FF050008", "1.0": "#E0050008"}),
    ))
    particle("spear_trail", "streak", "particles_add", merge(
        instant(2),
        {"minecraft:emitter_shape_sphere": {"radius": 0.12, "direction": ["-v.dx", "-v.dy", "-v.dz"]}},
        lifetime("math.random(0.3, 0.45)"),
        {"minecraft:particle_initial_speed": 0.6},
        dyn((0, 0, 0), 1),
        billboard([f"0.9 * (1 - {AGE})", 0.07], "lookat_direction", uv_full(64, 8)),
        tint(G_VOID),
    ))
    particle("soul_stream", "streak", "particles_add", merge(
        instant(6),
        {"minecraft:emitter_shape_sphere": {"radius": 0.45, "direction": direction}},
        lifetime(0.5),
        {"minecraft:particle_initial_speed": "v.dist * 2"},
        dyn(),
        billboard([0.7, 0.09], "lookat_direction", uv_full(64, 8)),
        tint({"0.0": "#00FFFFFF", "0.15": "#FFE0A0FF", "0.7": "#FFB03070", "1.0": "#00500060"}),
    ))

    # ---- suction / implosion / explosions --------------------------------------
    particle("suction", "streak", "particles_add", merge(
        init("v.rad = v.radius > 0 ? v.radius : 5;"),
        instant(22),
        {"minecraft:emitter_shape_sphere": {"radius": "v.rad", "surface_only": True, "direction": "inwards"}},
        lifetime(0.5),
        {"minecraft:particle_initial_speed": "v.rad * 1.9"},
        dyn(),
        billboard([0.6, 0.05], "lookat_direction", uv_full(64, 8)),
        tint({"0.0": "#00C080FF", "0.3": "#FFC080FF", "1.0": "#FF6A10C0"}),
    ))
    particle("implode", "glow", "particles_add", merge(
        init("v.rad = v.radius > 0 ? v.radius : 3;"),
        instant(16),
        {"minecraft:emitter_shape_sphere": {"radius": "v.rad", "surface_only": True, "direction": "inwards"}},
        lifetime(0.45),
        {"minecraft:particle_initial_speed": "v.rad * 2.2"},
        dyn(),
        billboard([f"0.3 * (1 - 0.8 * {AGE})"] * 2, "lookat_xyz", uv_full(64, 64)),
        tint(G_VOID),
    ))
    particle("charge_gather", "spark", "particles_add", merge(
        instant(6),
        {"minecraft:emitter_shape_sphere": {"radius": 2.2, "surface_only": True, "direction": "inwards"}},
        lifetime(0.45),
        {"minecraft:particle_initial_speed": 4.6},
        dyn(),
        billboard(["0.1 + v.particle_random_1 * 0.06"] * 2, "lookat_xyz", uv_full(16, 16)),
        tint({"0.0": "#00FFFFFF", "0.3": "#FFE0A0FF", "1.0": "#FFFF3050"}),
    ))
    particle("explosion_flash", "glow", "particles_add", merge(
        init("v.rad = v.radius > 0 ? v.radius : 3;"),
        instant(1),
        {"minecraft:emitter_shape_point": {}},
        lifetime(0.3),
        {"minecraft:particle_initial_speed": 0},
        dyn(),
        billboard([f"v.rad * 1.5 * math.sqrt(math.max(0, 1 - {AGE}))"] * 2, "lookat_xyz", uv_full(64, 64)),
        tint({"0.0": "#FFFFFFFF", "0.3": "#FFFF4A6A", "0.7": "#FFA020E0", "1.0": "#00300040"}),
    ))
    explosion_particle("explosion_black", "particles_blend", G_BLACK, 34)
    explosion_particle("explosion_crimson", "particles_add", G_CRIMSON, 28)
    explosion_particle("explosion_void", "particles_add", G_VOID, 24)
    particle("shards", "shard", "particles_add", merge(
        instant(18),
        {"minecraft:emitter_shape_sphere": {"radius": 0.3, "direction": ["math.random(-1,1)", "math.random(0.3,1.2)", "math.random(-1,1)"]}},
        lifetime("math.random(0.6, 1.0)"),
        {"minecraft:particle_initial_speed": "math.random(4, 9)"},
        {"minecraft:particle_initial_spin": {"rotation": "math.random(0, 360)", "rotation_rate": "math.random(-400, 400)"}},
        dyn((0, -9, 0), 1),
        billboard(["0.12 + v.particle_random_1 * 0.12"] * 2, "rotate_xyz", uv_full(16, 16)),
        tint({"0.0": "#FFF0D0FF", "0.4": "#FFA040FF", "1.0": "#00300040"}),
    ))
    for name, mat, grad, n in (("flame_wave", "particles_add", G_CRIMSON, 48),
                               ("flame_wave_dark", "particles_blend", G_BLACK, 36),
                               ("flame_wave_void", "particles_add", G_VOID, 36)):
        particle(name, "flame_sheet", mat, merge(
            init("v.rad = v.radius > 0 ? v.radius : 5;"),
            instant(n),
            {"minecraft:emitter_shape_disc": {"radius": 0.6, "plane_normal": [0, 1, 0], "direction": "outwards",
                                              "offset": [0, 0.4, 0]}},
            lifetime("math.random(0.6, 0.8)"),
            {"minecraft:particle_initial_speed": "v.rad * math.random(2.2, 2.6)"},
            dyn((0, 1.2, 0), 2.5),
            billboard([f"(0.6 + v.particle_random_1 * 0.4) * (1 - 0.4 * {AGE})",
                       f"(1.1 + v.particle_random_1 * 0.6) * (1 - 0.4 * {AGE})"], "lookat_y", UV_FLAME),
            tint(grad),
        ))

    # ---- Black Sun (persistent emitters, 5 s) -----------------------------------
    sun_scale = ("(math.min(1, v.particle_age / 0.35) * (v.particle_age > 4.55 ? "
                 "math.max(0.12, 1 - (v.particle_age - 4.55) / 0.45) : 1))")
    particle("sun_core", "sun_core", "particles_blend", merge(
        instant(1),
        {"minecraft:emitter_shape_point": {}},
        lifetime(5.05),
        {"minecraft:particle_initial_speed": 0},
        {"minecraft:particle_initial_spin": {"rotation": 0, "rotation_rate": 40}},
        dyn(),
        billboard([f"2.4 * {sun_scale} * (1 + 0.05 * math.sin(v.particle_age * 720))"] * 2, "lookat_xyz",
                  uv_full(64, 64)),
    ))
    for name, size, col, rate in (("sun_corona", 3.8, [1.0, 0.18, 0.12, 0.85], 400),
                                  ("sun_corona_void", 5.2, [0.55, 0.15, 1.0, 0.55], 260)):
        particle(name, "glow", "particles_add", merge(
            instant(1),
            {"minecraft:emitter_shape_point": {}},
            lifetime(5.05),
            {"minecraft:particle_initial_speed": 0},
            dyn(),
            billboard([f"{size} * {sun_scale} * (1 + 0.12 * math.sin(v.particle_age * {rate}))"] * 2, "lookat_xyz",
                      uv_full(64, 64)),
            {"minecraft:particle_appearance_tinting": {"color": col}},
        ))
    orbit_ring("sun_ring_a", "flame_sheet", UV_FLAME, G_CRIMSON, 1.7, 30, 0, 300, 70, 4.95, 4.55, 0.45, 0.55)
    orbit_ring("sun_ring_b", "spark", uv_full(16, 16), G_VOID, 2.0, -35, 60, -260, 60, 4.95, 4.55, 0.45, 0.22)
    orbit_ring("sun_ring_c", "flame_sheet", UV_FLAME, G_BLACK, 1.45, 75, 120, 340, 40, 4.95, 4.55, 0.45, 0.5,
               material="particles_blend")
    particle("sun_rim_flames", "flame_sheet", "particles_blend", merge(
        steady(26, 60, 4.5),
        {"minecraft:emitter_shape_sphere": {"radius": 1.05, "surface_only": True, "direction": "outwards"}},
        lifetime("math.random(0.5, 0.8)"),
        {"minecraft:particle_initial_speed": 0.6},
        dyn((0, 0.8, 0), 1),
        billboard([f"(0.35 + v.particle_random_1 * 0.2) * (1 - 0.4 * {AGE})",
                   f"(0.7 + v.particle_random_1 * 0.3) * (1 - 0.4 * {AGE})"], "lookat_y", UV_FLAME),
        tint(G_BLACK),
    ))
    particle("sun_inflow", "streak", "particles_add", merge(
        steady(40, 60, 4.5),
        {"minecraft:emitter_shape_sphere": {"radius": 5, "surface_only": True, "direction": "inwards"}},
        lifetime(0.5),
        {"minecraft:particle_initial_speed": 8.5},
        dyn(),
        billboard([0.7, 0.05], "lookat_direction", uv_full(64, 8)),
        tint({"0.0": "#00C080FF", "0.3": "#FFC080FF", "1.0": "#FF6A10C0"}),
    ))

    # ---- Void Core (ultimate, 3.5 s) ------------------------------------------------
    core_scale = ("(math.min(1, v.particle_age / 0.6) * (v.particle_age > 2.6 ? "
                  "math.max(0.15, 1 - (v.particle_age - 2.6) / 0.9) : 1))")
    particle("core_orb", "void_core", "particles_blend", merge(
        instant(1),
        {"minecraft:emitter_shape_point": {}},
        lifetime(3.55),
        {"minecraft:particle_initial_speed": 0},
        {"minecraft:particle_initial_spin": {"rotation": 0, "rotation_rate": -60}},
        dyn(),
        billboard([f"3.4 * {core_scale} * (1 + 0.06 * math.sin(v.particle_age * 900))"] * 2, "lookat_xyz",
                  uv_full(64, 64)),
    ))
    particle("core_halo", "glow", "particles_add", merge(
        instant(1),
        {"minecraft:emitter_shape_point": {}},
        lifetime(3.55),
        {"minecraft:particle_initial_speed": 0},
        dyn(),
        billboard([f"7.0 * {core_scale} * (1 + 0.15 * math.sin(v.particle_age * 500))"] * 2, "lookat_xyz",
                  uv_full(64, 64)),
        {"minecraft:particle_appearance_tinting": {"color": [0.55, 0.12, 1.0, 0.75]}},
    ))
    orbit_ring("core_ring_a", "spark", uv_full(16, 16), G_VOID, 3.4, 10, 0, 280, 80, 3.4, 2.6, 0.9, 0.3, grow=0.6)
    orbit_ring("core_ring_b", "flame_sheet", UV_FLAME, G_CRIMSON, 3.0, 60, 40, -320, 60, 3.4, 2.6, 0.9, 0.6, grow=0.6)
    orbit_ring("core_ring_c", "flame_sheet", UV_FLAME, G_BLACK, 2.6, -60, 100, 360, 50, 3.4, 2.6, 0.9, 0.6,
               material="particles_blend", grow=0.6)
    particle("core_inflow", "streak", "particles_add", merge(
        steady(90, 140, 3.4),
        {"minecraft:emitter_shape_sphere": {"radius": 12, "surface_only": True, "direction": "inwards"}},
        lifetime(0.55),
        {"minecraft:particle_initial_speed": 21},
        dyn(),
        billboard([1.3, 0.08], "lookat_direction", uv_full(64, 8)),
        tint({"0.0": "#00C080FF", "0.3": "#FFC080FF", "1.0": "#FF6A10C0"}),
    ))
    particle("core_lightning", "streak", "particles_add", merge(
        steady(14, 30, 3.4),
        {"minecraft:emitter_shape_sphere": {"radius": 1.7, "surface_only": True, "direction": "outwards"}},
        lifetime(0.12),
        {"minecraft:particle_initial_speed": 7},
        dyn(),
        billboard([1.5, 0.06], "lookat_direction", uv_full(64, 8)),
        tint({"0.0": "#FFFFFFFF", "1.0": "#00B060FF"}),
    ))

    # ---- zones / fields ------------------------------------------------------------
    particle("zone_mist", "smoke_sheet", "particles_blend", merge(
        init("v.rad = v.radius > 0 ? v.radius : 4; v.lf = v.life > 0 ? v.life : 4;"),
        {"minecraft:emitter_rate_steady": {"spawn_rate": 18, "max_particles": 50},
         "minecraft:emitter_lifetime_expression": {"activation_expression": 1,
                                                    "expiration_expression": "v.emitter_age > v.lf - 0.8"}},
        {"minecraft:emitter_shape_disc": {"radius": "v.rad", "plane_normal": [0, 1, 0], "offset": [0, 0.25, 0],
                                          "direction": [0, 1, 0]}},
        lifetime("math.random(1.2, 1.8)"),
        {"minecraft:particle_initial_speed": 0.15},
        {"minecraft:particle_initial_spin": {"rotation": "math.random(0, 360)", "rotation_rate": "math.random(-20, 20)"}},
        dyn((0, 0.2, 0), 1),
        billboard([f"1.0 + {AGE} * 0.7"] * 2, "rotate_xyz", UV_SMOKE),
        tint(G_MIST),
    ))
    for name, tex_name, uvd, grad, rate, mat, size, n_acc in (
            ("zone_motes", "glow", uv_full(64, 64), G_VOID, 20, "particles_add", "0.12", 0.8),
            ("field_flames", "flame_sheet", UV_FLAME, G_BLACK, 30, "particles_blend", None, 1.6),
            ("field_flames_red", "flame_sheet", UV_FLAME, G_CRIMSON, 22, "particles_add", None, 1.6),
            ("field_embers", "spark", uv_full(16, 16), G_EMBER, 16, "particles_add", "0.08", 1.0)):
        size_expr = ([f"{size} * (1 - 0.5 * {AGE})"] * 2 if size else
                     [f"(0.35 + v.particle_random_1 * 0.3) * (1 - 0.4 * {AGE})",
                      f"(0.7 + v.particle_random_1 * 0.6) * (1 - 0.4 * {AGE})"])
        particle(name, tex_name, mat, merge(
            init("v.rad = v.radius > 0 ? v.radius : 4; v.lf = v.life > 0 ? v.life : 4;"),
            {"minecraft:emitter_rate_steady": {"spawn_rate": rate, "max_particles": rate * 3},
             "minecraft:emitter_lifetime_expression": {"activation_expression": 1,
                                                        "expiration_expression": "v.emitter_age > v.lf - 0.6"}},
            {"minecraft:emitter_shape_disc": {"radius": "v.rad", "plane_normal": [0, 1, 0], "offset": [0, 0.1, 0],
                                              "direction": [0, 1, 0]}},
            lifetime("math.random(0.6, 1.2)"),
            {"minecraft:particle_initial_speed": "math.random(0.1, 0.5)"},
            dyn((0, n_acc, 0), 1.2),
            billboard(size_expr, "lookat_y" if not size else "lookat_xyz", uvd),
            tint(grad),
        ))
    particle("portal_rise", "streak", "particles_add", merge(
        steady(70, 80, 0.9),
        {"minecraft:emitter_shape_disc": {"radius": 1.4, "plane_normal": [0, 1, 0], "direction": [0, 1, 0]}},
        lifetime("math.random(0.3, 0.5)"),
        {"minecraft:particle_initial_speed": "math.random(4, 8)"},
        dyn(),
        billboard([0.9, 0.06], "lookat_direction", uv_full(64, 8)),
        tint(G_VOID),
    ))
    particle("rune_float", "runes_sheet", "particles_add", merge(
        init("v.rad = v.radius > 0 ? v.radius : 2;"),
        instant(8),
        {"minecraft:emitter_shape_disc": {"radius": "v.rad", "plane_normal": [0, 1, 0], "surface_only": True,
                                          "direction": [0, 1, 0], "offset": [0, 0.3, 0]}},
        lifetime("math.random(0.9, 1.4)"),
        {"minecraft:particle_initial_speed": "math.random(0.6, 1.2)"},
        dyn((0, 0, 0), 0.8),
        billboard([0.32, 0.32], "lookat_xyz",
                  {"texture_width": 128, "texture_height": 16, "uv": ["math.floor(v.particle_random_3 * 8) * 16", 0],
                   "uv_size": [16, 16]}),
        tint(G_SIGIL_VOID),
    ))
    particle("mark_rune", "mark_sheet", "particles_add", merge(
        init("v.stk = math.clamp(math.floor(v.stack) - 1, 0, 4);"),
        instant(1),
        {"minecraft:emitter_shape_point": {}},
        lifetime(0.42),
        {"minecraft:particle_initial_speed": 0},
        dyn(),
        billboard(["0.45 + v.stk * 0.03", "0.45 + v.stk * 0.03"], "lookat_xyz",
                  {"texture_width": 160, "texture_height": 32, "uv": ["v.stk * 32", 0], "uv_size": [32, 32]}),
        tint({"0.0": "#60FFFFFF", "0.25": "#FFE070FF", "0.8": "#FFB040FF", "1.0": "#40B040FF"}),
    ))

    pdir = os.path.join(RP, "particles")
    if os.path.isdir(pdir):
        shutil.rmtree(pdir)
    for name, data in PARTICLES.items():
        write_json(os.path.join(pdir, f"{name}.particle.json"), data)


# --------------------------------------------------------------------------
# player animations
# --------------------------------------------------------------------------
def keys(seq, smooth=True):
    """seq: list of (time, [x,y,z]). Returns a keyframe dict."""
    out = {}
    for t, v in seq:
        k = f"{t:g}" if isinstance(t, (int, float)) else t
        out[k] = {"post": v, "lerp_mode": "catmullrom"} if smooth else v
    return out


Z = [0, 0, 0]


def anim(length, bones, loop=False):
    data = {"animation_length": length, "override_previous_animation": True, "bones": {}}
    data["loop"] = loop
    for bone, chans in bones.items():
        data["bones"][bone] = {ch: keys(seq) for ch, seq in chans.items()}
    return data


def build_animations():
    A = {}
    A["animation.abyss.combo_1"] = anim(0.45, {
        "rightArm": {"rotation": [(0, Z), (0.08, [-165, -10, 35]), (0.14, [-150, -10, 30]), (0.22, [-35, 25, -25]),
                                  (0.36, [-30, 20, -20]), (0.45, Z)]},
        "leftArm": {"rotation": [(0, Z), (0.08, [-30, 0, -25]), (0.22, [25, 0, -20]), (0.36, [20, 0, -15]), (0.45, Z)]},
        "waist": {"rotation": [(0, Z), (0.08, [-5, -18, 0]), (0.22, [12, 22, 0]), (0.36, [10, 18, 0]), (0.45, Z)]},
        "rightLeg": {"rotation": [(0, Z), (0.22, [-12, 0, 0]), (0.36, [-10, 0, 0]), (0.45, Z)]},
        "leftLeg": {"rotation": [(0, Z), (0.22, [14, 0, 0]), (0.36, [12, 0, 0]), (0.45, Z)]},
    })
    A["animation.abyss.combo_2"] = anim(0.45, {
        "rightArm": {"rotation": [(0, Z), (0.08, [-20, 30, -35]), (0.14, [-15, 30, -40]), (0.24, [-160, -15, 40]),
                                  (0.36, [-150, -10, 35]), (0.45, Z)]},
        "leftArm": {"rotation": [(0, Z), (0.08, [-45, 0, -10]), (0.24, [15, 0, -30]), (0.45, Z)]},
        "waist": {"rotation": [(0, Z), (0.08, [8, 20, 0]), (0.24, [-8, -22, 0]), (0.36, [-6, -18, 0]), (0.45, Z)]},
        "head": {"rotation": [(0, Z), (0.24, [-10, 0, 0]), (0.45, Z)]},
        "rightLeg": {"rotation": [(0, Z), (0.24, [10, 0, 0]), (0.45, Z)]},
        "leftLeg": {"rotation": [(0, Z), (0.24, [-12, 0, 0]), (0.45, Z)]},
    })
    A["animation.abyss.combo_3"] = anim(0.5, {
        "rightArm": {"rotation": [(0, Z), (0.1, [25, 0, 15]), (0.16, [30, 0, 15]), (0.24, [-92, 0, 0]),
                                  (0.38, [-90, 0, 0]), (0.5, Z)]},
        "leftArm": {"rotation": [(0, Z), (0.1, [-75, 0, -15]), (0.24, [30, 0, -25]), (0.38, [25, 0, -20]), (0.5, Z)]},
        "waist": {"rotation": [(0, Z), (0.1, [-6, -25, 0]), (0.24, [18, 15, 0]), (0.38, [15, 12, 0]), (0.5, Z)]},
        "rightLeg": {"rotation": [(0, Z), (0.24, [-20, 0, 0]), (0.38, [-18, 0, 0]), (0.5, Z)]},
        "leftLeg": {"rotation": [(0, Z), (0.24, [22, 0, 0]), (0.38, [20, 0, 0]), (0.5, Z)]},
    })
    combo4 = anim(0.55, {
        "rightArm": {"rotation": [(0, Z), (0.06, [-85, 0, 20]), (0.3, [-85, 0, 20]), (0.45, [-40, 0, 10]), (0.55, Z)]},
        "leftArm": {"rotation": [(0, Z), (0.06, [-20, 0, -60]), (0.3, [-20, 0, -60]), (0.55, Z)]},
        "waist": {"rotation": [(0, Z), (0.06, [8, 0, 0]), (0.3, [10, 0, 0]), (0.55, Z)]},
        "rightLeg": {"rotation": [(0, Z), (0.15, [-15, 0, 8]), (0.3, [-10, 0, 5]), (0.55, Z)]},
        "leftLeg": {"rotation": [(0, Z), (0.15, [15, 0, -8]), (0.3, [10, 0, -5]), (0.55, Z)]},
    })
    combo4["bones"]["root"] = {"rotation": {
        "0": {"post": Z, "lerp_mode": "catmullrom"},
        "0.06": {"post": [0, 20, 0], "lerp_mode": "catmullrom"},
        "0.3": {"pre": [0, 360, 0], "post": [0, 0, 0]},
        "0.55": [0, 0, 0],
    }}
    A["animation.abyss.combo_4"] = combo4
    A["animation.abyss.combo_5"] = anim(0.7, {
        "root": {"position": [(0, Z), (0.12, [0, 3.5, 0]), (0.24, [0, 5, 0]), (0.32, [0, 0, 0]), (0.7, Z)]},
        "rightArm": {"rotation": [(0, Z), (0.12, [-190, 0, 10]), (0.24, [-200, 0, 8]), (0.32, [-40, 0, 0]),
                                  (0.5, [-35, 0, 0]), (0.7, Z)]},
        "leftArm": {"rotation": [(0, Z), (0.12, [-170, 0, -15]), (0.24, [-175, 0, -12]), (0.32, [-30, 0, -30]),
                                 (0.5, [-25, 0, -28]), (0.7, Z)]},
        "waist": {"rotation": [(0, Z), (0.24, [-18, 0, 0]), (0.32, [28, 0, 0]), (0.5, [25, 0, 0]), (0.7, Z)]},
        "head": {"rotation": [(0, Z), (0.24, [-15, 0, 0]), (0.32, [10, 0, 0]), (0.7, Z)]},
        "rightLeg": {"rotation": [(0, Z), (0.24, [-25, 0, 0]), (0.32, [-25, 0, 5]), (0.5, [-22, 0, 5]), (0.7, Z)]},
        "leftLeg": {"rotation": [(0, Z), (0.24, [-25, 0, 0]), (0.32, [30, 0, -5]), (0.5, [26, 0, -5]), (0.7, Z)]},
    })
    A["animation.abyss.rend"] = anim(0.8, {
        "root": {"position": [(0, Z), (0.12, [0, 0.8, 0]), (0.28, [0, -1.5, 0]), (0.6, [0, -1.2, 0]), (0.8, Z)]},
        "rightArm": {"rotation": [(0, Z), (0.12, [-200, 0, 10]), (0.2, [-205, 0, 10]), (0.28, [-25, 0, -5]),
                                  (0.6, [-25, 0, -5]), (0.8, Z)]},
        "leftArm": {"rotation": [(0, Z), (0.12, [-190, 0, -10]), (0.2, [-195, 0, -10]), (0.28, [-20, 0, -18]),
                                 (0.6, [-22, 0, -18]), (0.8, Z)]},
        "waist": {"rotation": [(0, Z), (0.12, [-15, 0, 0]), (0.28, [30, 0, 0]), (0.6, [26, 0, 0]), (0.8, Z)]},
        "head": {"rotation": [(0, Z), (0.12, [-20, 0, 0]), (0.28, [-5, 0, 0]), (0.8, Z)]},
        "rightLeg": {"rotation": [(0, Z), (0.28, [-35, 0, 0]), (0.6, [-32, 0, 0]), (0.8, Z)]},
        "leftLeg": {"rotation": [(0, Z), (0.28, [25, 0, 0]), (0.6, [22, 0, 0]), (0.8, Z)]},
    })
    A["animation.abyss.black_sun"] = anim(1.0, {
        "leftArm": {"rotation": [(0, Z), (0.15, [-60, 0, -30]), (0.3, [-100, 0, -5]), (0.7, [-98, 0, -5]), (1.0, Z)]},
        "rightArm": {"rotation": [(0, Z), (0.15, [-50, 0, 30]), (0.3, [25, 0, 25]), (0.7, [22, 0, 22]), (1.0, Z)]},
        "waist": {"rotation": [(0, Z), (0.15, [5, -20, 0]), (0.3, [-6, 15, 0]), (0.7, [-5, 12, 0]), (1.0, Z)]},
        "head": {"rotation": [(0, Z), (0.3, [-8, 0, 0]), (0.7, [-8, 0, 0]), (1.0, Z)]},
        "rightLeg": {"rotation": [(0, Z), (0.3, [18, 0, 0]), (0.7, [16, 0, 0]), (1.0, Z)]},
        "leftLeg": {"rotation": [(0, Z), (0.3, [-15, 0, 0]), (0.7, [-14, 0, 0]), (1.0, Z)]},
    })
    A["animation.abyss.flare"] = anim(0.9, {
        "root": {"position": [(0, Z), (0.3, [0, -2.5, 0]), (0.4, [0, 0.5, 0]), (0.7, [0, 0.3, 0]), (0.9, Z)]},
        "rightArm": {"rotation": [(0, Z), (0.3, [-55, 0, -35]), (0.4, [-20, 0, 110]), (0.7, [-25, 0, 100]), (0.9, Z)]},
        "leftArm": {"rotation": [(0, Z), (0.3, [-55, 0, 35]), (0.4, [-20, 0, -110]), (0.7, [-25, 0, -100]), (0.9, Z)]},
        "waist": {"rotation": [(0, Z), (0.3, [30, 0, 0]), (0.4, [-18, 0, 0]), (0.7, [-12, 0, 0]), (0.9, Z)]},
        "head": {"rotation": [(0, Z), (0.3, [20, 0, 0]), (0.4, [-25, 0, 0]), (0.7, [-20, 0, 0]), (0.9, Z)]},
        "rightLeg": {"rotation": [(0, Z), (0.3, [-30, 0, 10]), (0.4, [0, 0, 12]), (0.7, [0, 0, 10]), (0.9, Z)]},
        "leftLeg": {"rotation": [(0, Z), (0.3, [-30, 0, -10]), (0.4, [0, 0, -12]), (0.7, [0, 0, -10]), (0.9, Z)]},
    })
    A["animation.abyss.void_spear"] = anim(0.85, {
        "rightArm": {"rotation": [(0, Z), (0.2, [-150, 0, 25]), (0.38, [-200, 0, 15]), (0.46, [-75, 0, 0]),
                                  (0.65, [-60, 0, -10]), (0.85, Z)]},
        "leftArm": {"rotation": [(0, Z), (0.2, [-90, 0, -10]), (0.38, [-95, 0, -5]), (0.46, [30, 0, -20]),
                                 (0.65, [25, 0, -18]), (0.85, Z)]},
        "waist": {"rotation": [(0, Z), (0.38, [-12, -30, 0]), (0.46, [16, 25, 0]), (0.65, [12, 20, 0]), (0.85, Z)]},
        "head": {"rotation": [(0, Z), (0.38, [-5, 0, 0]), (0.85, Z)]},
        "rightLeg": {"rotation": [(0, Z), (0.38, [18, 0, 0]), (0.46, [-15, 0, 0]), (0.65, [-12, 0, 0]), (0.85, Z)]},
        "leftLeg": {"rotation": [(0, Z), (0.38, [-20, 0, 0]), (0.46, [20, 0, 0]), (0.65, [16, 0, 0]), (0.85, Z)]},
    })
    tremble = "math.sin(q.life_time * 1900) * 1.6"
    A["animation.abyss.charge"] = {
        "loop": "hold_on_last_frame", "animation_length": 0.25, "override_previous_animation": True,
        "bones": {
            "root": {"position": keys([(0, Z), (0.25, [0, -1.2, 0])])},
            "rightArm": {"rotation": keys([(0, Z), (0.25, [f"32 + {tremble}", 0, 24])])},
            "leftArm": {"rotation": keys([(0, Z), (0.25, [f"-78 + {tremble}", 0, -14])])},
            "waist": {"rotation": keys([(0, Z), (0.25, [f"20 + {tremble} * 0.5", f"{tremble} * 0.6", 0])])},
            "head": {"rotation": keys([(0, Z), (0.25, [-12, 0, 0])])},
            "rightLeg": {"rotation": keys([(0, Z), (0.25, [-22, 0, 8])])},
            "leftLeg": {"rotation": keys([(0, Z), (0.25, [25, 0, -8])])},
        },
    }
    release = anim(0.6, {
        "root": {"position": [(0, [0, -1.2, 0]), (0.1, [0, 1.5, 0]), (0.3, [0, 0, 0]), (0.6, Z)]},
        "rightArm": {"rotation": [(0, [32, 0, 24]), (0.08, [-10, 0, 95]), (0.3, [-10, 0, 95]), (0.6, Z)]},
        "leftArm": {"rotation": [(0, [-78, 0, -14]), (0.08, [-10, 0, -95]), (0.3, [-10, 0, -95]), (0.6, Z)]},
        "waist": {"rotation": [(0, [20, 0, 0]), (0.08, [-14, 0, 0]), (0.3, [-10, 0, 0]), (0.6, Z)]},
        "head": {"rotation": [(0, [-12, 0, 0]), (0.08, [-22, 0, 0]), (0.6, Z)]},
    })
    release["bones"]["root"]["rotation"] = {
        "0": {"post": Z, "lerp_mode": "catmullrom"},
        "0.28": {"pre": [0, 360, 0], "post": [0, 0, 0]},
        "0.6": [0, 0, 0],
    }
    A["animation.abyss.charge_release"] = release
    bob = "math.sin(q.life_time * 240) * 0.4"
    A["animation.abyss.ultimate"] = anim(4.3, {
        "root": {"position": [(0, Z), (0.4, [0, 2, 0]), (2.5, [0, f"2 + {bob}", 0]), (3.3, [0, 0, 0]),
                              (3.5, [0, 0.6, 0]), (3.8, [0, 0, 0]), (4.3, Z)]},
        "rightArm": {"rotation": [(0, Z), (0.4, [-170, 0, 20]), (2.5, [-172, 0, 22]), (3.3, [-70, 0, -40]),
                                  (3.45, [-75, 0, -42]), (3.55, [-30, 0, 120]), (3.9, [-28, 0, 115]), (4.3, Z)]},
        "leftArm": {"rotation": [(0, Z), (0.4, [-170, 0, -20]), (2.5, [-172, 0, -22]), (3.3, [-70, 0, 40]),
                                 (3.45, [-75, 0, 42]), (3.55, [-30, 0, -120]), (3.9, [-28, 0, -115]), (4.3, Z)]},
        "waist": {"rotation": [(0, Z), (0.4, [-10, 0, 0]), (2.5, [-12, 0, 0]), (3.3, [25, 0, 0]), (3.45, [28, 0, 0]),
                               (3.55, [-20, 0, 0]), (3.9, [-16, 0, 0]), (4.3, Z)]},
        "head": {"rotation": [(0, Z), (0.4, [-30, 0, 0]), (2.5, [-32, 0, 0]), (3.3, [15, 0, 0]), (3.55, [-20, 0, 0]),
                              (3.9, [-18, 0, 0]), (4.3, Z)]},
        "rightLeg": {"rotation": [(0, Z), (0.4, [10, 0, 5]), (2.5, [12, 0, 5]), (3.3, [-30, 0, 8]),
                                  (3.55, [0, 0, 14]), (3.9, [0, 0, 12]), (4.3, Z)]},
        "leftLeg": {"rotation": [(0, Z), (0.4, [-8, 0, -5]), (2.5, [-10, 0, -5]), (3.3, [25, 0, -8]),
                                 (3.55, [0, 0, -14]), (3.9, [0, 0, -12]), (4.3, Z)]},
    })
    A["animation.abyss.intro"] = anim(1.2, {
        "root": {"position": [(0, [0, -30, 0]), (0.5, [0, -4, 0]), (0.62, [0, 2, 0]), (0.75, [0, 0, 0]), (1.2, Z)]},
        "rightArm": {"rotation": [(0, [-20, 0, 40]), (0.5, [-20, 0, 40]), (0.62, [-150, 0, 30]), (0.95, [-140, 0, 28]),
                                  (1.2, Z)]},
        "leftArm": {"rotation": [(0, [-20, 0, -40]), (0.5, [-20, 0, -40]), (0.62, [-150, 0, -30]),
                                 (0.95, [-140, 0, -28]), (1.2, Z)]},
        "waist": {"rotation": [(0, Z), (0.62, [-15, 0, 0]), (0.95, [-10, 0, 0]), (1.2, Z)]},
        "head": {"rotation": [(0, Z), (0.62, [-20, 0, 0]), (1.2, Z)]},
    })
    A["animation.abyss.outro"] = anim(1.0, {
        "rightArm": {"rotation": [(0, Z), (0.25, [-45, 0, -10]), (0.7, [-42, 0, -10]), (1.0, Z)]},
        "leftArm": {"rotation": [(0, Z), (0.25, [-40, 0, 10]), (0.7, [-38, 0, 10]), (1.0, Z)]},
        "waist": {"rotation": [(0, Z), (0.25, [15, 0, 0]), (0.7, [14, 0, 0]), (1.0, Z)]},
        "head": {"rotation": [(0, Z), (0.25, [25, 0, 0]), (0.7, [24, 0, 0]), (1.0, Z)]},
    })
    A["animation.abyss.switch"] = anim(0.35, {
        "rightArm": {"rotation": [(0, Z), (0.1, [-70, 0, 28]), (0.18, [-55, 0, 22]), (0.35, Z)]},
        "leftArm": {"rotation": [(0, Z), (0.1, [-40, 0, -20]), (0.35, Z)]},
    })
    A["animation.abyss.none"] = {"animation_length": 0.05, "loop": False, "bones": {}}
    write_json(os.path.join(RP, "animations/abyss_player.animation.json"),
               {"format_version": "1.10.0", "animations": A})
    return A


# --------------------------------------------------------------------------
# entities, item, manifests
# --------------------------------------------------------------------------
FX_ENTITIES = {"black_sun": 8, "void_core": 7, "void_zone": 7, "black_flame": 8}


def build_entities():
    for name, life in FX_ENTITIES.items():
        ident = f"{NS}:{name}"
        write_json(os.path.join(BP, f"entities/{name}.json"), {
            "format_version": "1.21.40",
            "minecraft:entity": {
                "description": {"identifier": ident, "is_spawnable": False, "is_summonable": True},
                "component_groups": {"abyss:despawn": {"minecraft:instant_despawn": {}}},
                "components": {
                    "minecraft:type_family": {"family": ["abyss_fx", "inanimate"]},
                    "minecraft:collision_box": {"width": 0.05, "height": 0.05},
                    "minecraft:physics": {"has_gravity": False, "has_collision": False},
                    "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
                    "minecraft:knockback_resistance": {"value": 1.0},
                    "minecraft:damage_sensor": {"triggers": [{"cause": "all", "deals_damage": "no"}]},
                    "minecraft:fire_immune": {},
                    "minecraft:timer": {"looping": False, "time": life, "randomInterval": False,
                                        "time_down_event": {"event": "abyss:despawn", "target": "self"}},
                },
                "events": {"abyss:despawn": {"add": {"component_groups": ["abyss:despawn"]}}},
            },
        })
        write_json(os.path.join(RP, f"entity/{name}.entity.json"), {
            "format_version": "1.10.0",
            "minecraft:client_entity": {
                "description": {
                    "identifier": ident,
                    "materials": {"default": "entity_alphatest"},
                    "textures": {"default": "textures/entity/abyss_blank"},
                    "geometry": {"default": "geometry.abyss.blank"},
                    "render_controllers": ["controller.render.default"],
                },
            },
        })
    write_json(os.path.join(RP, "models/entity/abyss_blank.geo.json"), {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {"identifier": "geometry.abyss.blank", "texture_width": 16, "texture_height": 16,
                            "visible_bounds_width": 2, "visible_bounds_height": 2, "visible_bounds_offset": [0, 0.5, 0]},
            "bones": [{"name": "root", "pivot": [0, 0, 0]}],
        }],
    })


def build_item():
    write_json(os.path.join(BP, "items/abyssal_inferno.json"), {
        "format_version": "1.21.40",
        "minecraft:item": {
            "description": {"identifier": ITEM, "menu_category": {"category": "equipment"}},
            "components": {
                "minecraft:icon": "abyss_abyssal_inferno",
                "minecraft:display_name": {"value": "§l§4Abyssal §5Inferno"},
                "minecraft:max_stack_size": 1,
                "minecraft:hand_equipped": True,
                "minecraft:damage": 6,
                "minecraft:enchantable": {"slot": "sword", "value": 15},
                "minecraft:can_destroy_in_creative": False,
                "minecraft:custom_components": [f"{NS}:inferno_weapon"],
            },
        },
    })
    write_json(os.path.join(RP, "textures/item_texture.json"), {
        "resource_pack_name": "abyssal_inferno",
        "texture_name": "atlas.items",
        "texture_data": {"abyss_abyssal_inferno": {"textures": "textures/items/abyssal_inferno"}},
    })
    write_json(os.path.join(BP, "recipes/abyssal_inferno.json"), {
        "format_version": "1.20.10",
        "minecraft:recipe_shaped": {
            "description": {"identifier": f"{NS}:abyssal_inferno"},
            "tags": ["crafting_table"],
            "pattern": [" E ", "CNC", " B "],
            "key": {"E": {"item": "minecraft:echo_shard"}, "C": {"item": "minecraft:crying_obsidian"},
                    "N": {"item": "minecraft:netherite_sword"}, "B": {"item": "minecraft:blaze_rod"}},
            "unlock": [{"item": "minecraft:netherite_sword"}],
            "result": {"item": ITEM},
        },
    })


def build_manifests():
    write_json(os.path.join(BP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": "Abyssal Inferno (BP)",
                   "description": "Black Flame / Void / Abyss combat power - Sneak: switch skill, Use: cast",
                   "uuid": UUID_BP_HEADER, "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [
            {"type": "data", "uuid": UUID_BP_DATA, "version": VERSION},
            {"type": "script", "language": "javascript", "uuid": UUID_BP_SCRIPT, "version": VERSION,
             "entry": "scripts/main.js"},
        ],
        "dependencies": [
            {"uuid": UUID_RP_HEADER, "version": VERSION},
            {"module_name": "@minecraft/server", "version": "1.17.0"},
        ],
    })
    write_json(os.path.join(RP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": "Abyssal Inferno (RP)",
                   "description": "Black flame / void particles and skill animations",
                   "uuid": UUID_RP_HEADER, "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": UUID_RP_RES, "version": VERSION}],
    })


# --------------------------------------------------------------------------
# validation, preview, packaging
# --------------------------------------------------------------------------
def validate(anims):
    import re
    problems = []
    for root, _, files in os.walk(OUT):
        for f in files:
            if f.endswith(".json"):
                with open(os.path.join(root, f), encoding="utf-8") as fh:
                    try:
                        json.load(fh)
                    except Exception as e:  # noqa: BLE001
                        problems.append(f"bad json {f}: {e}")
    # every particle / animation / entity referenced from scripts must exist
    sdir = os.path.join(BP, "scripts")
    src = ""
    for f in sorted(os.listdir(sdir)):
        if f.endswith(".js"):
            with open(os.path.join(sdir, f), encoding="utf-8") as fh:
                src += fh.read()
    for pid in sorted(set(re.findall(r'"abyss:([a-z_]+)"', src))):
        if pid not in PARTICLES and pid not in FX_ENTITIES and f"{NS}:{pid}" != ITEM \
                and pid not in ("inferno_weapon", "despawn", "inferno", "void", "sel"):
            problems.append(f"script references unknown id abyss:{pid}")
    for aid in sorted(set(re.findall(r'"(animation\.abyss\.[a-z_0-9]+)"', src))):
        if aid not in anims:
            problems.append(f"script references unknown animation {aid}")
    for name in re.findall(r'P\.([a-zA-Z_]+)', src):
        pass
    for pname, data in PARTICLES.items():
        texpath = data["particle_effect"]["description"]["basic_render_parameters"]["texture"]
        if not os.path.exists(os.path.join(RP, texpath + ".png")):
            problems.append(f"particle {pname} texture missing {texpath}")
    return problems


def preview_sheet():
    os.makedirs(PREVIEW, exist_ok=True)
    tiles = [
        ("flame_sheet", (255, 70, 50)), ("smoke_sheet", (120, 70, 150)), ("crescent_sheet", (255, 80, 110)),
        ("sigil", (170, 90, 255)), ("crack", (170, 90, 255)), ("ring_shatter", (200, 120, 255)),
        ("rift", (160, 80, 255)), ("spear", (200, 140, 255)), ("mark_sheet", (220, 110, 255)),
        ("runes_sheet", (220, 110, 255)), ("sun_core", None), ("void_core", None),
    ]
    W = 1100
    rows = []
    for name, col in tiles:
        img = TEXTURES[name]
        if col:
            a = np.asarray(img).astype(float) / 255
            img = to_img(a[..., 3], rgb=a[..., :3] * np.array(col) / 255.0)
        bg = Image.new("RGBA", img.size, (12, 6, 16, 255))
        bg.alpha_composite(img)
        scale = min(1060 / img.width, 220 / img.height, 4)
        rows.append(bg.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BICUBIC))
    H = sum(r.height + 20 for r in rows) + 20
    sheet = Image.new("RGBA", (W, H), (12, 6, 16, 255))
    y = 20
    for r in rows:
        sheet.paste(r, ((W - r.width) // 2, y))
        y += r.height + 20
    sheet.save(os.path.join(PREVIEW, "abyssal_particles_preview.png"))
    big_icon = TEXTURES["icon"].resize((256, 256), Image.NEAREST)
    big_icon.save(os.path.join(PREVIEW, "abyssal_inferno_icon.png"))


def package():
    os.makedirs(DIST, exist_ok=True)
    path = os.path.join(DIST, "Abyssal_Inferno.mcaddon")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for pack in (BP, RP):
            base = os.path.basename(pack)
            for root, _, files in os.walk(pack):
                for f in sorted(files):
                    full = os.path.join(root, f)
                    z.write(full, os.path.join(base, os.path.relpath(full, pack)))
    return path


def main():
    for sub in ("animations", "entity", "models", "textures"):
        p = os.path.join(RP, sub)
        if os.path.isdir(p):
            shutil.rmtree(p)
    for sub in ("entities", "items", "recipes"):
        p = os.path.join(BP, sub)
        if os.path.isdir(p):
            shutil.rmtree(p)
    build_textures()
    build_particles()
    anims = build_animations()
    build_entities()
    build_item()
    build_manifests()
    problems = validate(anims)
    for p in problems:
        print("PROBLEM:", p)
    preview_sheet()
    path = package()
    print(f"{len(PARTICLES)} particles, {len(anims)} animations, {len(TEXTURES)} textures")
    print("wrote", os.path.relpath(path, ROOT))
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
