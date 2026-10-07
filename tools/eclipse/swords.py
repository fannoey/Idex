"""SOLARIS and NOCTIS - poly_mesh models, texture atlas, icons and rig.

Local sword frame (units = model pixels, 1/16 block):
    a: along the blade (tip +a, guard centre near 0), b: across (blade plane),
    c: thickness.  Solaris' sun rays sit on the -b side like the reference art.
"""
import math

import numpy as np

from mesh import (Mesh, blade, ellipsoid, grid_normals, lens_strip, loft, map_uv, torus, tube)

ATLAS = 512
UVC = (ATLAS, ATLAS)

# texture regions (x0, y0, x1, y1) inside the top-half content area (512 x 256)
R = {
    "S_BLADE": (0, 0, 512, 32),
    "N_BLADE": (0, 34, 512, 66),
    "S_PLATE": (0, 68, 256, 100),
    "GOLD": (258, 68, 384, 100),
    "GOLD_GLOW": (386, 68, 512, 100),
    "S_GRIP": (0, 102, 128, 134),
    "S_RIBBON": (130, 102, 256, 118),
    "S_RAY": (130, 120, 256, 134),
    "S_CORE": (258, 102, 290, 134),
    "SILVER": (292, 102, 420, 134),
    "N_GEM": (422, 102, 486, 166),
    "N_GRIP": (0, 136, 128, 168),
    "N_TENDRIL": (130, 136, 256, 152),
    "N_DARK": (130, 154, 256, 168),
    "N_GLOW": (258, 136, 290, 168),
}


def curve(points):
    """Smooth 1D profile through (x, y) control points (Catmull-Rom)."""
    xs = np.array([p[0] for p in points], float)
    ys = np.array([p[1] for p in points], float)

    def f(x):
        x = float(np.clip(x, xs[0], xs[-1]))
        i = int(np.clip(np.searchsorted(xs, x) - 1, 0, len(xs) - 2))
        t = (x - xs[i]) / (xs[i + 1] - xs[i])
        p0 = ys[max(i - 1, 0)]
        p1, p2 = ys[i], ys[i + 1]
        p3 = ys[min(i + 2, len(ys) - 1)]
        return 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)
    return f


def stations(a0, a1, n, tip_dense=0):
    s = list(np.linspace(a0, a1, n))
    if tip_dense:
        L = a1 - a0
        s = list(np.linspace(a0, a1 - 0.12 * L, n)) + [a1 - 0.12 * L * (1 - math.sin(math.pi / 2 * k / tip_dense)) for k in range(1, tip_dense + 1)]
    return sorted(set(round(x, 5) for x in s))


def spiral_path(center_ab, r0, r1, ang0, turns, n, c=0.0, sign=1):
    pts = []
    for k in range(n):
        t = k / (n - 1)
        ang = ang0 + sign * turns * 2 * math.pi * t
        r = r0 + (r1 - r0) * t
        pts.append((center_ab[0] + r * math.cos(ang), center_ab[1] + r * math.sin(ang), c))
    return pts


def bezier(ctrl, n):
    ctrl = np.asarray(ctrl, float)
    out = []
    for k in range(n):
        t = k / (n - 1)
        pts = ctrl.copy()
        while len(pts) > 1:
            pts = (1 - t) * pts[:-1] + t * pts[1:]
        out.append(pts[0])
    return np.array(out)


def chain(*parts):
    out = [np.asarray(parts[0], float)]
    for p in parts[1:]:
        p = np.asarray(p, float)
        out.append(p[1:] if np.allclose(out[-1][-1], p[0], atol=1e-3) else p)
    return np.concatenate(out)


def helix(a0, a1, radius, turns, n, phase=0.0):
    a = np.linspace(a0, a1, n)
    th = phase + 2 * math.pi * turns * np.linspace(0, 1, n)
    return np.stack([a, radius * np.cos(th), radius * np.sin(th)], 1)


def taper(n, r0, r1, end_power=1.0, start_round=0.12):
    t = np.linspace(0, 1, n)
    r = r0 + (r1 - r0) * t ** end_power
    r *= np.clip(t / start_round, 0.35, 1.0) ** 0.5 if start_round else 1.0
    return r


# ================================================================== SOLARIS

