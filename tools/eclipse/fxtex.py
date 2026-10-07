"""Procedural particle textures for ECLIPSE TWIN SWORDS.

Every texture is drawn from math (no external images). Shapes are authored in
white (alpha = shape) unless a texture needs baked colour gradients (sun, moon,
eclipse, spear) - those are tinted white in the particle JSON.

Small sprites share one 512x512 atlas (fx_atlas, 64 px cells) so a single
particle emitter can mix sprites by UV, which keeps the emitter count low on
mobile. Large shapes (rings, circles, slash arcs) get their own textures.
"""
import math
import os

import numpy as np
from PIL import Image

from common import PARTICLE_TEX_DIR, RP, save_rgba, smoothstep

SS = 2  # supersampling factor
RNG = np.random.default_rng(20261007)

# --------------------------------------------------------------------- helpers


def grid(w, h, ss=SS, xr=(-1.0, 1.0), yr=(-1.0, 1.0)):
    """Pixel-centre coordinates. x grows right, y grows UP."""
    W, H = w * ss, h * ss
    xs = xr[0] + (np.arange(W) + 0.5) / W * (xr[1] - xr[0])
    ys = yr[1] - (np.arange(H) + 0.5) / H * (yr[1] - yr[0])
    return np.meshgrid(xs, ys)


