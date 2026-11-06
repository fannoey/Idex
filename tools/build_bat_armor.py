#!/usr/bin/env python3
"""Generate the "Bat Rider" armor + transformation belt as Blockbench .bbmodel files.

Two separate models are written (Bedrock Entity format, per-face UV, texture
embedded in the file so it opens directly in Blockbench):

  bat_rider_armor/Bat_Rider_Armor.bbmodel   helmet, chest, pauldrons + chains,
                                            mantle, gloves/claws, coat tails,
                                            chained right greave, boots
  bat_rider_armor/Bat_Rider_Belt.bbmodel    the transformation belt on its own

Coordinates are Blockbench (bbmodel) space: front = -Z, up = +Y and the
player's RIGHT side is +X (Blockbench flips X compared to .geo.json).
Bones follow the vanilla player skeleton so the parts can be bound to a player
later (head / body / rightArm / leftArm / rightLeg / leftLeg).

Run:  python3 tools/build_bat_armor.py
"""
import base64
import io
import json
import math
import os
import uuid

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "bat_rider_armor")
PX = 16                       # texture pixels per model unit
ATLAS_W = 1024

# bbmodel-space pivots of the player bones (x mirrored vs. geo.json)
BONES = {
    "body": dict(pivot=[0, 24, 0], parent=None),
    "head": dict(pivot=[0, 24, 0], parent="body"),
    "rightArm": dict(pivot=[5, 22, 0], parent="body"),
    "leftArm": dict(pivot=[-5, 22, 0], parent="body"),
    "rightLeg": dict(pivot=[1.9, 12, 0], parent=None),
    "leftLeg": dict(pivot=[-1.9, 12, 0], parent=None),
}

FACES = ("north", "south", "east", "west", "up", "down")


def uid(*names):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "idex/bat_rider/" + "/".join(names)))


# --------------------------------------------------------------------------
# texture helpers (float RGBA numpy arrays, shape h x w x 4)
# --------------------------------------------------------------------------
RNG = np.random.default_rng(7)


def solid(w, h, col, a=255):
    out = np.zeros((h, w, 4))
    out[..., :3] = col
    out[..., 3] = a
    return out


def vgrad(w, h, top, bot):
    t = np.linspace(0, 1, h)[:, None, None]
    out = np.zeros((h, w, 4))
    out[..., :3] = np.array(top, float) * (1 - t) + np.array(bot, float) * t
    out[..., 3] = 255
    return out


def add_noise(a, amp):
    n = RNG.normal(0, amp, a.shape[:2])
    a[..., :3] += n[..., None]
    return a