def build_solaris():
    m = Mesh()
    # --- blade: long, thin, glowing (tip at a = 27)
    L = 27.0
    w = curve([(0, 0.96), (5, 0.9), (10, 0.76), (15, 0.6), (20, 0.44), (24, 0.27), (26.2, 0.1), (L, 0.0)])
    t = curve([(0, 0.21), (8, 0.19), (16, 0.15), (24, 0.11), (L, 0.05)])

    def half_w(a):
        return max(0.0, w(a))

    def half_t(a):
        return max(0.004, min(t(a), half_w(a) * 0.45 + 0.004))

    m.merge(blade(stations(0.0, L, 34, tip_dense=8), half_w, half_t, R["S_BLADE"], UVC))

    # --- golden ornament plate on the lower blade (with star cut-outs in texture)
    wp = curve([(-0.2, 1.08), (1.0, 1.18), (2.2, 1.08), (3.4, 0.8), (4.6, 0.68), (5.8, 0.74), (7.0, 0.5), (8.6, 0.0)])
    tp = curve([(-0.2, 0.30), (4.0, 0.27), (8.6, 0.22)])
    m.merge(loft(stations(-0.2, 8.6, 22), lambda a: max(wp(a), 0.01), lambda a: max(tp(a) * min(1, wp(a) / 0.5), 0.01),
                 12, R["S_PLATE"], UVC, power=1.35))

    # --- guard body / sun emblem
    gw = curve([(-2.7, 0.48), (-2.1, 0.66), (-1.3, 0.92), (-0.5, 0.98), (0.2, 0.9), (0.7, 0.74)])
    m.merge(loft(stations(-2.7, 0.7, 12), gw, lambda a: 0.44 - 0.04 * (a + 2.7) / 3.4, 16, R["GOLD"], UVC, power=2.4))

    # --- halo ring (outer gold + inner glowing line) in the blade plane
    ring_c = np.array([-0.9, 0.0, 0.0])
    ea, eb = np.array([1.0, 0, 0]), np.array([0, 1.0, 0])
    m.merge(torus(ring_c, ea, eb, 2.12, 0.15, 44, 8, R["GOLD"], UVC))
    m.merge(torus(ring_c, ea, eb, 1.76, 0.085, 44, 6, R["GOLD_GLOW"], UVC))
    m.merge(torus(ring_c, ea, eb, 2.48, 0.05, 44, 5, R["GOLD_GLOW"], UVC, arc=(math.radians(40), math.radians(320))))

    # --- core gem (white glow)
    m.merge(ellipsoid(ring_c, (0.78, 0.46, 0.52), 12, 8, R["S_CORE"], UVC))

    # --- sun-ray fan on the -b side
    rays = [(28, 1.3, 0.3), (48, 1.75, 0.38), (68, 2.05, 0.42), (88, 2.15, 0.44), (108, 1.85, 0.4), (128, 1.35, 0.32)]
    for ang, length, base in rays:
        phi = math.radians(ang)
        d = np.array([math.cos(phi), -math.sin(phi)])
        p0 = ring_c[:2] + d * 2.18

        def cab(s, p0=p0, d=d, length=length):
            return p0 + d * length * s

        m.merge(lens_strip(cab, lambda s, base=base: base * (1 - s) ** 0.9 + 0.01, lambda s: 0.13 * (1 - 0.6 * s) + 0.01,
                           8, 3, R["S_RAY"], UVC))

    # --- grip (gold lattice) + collars
    m.merge(loft(stations(-10.7, -2.6, 16), lambda a: 0.40 + 0.05 * math.sin(math.pi * (a + 10.7) / 8.1),
                 lambda a: 0.40 + 0.05 * math.sin(math.pi * (a + 10.7) / 8.1), 12, R["S_GRIP"], UVC))
    for a0 in (-2.75, -10.55):
        m.merge(torus((a0, 0, 0), (0, 1.0, 0), (0, 0, 1.0), 0.47, 0.11, 14, 6, R["GOLD"], UVC))

    # --- flame ribbons (orange, glowing)
    r1 = helix(-2.9, -10.2, 0.6, 1.35, 34, phase=0.4)
    m.merge(tube(r1, taper(34, 0.2, 0.12), 6, R["S_RIBBON"], UVC, flat=0.26,
                 normal_fn=lambda k, p=r1: np.array([0, p[k][1], p[k][2]])))
    curl_r = chain(bezier([(-0.9, 2.15, 0.12), (-0.6, 2.9, 0.18), (-1.2, 3.7, 0.12), (-2.0, 3.6, 0.1)], 10),
                   spiral_path((-1.75, 2.95), 0.68, 0.12, math.radians(70), 1.25, 18, c=0.1))
    m.merge(tube(curl_r, taper(len(curl_r), 0.19, 0.03, 1.2), 6, R["S_RIBBON"], UVC, flat=0.25,
                 normal_fn=lambda k: np.array([0, 0, 1.0])))
    loop_l = bezier([(-3.1, -0.45, 0.2), (-4.4, -2.9, 0.35), (-7.4, -3.4, 0.1), (-9.5, -1.6, -0.15), (-10.3, -0.45, 0.0)], 30)
    m.merge(tube(loop_l, taper(30, 0.17, 0.1), 6, R["S_RIBBON"], UVC, flat=0.25,
                 normal_fn=lambda k: np.array([0, 0, 1.0])))
    curl_low = chain(bezier([(-5.0, 0.55, -0.2), (-5.4, 1.4, -0.15), (-6.4, 2.0, -0.1)], 8),
                     spiral_path((-6.55, 1.45), 0.55, 0.1, math.radians(80), 1.1, 14, c=-0.1))
    m.merge(tube(curl_low, taper(len(curl_low), 0.15, 0.03, 1.2), 6, R["S_RIBBON"], UVC, flat=0.25,
                 normal_fn=lambda k: np.array([0, 0, 1.0])))

    # --- pommel: small sun
    m.merge(loft(stations(-11.05, -10.7, 3), lambda a: 0.34, lambda a: 0.34, 10, R["GOLD"], UVC))
    pc = np.array([-11.55, 0.0, 0.0])
    m.merge(ellipsoid(pc, (0.55, 0.55, 0.3), 14, 8, R["GOLD_GLOW"], UVC))
    for k in range(8):
        phi = 2 * math.pi * k / 8 + math.pi / 8
        d = np.array([math.cos(phi), math.sin(phi)])
        p0 = pc[:2] + d * 0.5
        m.merge(lens_strip(lambda s, p0=p0, d=d: p0 + d * 0.42 * s, lambda s: 0.12 * (1 - s) + 0.01,
                           lambda s: 0.07, 4, 2, R["S_RAY"], UVC))
    return m