def down(a, ss=SS):
    if ss == 1:
        return a
    H, W = a.shape[:2]
    if a.ndim == 2:
        return a.reshape(H // ss, ss, W // ss, ss).mean(axis=(1, 3))
    return a.reshape(H // ss, ss, W // ss, ss, a.shape[2]).mean(axis=(1, 3))


def rgba(alpha, color=(1.0, 1.0, 1.0)):
    """alpha: HxW; color: tuple or HxWx3."""
    alpha = np.clip(alpha, 0, 1)
    out = np.zeros(alpha.shape + (4,))
    col = np.asarray(color, dtype=float)
    out[..., :3] = col if col.ndim == 1 else col
    out[..., 3] = alpha
    return out


def line_ring(r, r0, w):
    return np.exp(-((r - r0) / w) ** 2)


def seg_dist(px, py, ax, ay, bx, by):
    """Distance from points to segment AB (vectorised)."""
    abx, aby = bx - ax, by - ay
    l2 = abx * abx + aby * aby + 1e-12
    t = np.clip(((px - ax) * abx + (py - ay) * aby) / l2, 0.0, 1.0)
    dx, dy = px - (ax + t * abx), py - (ay + t * aby)
    return np.sqrt(dx * dx + dy * dy)


def value_noise(h, w, cells, seed):
    rng = np.random.default_rng(seed)
    small = rng.random((cells, cells))
    img = Image.fromarray((small * 255).astype(np.uint8), "L").resize((w, h), Image.BICUBIC)
    return np.asarray(img, dtype=float) / 255.0


def fbm(h, w, seed, octaves=4, base=4):
    acc, amp, tot = np.zeros((h, w)), 1.0, 0.0
    for o in range(octaves):
        acc += amp * value_noise(h, w, base * 2 ** o, seed + o * 17)
        tot += amp
        amp *= 0.5
    return acc / tot


def noise1d(x, freq, seed):
    """Smooth 1D noise evaluated at x (array), periodic-free."""
    rng = np.random.default_rng(seed)
    n = int(freq) + 4
    knots = rng.random(n)
    xs = (x - x.min()) / (np.ptp(x) + 1e-9) * (n - 3) + 1
    i = np.floor(xs).astype(int)
    f = xs - i
    p0, p1, p2, p3 = knots[i - 1], knots[i], knots[np.minimum(i + 1, n - 1)], knots[np.minimum(i + 2, n - 1)]
    return 0.5 * ((2 * p1) + (-p0 + p2) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f + (-p0 + 3 * p1 - 3 * p2 + p3) * f ** 3)


def ang_noise(theta, harmonics, seed, amp_decay=0.7):
    """Periodic angular noise in [0,1]."""
    rng = np.random.default_rng(seed)
    acc = np.zeros_like(theta)
    amp, tot = 1.0, 0.0
    for k in harmonics:
        acc += amp * np.sin(k * theta + rng.random() * 6.283)
        tot += amp
        amp *= amp_decay
    return 0.5 + 0.5 * acc / tot


# ------------------------------------------------------------------ glyphs

def make_glyphs(count=12, seed=7):
    """Runic glyphs as segment lists on a [-1,1]^2 cell."""
    rng = np.random.default_rng(seed)
    nodes = [(-0.6, 0.8), (0.0, 0.8), (0.6, 0.8), (-0.6, 0.0), (0.0, 0.0), (0.6, 0.0),
             (-0.6, -0.8), (0.0, -0.8), (0.6, -0.8)]
    glyphs = []
    for g in range(count):
        segs = [(nodes[1], nodes[7])] if g % 3 else [(nodes[0], nodes[6])]
        for _ in range(int(rng.integers(2, 4))):
            a, b = rng.choice(9, 2, replace=False)
            if a != b:
                segs.append((nodes[a], nodes[b]))
        glyphs.append(segs)
    return glyphs


GLYPHS = make_glyphs()


def glyph_alpha(lx, ly, gid, width):
    d = np.full(lx.shape, 9.0)
    for (ax, ay), (bx, by) in GLYPHS[gid % len(GLYPHS)]:
        d = np.minimum(d, seg_dist(lx, ly, ax, ay, bx, by))
    return smoothstep(width * 1.6, width * 0.6, d)


def rune_band(r, th, r_mid, half_h, cells, width=0.11, seed=0):
    """Glyphs arranged around a circle (follow the curvature)."""
    step = 2 * math.pi / cells
    k = np.floor((th + math.pi) / step).astype(int)
    phi = -math.pi + (k + 0.5) * step
    arc_half = 0.5 * step * r_mid
    lx = (th - phi) * r / (arc_half * 0.82)
    ly = (r - r_mid) / half_h
    inside = (np.abs(lx) <= 1.2) & (np.abs(ly) <= 1.2)
    out = np.zeros_like(r)
    for gid in range(len(GLYPHS)):
        m = inside & ((k + seed) % len(GLYPHS) == gid)
        if m.any():
            out[m] = glyph_alpha(lx[m], ly[m], gid, width)
    return out


def star_polygon(px, py, n, step, radius, width, rot=math.pi / 2):
    d = np.full(px.shape, 9.0)
    pts = [(radius * math.cos(rot + 2 * math.pi * i / n), radius * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)]
    for i in range(n):
        a, b = pts[i], pts[(i + step) % n]
        d = np.minimum(d, seg_dist(px, py, a[0], a[1], b[0], b[1]))
    return smoothstep(width * 1.5, width * 0.5, d)


def crescent_shape(px, py, cx, cy, r_out, off, r_in):
    """Crescent = disc minus offset disc (soft edges)."""
    d1 = np.hypot(px - cx, py - cy)
    d2 = np.hypot(px - cx - off[0], py - cy - off[1])
    e = 0.012
    return smoothstep(r_out + e, r_out - e, d1) * smoothstep(r_in - e, r_in + e, d2)


# ------------------------------------------------------------- small sprites

def spr_glow(X, Y):
    r = np.hypot(X, Y)
    a = 0.62 * np.exp(-r * r * 10) + 0.38 * np.exp(-r * r * 2.6)
    return a * smoothstep(1.0, 0.82, r)


def spr_glow_hard(X, Y):
    r = np.hypot(X, Y)
    return smoothstep(0.55, 0.35, r) * 0.9 + 0.35 * np.exp(-r * r * 4) * smoothstep(1.0, 0.8, r)


def _ray(u, v, width, power=1.6):
    w = width * np.clip(1 - np.abs(u), 0, 1) ** power + 0.004
    return np.exp(-(v / w) ** 2) * np.clip(1 - np.abs(u), 0, 1) ** 2


def spr_spark4(X, Y, rot=0.0, diag=0.32):
    c, s = math.cos(rot), math.sin(rot)
    x, y = c * X - s * Y, s * X + c * Y
    a = _ray(x, y, 0.07) + _ray(y, x, 0.07)
    xd, yd = (x + y) / math.sqrt(2), (y - x) / math.sqrt(2)
    a += diag * (_ray(xd * 1.7, yd, 0.05) + _ray(yd * 1.7, xd, 0.05))
    r = np.hypot(X, Y)
    a += np.exp(-r * r * 60) + 0.25 * np.exp(-r * r * 8)
    return np.clip(a, 0, 1) * smoothstep(1.0, 0.9, r)


def spr_spark8(X, Y):
    r, th = np.hypot(X, Y), np.arctan2(Y, X)
    a = np.zeros_like(X)
    for i in range(8):
        ang = i * math.pi / 4
        L = 1.0 if i % 2 == 0 else 0.55
        u = (X * math.cos(ang) + Y * math.sin(ang)) / L
        v = -X * math.sin(ang) + Y * math.cos(ang)
        a += np.where(u > 0, _ray(u, v, 0.06), 0)
    a += np.exp(-r * r * 50) + 0.3 * np.exp(-r * r * 6)
    return np.clip(a, 0, 1) * smoothstep(1.0, 0.9, r)


def spr_dot(X, Y):
    r = np.hypot(X, Y)
    return np.clip(smoothstep(0.42, 0.3, r) + 0.45 * np.exp(-r * r * 5), 0, 1) * smoothstep(1, 0.85, r)


def spr_ring_small(X, Y):
    r = np.hypot(X, Y)
    return np.clip(line_ring(r, 0.7, 0.07) + 0.3 * line_ring(r, 0.7, 0.2), 0, 1)


def spr_crescent(X, Y):
    a = crescent_shape(X, Y, 0, 0, 0.78, (0.32, 0.18), 0.66)
    r = np.hypot(X, Y)
    glow = 0.25 * np.exp(-((r - 0.6) / 0.25) ** 2) * (X < 0.2)
    return np.clip(a + glow * 0.5, 0, 1)


def spr_shard(X, Y):
    k = np.abs(X) / 0.3 + np.abs(Y) / 0.95
    body = smoothstep(1.0, 0.9, k)
    edge = np.exp(-((k - 0.92) / 0.06) ** 2)
    ridge = np.exp(-(X / 0.04) ** 2) * (k < 1)
    return np.clip(body * 0.55 + edge * 0.7 + ridge * 0.6, 0, 1)


def spr_wisp(X, Y, seed, n):
    r = np.hypot(X, Y)
    noise = fbm(n, n, seed, octaves=4, base=3)
    a = (noise - 0.30) * 3.2 * np.clip(1 - r, 0, 1) ** 1.1
    return np.clip(a, 0, 1)


def build_atlas(path):
    cell = 64
    n = cell * SS
    X, Y = grid(cell, cell)
    atlas = np.zeros((512, 512, 4))
    sprites = [
        # row 0
        spr_glow(X, Y), spr_glow_hard(X, Y), spr_spark4(X, Y), spr_spark8(X, Y),
        spr_dot(X, Y), spr_ring_small(X, Y), spr_crescent(X, Y), spr_shard(X, Y),
        # row 1: wisps (4) + twinkle flipbook (4)
        spr_wisp(X, Y, 11, n), spr_wisp(X, Y, 23, n), spr_wisp(X, Y, 37, n), spr_wisp(X, Y, 51, n),
        spr_spark4(X * 2.2, Y * 2.2), spr_spark4(X, Y, rot=0.2), spr_spark4(X * 1.4, Y * 1.4, rot=0.4), spr_spark4(X * 3, Y * 3, rot=0.6),
    ]
    # row 2: rune glyphs
    for gid in range(8):
        sprites.append(np.clip(glyph_alpha(X * 1.25, Y * 1.25, gid, 0.12) + 0.25 * glyph_alpha(X * 1.25, Y * 1.25, gid, 0.3), 0, 1))
    for i, spr in enumerate(sprites):
        a = down(spr)
        r, c = divmod(i, 8)
        atlas[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell] = rgba(a)
    save_rgba(path, atlas)
    return atlas


# Atlas UV lookup (pixel coords, 64x64 cells) used by particles.py
ATLAS_CELLS = {
    "glow": (0, 0), "glow_hard": (1, 0), "spark4": (2, 0), "spark8": (3, 0),
    "dot": (4, 0), "ring_small": (5, 0), "crescent": (6, 0), "shard": (7, 0),
    "wisp0": (0, 1), "wisp1": (1, 1), "wisp2": (2, 1), "wisp3": (3, 1),
    "twinkle0": (4, 1), "rune0": (0, 2),
}


# ------------------------------------------------------------ large textures

def tex_slash_arc(edge_only=False):
    w, h = 256, 128
    X, Y = grid(w, h, xr=(-1, 1), yr=(-0.5, 0.5))
    cx, cy, R, thmax = 0.0, -0.55, 0.95, math.radians(72)
    dx, dy = X - cx, Y - cy
    r = np.hypot(dx, dy)
    th = np.arctan2(dx, dy)  # 0 at top
    q = np.clip(np.abs(th) / thmax, 0, 1.2)
    inside_ang = q < 1
    if edge_only:
        taper = np.clip(1 - q ** 2, 0, 1) ** 1.3
        w_line = 0.010 + 0.012 * taper
        a = np.exp(-((r - R + 0.012) / w_line) ** 2) * taper
        a += 0.35 * np.exp(-((r - R + 0.02) / 0.05) ** 2) * taper
        return rgba(down(np.clip(a * inside_ang, 0, 1)))
    T = 0.36 * np.clip(1 - q ** 2, 0, 1) ** 0.6
    u = (r - (R - T)) / (T + 1e-6)
    body = np.clip(u, 0, 1) ** 1.15 * smoothstep(1.02, 0.97, u) * (u > 0)
    lines = noise1d(np.clip(u, 0, 1).ravel(), 22, 5).reshape(u.shape)
    streak = 0.55 + 0.45 * np.clip((lines - 0.25) * 1.6, 0, 1)
    # broken tail: the trailing half breaks up along the arc
    brk = noise1d(th.ravel(), 30, 8).reshape(th.shape)
    streak *= np.where(u < 0.45, 0.55 + 0.45 * brk, 1.0)
    tipfade = np.clip(1 - q ** 5, 0, 1)
    a = body * streak * tipfade * inside_ang
    # soft outer glow ahead of the edge
    a += 0.22 * np.exp(-((r - R) / 0.05) ** 2) * tipfade * inside_ang
    return rgba(down(np.clip(a, 0, 1)))


def tex_ring():
    X, Y = grid(256, 256)
    r = np.hypot(X, Y)
    a = line_ring(r, 0.86, 0.03) + 0.35 * line_ring(r, 0.86, 0.10)
    return rgba(down(np.clip(a, 0, 1) * smoothstep(1.0, 0.97, r)))


def tex_shock_ring():
    X, Y = grid(256, 256)
    r, th = np.hypot(X, Y), np.arctan2(Y, X)
    ramp = smoothstep(0.40, 0.90, r) ** 2.2 * smoothstep(0.96, 0.905, r)
    rim = np.exp(-((r - 0.905) / 0.018) ** 2)
    streak = 0.75 + 0.25 * ang_noise(th, [23, 41, 67, 97], 3)
    a = (ramp * 0.8 * streak + rim) * smoothstep(1.0, 0.95, r)
    return rgba(down(np.clip(a, 0, 1)))


def tex_rune_ring():
    X, Y = grid(512, 512)
    r, th = np.hypot(X, Y), np.arctan2(Y, X)
    a = line_ring(r, 0.74, 0.006) + line_ring(r, 0.93, 0.008) + 0.6 * line_ring(r, 0.97, 0.004)
    a += 0.9 * rune_band(r, th, 0.835, 0.065, 28, width=0.12)
    ticks = (np.abs(((th + math.pi) / (2 * math.pi) * 96) % 1 - 0.5) < 0.08) & (r > 0.945) & (r < 0.965)
    a += ticks * 0.8
    a += 0.08 * ((r > 0.74) & (r < 0.93))
    return rgba(down(np.clip(a, 0, 1)))


def tex_magic_circle_solar():
    X, Y = grid(512, 512)
    r, th = np.hypot(X, Y), np.arctan2(Y, X)
    a = np.zeros_like(r)
    for rr, ww in [(0.98, 0.006), (0.95, 0.004), (0.79, 0.006), (0.745, 0.004), (0.43, 0.005), (0.19, 0.006)]:
        a += line_ring(r, rr, ww)
    a += 0.95 * rune_band(r, th, 0.87, 0.06, 32, width=0.12, seed=3)
    # hexagram
    a += star_polygon(X, Y, 6, 2, 0.745, 0.006)
    # vertex circles
    for i in range(6):
        ang = math.pi / 2 + i * math.pi / 3
        vx, vy = 0.745 * math.cos(ang), 0.745 * math.sin(ang)
        d = np.hypot(X - vx, Y - vy)
        a += line_ring(d, 0.055, 0.005) + smoothstep(0.022, 0.012, d)
    # dots ring
    for i in range(24):
        ang = i * math.pi / 12
        d = np.hypot(X - 0.6 * math.cos(ang), Y - 0.6 * math.sin(ang))
        a += smoothstep(0.014, 0.007, d)
    # central sun: 12 rays
    for i in range(12):
        ang = i * math.pi / 6
        u = X * math.cos(ang) + Y * math.sin(ang)
        v = -X * math.sin(ang) + Y * math.cos(ang)
        L = 0.40 if i % 2 == 0 else 0.31
        tri = (u > 0.2) & (u < L) & (np.abs(v) < 0.03 * (L - u) / (L - 0.2))
        a += tri * 0.9
    a += smoothstep(0.12, 0.10, r) * 0.25 + line_ring(r, 0.11, 0.006)
    a += 0.06 * ((r > 0.745) & (r < 0.98))
    return rgba(down(np.clip(a, 0, 1)))


def tex_magic_circle_void():
    X, Y = grid(512, 512)
    r, th = np.hypot(X, Y), np.arctan2(Y, X)
    a = np.zeros_like(r)
    for rr, ww in [(0.975, 0.006), (0.935, 0.004), (0.70, 0.006), (0.66, 0.004), (0.36, 0.005)]:
        a += line_ring(r, rr, ww)
    a += star_polygon(X, Y, 7, 3, 0.66, 0.006)
    ticks = (np.abs(((th + math.pi) / (2 * math.pi) * 84) % 1 - 0.5) < 0.12) & (r > 0.94) & (r < 0.97)
    a += ticks * 0.7
    for i in range(8):
        ang = i * math.pi / 4 + math.pi / 8
        cx, cy = 0.82 * math.cos(ang), 0.82 * math.sin(ang)
        # crescent opening outward
        off = (0.03 * math.cos(ang), 0.03 * math.sin(ang))
        a += crescent_shape(X, Y, cx, cy, 0.075, off, 0.065)
        dx, dy = 0.82 * math.cos(ang + math.pi / 8), 0.82 * math.sin(ang + math.pi / 8)
        a += smoothstep(0.016, 0.008, np.hypot(X - dx, Y - dy))
    a += 0.85 * rune_band(r, th, 0.515, 0.07, 20, width=0.12, seed=5)
    a += crescent_shape(X, Y, 0, 0, 0.24, (0.09, 0.05), 0.2)
    # spiral dots in centre
    for i in range(14):
        t = i / 14
        ang, rad = t * 4.5 * math.pi, 0.05 + 0.27 * t
        a += smoothstep(0.012, 0.005, np.hypot(X - rad * math.cos(ang), Y - rad * math.sin(ang))) * (1 - t * 0.5)
    a += 0.07 * ((r > 0.66) & (r < 0.975))
    return rgba(down(np.clip(a, 0, 1)))


def tex_sun_halo():
    X, Y = grid(512, 512)
    r, th = np.hypot(X, Y), np.arctan2(Y, X)
    a = line_ring(r, 0.55, 0.018) + 0.6 * line_ring(r, 0.61, 0.006) + 0.5 * line_ring(r, 0.49, 0.005)
    for i in range(16):
        ang = i * math.pi / 8
        L = 0.97 if i % 2 == 0 else 0.80
        u = X * math.cos(ang) + Y * math.sin(ang)
        v = -X * math.sin(ang) + Y * math.cos(ang)
        base = 0.035 if i % 2 == 0 else 0.025
        half = base * np.clip((L - u) / (L - 0.62), 0, 1)
        spike = (u > 0.62) & (u < L) & (np.abs(v) < half)
        a += spike * (0.55 + 0.45 * (1 - (u - 0.62) / (L - 0.62)))
        a += 0.5 * np.exp(-(v / 0.01) ** 2) * (u > 0.62) * (u < L) * (1 - (u - 0.62) / (L - 0.62))
    for i in range(32):
        ang = i * math.pi / 16 + math.pi / 32
        a += smoothstep(0.012, 0.006, np.hypot(X - 0.44 * math.cos(ang), Y - 0.44 * math.sin(ang)))
    a += 0.25 * np.exp(-((r - 0.55) / 0.08) ** 2)
    return rgba(down(np.clip(a, 0, 1)))


def tex_crown_orbit(n_arcs=5, colors=None, radius=0.82, span=55.0, seed=0):
    """Flat ring of symmetric light arcs (rotating light lines around the body).

    Arcs are symmetric (bright centre, fading both ends) so they read correctly
    whichever way the particle spins.
    """
    X, Y = grid(512, 512)
    r, th = np.hypot(X, Y), np.arctan2(Y, X)
    col = np.zeros(r.shape + (3,))
    alpha = np.zeros_like(r)
    half = math.radians(span) / 2
    for i in range(n_arcs):
        mid = 2 * math.pi * i / n_arcs
        rad = radius[i % len(radius)] if isinstance(radius, (list, tuple)) else radius
        dth = np.abs((th - mid + math.pi) % (2 * math.pi) - math.pi)
        s = np.clip(dth / half, 0, 1)
        prof = np.clip(1 - s * s, 0, 1) ** 1.5
        width = 0.006 + 0.016 * prof
        inten = prof * np.exp(-((r - rad) / width) ** 2)
        hx, hy = rad * math.cos(mid), rad * math.sin(mid)
        dh = np.hypot(X - hx, Y - hy)
        inten = inten + 0.9 * np.exp(-(dh / 0.025) ** 2) + 0.3 * np.exp(-(dh / 0.08) ** 2)
        c = np.array(colors[i % len(colors)] if colors else (1, 1, 1))
        col += inten[..., None] * c
        alpha += inten
    alpha = np.clip(alpha, 0, 1)
    col = np.where(alpha[..., None] > 1e-4, col / np.maximum(alpha[..., None], 1e-4), 1)
    col = np.clip(col, 0, 1)
    return np.dstack([down(col[..., k]) for k in range(3)] + [down(alpha)])


def tex_spear():
    """Falling spear of light, tip pointing DOWN. Baked colour."""
    w, h = 128, 512
    X, Y = grid(w, h, xr=(-1, 1), yr=(0, 1))  # Y=0 bottom (tip), 1 top
    y = Y
    wid = np.where(y < 0.20, 0.80 * (y / 0.20) ** 0.8,
          np.where(y < 0.30, 0.80 - (0.80 - 0.24) * (y - 0.20) / 0.10,
          np.where(y < 0.34, 0.24 + 0.40 * np.sin((y - 0.30) / 0.04 * math.pi),
                   0.24 - 0.10 * (y - 0.34) / 0.66)))
    wid = np.maximum(wid, 1e-3)
    q = np.abs(X) / wid
    body = smoothstep(1.0, 0.92, q)
    core = np.clip(1 - q, 0, 1) ** 0.6
    glow = 0.55 * np.exp(-np.clip(np.abs(X) - wid, 0, None) / 0.16)
    fade = 1 - smoothstep(0.72, 1.0, y)
    alpha = np.clip(body * (0.55 + 0.45 * core) + glow * (1 - body), 0, 1) * fade
    ridge = np.exp(-(X / 0.03) ** 2) * (y < 0.33)
    white = np.array([1.0, 1.0, 0.97])
    gold = np.array([1.0, 0.78, 0.30])
    orange = np.array([1.0, 0.50, 0.12])
    t = np.clip(q, 0, 1)[..., None]
    col = np.where(t < 0.5, white + (gold - white) * (t / 0.5), gold + (orange - gold) * ((t - 0.5) / 0.5))
    col = np.where((body < 0.5)[..., None], orange * 0.9 + gold * 0.1, col)
    col = col + ridge[..., None] * 0.6
    col = np.clip(col, 0, 1)
    return np.dstack([down(col[..., k]) for k in range(3)] + [down(alpha)])


def tex_beam():
    X, Y = grid(64, 256, xr=(-1, 1), yr=(0, 1))
    a = np.exp(-(X / 0.14) ** 2) + 0.45 * np.exp(-(X / 0.5) ** 2)
    a *= smoothstep(0.0, 0.15, Y) * smoothstep(1.0, 0.7, Y)
    return rgba(down(np.clip(a, 0, 1)))


def tex_flash():
    X, Y = grid(256, 256)
    r, th = np.hypot(X, Y), np.arctan2(Y, X)
    a = np.exp(-r * r * 28) + 0.55 * np.exp(-r * r * 5)
    rng = np.random.default_rng(9)
    for i in range(10):
        ang = i * math.pi / 5 + rng.uniform(-0.15, 0.15)
        L = rng.uniform(0.6, 1.0)
        u = (X * math.cos(ang) + Y * math.sin(ang)) / L
        v = -X * math.sin(ang) + Y * math.cos(ang)
        a += np.where(u > 0, _ray(u, v, 0.05), 0) * 0.8
    a += 0.25 * line_ring(r, 0.5, 0.04)
    return rgba(down(np.clip(a, 0, 1) * smoothstep(1.0, 0.9, r)))


def tex_sun_disc():
    X, Y = grid(256, 256)
    r, th = np.hypot(X, Y), np.arctan2(Y, X)
    R0 = 0.40
    disc = smoothstep(R0 + 0.01, R0 - 0.01, r)
    limb = np.clip(r / R0, 0, 1)
    disc_col = np.stack([np.ones_like(r), 1 - 0.18 * limb ** 3, 0.92 - 0.55 * limb ** 2], -1)
    fl = 0.65 + 0.35 * ang_noise(th, [7, 13, 19, 29], 4)
    cor = np.exp(-np.clip(r - R0, 0, None) / (0.10 * fl)) * (r >= R0 - 0.01)
    rays = np.zeros_like(r)
    for i in range(12):
        ang = i * math.pi / 6 + 0.13
        u = X * math.cos(ang) + Y * math.sin(ang)
        v = -X * math.sin(ang) + Y * math.cos(ang)
        rays += np.where(u > 0, _ray(u, v, 0.05), 0)
    cor = np.clip(cor + 0.5 * rays * (r > R0), 0, 1)
    cor_col = np.stack([np.ones_like(r), 0.62 + 0.25 * cor, 0.18 + 0.2 * cor], -1)
    alpha = np.clip(disc + cor * (1 - disc), 0, 1) * smoothstep(1.0, 0.92, r)
    col = disc_col * disc[..., None] + cor_col * (1 - disc[..., None])
    return np.dstack([down(col[..., k]) for k in range(3)] + [down(alpha)])


def tex_black_moon():
    X, Y = grid(256, 256)
    r = np.hypot(X, Y)
    R0 = 0.76
    disc = smoothstep(R0 + 0.012, R0 - 0.012, r)
    n = fbm(512, 512, 77, octaves=4, base=6)
    base = np.stack([0.045 + 0.04 * n, 0.02 + 0.02 * n, 0.08 + 0.06 * n], -1)
    lit = np.clip((-X * 0.7 + Y * 0.7) / (r + 1e-6), 0, 1) ** 1.6 * smoothstep(0.45, R0, r)
    rim_col = np.array([0.62, 0.36, 1.0])
    col = base + lit[..., None] * rim_col * 0.95
    thin = np.exp(-((r - R0 + 0.01) / 0.012) ** 2)
    col = col + thin[..., None] * np.array([0.5, 0.35, 0.95]) * 0.8
    glow = 0.65 * np.exp(-np.clip(r - R0, 0, None) / 0.07) * (r > R0 - 0.01)
    glow_col = np.array([0.38, 0.14, 0.72])
    alpha = np.clip(disc + glow * (1 - disc), 0, 1) * smoothstep(1.0, 0.94, r)
    col = col * disc[..., None] + glow_col * (1 - disc[..., None])
    col = np.clip(col, 0, 1)
    return np.dstack([down(col[..., k]) for k in range(3)] + [down(alpha)])


def tex_eclipse_disc():
    X, Y = grid(256, 256)
    r = np.hypot(X, Y)
    R0 = 0.62
    disc = smoothstep(R0 + 0.008, R0 - 0.008, r)
    haze = 0.55 * np.exp(-np.clip(r - R0, 0, None) / 0.05) * (r > R0 - 0.01)
    alpha = np.clip(disc + haze * (1 - disc), 0, 1)
    col = np.stack([0.02 + 0.06 * (1 - disc), 0.0 * r, 0.03 + 0.1 * (1 - disc)], -1)
    return np.dstack([down(col[..., k]) for k in range(3)] + [down(alpha)])


def tex_corona():
    X, Y = grid(512, 512)
    r, th = np.hypot(X, Y), np.arctan2(Y, X)
    R0 = 0.31
    streak = ang_noise(th, [9, 17, 31, 53, 87], 21, 0.8) ** 3
    rays = np.exp(-np.clip(r - R0, 0, None) / (0.08 + 0.32 * streak)) * (r > R0 - 0.005)
    rim = np.exp(-((r - R0) / 0.012) ** 2) * 1.3
    inner = 0.4 * np.exp(-((r - R0) / 0.05) ** 2)
    # diamond-ring flare
    fx, fy = R0 * math.cos(math.radians(38)), R0 * math.sin(math.radians(38))
    fd = np.hypot(X - fx, Y - fy)
    flare = np.exp(-(fd / 0.03) ** 2) + 0.4 * np.exp(-(fd / 0.12) ** 2)
    flare += 0.6 * (_ray((X - fx) / 0.5, Y - fy, 0.02) + _ray((Y - fy) / 0.5, X - fx, 0.02))
    a = np.clip(rays * 0.85 + rim + inner + flare, 0, 1) * smoothstep(1.0, 0.9, r)
    t = np.clip((r - R0) / 0.5, 0, 1)
    col = np.stack([np.ones_like(r), 0.95 - 0.35 * t, 0.85 - 0.7 * t], -1)
    return np.dstack([down(col[..., k]) for k in range(3)] + [down(a)])


def tex_eclipse_halo():
    X, Y = grid(512, 512)
    r, th = np.hypot(X, Y), np.arctan2(Y, X)
    R0 = 0.50
    streak = ang_noise(th, [11, 19, 37, 61], 31, 0.8) ** 2.5
    gold_a = np.exp(-np.clip(r - R0, 0, None) / (0.05 + 0.2 * streak)) * (r > R0 - 0.004)
    gold_a = gold_a * 0.75 + np.exp(-((r - R0) / 0.012) ** 2)
    purple_a = line_ring(r, 0.86, 0.010) + 0.5 * line_ring(r, 0.42, 0.006) + 0.3 * line_ring(r, 0.86, 0.04)
    purple_a += 0.8 * rune_band(r, th, 0.915, 0.035, 36, width=0.13, seed=2)
    gold = np.array([1.0, 0.80, 0.36])
    purple = np.array([0.62, 0.32, 1.0])
    alpha = np.clip(gold_a + purple_a, 0, 1) * smoothstep(1.0, 0.96, r)
    w = gold_a / (gold_a + purple_a + 1e-6)
    col = gold * w[..., None] + purple * (1 - w[..., None])
    white = np.exp(-((r - R0) / 0.008) ** 2)[..., None]
    col = np.clip(col + white * 0.5, 0, 1)
    return np.dstack([down(col[..., k]) for k in range(3)] + [down(alpha)])


def tex_split_ring():
    X, Y = grid(512, 512)
    r, th = np.hypot(X, Y), np.arctan2(Y, X)
    a = line_ring(r, 0.80, 0.008) + line_ring(r, 0.95, 0.010) + 0.6 * line_ring(r, 0.68, 0.006)
    a += 0.9 * rune_band(r, th, 0.875, 0.06, 30, width=0.12, seed=4)
    a += 0.18 * ((r > 0.80) & (r < 0.95))
    for i in range(24):
        ang = i * math.pi / 12
        u = X * math.cos(ang) + Y * math.sin(ang)
        v = -X * math.sin(ang) + Y * math.cos(ang)
        a += ((u > 0.955) & (u < 0.99) & (np.abs(v) < 0.008)) * 0.9
    gold = np.array([1.0, 0.80, 0.35])
    purple = np.array([0.56, 0.24, 1.0])
    # left half gold, right half purple, soft seam at top/bottom
    m = smoothstep(-0.08, 0.08, -X / (r + 1e-6))[..., None]
    col = gold * m + purple * (1 - m)
    alpha = np.clip(a, 0, 1) * smoothstep(1.0, 0.99, r)
    return np.dstack([down(col[..., k]) for k in range(3)] + [down(alpha)])


def tex_void_core():
    X, Y = grid(256, 256)
    r, th = np.hypot(X, Y), np.arctan2(Y, X)
    s = th + 3.5 * np.log(r + 1e-3)
    arms = (0.5 + 0.5 * np.cos(3 * s)) ** 3
    core = smoothstep(0.36, 0.30, r)
    horizon = np.exp(-((r - 0.35) / 0.025) ** 2)
    swirl = arms * smoothstep(0.30, 0.42, r) * np.clip(1 - r, 0, 1) ** 1.2 * 1.4
    alpha = np.clip(core + horizon * 0.9 + swirl, 0, 1) * smoothstep(1.0, 0.9, r)
    purple = np.array([0.50, 0.20, 0.85])
    col = np.zeros(r.shape + (3,))
    wv = np.clip(horizon * 1.2 + swirl, 0, 1)[..., None]
    col = col * (1 - wv) + purple * wv
    col = col * (1 - core[..., None]) + np.array([0.01, 0.0, 0.02]) * core[..., None]
    return np.dstack([down(col[..., k]) for k in range(3)] + [down(alpha)])


def tex_void_swirl():
    X, Y = grid(512, 512)
    r, th = np.hypot(X, Y), np.arctan2(Y, X)
    s = th + 3.0 * np.log(r + 1e-3)
    arms = (0.5 + 0.5 * np.cos(5 * s)) ** 4
    n = fbm(1024, 1024, 5, octaves=3, base=8)
    a = arms * smoothstep(0.06, 0.28, r) * smoothstep(1.0, 0.55, r) * (0.55 + 0.45 * n)
    a += 0.35 * line_ring(r, 0.96, 0.012)
    return rgba(down(np.clip(a * 1.2, 0, 1)))


def tex_crack_star():
    X, Y = grid(512, 512)
    r = np.hypot(X, Y)
    rng = np.random.default_rng(42)
    d = np.full(X.shape, 9.0)

    def crack(x0, y0, ang, length, depth):
        nonlocal d
        x, y = x0, y0
        steps = 7
        for i in range(steps):
            ang += rng.uniform(-0.35, 0.35)
            seg = length / steps
            nx, ny = x + seg * math.cos(ang), y + seg * math.sin(ang)
            d = np.minimum(d, seg_dist(X, Y, x, y, nx, ny))
            if depth > 0 and rng.random() < 0.28:
                crack(nx, ny, ang + rng.choice([-1, 1]) * rng.uniform(0.5, 0.9), length * 0.35, depth - 1)
            x, y = nx, ny

    for i in range(14):
        ang = i * 2 * math.pi / 14 + rng.uniform(-0.15, 0.15)
        crack(0.06 * math.cos(ang), 0.06 * math.sin(ang), ang, rng.uniform(0.55, 0.92), 1)
    a = np.exp(-(d / 0.007) ** 2) + 0.45 * np.exp(-(d / 0.03) ** 2)
    a *= np.clip(1 - r ** 1.5, 0, 1)
    a += 0.7 * np.exp(-(r / 0.12) ** 2)
    return rgba(down(np.clip(a, 0, 1)))


LARGE = {
    "slash_arc": lambda: tex_slash_arc(False),
    "slash_edge": lambda: tex_slash_arc(True),
    "ring": tex_ring,
    "shock_ring": tex_shock_ring,
    "rune_ring": tex_rune_ring,
    "magic_circle_solar": tex_magic_circle_solar,
    "magic_circle_void": tex_magic_circle_void,
    "sun_halo": tex_sun_halo,
    "crown_orbit": lambda: tex_crown_orbit(5),
    "eclipse_orbit": lambda: tex_crown_orbit(6, colors=[(1.0, 0.80, 0.35), (0.62, 0.30, 1.0)], radius=[0.86, 0.70], span=62),
    "spear": tex_spear,
    "beam": tex_beam,
    "flash": tex_flash,
    "sun_disc": tex_sun_disc,
    "black_moon": tex_black_moon,
    "eclipse_disc": tex_eclipse_disc,
    "corona": tex_corona,
    "eclipse_halo": tex_eclipse_halo,
    "split_ring": tex_split_ring,
    "void_core": tex_void_core,
    "void_swirl": tex_void_swirl,
    "crack_star": tex_crack_star,
}

# texture sizes (w, h) for particle UV declarations
SIZES = {"fx_atlas": (512, 512), "slash_arc": (256, 128), "slash_edge": (256, 128), "spear": (128, 512), "beam": (64, 256)}


def tex_size(name):
    if name in SIZES:
        return SIZES[name]
    return (512, 512) if name in ("rune_ring", "magic_circle_solar", "magic_circle_void", "sun_halo", "crown_orbit",
                                  "eclipse_orbit", "corona", "eclipse_halo", "split_ring", "void_swirl", "crack_star") else (256, 256)


def build_all():
    out_dir = os.path.join(RP, PARTICLE_TEX_DIR)
    built = {}
    built["fx_atlas"] = build_atlas(os.path.join(out_dir, "fx_atlas.png"))
    for name, fn in LARGE.items():
        img = fn()
        save_rgba(os.path.join(out_dir, name + ".png"), img)
        built[name] = img
    return built


if __name__ == "__main__":
    build_all()