def bevel(a, dark=0.55, light=1.25, wpx=1):
    h, w = a.shape[:2]
    k = min(wpx, max(1, min(h, w) // 4))
    if h > 2 and w > 2:
        a[:k, :, :3] *= light
        a[-k:, :, :3] *= dark
        a[:, :k, :3] *= 0.8
        a[:, -k:, :3] *= 0.7
    return a


def to_img(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGBA")


def to_arr(img):
    return np.asarray(img.convert("RGBA")).astype(float)


def vector(w, h, fn, ss=4):
    """Draw fn(draw, S) on an ss-supersampled RGBA canvas, return it at (w, h).

    S(u, v) maps normalised face coords (0..1, top-left origin) to canvas px."""
    W, H = w * ss, h * ss
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    def S(u, v):
        return (u * W, v * H)

    fn(d, S, W, H)
    return to_arr(im.resize((w, h), Image.LANCZOS))


def over(dst, src):
    """Alpha-composite src over dst (both float RGBA arrays)."""
    sa = src[..., 3:4] / 255.0
    dst[..., :3] = src[..., :3] * sa + dst[..., :3] * (1 - sa)
    dst[..., 3] = np.maximum(dst[..., 3], src[..., 3])
    return dst


def mask_from(w, h, fn, ss=4):
    """Greyscale coverage mask 0..1 drawn by fn(draw, S, W, H) with fill=255."""
    W, H = w * ss, h * ss
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    fn(d, lambda u, v: (u * W, v * H), W, H)
    return np.asarray(im.resize((w, h), Image.LANCZOS)).astype(float) / 255.0


def mirror_pts(pts):
    return [(1 - u, v) for u, v in pts]


# --------------------------------------------------------------------------
# palette (sampled from the reference picture)
# --------------------------------------------------------------------------
RED_HI = (226, 40, 46)
RED = (176, 14, 24)
RED_LO = (98, 4, 12)
SUIT = (30, 29, 34)
BLACK = (16, 15, 18)
SILVER_HI = (238, 239, 244)
SILVER_LO = (118, 120, 130)
GOLD_HI = (255, 214, 80)
GOLD_LO = (160, 104, 12)
YELLOW = (246, 206, 34)
CAPE = (112, 22, 30)
CAPE_LO = (64, 10, 16)


# --------------------------------------------------------------------------
# materials: painter(face, w, h, cube) -> float RGBA array
# --------------------------------------------------------------------------
def m_suit(face, w, h, cube):
    a = solid(w, h, SUIT)
    xs = np.arange(w)
    a[:, (xs % 4) == 0, :3] *= 0.8            # fine knit lines
    add_noise(a, 3)
    return a


def m_black(face, w, h, cube):
    return add_noise(solid(w, h, BLACK), 2)


def m_red(face, w, h, cube):
    a = vgrad(w, h, RED_HI, RED)
    # glossy diagonal highlight
    yy, xx = np.mgrid[0:h, 0:w]
    band = np.exp(-(((xx + yy * 0.6) / max(w, 1) - 0.35) ** 2) / 0.01)
    a[..., :3] += band[..., None] * 45
    add_noise(a, 2)
    return bevel(a, 0.45, 1.15, 2 if min(w, h) > 10 else 1)


def m_silver(face, w, h, cube):
    a = vgrad(w, h, SILVER_HI, SILVER_LO)
    a[..., :3] += RNG.normal(0, 6, (h, 1))[..., None]     # brushed rows
    add_noise(a, 2)
    return bevel(a, 0.5, 1.05, 2 if min(w, h) > 10 else 1)


def m_gold(face, w, h, cube):
    a = vgrad(w, h, GOLD_HI, GOLD_LO)
    yy, xx = np.mgrid[0:h, 0:w]
    band = np.exp(-(((xx - yy * 0.5) / max(w, 1) - 0.4) ** 2) / 0.02)
    a[..., :3] += band[..., None] * 40
    add_noise(a, 2)
    return bevel(a, 0.5, 1.1)


def m_clear(face, w, h, cube):
    return np.zeros((h, w, 4))


def m_boot(face, w, h, cube):
    a = add_noise(solid(w, h, (34, 34, 40)), 2)
    if face in ("north", "south", "east", "west"):
        sole = max(2, int(h * 0.22))
        a[-sole:, :, :3] = (58, 58, 66)
        a[-sole, :, :3] = (90, 90, 100)
        # stitched toe cap line
        a[int(h * 0.35), ::3, :3] = (70, 70, 80)
    if face == "down":
        a[..., :3] = (50, 50, 58)
    return a


def m_glove(face, w, h, cube):
    a = m_red(face, w, h, cube)
    if face in ("north", "south", "east", "west"):
        # knuckle ridges + black finger gaps
        for i in range(1, 4):
            x = int(w * i / 4)
            a[int(h * 0.45):, max(0, x - 1):x + 1, :3] = (40, 4, 8)
        a[int(h * 0.4):int(h * 0.4) + 2, :, :3] = (60, 4, 10)
    return a


def chain_painter(face, w, h, cube):
    """Transparent strip with chain links running along its long side."""
    long_axis = cube.long_axis()
    sizes = cube.size()
    # which image axis is the long axis on this face?
    face_axes = {"north": (0, 1), "south": (0, 1), "east": (2, 1), "west": (2, 1),
                 "up": (0, 2), "down": (0, 2)}[face]
    if long_axis not in face_axes:
        return np.zeros((h, w, 4))
    horiz = face_axes[0] == long_axis
    L, T = (w, h) if horiz else (h, w)

    def draw(d, S, W, H):
        Ls, Ts = (W, H) if horiz else (H, W)
        p = Ts * 1.5
        n = int(Ls / p) + 2
        for i in range(n):
            c = i * p + p * 0.3
            if i % 2 == 0:   # face-on oval link
                box = [c - p * 0.55, Ts * 0.06, c + p * 0.55, Ts * 0.94]
                wd = max(2, int(Ts * 0.2))
            else:            # edge-on link
                box = [c - p * 0.6, Ts * 0.36, c + p * 0.6, Ts * 0.64]
                wd = 0
            if not horiz:
                box = [box[1], box[0], box[3], box[2]]
            if wd:
                d.ellipse(box, outline=(40, 40, 46, 255), width=wd + 2)
                d.ellipse([box[0] + 2, box[1] + 2, box[2] - 2, box[3] - 2],
                          outline=(222, 224, 230, 255), width=wd - 1)
            else:
                d.rounded_rectangle(box, radius=4, fill=(205, 207, 214, 255),
                                    outline=(40, 40, 46, 255), width=3)

    return vector(w, h, draw)


# ---- cape / mantle panels -------------------------------------------------
def hem_mask(w, h, depth_px, n=None):
    """Alpha mask with a scalloped bat-wing hem along the bottom edge."""
    n = n or max(2, int(round(w / (1.6 * PX))))
    yy, xx = np.mgrid[0:h, 0:w]
    t = (xx + 0.5) / w * n
    frac = t - np.floor(t)
    cut = h - depth_px * np.sin(np.pi * frac) ** 0.6
    return (yy < cut).astype(float)


def cape_cloth(w, h, col, lo, seed):
    a = vgrad(w, h, col, lo)
    xs = np.arange(w)
    period = max(6.0, w / max(1, round(w / (1.3 * PX))))
    fold = 0.82 + 0.18 * np.sin(xs / period * 2 * np.pi + seed)
    a[..., :3] *= fold[None, :, None]
    add_noise(a, 2)
    return a


def panel(outer, hem_units=1.3, red=True):
    """Thin cloth panel: `outer` face red cloth, opposite face black lining."""
    opp = {"north": "south", "south": "north", "east": "west", "west": "east"}[outer]

    def paint(face, w, h, cube):
        if face == "down":
            return np.zeros((h, w, 4))
        if face == "up":
            return add_noise(solid(w, h, BLACK), 2)
        if face in (outer, opp):
            if face == outer and red:
                a = cape_cloth(w, h, CAPE, CAPE_LO, hash(cube.name) % 7)
            else:
                a = cape_cloth(w, h, (34, 30, 34), (14, 12, 15), 1)
            m = hem_mask(w, h, int(hem_units * PX))
            # black trim following the hem on the red side
            if face == outer and red:
                edge = (m > 0) & (np.roll(m, -3, axis=0) == 0)
                edge |= (m > 0) & (np.roll(m, -1, axis=0) == 0)
                a[edge, :3] = (22, 18, 22)
                # trim along the open vertical edges too
                a[:, :2, :3] = (22, 18, 22)
                a[:, -2:, :3] = (22, 18, 22)
            a[..., 3] = m * 255
            return a
        return add_noise(solid(w, h, (22, 18, 22)), 2)

    return paint


# ---- helmet --------------------------------------------------------------
HELM = dict(x0=-4.45, x1=4.45, y0=23.6, y1=32.5, z0=-4.5, z1=4.45)

# eye outline (viewer's left eye = player's right), normalised helmet-front coords
EYE_L = [(0.465, 0.56), (0.42, 0.33), (0.33, 0.12), (0.22, 0.05), (0.10, 0.08), (0.04, 0.18),
         (0.035, 0.36), (0.07, 0.50), (0.17, 0.60), (0.31, 0.65), (0.42, 0.64)]
EYE_R = mirror_pts(EYE_L)
CREST = [(0.30, 0.0), (0.70, 0.0), (0.64, 0.12), (0.535, 0.56), (0.5, 0.62), (0.465, 0.56),
         (0.36, 0.12)]


def honeycomb(d, W, H, cell, col, width):
    r = cell
    dx = r * math.sqrt(3)
    row = 0
    y = -r
    while y < H + r:
        x0 = -dx if row % 2 else -dx / 2
        x = x0
        while x < W + dx:
            pts = [(x + r * math.cos(math.radians(30 + 60 * k)),
                    y + r * math.sin(math.radians(30 + 60 * k))) for k in range(7)]
            d.line(pts, fill=col, width=width)
            x += dx
        y += r * 1.5
        row += 1


def helmet_front_full(w, h):
    def draw(d, S, W, H):
        d.rectangle([0, 0, W, H], fill=BLACK + (255,))
        # cheek / jaw silver plates
        for side in (1, -1):
            def m(u, v):
                return S(u if side == 1 else 1 - u, v)
            d.polygon([m(0.06, 0.62), m(0.30, 0.70), m(0.38, 0.86), m(0.20, 0.95), m(0.08, 0.80)],
                      fill=(70, 70, 78, 255))
            d.polygon([m(0.30, 0.64), m(0.44, 0.66), m(0.40, 0.82)], fill=SILVER_HI + (255,),
                      outline=(60, 60, 66, 255))
        # mouth guard
        d.polygon([S(0.37, 0.70), S(0.63, 0.70), S(0.60, 0.95), S(0.40, 0.95)],
                  fill=(196, 198, 206, 255), outline=(50, 50, 56, 255), width=6)
        for k in range(5):
            u = 0.42 + k * 0.04
            d.line([S(u, 0.75), S(u, 0.92)], fill=(70, 70, 78, 255), width=4)
        # eyes: silver rim, yellow, honeycomb
        for eye in (EYE_L, EYE_R):
            d.polygon([S(*p) for p in eye], fill=(200, 200, 206, 255))
        for eye in (EYE_L, EYE_R):
            shrink = [((u - 0.5) * 0.985 + 0.5 + (0.006 if u < 0.5 else -0.006), v * 0.99 + 0.006)
                      for u, v in eye]
            d.polygon([S(*p) for p in shrink], fill=YELLOW + (255,))
        # red crest with darker ridge
        d.polygon([S(*p) for p in CREST], fill=RED + (255,), outline=SILVER_HI + (255,), width=8)
        d.line([S(0.5, 0.0), S(0.5, 0.58)], fill=RED_LO + (255,), width=8)
        d.line([S(0.41, 0.02), S(0.49, 0.45)], fill=RED_HI + (255,), width=5)
        d.line([S(0.59, 0.02), S(0.51, 0.45)], fill=RED_HI + (255,), width=5)
        # small silver gem between eyes
        d.ellipse([*S(0.475, 0.565), *S(0.525, 0.605)], fill=SILVER_HI + (255,))

    a = vector(w, h, draw)
    # honeycomb overlay restricted to the yellow eye area
    eye_m = mask_from(w, h, lambda d, S, W, H: [d.polygon([S(*p) for p in e], fill=255)
                                                  for e in (EYE_L, EYE_R)])
    comb = vector(w, h, lambda d, S, W, H: honeycomb(d, W, H, W * 0.022, (190, 120, 10, 255),
                                                     max(2, int(W * 0.004))))
    comb[..., 3] *= (eye_m > 0.9)
    over(a, comb)
    # glossy gradient on the eyes
    yy = np.linspace(1.15, 0.85, h)[:, None]
    a[..., :3] = np.where(eye_m[..., None] > 0.5, a[..., :3] * yy[..., None], a[..., :3])
    add_noise(a, 1.5)
    return a, eye_m


_HELM_CACHE = {}


def helmet_front(w, h):
    if (w, h) not in _HELM_CACHE:
        _HELM_CACHE[(w, h)] = helmet_front_full(w, h)
    return _HELM_CACHE[(w, h)]


def p_helmet(face, w, h, cube):
    if face == "north":
        return helmet_front(w, h)[0].copy()
    a = add_noise(solid(w, h, BLACK), 2)
    if face == "up":
        # red crest continues over the top (image top = front)
        def draw(d, S, W, H):
            d.polygon([S(0.33, 0), S(0.67, 0), S(0.58, 0.85), S(0.42, 0.85)], fill=RED + (255,),
                      outline=SILVER_HI + (255,), width=6)
            d.line([S(0.5, 0), S(0.5, 0.85)], fill=RED_LO + (255,), width=6)
        over(a, vector(w, h, draw))
    elif face in ("east", "west"):
        def draw(d, S, W, H):
            # silver ear disk and a red flash sweeping back from the eye
            d.ellipse([*S(0.38, 0.42), *S(0.62, 0.66)], fill=(190, 192, 200, 255),
                      outline=(60, 60, 66, 255), width=6)
            d.ellipse([*S(0.45, 0.49), *S(0.55, 0.59)], fill=RED + (255,))
            fr = [(0.0, 0.08), (0.0, 0.25), (0.6, 0.30), (0.95, 0.12)]
            if face == "west":      # west image runs back -> front, mirror it
                fr = mirror_pts(fr)
            d.polygon([S(*p) for p in fr], fill=RED + (255,))
        over(a, vector(w, h, draw))
    elif face == "south":
        def draw(d, S, W, H):
            d.rectangle([*S(0.44, 0), *S(0.56, 0.75)], fill=RED + (255,))
            d.line([S(0.15, 0.85), S(0.85, 0.85)], fill=(80, 80, 88, 255), width=6)
        over(a, vector(w, h, draw))
    return bevel(a, 0.6, 1.1)


def eye_plate(face, w, h, cube):
    """Raised eye lens: crop of the helmet front where the eye mask is."""
    if face != "north":
        return np.zeros((h, w, 4))
    fw = int(round((HELM["x1"] - HELM["x0"]) * PX))
    fh = int(round((HELM["y1"] - HELM["y0"]) * PX))
    full, eye_m = helmet_front(fw, fh)
    (x0, y0, _), (x1, y1, _) = cube.frm, cube.to
    c0 = int(round((HELM["x1"] - x1) * PX))
    r0 = int(round((HELM["y1"] - y1) * PX))
    crop = full[r0:r0 + h, c0:c0 + w].copy()
    m = eye_m[r0:r0 + h, c0:c0 + w]
    if crop.shape[:2] != (h, w):
        crop = to_arr(to_img(crop).resize((w, h)))
        m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).resize((w, h))) / 255.0
    crop[..., :3] *= 1.08
    crop[..., 3] = np.where(m > 0.6, 255, 0)
    return crop


def horn(face, w, h, cube):
    a = m_red(face, w, h, cube)
    if face not in ("up", "down"):
        tip = int(h * 0.38)
        a[:tip] = m_silver(face, w, max(1, tip), cube)[:tip]
        a[tip:tip + 1, :, :3] = (40, 40, 46)
    elif face == "up":
        a[...] = m_silver(face, w, h, cube)
    return a


# ---- chest ---------------------------------------------------------------
def p_chest(face, w, h, cube):
    a = m_red(face, w, h, cube)
    groove = (24, 6, 10, 255)
    if face == "north":
        def draw(d, S, W, H):
            lw = max(4, int(W * 0.018))
            # collar bat emblem (black) at the neck
            d.polygon([S(0.30, 0.0), S(0.70, 0.0), S(0.62, 0.10), S(0.56, 0.08), S(0.5, 0.17),
                       S(0.44, 0.08), S(0.38, 0.10)], fill=groove)
            d.line([S(0.5, 0.17), S(0.5, 1.0)], fill=groove, width=lw)
            # pec outline
            for s in (1, -1):
                def m(u, v):
                    return S(u if s == 1 else 1 - u, v)
                d.line([m(0.05, 0.12), m(0.30, 0.13), m(0.47, 0.22), m(0.49, 0.45), m(0.30, 0.52),
                        m(0.08, 0.45), m(0.02, 0.30)], fill=groove, width=lw)
                # rib / abs segments
                for v in (0.62, 0.76, 0.90):
                    d.line([m(0.12, v - 0.03), m(0.30, v), m(0.47, v - 0.02)], fill=groove, width=lw)
                d.line([m(0.12, 0.55), m(0.10, 1.0)], fill=groove, width=lw)
        over(a, vector(w, h, draw))
    elif face == "south":
        def draw(d, S, W, H):
            lw = max(4, int(W * 0.018))
            d.line([S(0.5, 0), S(0.5, 1)], fill=groove, width=lw)
            for v in (0.35, 0.6, 0.85):
                d.line([S(0.1, v), S(0.5, v - 0.05), S(0.9, v)], fill=groove, width=lw)
        over(a, vector(w, h, draw))
    elif face in ("east", "west"):
        a[:, w // 2 - 1:w // 2 + 1, :3] = groove[:3]
    return a


def p_collar(face, w, h, cube):
    a = m_silver(face, w, h, cube)
    a[..., :3] *= 0.75
    return a


def p_bracelet(face, w, h, cube):
    a = m_silver(face, w, h, cube)
    if face in ("north", "south", "east", "west"):
        def draw(d, S, W, H):
            n = max(1, int(W / (H * 1.3)))
            for i in range(n):
                u0, u1 = i / n + 0.08 / n, (i + 1) / n - 0.08 / n
                um = (u0 + u1) / 2
                d.line([S(u0, 0.8), S(u0, 0.25), S(um, 0.6), S(u1, 0.25), S(u1, 0.8)],
                       fill=(50, 50, 58, 255), width=max(3, H // 9))
            d.line([S(0, 0.08), S(1, 0.08)], fill=(70, 4, 10, 255), width=max(2, H // 12))
            d.line([S(0, 0.92), S(1, 0.92)], fill=(70, 4, 10, 255), width=max(2, H // 12))
        over(a, vector(w, h, draw))
    return a


def p_pauldron(face, w, h, cube):
    a = m_silver(face, w, h, cube)
    if face in ("north", "south", "east", "west", "up"):
        def draw(d, S, W, H):
            lw = max(3, int(min(W, H) * 0.05))
            d.line([S(0.06, 0.7), S(0.5, 0.82), S(0.94, 0.7)], fill=(80, 82, 92, 255), width=lw)
            d.line([S(0.1, 0.35), S(0.5, 0.45), S(0.9, 0.35)], fill=(255, 255, 255, 140), width=lw)
        over(a, vector(w, h, draw))
    if face == "down":
        a[..., :3] = (40, 40, 46)
    return a


def p_greave(face, w, h, cube):
    a = m_silver(face, w, h, cube)
    if face in ("north", "south", "east", "west"):
        def draw(d, S, W, H):
            lw = max(3, int(W * 0.03))
            for v in (0.3, 0.62):
                d.line([S(0.0, v), S(0.5, v + 0.06), S(1.0, v)], fill=(70, 72, 82, 255), width=lw)
            d.line([S(0.5, 0.0), S(0.5, 1.0)], fill=(150, 152, 162, 255), width=lw)
        over(a, vector(w, h, draw))
    return a


# ---- belt ----------------------------------------------------------------
def p_strap(face, w, h, cube):
    a = add_noise(solid(w, h, (22, 20, 24)), 2)
    if face in ("north", "south", "east", "west"):
        e = max(1, h // 7)
        a[:e, :, :3] = (200, 202, 210)
        a[-e:, :, :3] = (200, 202, 210)
        mid = h // 2
        a[mid - e:mid + e, :, :3] = (150, 12, 22)
        a[:, ::max(2, PX // 2), :3] *= 0.85
    return a


def p_kivat_face(face, w, h, cube):
    a = m_red(face, w, h, cube)
    if face == "north":
        def draw(d, S, W, H):
            for s in (0, 1):
                cx = 0.3 if s == 0 else 0.7
                d.ellipse([*S(cx - 0.2, 0.18), *S(cx + 0.2, 0.68)], fill=GOLD_HI + (255,))
                d.ellipse([*S(cx - 0.15, 0.24), *S(cx + 0.15, 0.62)], fill=(220, 20, 30, 255))
                d.ellipse([*S(cx - 0.07, 0.29), *S(cx + 0.0, 0.40)], fill=(255, 190, 190, 230))
            # gold brow / ears
            d.polygon([S(0.0, 0.0), S(0.25, 0.14), S(0.5, 0.05), S(0.75, 0.14), S(1, 0), S(1, 0.12),
                       S(0.5, 0.2), S(0, 0.12)], fill=GOLD_LO + (255,))
            # fangs
            d.polygon([S(0.38, 0.78), S(0.62, 0.78), S(0.56, 0.95), S(0.5, 0.86), S(0.44, 0.95)],
                      fill=(240, 240, 240, 255), outline=(40, 40, 40, 255), width=4)
        over(a, vector(w, h, draw))
    return a


WING = [(0.0, 0.30), (0.25, 0.12), (0.55, 0.02), (0.85, 0.0), (1.0, 0.15), (0.92, 0.32),
        (0.98, 0.52), (0.86, 0.66), (0.92, 0.86), (0.70, 1.0), (0.45, 0.88), (0.22, 0.86),
        (0.0, 0.72)]


def wing_painter(flip):
    def paint(face, w, h, cube):
        pts = mirror_pts(WING) if flip else WING
        if face not in ("north", "south"):
            return np.zeros((h, w, 4))     # thin cut-out plate: no box edges
        if face == "south":
            pts = mirror_pts(pts)

        def draw(d, S, W, H):
            d.polygon([S(*p) for p in pts], fill=GOLD_LO + (255,))
            inner = [((u - 0.5) * 0.86 + 0.5, (v - 0.5) * 0.8 + 0.5) for u, v in pts]
            d.polygon([S(*p) for p in inner], fill=GOLD_HI + (255,))
            # silver web inside the wing
            ctr = (0.08, 0.5) if (not flip) == (face == "north") else (0.92, 0.5)
            for k in range(6):
                ang = math.radians(-70 + k * 28)
                u = ctr[0] + (0.8 if ctr[0] < 0.5 else -0.8) * math.cos(ang)
                v = ctr[1] + 0.45 * math.sin(ang)
                d.line([S(*ctr), S(u, v)], fill=(230, 232, 240, 255), width=max(3, W // 60))
            for r in (0.3, 0.55):
                bx = [ctr[0] - r, ctr[1] - r * 0.6, ctr[0] + r, ctr[1] + r * 0.6]
                d.arc([*S(bx[0], bx[1]), *S(bx[2], bx[3])], -80, 80 if ctr[0] < 0.5 else 260,
                      fill=(230, 232, 240, 255), width=max(3, W // 60))

        a = vector(w, h, draw)
        m = mask_from(w, h, lambda d, S, W, H: d.polygon([S(*p) for p in pts], fill=255))
        a[..., 3] = np.where(m > 0.5, 255, 0)
        return a
    return paint


def p_slot(face, w, h, cube):
    a = m_red(face, w, h, cube)
    if face in ("east", "west"):
        a[:, :2, :3] = GOLD_HI
        a[:, -2:, :3] = GOLD_HI
        a[:2, :, :3] = GOLD_HI
        a[-2:, :, :3] = GOLD_HI
    return a


def p_skin(face, w, h, cube):
    return add_noise(solid(w, h, (176, 176, 184)), 3)


# --------------------------------------------------------------------------
# cube element
# --------------------------------------------------------------------------
class Cube:
    def __init__(self, name, bone, frm, to, paint, rot=(0, 0, 0), pivot=None, group=None):
        self.name, self.bone = name, bone
        self.frm = [float(v) for v in frm]
        self.to = [float(v) for v in to]
        self.paint = paint
        self.rot = [float(r) for r in rot]
        self.pivot = list(pivot) if pivot is not None else [
            (self.frm[k] + self.to[k]) / 2 for k in range(3)]
        self.group = group
        self.uv = {}
        self.tex = {}

    def size(self):
        return [self.to[k] - self.frm[k] for k in range(3)]

    def long_axis(self):
        s = self.size()
        return int(np.argmax(s))

    def face_px(self, f):
        dx, dy, dz = self.size()
        w, h = {"north": (dx, dy), "south": (dx, dy), "east": (dz, dy), "west": (dz, dy),
                "up": (dx, dz), "down": (dx, dz)}[f]
        return max(1, int(round(w * PX))), max(1, int(round(h * PX)))

    def faces_3d(self):
        (x0, y0, z0), (x1, y1, z1) = self.frm, self.to
        dx, dy, dz = self.size()
        A = np.array
        return {
            "north": (A([x1, y1, z0]), A([-dx, 0, 0]), A([0, -dy, 0]), A([0, 0, -1])),
            "south": (A([x0, y1, z1]), A([dx, 0, 0]), A([0, -dy, 0]), A([0, 0, 1])),
            "east": (A([x1, y1, z1]), A([0, 0, -dz]), A([0, -dy, 0]), A([1, 0, 0])),
            "west": (A([x0, y1, z0]), A([0, 0, dz]), A([0, -dy, 0]), A([-1, 0, 0])),
            "up": (A([x0, y1, z0]), A([dx, 0, 0]), A([0, 0, dz]), A([0, 1, 0])),
            "down": (A([x0, y0, z1]), A([dx, 0, 0]), A([0, 0, -dz]), A([0, -1, 0])),
        }


def mirror_x(c, name, bone):
    """Mirror a cube across x=0 (right <-> left)."""
    frm = [-c.to[0], c.frm[1], c.frm[2]]
    to = [-c.frm[0], c.to[1], c.to[2]]
    piv = [-c.pivot[0], c.pivot[1], c.pivot[2]]
    rot = [c.rot[0], -c.rot[1], -c.rot[2]]
    grp = c.group.replace("right", "left").replace("Right", "Left") if c.group else None
    return Cube(name, bone, frm, to, c.paint, rot, piv, grp)


# --------------------------------------------------------------------------
# the armor
# --------------------------------------------------------------------------
def chain_ring(prefix, bone, cx, y, hx, hz, cz=0.0, tilt=8.0, t=0.55, group=None):
    """Four chain bars wrapped around a limb (slightly tilted, like the picture)."""
    out = []
    piv = [cx, y, cz]
    rot = (0, 0, tilt)
    out.append(Cube(prefix + "_f", bone, [cx - hx - t, y, cz - hz - t], [cx + hx + t, y + t, cz - hz],
                    chain_painter, rot, piv, group))
    out.append(Cube(prefix + "_b", bone, [cx - hx - t, y, cz + hz], [cx + hx + t, y + t, cz + hz + t],
                    chain_painter, rot, piv, group))
    out.append(Cube(prefix + "_r", bone, [cx + hx, y, cz - hz], [cx + hx + t, y + t, cz + hz],
                    chain_painter, rot, piv, group))
    out.append(Cube(prefix + "_l", bone, [cx - hx - t, y, cz - hz], [cx - hx, y + t, cz + hz],
                    chain_painter, rot, piv, group))
    return out


def armor_cubes():
    C = []
    H = HELM
    # ---------------- head ----------------
    C.append(Cube("helmet", "head", [H["x0"], H["y0"], H["z0"]], [H["x1"], H["y1"], H["z1"]],
                  p_helmet, group="helmet"))
    C.append(Cube("eye_right", "head", [0.15, 26.6, -4.72], [4.35, 32.2, -4.5], eye_plate,
                  group="helmet"))
    C.append(Cube("eye_left", "head", [-4.35, 26.6, -4.72], [-0.15, 32.2, -4.5], eye_plate,
                  group="helmet"))
    C.append(Cube("crest_fin", "head", [-0.45, 31.6, -4.8], [0.45, 34.2, -0.5], horn,
                  rot=(-12, 0, 0), pivot=[0, 32, -4.5], group="helmet"))
    hr = Cube("horn_right", "head", [1.0, 31.8, -4.6], [2.0, 35.6, -3.4], horn,
              rot=(-8, 0, -24), pivot=[1.5, 32, -4], group="helmet")
    C += [hr, mirror_x(hr, "horn_left", "head")]
    hr2 = Cube("horn_right_back", "head", [2.6, 31.4, -3.0], [3.4, 34.0, -1.8], horn,
               rot=(-4, 0, -36), pivot=[3.0, 31.6, -2.4], group="helmet")
    C += [hr2, mirror_x(hr2, "horn_left_back", "head")]

    # ---------------- body ----------------
    C.append(Cube("suit_body", "body", [-4.2, 12, -2.2], [4.2, 24, 2.2], m_suit, group="torso"))
    C.append(Cube("chest_plate", "body", [-4.45, 15.6, -2.65], [4.45, 24.2, 2.55], p_chest,
                  group="torso"))
    for s, nm in ((1, "right"), (-1, "left")):
        x0, x1 = sorted((s * 0.3, s * 4.1))
        C.append(Cube("pec_" + nm, "body", [x0, 19.9, -2.95], [x1, 23.2, -2.6], m_red, group="torso"))
        for i, (ya, yb) in enumerate(((18.3, 19.5), (17.0, 18.1), (15.8, 16.8))):
            xa, xb = sorted((s * 0.35, s * 2.3))
            C.append(Cube(f"abs_{nm}_{i}", "body", [xa, ya, -2.85], [xb, yb, -2.6], m_red,
                          group="torso"))
    C.append(Cube("collar", "body", [-2.8, 23.6, -2.9], [2.8, 24.7, 2.75], p_collar, group="torso"))
    C.append(Cube("cape_back", "body", [-4.7, 10.2, 2.6], [4.7, 24.3, 3.1], panel("south"),
                  rot=(-7, 0, 0), pivot=[0, 24, 2.8], group="mantle"))

    # ---------------- right arm (mirrored to left) ----------------
    ra = []
    ra.append(Cube("sleeve_right", "rightArm", [3.8, 12, -2.2], [8.2, 24, 2.2], m_suit,
                   group="rightSleeve"))
    ra.append(Cube("glove_right", "rightArm", [3.7, 11.6, -2.3], [8.3, 15.4, 2.3], m_glove,
                   group="rightSleeve"))
    for i, x in enumerate((4.2, 5.25, 6.3, 7.35)):
        ra.append(Cube(f"claw_right_{i}", "rightArm", [x, 10.2, -2.2], [x + 0.75, 11.8, -1.45], horn,
                       rot=(18, 0, 0), pivot=[x + 0.37, 11.8, -1.8], group="rightClaws"))
    ra.append(Cube("pauldron_right_top", "rightArm", [3.3, 22.6, -3.0], [9.2, 25.0, 3.0],
                   p_pauldron, rot=(0, 0, -12), pivot=[5, 24, 0], group="rightPauldron"))
    ra.append(Cube("pauldron_right_mid", "rightArm", [4.4, 20.7, -3.2], [9.7, 23.1, 3.2],
                   p_pauldron, rot=(0, 0, -20), pivot=[5, 23, 0], group="rightPauldron"))
    ra.append(Cube("pauldron_right_low", "rightArm", [5.4, 19.1, -3.0], [9.8, 21.2, 3.0],
                   p_pauldron, rot=(0, 0, -28), pivot=[6, 21, 0], group="rightPauldron"))
    ra.append(Cube("chain_right_a", "rightArm", [3.0, 22.0, -3.75], [10.0, 22.6, -3.15],
                   chain_painter, rot=(0, 0, -28), pivot=[5, 22.3, -3.4], group="rightChains"))
    ra.append(Cube("chain_right_b", "rightArm", [4.2, 20.0, -3.85], [10.2, 20.6, -3.25],
                   chain_painter, rot=(0, 0, -6), pivot=[7, 20.3, -3.5], group="rightChains"))
    ra.append(Cube("chain_right_c", "rightArm", [3.0, 22.0, 3.15], [10.0, 22.6, 3.75],
                   chain_painter, rot=(0, 0, -28), pivot=[5, 22.3, 3.4], group="rightChains"))
    ra.append(Cube("chain_right_hang", "rightArm", [9.4, 15.6, -3.6], [10.0, 21.6, -3.0],
                   chain_painter, rot=(0, 0, 8), pivot=[9.7, 21.6, -3.3], group="rightChains"))
    ra.append(Cube("cape_right_outer", "rightArm", [8.7, 9.6, -3.3], [9.2, 22.4, 3.5],
                   panel("east"), rot=(0, 0, -5), pivot=[9, 22.4, 0], group="rightMantle"))
    ra.append(Cube("cape_right_front", "rightArm", [6.2, 11.4, -3.6], [9.2, 22.0, -3.1],
                   panel("north"), rot=(3, 0, 0), pivot=[7.7, 22, -3.3], group="rightMantle"))
    ra.append(Cube("cape_right_back", "rightArm", [3.9, 10.4, 3.1], [9.2, 22.4, 3.6],
                   panel("south"), rot=(-5, 0, 0), pivot=[6.5, 22.4, 3.3], group="rightMantle"))
    C += ra
    for c in ra:
        C.append(mirror_x(c, c.name.replace("right", "left"), "leftArm"))
    C.append(Cube("bracelet_left", "leftArm", [-8.4, 15.2, -2.4], [-3.6, 16.7, 2.4], p_bracelet,
                  group="leftSleeve"))

    # ---------------- legs ----------------
    rl = []
    rl.append(Cube("suit_leg_right", "rightLeg", [0.05, 0, -2.2], [4.1, 12, 2.2], m_suit,
                   group="rightLegSuit"))
    rl.append(Cube("boot_right", "rightLeg", [0.0, 0, -2.6], [4.2, 2.6, 2.4], m_boot,
                   group="rightBoot"))
    rl.append(Cube("toe_right", "rightLeg", [0.4, 0, -3.3], [3.8, 1.5, -2.55], m_boot,
                   group="rightBoot"))
    rl.append(Cube("tail_right_outer", "rightLeg", [4.3, 3.2, -2.6], [4.8, 12.4, 2.8],
                   panel("east", 1.1), rot=(0, 0, -5), pivot=[4.5, 12.4, 0], group="rightCoatTail"))
    rl.append(Cube("tail_right_back", "rightLeg", [0.1, 3.2, 2.6], [4.8, 12.4, 3.1],
                   panel("south", 1.1), rot=(-6, 0, 0), pivot=[2.4, 12.4, 2.8],
                   group="rightCoatTail"))
    rl.append(Cube("tail_right_front", "rightLeg", [2.7, 4.2, -3.25], [4.8, 12.4, -2.75],
                   panel("north", 1.1), rot=(4, 0, 0), pivot=[3.7, 12.4, -3.0],
                   group="rightCoatTail"))
    C += rl
    for c in rl:
        C.append(mirror_x(c, c.name.replace("right", "left"), "leftLeg"))
    # right leg: silver greave wrapped in chains
    C.append(Cube("greave_right", "rightLeg", [-0.05, 2.4, -2.5], [4.25, 8.6, 2.45], p_greave,
                  group="rightGreave"))
    C.append(Cube("knee_right", "rightLeg", [0.5, 8.0, -2.95], [3.6, 10.6, -2.3], p_pauldron,
                  rot=(-6, 0, 0), pivot=[2, 9, -2.6], group="rightGreave"))
    for i, (y, tilt) in enumerate(((2.9, 9), (4.5, -7), (6.6, 10), (8.6, -6), (10.4, 7))):
        C += chain_ring(f"leg_chain_{i}", "rightLeg", 2.1, y, 2.25, 2.55, tilt=tilt,
                        group="rightLegChains")
    # left leg: silver ankle cuff
    C.append(Cube("anklet_left", "leftLeg", [-4.35, 2.2, -2.6], [0.15, 3.7, 2.55], p_bracelet,
                  group="leftBoot"))
    return C


def belt_cubes():
    C = []
    g = "belt"
    C.append(Cube("belt_strap", "body", [-4.6, 12.2, -2.65], [4.6, 13.8, 2.65], p_strap, group=g))
    C.append(Cube("buckle_base", "body", [-1.9, 11.6, -3.2], [1.9, 14.4, -2.65], m_gold, group=g))
    C.append(Cube("buckle_face", "body", [-1.2, 12.1, -3.8], [1.2, 14.0, -3.2], p_kivat_face,
                  group=g))
    C.append(Cube("buckle_ear_right", "body", [0.6, 13.9, -3.7], [1.4, 14.9, -3.3], m_gold,
                  rot=(0, 0, -20), pivot=[1.0, 13.9, -3.5], group=g))
    C.append(Cube("buckle_ear_left", "body", [-1.4, 13.9, -3.7], [-0.6, 14.9, -3.3], m_gold,
                  rot=(0, 0, 20), pivot=[-1.0, 13.9, -3.5], group=g))
    C.append(Cube("wing_right", "body", [1.6, 11.3, -3.25], [5.0, 14.8, -2.95], wing_painter(False),
                  rot=(0, -18, 0), pivot=[1.6, 13, -3.1], group=g))
    C.append(Cube("wing_left", "body", [-5.0, 11.3, -3.25], [-1.6, 14.8, -2.95], wing_painter(True),
                  rot=(0, 18, 0), pivot=[-1.6, 13, -3.1], group=g))
    C.append(Cube("slot_right", "body", [4.55, 11.4, -1.4], [5.15, 14.0, 1.4], p_slot, group=g))
    C.append(Cube("slot_left", "body", [-5.15, 11.4, -1.4], [-4.55, 14.0, 1.4], p_slot, group=g))
    C.append(Cube("back_plate", "body", [-1.6, 12.0, 2.65], [1.6, 14.0, 3.0], m_gold, group=g))
    return C


def mannequin_cubes():
    return [
        Cube("m_head", "head", [-4, 24, -4], [4, 32, 4], p_skin),
        Cube("m_body", "body", [-4, 12, -2], [4, 24, 2], p_skin),
        Cube("m_rarm", "rightArm", [4, 12, -2], [8, 24, 2], p_skin),
        Cube("m_larm", "leftArm", [-8, 12, -2], [-4, 24, 2], p_skin),
        Cube("m_rleg", "rightLeg", [-0.1, 0, -2], [3.9, 12, 2], p_skin),
        Cube("m_lleg", "leftLeg", [-3.9, 0, -2], [0.1, 12, 2], p_skin),
    ]


# --------------------------------------------------------------------------
# atlas packing + texture
# --------------------------------------------------------------------------
def build_texture(cubes, width=ATLAS_W, pad=1):
    rects = []
    for c in cubes:
        for f in FACES:
            w, h = c.face_px(f)
            c.tex[f] = c.paint(f, w, h, c)
            rects.append((c, f, w, h))
    rects.sort(key=lambda r: (-r[3], -r[2]))
    x = y = shelf = 0
    for c, f, w, h in rects:
        if x + w > width:
            x, y, shelf = 0, y + shelf + pad, 0
        c.uv[f] = (x, y, w, h)
        x += w + pad
        shelf = max(shelf, h)
    height = 64
    while height < y + shelf:
        height *= 2
    atlas = np.zeros((height, width, 4))
    for c, f, w, h in rects:
        ux, uy, _, _ = c.uv[f]
        atlas[uy:uy + h, ux:ux + w] = c.tex[f]
    return to_img(atlas)


# --------------------------------------------------------------------------
# bbmodel writer
# --------------------------------------------------------------------------
def r4(v):
    return [round(float(x), 4) for x in v]


def bbmodel(name, ident, cubes, tex_img, tex_name):
    tw, th = tex_img.size
    elements = []
    for c in cubes:
        faces = {}
        for f in FACES:
            ux, uy, w, h = c.uv[f]
            faces[f] = {"uv": [ux, uy, ux + w, uy + h], "texture": 0}
        elements.append({
            "name": c.name, "box_uv": False, "rescale": False, "locked": False,
            "light_emission": 0, "render_order": "default", "allow_mirror_modeling": True,
            "from": r4(c.frm), "to": r4(c.to), "autouv": 0, "color": 0, "inflate": 0,
            "rotation": r4(c.rot), "origin": r4(c.pivot), "faces": faces,
            "type": "cube", "uuid": uid(ident, "cube", c.name),
        })

    def group(gname, children, pivot):
        return {"name": gname, "origin": r4(pivot), "rotation": [0, 0, 0], "color": 0,
                "uuid": uid(ident, "group", gname), "export": True, "mirror_uv": False,
                "isOpen": False, "locked": False, "visibility": True, "autouv": 0,
                "children": children}

    used = {c.bone for c in cubes}
    # include parents of used bones so the hierarchy is valid
    for b in list(used):
        p = BONES[b]["parent"]
        while p:
            used.add(p)
            p = BONES[p]["parent"]

    def bone_node(b):
        kids = []
        subs = {}
        for c in cubes:
            if c.bone != b:
                continue
            if c.group:
                subs.setdefault(c.group, []).append(uid(ident, "cube", c.name))
            else:
                kids.append(uid(ident, "cube", c.name))
        for gname, ids in subs.items():
            kids.append(group(gname, ids, BONES[b]["pivot"]))
        for child, info in BONES.items():
            if info["parent"] == b and child in used:
                kids.append(bone_node(child))
        return group(b, kids, BONES[b]["pivot"])

    outliner = [bone_node(b) for b, info in BONES.items() if info["parent"] is None and b in used]

    buf = io.BytesIO()
    tex_img.save(buf, "PNG", optimize=True)
    src = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    return {
        "meta": {"format_version": "4.10", "model_format": "bedrock", "box_uv": False},
        "name": name, "model_identifier": ident, "visible_box": [2, 3.5, 0.75],
        "variable_placeholders": "", "variable_placeholder_buttons": [],
        "timeline_setups": [], "unhandled_root_fields": {},
        "resolution": {"width": tw, "height": th},
        "elements": elements, "outliner": outliner,
        "textures": [{
            "path": "", "name": tex_name, "folder": "", "namespace": "", "id": "0",
            "group": "", "width": tw, "height": th, "uv_width": tw, "uv_height": th,
            "particle": False, "use_as_default": False, "layers_enabled": False,
            "sync_to_project": "", "render_mode": "default", "render_sides": "auto",
            "frame_time": 1, "frame_order_type": "loop", "frame_order": "",
            "frame_interpolate": False, "visible": True, "internal": True, "saved": False,
            "uuid": uid(ident, "texture"), "source": src,
        }],
        "animations": [],
    }


# --------------------------------------------------------------------------
# preview renderer (orthographic, z-buffered, alpha cutout)
# --------------------------------------------------------------------------
def Rx(d):
    t = math.radians(d)
    return np.array([[1, 0, 0], [0, math.cos(t), -math.sin(t)], [0, math.sin(t), math.cos(t)]])


def Ry(d):
    t = math.radians(d)
    return np.array([[math.cos(t), 0, math.sin(t)], [0, 1, 0], [-math.sin(t), 0, math.cos(t)]])


def Rz(d):
    t = math.radians(d)
    return np.array([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1]])


def render(cubes, yaw=0.0, pitch=0.0, pose=None, scale=14, size=(420, 600), center_y=17.0, ss=2,
           bg=(232, 232, 238)):
    pose = pose or {}
    W, H = size[0] * ss, size[1] * ss
    sc = scale * ss
    col = np.zeros((H, W, 3)) + np.array(bg, float)
    zb = np.full((H, W), np.inf)
    view = Rx(pitch) @ Ry(yaw)
    L = np.array([0.45, 0.8, -0.6])
    L /= np.linalg.norm(L)
    for c in cubes:
        Rc = Rz(c.rot[2]) @ Ry(c.rot[1]) @ Rx(c.rot[0])
        piv = np.array(c.pivot, float)
        chain = []
        b = c.bone
        while b:
            chain.append(b)
            b = BONES[b]["parent"]
        for f, (P0, U, V, N) in c.faces_3d().items():
            img = c.tex[f]
            th_, tw_ = img.shape[:2]
            P = Rc @ (P0 - piv) + piv
            Uw, Vw, Nw = Rc @ U, Rc @ V, Rc @ N
            for bn in chain:
                Rb = Rx(pose.get(bn, 0.0))
                bp = np.array(BONES[bn]["pivot"], float)
                P = Rb @ (P - bp) + bp
                Uw, Vw, Nw = Rb @ Uw, Rb @ Vw, Rb @ Nw
            p0, u, v = view @ P, view @ Uw, view @ Vw
            n_view = view @ Nw
            # camera looks along +z from the front: screen right = -x
            s0 = np.array([W / 2 - p0[0] * sc, H / 2 - (p0[1] - center_y) * sc])
            us = np.array([-u[0] * sc, -u[1] * sc])
            vs = np.array([-v[0] * sc, -v[1] * sc])
            M = np.array([[us[0], vs[0]], [us[1], vs[1]]])
            if abs(np.linalg.det(M)) < 1e-6:
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
            cx = np.clip(np.floor(s_ * tw_).astype(int), 0, tw_ - 1)
            cy = np.clip(np.floor(t_ * th_).astype(int), 0, th_ - 1)
            texel = img[cy, cx]
            inside &= texel[..., 3] >= 128
            depth = p0[2] + s_ * u[2] + t_ * v[2]
            sub_z = zb[y0:y1, x0:x1]
            win = inside & (depth < sub_z - 1e-4)
            if not win.any():
                continue
            nn = Nw / np.linalg.norm(Nw)
            if n_view[2] > 0:
                nn = -nn
            bright = 0.55 + 0.45 * max(0.0, float(nn @ L))
            sub_c = col[y0:y1, x0:x1]
            sub_c[win] = texel[..., :3][win] * bright
            sub_z[win] = depth[win]
    im = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8), "RGB")
    return im.resize(size, Image.LANCZOS)


def label(im, text):
    d = ImageDraw.Draw(im)
    d.text((10, 8), text, fill=(30, 30, 30))
    return im


def check_molang_free(cubes):
    names = [c.name for c in cubes]
    assert len(names) == len(set(names)), "duplicate cube names"


# --------------------------------------------------------------------------
def main():
    os.makedirs(OUT, exist_ok=True)
    armor = armor_cubes()
    belt = belt_cubes()
    check_molang_free(armor)
    check_molang_free(belt)

    armor_tex = build_texture(armor)
    belt_tex = build_texture(belt, width=256)
    armor_tex.save(os.path.join(OUT, "bat_rider_armor.png"))
    belt_tex.save(os.path.join(OUT, "bat_rider_belt.png"))

    for fname, name, ident, cubes, tex, tname in (
            ("Bat_Rider_Armor.bbmodel", "Bat Rider Armor", "bat_rider_armor", armor, armor_tex,
             "bat_rider_armor.png"),
            ("Bat_Rider_Belt.bbmodel", "Bat Rider Belt", "bat_rider_belt", belt, belt_tex,
             "bat_rider_belt.png")):
        with open(os.path.join(OUT, fname), "w") as fh:
            json.dump(bbmodel(name, ident, cubes, tex, tname), fh, separators=(",", ":"))

    # ---- previews ----
    man = mannequin_cubes()
    build_texture(man, width=256)
    full = man + armor + belt
    views = [("front", 0, 0), ("3/4", 35, 8), ("side", 90, 0), ("back", 180, 0)]
    shots = [label(render(full, yaw=y, pitch=p), t) for t, y, p in views]
    walk = {"rightArm": -35, "leftArm": 35, "rightLeg": 30, "leftLeg": -30}
    shots.append(label(render(full, yaw=30, pitch=5, pose=walk), "walk"))
    sheet = Image.new("RGB", (420 * len(shots), 600), (232, 232, 238))
    for i, s in enumerate(shots):
        sheet.paste(s, (420 * i, 0))
    sheet.save(os.path.join(OUT, "preview_armor.png"))

    bshots = [label(render(belt, yaw=y, pitch=p, scale=40, size=(520, 360), center_y=13.0), t)
              for t, y, p in (("belt front", 0, 0), ("belt 3/4", 40, 15), ("belt back", 180, 0))]
    bsheet = Image.new("RGB", (520 * 3, 360), (232, 232, 238))
    for i, s in enumerate(bshots):
        bsheet.paste(s, (520 * i, 0))
    bsheet.save(os.path.join(OUT, "preview_belt.png"))

    # no-mannequin render to spot see-through gaps
    render(armor + belt, yaw=20, pitch=5, bg=(255, 0, 255)).save(
        os.path.join(OUT, "preview_no_body.png"))
    print("armor cubes:", len(armor), "texture", armor_tex.size)
    print("belt cubes:", len(belt), "texture", belt_tex.size)


if __name__ == "__main__":
    main()