# =================================================================== NOCTIS

def crescent_lens(center, R1, R2, offset_b, thick, n_theta, n_x, region, open_dir=1.0, c0=0.0):
    """Crescent moon (disc minus offset disc) with a lens cross-section, in the a-b plane.
    open_dir: +1 opens toward +b, -1 toward -b. Returns Mesh."""
    C = np.asarray(center, float)
    d = np.array([0.0, offset_b * open_dir])

    def direction(psi):
        # psi = angle measured from the BACK of the crescent (-b * open_dir)
        return np.array([math.sin(psi), -math.cos(psi) * open_dir])

    def inner(psi):
        u = direction(psi)
        ud = u @ d
        return ud + math.sqrt(max(ud * ud - d @ d + R2 * R2, 0.0))

    lo, hi = 0.0, math.pi
    for _ in range(60):  # horn angle where the inner circle meets the outer one
        mid = 0.5 * (lo + hi)
        if inner(mid) < R1:
            lo = mid
        else:
            hi = mid
    psi_max = lo * 0.995
    psis = np.linspace(-psi_max, psi_max, n_theta)
    x = np.linspace(0, 1, n_x + 1)
    prof = np.sqrt(np.clip(1 - (2 * x - 1) ** 2, 0, 1))
    m = Mesh()
    for side in (1, -1):
        pts = np.zeros((n_theta, n_x + 1, 3))
        for i, psi in enumerate(psis):
            u = direction(psi)
            r_in = min(inner(psi), R1)
            rr = r_in + (R1 - r_in) * x
            width = R1 - r_in
            pts[i, :, 0] = C[0] + u[0] * rr
            pts[i, :, 1] = C[1] + u[1] * rr
            pts[i, :, 2] = c0 + side * thick * prof * min(1.0, width / 0.35 + 0.15)
        nrm = grid_normals(pts)
        s = np.sign(nrm[..., 2:3] * side)
        s[s == 0] = 1
        nrm *= s
        U, V = np.meshgrid(np.linspace(0, 1, n_theta), x, indexing="ij")
        m.add_grid(pts, nrm, map_uv(U, V, region, *UVC))
    return m


def build_noctis():
    m = Mesh()
    L = 27.5
    w = curve([(0, 1.02), (4, 0.94), (10, 0.78), (16, 0.6), (21, 0.42), (25, 0.24), (26.8, 0.08), (L, 0.0)])
    t = curve([(0, 0.25), (10, 0.21), (18, 0.16), (25, 0.11), (L, 0.05)])

    def half_w(a):
        return max(0.0, w(a))

    def half_t(a):
        return max(0.004, min(t(a), half_w(a) * 0.45 + 0.004))

    m.merge(blade(stations(0.0, L, 34, tip_dense=8), half_w, half_t, R["N_BLADE"], UVC))
    # blade root collar
    m.merge(loft(stations(-0.3, 0.9, 4), lambda a: 1.08 - 0.12 * (a + 0.3), lambda a: 0.32, 12, R["N_DARK"], UVC, power=1.6))

    C = np.array([-1.0, 0.0])
    # --- main crescent (silver), opening toward +b
    m.merge(crescent_lens(C, 2.05, 1.62, 0.62, 0.36, 40, 6, R["SILVER"]))
    # inner rim line of the crescent (glowing blue edge)
    # --- gem (blue star) seated inside the crescent
    gem_c = np.array([C[0], 0.45, 0.0])
    m.merge(ellipsoid(gem_c, (0.82, 0.82, 0.56), 16, 10, R["N_GEM"], UVC))
    m.merge(torus(gem_c, (1.0, 0, 0), (0, 1.0, 0), 0.9, 0.08, 28, 5, R["N_DARK"], UVC))

    # --- small crescents beside the blade root (opening outward)
    for sb in (-1, 1):
        m.merge(crescent_lens((1.6, sb * 1.95), 0.6, 0.48, 0.26, 0.16, 18, 4, R["SILVER"], open_dir=sb))

    # --- spine between blade and grip (behind the gem)
    m.merge(loft(stations(-2.8, 0.0, 6), lambda a: 0.36, lambda a: 0.3, 10, R["N_DARK"], UVC))

    # --- tendrils: dark navy filigree with glowing edges
    def tendril(path, r0=0.16, r1=0.03):
        path = np.asarray(path, float)
        return tube(path, taper(len(path), r0, r1, 1.1, 0.08), 5, R["N_TENDRIL"], UVC)

    t1 = chain(bezier([(0.4, -1.75, 0.15), (2.0, -1.3, 0.2), (3.6, -1.15, 0.15), (4.9, -1.75, 0.1)], 12),
               spiral_path((4.75, -2.45), 0.7, 0.12, math.radians(80), 1.2, 16, c=0.1, sign=1))
    t2 = chain(bezier([(0.2, 1.85, 0.12), (1.6, 2.6, 0.18), (3.0, 2.6, 0.1), (3.7, 1.95, 0.1)], 10),
               spiral_path((3.25, 1.6), 0.5, 0.1, math.radians(30), 1.1, 12, c=0.1, sign=-1))
    t3 = chain(bezier([(-2.6, -1.3, -0.1), (-2.7, -2.4, -0.15), (-2.0, -3.3, -0.1), (-1.1, -3.25, -0.1)], 10),
               spiral_path((-1.35, -2.7), 0.6, 0.1, math.radians(60), 1.15, 14, c=-0.1, sign=-1))
    t4 = chain(bezier([(-2.5, 1.2, -0.12), (-2.0, 2.4, -0.15), (-0.9, 3.4, -0.1), (0.1, 3.1, -0.1)], 12),
               spiral_path((-0.45, 2.75), 0.55, 0.1, math.radians(20), 1.2, 14, c=-0.1, sign=1))
    for p in (t1, t2, t3, t4):
        m.merge(tendril(p))
    t5 = helix(-3.0, -10.1, 0.58, 1.4, 30, phase=2.2)
    m.merge(tube(t5, taper(30, 0.14, 0.08, 1, 0.05), 5, R["N_TENDRIL"], UVC))
    t6 = bezier([(-3.0, 0.45, 0.2), (-4.6, 2.5, 0.3), (-7.8, 2.9, 0.05), (-9.6, 1.2, -0.1), (-10.4, 0.4, 0)], 26)
    m.merge(tendril(t6, 0.14, 0.06))
    t7 = chain(bezier([(-6.0, -0.5, -0.2), (-6.6, -1.6, -0.2), (-7.8, -2.0, -0.1)], 8),
               spiral_path((-7.75, -1.4), 0.55, 0.1, math.radians(250), 1.1, 12, c=-0.1, sign=-1))
    m.merge(tendril(t7, 0.13, 0.03))

    # --- grip (black wrap) + silver collars
    m.merge(loft(stations(-10.8, -2.7, 16), lambda a: 0.4 + 0.04 * math.sin(math.pi * (a + 10.8) / 8.1),
                 lambda a: 0.4 + 0.04 * math.sin(math.pi * (a + 10.8) / 8.1), 12, R["N_GRIP"], UVC))
    for a0 in (-2.85, -10.65):
        m.merge(torus((a0, 0, 0), (0, 1.0, 0), (0, 0, 1.0), 0.47, 0.11, 14, 6, R["SILVER"], UVC))

    # --- pommel: silver ring + orb
    m.merge(loft(stations(-11.2, -10.8, 3), lambda a: 0.3, lambda a: 0.3, 10, R["N_DARK"], UVC))
    m.merge(torus((-11.75, 0, 0), (1.0, 0, 0), (0, 1.0, 0), 0.5, 0.1, 22, 6, R["SILVER"], UVC))
    m.merge(ellipsoid((-11.75, 0, 0), (0.24, 0.24, 0.24), 10, 6, R["N_GLOW"], UVC))
    m.merge(ellipsoid((-12.45, 0, 0), (0.2, 0.2, 0.2), 10, 6, R["SILVER"], UVC))
    return m


# ==================================================================== ATLAS

def _uv_grid(region, scale=1):
    x0, y0, x1, y1 = region
    w, h = (x1 - x0) * scale, (y1 - y0) * scale
    u = (np.arange(w) + 0.5) / w
    v = (np.arange(h) + 0.5) / h
    U, V = np.meshgrid(u, v)
    return U, V


def _put(atlas, region, rgb, glow):
    x0, y0, x1, y1 = region
    atlas[y0:y1, x0:x1, :3] = np.clip(rgb, 0, 1)
    atlas[y0:y1, x0:x1, 3] = np.clip(1 - glow, 0, 1)


def _star(U, V, cu, cv, size, aspect=1.0):
    du, dv = (U - cu) / size * aspect, (V - cv) / size
    r = np.abs(du) ** 0.6 + np.abs(dv) ** 0.6
    return np.clip(1.25 - r * 1.4, 0, 1)


def paint_atlas():
    atlas = np.zeros((ATLAS, ATLAS, 4))
    atlas[..., 3] = 1.0

    # SOLARIS blade - white-gold glow; v: edge(0) -> ridge(1)
    U, V = _uv_grid(R["S_BLADE"])
    warm = np.clip(1 - U * 2.2, 0, 1)
    edge = np.exp(-(V / 0.18) ** 2)
    ridge = np.exp(-((1 - V) / 0.12) ** 2)
    rgb = np.stack([np.ones_like(U), 0.93 - 0.18 * warm + 0.04 * ridge, 0.78 - 0.45 * warm + 0.18 * ridge], -1)
    rgb = rgb * (0.92 + 0.08 * ridge[..., None]) + edge[..., None] * np.array([0.0, 0.03, 0.12])
    sparks = np.zeros_like(U)
    for k, cu in enumerate(np.arange(0.36, 0.95, 0.11)):
        sparks = np.maximum(sparks, _star(U, V, cu, 0.85, 0.035, aspect=0.28))
    rgb = rgb * (1 - sparks[..., None]) + sparks[..., None]
    glow = np.clip(0.78 + 0.22 * edge + 0.2 * ridge + sparks, 0, 1)
    _put(atlas, R["S_BLADE"], rgb, glow)

    # SOLARIS ornament plate - gold with glowing star cut-outs (u along, v around)
    U, V = _uv_grid(R["S_PLATE"])
    face = np.abs(np.sin(V * 2 * math.pi))
    band = 0.55 + 0.45 * np.cos((V * 4) * math.pi) ** 2
    gold = np.stack([0.95 * band + 0.05, 0.70 * band + 0.05, 0.28 * band], -1)
    stars = np.zeros_like(U)
    for cu, sz in [(0.16, 0.07), (0.30, 0.05), (0.47, 0.06), (0.68, 0.045)]:
        for cv in (0.25, 0.75):
            stars = np.maximum(stars, _star(U, V, cu, cv, sz, aspect=0.5))
    lines = np.exp(-((np.abs(V - 0.25) - 0.18) / 0.02) ** 2) + np.exp(-((np.abs(V - 0.75) - 0.18) / 0.02) ** 2)
    gold = gold * (1 - 0.35 * np.clip(lines, 0, 1)[..., None])
    rgb = gold * (1 - stars[..., None]) + stars[..., None] * np.array([1.0, 0.98, 0.88])
    glow = np.clip(0.22 + stars * 0.9 + 0.1 * face, 0, 1)
    _put(atlas, R["S_PLATE"], rgb, glow)

    # polished gold / glowing gold
    U, V = _uv_grid(R["GOLD"])
    band = 0.5 + 0.5 * np.cos(V * 2 * math.pi) ** 2
    rgb = np.stack([0.98 * (0.55 + 0.45 * band), 0.74 * (0.5 + 0.5 * band), 0.30 * (0.4 + 0.6 * band)], -1)
    _put(atlas, R["GOLD"], rgb, 0.25 + 0.1 * band)
    U, V = _uv_grid(R["GOLD_GLOW"])
    rgb = np.stack([np.ones_like(U), 0.86 + 0.1 * np.cos(V * 2 * math.pi) ** 2, 0.52 + 0.3 * np.cos(V * 2 * math.pi) ** 2], -1)
    _put(atlas, R["GOLD_GLOW"], rgb, np.full_like(U, 0.85))

    # gold lattice grip (u along length, v around)
    U, V = _uv_grid(R["S_GRIP"])
    du = (U * 9) % 1 - 0.5
    dv = (V * 6) % 1 - 0.5
    diamond = np.abs(du) / 0.5 + np.abs(dv) / 0.5
    groove = np.exp(-((diamond - 1.0) / 0.12) ** 2)
    stud = np.clip(1 - diamond / 0.25, 0, 1)
    base = np.stack([0.85 - 0.25 * diamond * 0.4, 0.6 - 0.2 * diamond * 0.4, 0.22 + 0.0 * U], -1)
    rgb = base * (1 - 0.6 * groove[..., None]) + stud[..., None] * np.array([0.25, 0.25, 0.2])
    _put(atlas, R["S_GRIP"], rgb, 0.18 + 0.6 * stud)

    # flame ribbon (u along length, v around the flat tube)
    U, V = _uv_grid(R["S_RIBBON"])
    core = np.cos((V - 0.5) * math.pi) ** 2
    rgb = np.stack([np.ones_like(U), 0.55 + 0.25 * core - 0.2 * U, 0.18 + 0.12 * core - 0.1 * U], -1)
    _put(atlas, R["S_RIBBON"], rgb, 0.55 + 0.3 * core)

    # sun ray (u base -> tip, v across)
    U, V = _uv_grid(R["S_RAY"])
    mid = np.exp(-((V - 0.5) / 0.22) ** 2)
    rgb = np.stack([np.ones_like(U), 0.78 - 0.25 * U + 0.12 * mid, 0.36 - 0.25 * U + 0.2 * mid], -1)
    _put(atlas, R["S_RAY"], rgb, 0.55 + 0.35 * mid)

    # white core
    U, V = _uv_grid(R["S_CORE"])
    _put(atlas, R["S_CORE"], np.stack([np.ones_like(U), np.ones_like(U) * 0.97, 0.86 + 0 * U], -1), np.ones_like(U))

    # silver (with a cool blue reflection band)
    U, V = _uv_grid(R["SILVER"])
    band = np.cos(V * 2 * math.pi) ** 2
    rgb = np.stack([0.62 + 0.33 * band, 0.66 + 0.30 * band, 0.78 + 0.2 * band], -1)
    _put(atlas, R["SILVER"], rgb, 0.12 + 0.1 * band)

    # NOCTIS blade - dark steel, bright bevel and ridge, faint blue sheen
    U, V = _uv_grid(R["N_BLADE"])
    edge = np.exp(-(V / 0.14) ** 2)
    ridge = np.exp(-((1 - V) / 0.1) ** 2)
    sheen = np.exp(-((V - 0.55 - 0.15 * np.sin(U * 9)) / 0.08) ** 2) * 0.35
    base = 0.17 + 0.06 * (1 - U)
    rgb = np.stack([base + 0.42 * edge + 0.44 * ridge + 0.05 * sheen,
                    base + 0.44 * edge + 0.46 * ridge + 0.10 * sheen,
                    base + 0.06 + 0.48 * edge + 0.5 * ridge + 0.3 * sheen], -1)
    _put(atlas, R["N_BLADE"], rgb, 0.04 + 0.12 * edge + sheen * 0.2)

    # blue gem with a star (u around, v pole->pole)
    U, V = _uv_grid(R["N_GEM"])
    lat = np.sin(V * math.pi)
    front = np.maximum(np.cos((U - 0.25) * 2 * math.pi), np.cos((U - 0.75) * 2 * math.pi))
    face = np.clip(front, 0, 1) * lat
    star = np.zeros_like(U)
    for cu in (0.25, 0.75):
        star = np.maximum(star, _star(U, V, cu, 0.5, 0.16, aspect=1.0))
    rgb = np.stack([0.06 + 0.3 * face ** 3, 0.12 + 0.4 * face ** 2, 0.55 + 0.45 * face], -1)
    rgb = rgb * (1 - star[..., None]) + star[..., None] * np.array([0.85, 0.92, 1.0])
    _put(atlas, R["N_GEM"], rgb, np.clip(0.7 + 0.3 * star, 0, 1))

    # black wrap grip with diagonal binding
    U, V = _uv_grid(R["N_GRIP"])
    diag = ((U * 10 + V * 2) % 1)
    wrap = np.exp(-((diag - 0.5) / 0.22) ** 2)
    rgb = np.stack([0.05 + 0.1 * wrap, 0.05 + 0.1 * wrap, 0.08 + 0.15 * wrap], -1)
    _put(atlas, R["N_GRIP"], rgb, 0.0 * U)

    # navy tendril with a glowing blue line
    U, V = _uv_grid(R["N_TENDRIL"])
    line = np.exp(-((V - 0.25) / 0.1) ** 2) + np.exp(-((V - 0.75) / 0.06) ** 2) * 0.5
    rgb = np.stack([0.10 + 0.25 * line, 0.14 + 0.4 * line, 0.42 + 0.55 * line], -1)
    _put(atlas, R["N_TENDRIL"], rgb, 0.18 + 0.7 * line)

    # dark metal / blue glow
    U, V = _uv_grid(R["N_DARK"])
    band = np.cos(V * 2 * math.pi) ** 2
    _put(atlas, R["N_DARK"], np.stack([0.12 + 0.16 * band, 0.12 + 0.16 * band, 0.18 + 0.2 * band], -1), 0.05 * band)
    U, V = _uv_grid(R["N_GLOW"])
    _put(atlas, R["N_GLOW"], np.stack([0.45 + 0 * U, 0.65 + 0 * U, 1.0 + 0 * U], -1), np.ones_like(U))

    # mirror the content into the bottom half (UV orientation proof)
    atlas[ATLAS // 2:] = atlas[:ATLAS // 2][::-1]
    return atlas


# ====================================================================== RIG

TILT = math.radians(20)                     # blade points forward-up at rest
D = np.array([0.0, math.sin(TILT), -math.cos(TILT)])   # local a  (-Z is the player's front)
UP = np.array([0.0, math.cos(TILT), math.sin(TILT)])   # local b
CX = np.array([1.0, 0.0, 0.0])                          # local c
GRIP_R = np.array([-6.0, 15.0, 1.0])        # rightItem pivot = centre of the right fist
GRIP_L = np.array([6.0, 15.0, 1.0])         # leftItem pivot
PLAYER = {"root": ([0, 0, 0], None), "waist": ([0, 12, 0], "root"), "body": ([0, 24, 0], "waist"),
          "rightArm": ([-5, 22, 0], "body"), "leftArm": ([5, 22, 0], "body")}

SWORD_INFO = {
    "solaris": {"grip": -4.6},
    "noctis": {"grip": -4.7},
}

FP_PIVOT = [0, 24, 0]                        # vanilla trident frame (first person)
FP_BOTTOM, FP_TOP = -3.0, 28.0


def third_person(mesh, grip_a, hand):
    g = GRIP_R if hand == "right" else GRIP_L
    basis = np.stack([D, UP, CX])           # rows: a, b, c

    def pos(P):
        P = P.copy()
        P[:, 0] -= grip_a
        return g + P @ basis

    return mesh.transformed(pos, lambda N: N @ basis)


def first_person(mesh):
    P, _, _, _ = mesh.arrays()
    a0, a1 = P[:, 0].min(), P[:, 0].max()
    s = (FP_TOP - FP_BOTTOM) / (a1 - a0)

    def pos(Q):
        return np.stack([Q[:, 1] * s, FP_BOTTOM + (Q[:, 0] - a0) * s, Q[:, 2] * s], 1)

    return mesh.transformed(pos, lambda N: np.stack([N[:, 1], N[:, 0], N[:, 2]], 1))


def poly_mesh(mesh):
    P, N, UV, Q = mesh.arrays()
    return {
        "normalized_uvs": True,
        "positions": np.round(P, 4).tolist(),
        "normals": np.round(N, 3).tolist(),
        "uvs": np.round(UV, 5).tolist(),
        "polys": [[[int(i), int(i), int(i)] for i in q] for q in Q],
    }


def _skeleton(names):
    out = []
    for n in names:
        pivot, parent = PLAYER[n]
        b = {"name": n, "pivot": pivot}
        if parent:
            b["parent"] = parent
        out.append(b)
    return out


def geometry_main(ident, self_mesh, self_grip, twin_mesh, twin_grip):
    bones = _skeleton(["root", "waist", "body", "rightArm", "leftArm"])
    bones.append({"name": "blade_r", "parent": "rightArm", "pivot": GRIP_R.tolist(),
                  "poly_mesh": poly_mesh(third_person(self_mesh, self_grip, "right"))})
    bones.append({"name": "twin_l", "parent": "leftArm", "pivot": GRIP_L.tolist(),
                  "poly_mesh": poly_mesh(third_person(twin_mesh, twin_grip, "left"))})
    bones.append({"name": "blade_fp", "binding": "q.item_slot_to_bone_name(c.item_slot)", "pivot": FP_PIVOT,
                  "poly_mesh": poly_mesh(first_person(self_mesh))})
    return _geo(ident, bones)


def geometry_offhand(ident, self_mesh, self_grip):
    bones = _skeleton(["root", "waist", "body", "leftArm"])
    bones.append({"name": "blade_l", "parent": "leftArm", "pivot": GRIP_L.tolist(),
                  "poly_mesh": poly_mesh(third_person(self_mesh, self_grip, "left"))})
    return _geo(ident, bones)


def _geo(ident, bones):
    return {
        "format_version": "1.16.0",
        "minecraft:geometry": [{
            "description": {
                "identifier": ident, "texture_width": ATLAS, "texture_height": ATLAS,
                "visible_bounds_width": 8, "visible_bounds_height": 6, "visible_bounds_offset": [0, 1.5, 0],
            },
            "bones": bones,
        }],
    }


def icon(mesh, atlas, size=64, roll=-45.0):
    """Diagonal item icon rendered from the real model."""
    from PIL import Image
    from mesh import render, rot_z

    front = mesh.transformed(lambda P: np.stack([P[:, 1], P[:, 0], P[:, 2]], 1),
                             lambda N: np.stack([N[:, 1], N[:, 0], N[:, 2]], 1))
    img, mask = render([(front, atlas, True)], rot_z(roll), size=(512, 512), bg=(0, 0, 0), light=(0.3, 0.6, 0.9))
    rgba = np.dstack([img, (np.clip(mask, 0, 1) * 255).astype(np.uint8)])
    im = Image.fromarray(rgba, "RGBA")
    bbox = im.getbbox()
    im = im.crop(bbox)
    side = max(im.size)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2))
    return sq.resize((size, size), Image.LANCZOS)
