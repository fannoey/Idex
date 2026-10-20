#!/usr/bin/env python3
"""Generate the black grim-reaper scythe as a Blockbench project (.bbmodel).

The silhouette is traced from the reference image (476x648 px). Every point in
this file is given in *reference-image pixels* (x right, y down) and converted
to Blockbench units by img(): X = (x - CX) * S, Y = (Y0 - y) * S, so the
Blockbench "South" (front) orthographic view matches the reference picture.

Project type: Generic Model ("free"), saved as bbmodel format 4.10 (nested
outliner) which opens in Blockbench 4.10+ and 5.x. Blade, frame, horns, shaft
and pendant are Custom Meshes; chain links are separate small mesh tori.

Run:  python3 tools/build_scythe.py
"""
import base64
import io
import json
import math
import os
import uuid

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "Output")
TEX_REL = "textures/scythe_texture.png"

S = 0.12          # Blockbench units per reference pixel (total height ~71 units)
CX, Y0 = 236, 616  # reference pixel that maps to X=0 / Y=0 (bottom spike tip)
TEX = 128         # texture size in pixels (= UV size)

# Deterministic UUIDs so rebuilding does not churn the file.
_NS = uuid.UUID("6d1f3b9e-2a4c-4f7e-9b1d-5c3a7e8f0a12")
_counter = [0]


def uid(name):
    _counter[0] += 1
    return str(uuid.uuid5(_NS, f"{name}:{_counter[0]}"))


def img(x, y, z=0.0):
    """Reference pixel -> Blockbench units (z already in pixels)."""
    return np.array([(x - CX) * S, (Y0 - y) * S, z * S])


# --------------------------------------------------------------------------
# Texture atlas (128x128). Regions in pixels: (u0, v0, u1, v1)
# --------------------------------------------------------------------------
R_BLADE = (0, 0, 96, 64)     # u = along blade, v = edge(top)->spine(bottom)
R_BLACK = (96, 0, 128, 32)   # black lacquered metal (frame, horns, shaft)
R_SILVER = (96, 32, 128, 64)  # polished silver (chain, pendant)
R_DARKSIL = (0, 64, 32, 96)  # dark gunmetal (ferrules / bands)
R_GEM = (32, 64, 64, 96)     # pale white bead under the head


def make_texture():
    t = np.zeros((TEX, TEX, 4), np.float32)
    rng = np.random.default_rng(7)

    # Blade: black spine band, glossy pale reflection on the lower half near
    # the base (like the reference), sharp lighter cutting edge line.
    u0, v0, u1, v1 = R_BLADE
    for py in range(v0, v1):
        f = (py - v0 + 0.5) / (v1 - v0)            # 0 = edge (top row), 1 = spine
        for px in range(u0, u1):
            s = (px - u0 + 0.5) / (u1 - u0)          # 0 = base, 1 = tip
            c = 0.05 + 0.03 * f
            # glossy pale reflection on the wide lower half near the root
            hl = min(1.0, max(0.0, 1 - (s - 0.13) / 0.19) ** 1.2) * \
                min(1.0, max(0.0, 1 - (f - 0.18) / 0.42) ** 1.1)
            hl *= min(1.0, max(0.0, (s - 0.035) / 0.05))   # root stays black (frame lobes)
            c = c + (0.93 - c) * hl
            # faint grey sheen along the whole edge side and below the spine
            c += 0.10 * max(0.0, 1 - f / 0.45) * (1 - hl)
            c += math.exp(-((f - 0.78) / 0.06) ** 2) * 0.08 * (1 - s)
            if f < 0.05:
                c = max(c, 0.40 - 0.18 * s)
            c += rng.normal(0, 0.006)
            t[py, px] = [c, c, c * 1.04 + 0.01, 1]

    def fill(region, base, var, grad=0.0, tint=(1, 1, 1)):
        u0, v0, u1, v1 = region
        for py in range(v0, v1):
            g = (py - v0) / (v1 - v0 - 1)
            for px in range(u0, u1):
                c = base + grad * (0.5 - abs(g - 0.5)) * 2 + rng.normal(0, var)
                t[py, px] = [c * tint[0], c * tint[1], c * tint[2], 1]

    fill(R_BLACK, 0.075, 0.01, grad=0.05)
    fill(R_SILVER, 0.62, 0.03, grad=0.30, tint=(0.97, 0.98, 1.0))
    fill(R_DARKSIL, 0.30, 0.02, grad=0.18, tint=(0.95, 0.97, 1.0))
    fill(R_GEM, 0.86, 0.02, grad=0.12, tint=(0.96, 0.98, 1.0))
    t = np.clip(t, 0, 1)
    return Image.fromarray((t * 255).round().astype(np.uint8), "RGBA")


def ruv(region, s, v, pad=0.5):
    """Map normalised (s, v) in [0,1] into a texture region (pixel UVs)."""
    u0, v0, u1, v1 = region
    return [round(u0 + pad + (u1 - u0 - 2 * pad) * min(max(s, 0), 1), 4),
            round(v0 + pad + (v1 - v0 - 2 * pad) * min(max(v, 0), 1), 4)]


# --------------------------------------------------------------------------
# Mesh builder
# --------------------------------------------------------------------------
class Mesh:
    def __init__(self, name, origin):
        self.name = name
        self.origin = np.asarray(origin, float)
        self.verts = []      # absolute positions
        self.faces = []      # (vertex indices, uv list)

    def v(self, p):
        self.verts.append(np.asarray(p, float))
        return len(self.verts) - 1

    def face(self, idx, uvs):
        # drop degenerate repeats (quad collapsing to triangle)
        out_i, out_uv = [], []
        for i, u in zip(idx, uvs):
            if i not in out_i:
                out_i.append(i)
                out_uv.append(u)
        if len(out_i) >= 3:
            self.faces.append((out_i, out_uv))

    def element(self):
        keys = [f"v{i}" for i in range(len(self.verts))]
        verts = {k: [round(float(c), 4) for c in (p - self.origin)]
                 for k, p in zip(keys, self.verts)}
        faces = {}
        for n, (idx, uvs) in enumerate(self.faces):
            faces[f"f{n}"] = {
                "uv": {keys[i]: u for i, u in zip(idx, uvs)},
                "vertices": [keys[i] for i in idx],
                "texture": 0,
            }
        return {
            "name": self.name,
            "color": 0,
            "origin": [round(float(c), 4) for c in self.origin],
            "rotation": [0, 0, 0],
            "export": True,
            "visibility": True,
            "locked": False,
            "render_order": "default",
            "allow_mirror_modeling": True,
            "vertices": verts,
            "faces": faces,
            "type": "mesh",
            "uuid": uid(self.name),
        }


def grid(m, rows, region, s_list, v_list, closed=False, flip=False):
    """Connect a 2D array of vertex indices rows[i][j] with quads.

    i runs along the part, j around/across it. UVs come from s_list[i] and
    v_list[j]. flip reverses winding so normals face outward.
    """
    ni, nj = len(rows), len(rows[0])
    jmax = nj if closed else nj - 1
    for i in range(ni - 1):
        for j in range(jmax):
            j2 = (j + 1) % nj
            vj2 = v_list[j + 1] if j + 1 < len(v_list) else 1.0
            q = [rows[i][j], rows[i + 1][j], rows[i + 1][j2], rows[i][j2]]
            uv = [ruv(region, s_list[i], v_list[j]), ruv(region, s_list[i + 1], v_list[j]),
                  ruv(region, s_list[i + 1], vj2), ruv(region, s_list[i], vj2)]
            if flip:
                q, uv = q[::-1], uv[::-1]
            m.face(q, uv)


def resample(points, n):
    """Resample a polyline (image px) to n points evenly spaced by arc length."""
    p = np.asarray(points, float)
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    d = np.concatenate([[0], np.cumsum(seg)])
    t = np.linspace(0, d[-1], n)
    return np.stack([np.interp(t, d, p[:, k]) for k in range(p.shape[1])], 1)


def smooth_curve(points, n):
    """Catmull-Rom through points, then resample evenly."""
    p = np.asarray(points, float)
    ext = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for t in np.linspace(0, 1, 12, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(p[-1])
    return resample(out, n)


# --------------------------------------------------------------------------
# A. Main blade
# --------------------------------------------------------------------------
BLADE_SPINE = [(262, 41), (240, 45), (221, 50), (205, 54), (190, 60), (170, 70), (148, 80),
               (133, 90), (119, 100), (107, 110), (96, 120), (87, 130), (79, 140), (72, 150),
               (65, 160), (59, 170), (53, 180), (48, 190), (43, 200), (39, 210), (36, 220),
               (33, 230), (30, 240), (28, 250), (26, 262)]
# inner (cutting) edge, base -> tip: wide pale base under the frame, then the
# long narrowing curve down to the needle tip
BLADE_EDGE = [(254, 104), (244, 101), (234, 106), (222, 111), (205, 112), (188, 111),
              (172, 108), (158, 104), (146, 100), (130, 110), (116, 120), (104, 130),
              (93, 140), (83, 150), (74, 160), (66, 170), (59, 180), (52, 190), (47, 200),
              (42, 210), (38, 220), (34, 230), (31, 240), (28, 251), (26, 262)]


def build_blade():
    n = 44
    spine = smooth_curve(BLADE_SPINE, n)
    edge = smooth_curve(BLADE_EDGE, n)
    fs = [0.0, 0.08, 0.2, 0.36, 0.55, 0.75, 0.9, 1.0]   # edge -> spine

    def half_thick(f, s):
        base = 5.0 * (1 - s) ** 0.9 + 0.5              # px at the spine
        if f >= 0.9:
            k = 1.0 - 0.15 * (f - 0.9) / 0.1
        else:
            k = 0.06 + 0.94 * (1 - (1 - f / 0.9) ** 2)
        return base * k

    m = Mesh("blade_mesh", img(240, 60))
    front, back = [], []
    s_list = []
    for i in range(n):
        s = i / (n - 1)
        s_list.append(s)
        fr, bk = [], []
        for f in fs:
            p = edge[i] + f * (spine[i] - edge[i])
            if i == n - 1 or f == 0.0:
                vi = m.v(img(p[0], p[1], 0))
                fr.append(vi)
                bk.append(vi)
            else:
                h = half_thick(f, s)
                fr.append(m.v(img(p[0], p[1], h)))
                bk.append(m.v(img(p[0], p[1], -h)))
        front.append(fr)
        back.append(bk)
    v_list = fs
    grid(m, front, R_BLADE, s_list, v_list)
    grid(m, back, R_BLADE, s_list, v_list, flip=True)
    # spine strip (front f=1 -> back f=1)
    for i in range(n - 1):
        q = [front[i][-1], back[i][-1], back[i + 1][-1], front[i + 1][-1]]
        m.face(q, [ruv(R_BLADE, s_list[i], 1), ruv(R_BLADE, s_list[i], 1),
                   ruv(R_BLADE, s_list[i + 1], 1), ruv(R_BLADE, s_list[i + 1], 1)])
    # base cap (hidden inside the frame, closes the solid)
    for j in range(len(fs) - 1):
        q = [front[0][j], front[0][j + 1], back[0][j + 1], back[0][j]]
        m.face(q, [ruv(R_BLADE, 0, fs[j])] * 2 + [ruv(R_BLADE, 0, fs[j + 1])] * 2)
    return [m]


# --------------------------------------------------------------------------
# Generic loft: tube along an image-space curve with superellipse sections
# --------------------------------------------------------------------------
def loft(name, center, rx, rz, region, ring=10, n_exp=2.0, cap0=True, cap1=True,
         z_off=0.0, origin=None, rx_list=None, rz_list=None):
    """center: (N,2) image points; rx/rz: callables of s in [0,1] (pixels),
    rx is the in-plane half width, rz the depth half width."""
    c = np.asarray(center, float)
    nseg = len(c)
    m = Mesh(name, origin if origin is not None else img(*c[nseg // 2]))
    rows, s_list = [], []
    for i in range(nseg):
        s = i / (nseg - 1)
        s_list.append(s)
        a = c[min(i + 1, nseg - 1)] - c[max(i - 1, 0)]
        a = a / (np.linalg.norm(a) + 1e-9)
        nrm = np.array([-a[1], a[0]])              # in-plane normal
        hx = rx_list[i] if rx_list is not None else rx(s)
        hz = rz_list[i] if rz_list is not None else rz(s)
        row = []
        if hx < 1e-4 and hz < 1e-4:
            vi = m.v(img(c[i][0], c[i][1], z_off))
            row = [vi] * ring
        else:
            for k in range(ring):
                ph = 2 * math.pi * k / ring
                cs, sn = math.cos(ph), math.sin(ph)
                ex = math.copysign(abs(cs) ** (2 / n_exp), cs)
                ez = math.copysign(abs(sn) ** (2 / n_exp), sn)
                p = c[i] + nrm * hx * ex
                row.append(m.v(img(p[0], p[1], z_off + hz * ez)))
        rows.append(row)
    v_list = [k / ring for k in range(ring + 1)]
    # winding: decide using the first real segment so faces point outward
    grid(m, rows, region, s_list, v_list, closed=True, flip=_needs_flip(m, rows))
    for end, do in ((0, cap0), (nseg - 1, cap1)):
        r = rows[end]
        if not do or len(set(r)) == 1:
            continue
        ctr = m.v(np.mean([m.verts[k] for k in r], axis=0))
        for k in range(ring):
            tri = [r[k], r[(k + 1) % ring], ctr]
            if (end == 0) != _needs_flip(m, rows):
                tri = tri[::-1]
            m.face(tri, [ruv(region, s_list[end], 0.5)] * 3)
    return m


def _needs_flip(m, rows):
    for i in range(len(rows) - 1):
        a, b = rows[i], rows[i + 1]
        if len(set(a)) > 1 and len(set(b)) > 1:
            p00, p10, p11 = m.verts[a[0]], m.verts[b[0]], m.verts[b[1]]
            nrm = np.cross(p10 - p00, p11 - p00)
            ctr = np.mean([m.verts[k] for k in a], axis=0)
            return float(np.dot(nrm, p00 - ctr)) < 0
    return False


# --------------------------------------------------------------------------
# B. Upper frame and horns
# --------------------------------------------------------------------------
def build_frame():
    parts = []
    # socket rising from the neck to the crown; widest where the blade root
    # is clamped (y 60-95), narrow neck below it
    ctrl = [(258, 152), (258, 140), (258, 128), (259, 116), (260, 104), (261, 94),
            (261, 84), (262, 74), (263, 62), (265, 50), (268, 38)]
    hw_ctrl = [4.2, 4.2, 4.6, 4.4, 4.6, 6.5, 7.5, 7.5, 7.0, 6.0, 5.0]
    n = 24
    spine = smooth_curve(ctrl, n)
    hw = np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(ctrl)), hw_ctrl).tolist()
    hz = [3.6 if i < 9 else 3.2 for i in range(n)]
    parts.append(loft("frame_socket", spine, None, None, R_BLACK, ring=12, n_exp=2.6,
                      rx_list=hw, rz_list=hz, origin=img(261, 100)))
    # core rod running through the neck bands, bead and ferrule
    parts.append(loft("neck_core", smooth_curve([(258, 140), (258, 152), (259, 164),
                                                (261, 174), (265, 186)], 10),
                      lambda s: 3.3, lambda s: 3.3, R_BLACK, ring=10))
    # ridge plates where the blade enters the frame (thicker block, flat faces)
    parts.append(loft("frame_blade_clamp", smooth_curve([(246, 72), (254, 64), (262, 58)], 6),
                      lambda s: 6.5 - 1.5 * s, lambda s: 4.2, R_BLACK, ring=10, n_exp=3.2))
    return parts


def horn(name, pts, r0, z0=2.6, n=14, curl=1.0):
    c = smooth_curve(pts, n)
    return loft(name, c, lambda s: r0 * (1 - s) ** curl, lambda s: z0 * (1 - s) ** curl,
                R_BLACK, ring=8, n_exp=2.0, cap1=False, origin=img(*pts[0]))


def build_horns():
    return [
        # big crescent horn sweeping right off the top of the head
        horn("horn_top_main", [(263, 37), (276, 31), (290, 27), (304, 26), (316, 27), (327, 31)],
             6.0, z0=2.8, n=18, curl=0.9),
        # smaller spike pointing back-left at the top
        horn("horn_top_left", [(262, 36), (254, 34), (247, 32), (240, 31)], 3.4, z0=2.2),
        # two small points at the base of the main horn
        horn("horn_small_upper", [(269, 34), (266, 30), (263, 26)], 2.2, z0=1.6, n=6),
        horn("horn_small_back", [(264, 36), (261, 33), (257, 30)], 2.0, z0=1.5, n=6),
        # thorns on the right side of the frame
        horn("thorn_right_upper", [(266, 70), (271, 69), (277, 67)], 2.6, z0=1.8, n=8),
        horn("thorn_right_mid", [(266, 88), (273, 88), (283, 86)], 3.2, z0=2.0, n=10),
        horn("thorn_right_lower", [(264, 100), (270, 102), (277, 103)], 2.4, z0=1.6, n=8),
        # lobe spike hanging from the blade root
        horn("root_lobe_spike", [(254, 92), (248, 97), (241, 102), (235, 105)], 3.0, z0=2.6, n=8),
        # barb under the blade root pointing left
        horn("barb_lower_left", [(254, 108), (244, 110), (234, 111), (223, 112)], 3.4, z0=2.0, n=12),
    ]


# --------------------------------------------------------------------------
# C. Shaft, connectors
# --------------------------------------------------------------------------
SHAFT_LINE = [(261, 172), (265, 186), (271, 200), (291.5, 250), (312.5, 300), (333.5, 350),
              (354.5, 400), (375, 450), (395.5, 500), (412, 540), (426, 572), (435, 590),
              (446, 616)]


def shaft_point(y):
    p = np.asarray(SHAFT_LINE, float)
    return np.array([np.interp(y, p[:, 1], p[:, 0]), y])


def shaft_segment(name, y0, y1, r0, r1, region, n=8, ring=10, caps=(True, True), n_exp=2.0):
    ys = np.linspace(y0, y1, n)
    c = [shaft_point(y) for y in ys]
    return loft(name, c, lambda s: r0 + (r1 - r0) * s, lambda s: r0 + (r1 - r0) * s,
                region, ring=ring, n_exp=n_exp, cap0=caps[0], cap1=caps[1],
                origin=img(*shaft_point((y0 + y1) / 2)))


def build_shaft():
    return [
        shaft_segment("shaft_upper", 200, 360, 3.7, 3.8, R_BLACK, n=10, caps=(True, False)),
        shaft_segment("shaft_lower", 360, 523, 3.8, 3.9, R_BLACK, n=10, caps=(False, True)),
        shaft_segment("shaft_butt", 529, 557, 3.8, 4.0, R_BLACK, n=4),
        shaft_segment("shaft_butt_end", 563, 588, 4.0, 4.3, R_BLACK, n=4),
        # tapered spear point at the bottom of the shaft
        shaft_segment("shaft_spike", 588, 616, 4.3, 0.0, R_BLACK, n=8, caps=(True, False)),
    ]


def build_connectors():
    parts = []
    # binding bands at the neck of the head (chain is wrapped over these)
    parts.append(loft("neck_band_upper", smooth_curve([(258, 140), (258, 146)], 3),
                      lambda s: 5.2, lambda s: 5.0, R_DARKSIL, ring=12))
    parts.append(loft("neck_band_lower", smooth_curve([(258, 151), (258.5, 157)], 3),
                      lambda s: 5.0, lambda s: 4.8, R_DARKSIL, ring=12))
    # flared black ferrule between the bead and the shaft
    parts.append(loft("neck_ferrule", smooth_curve([(261, 172), (264, 182), (268, 192),
                                                   (271, 202)], 8),
                      lambda s: 5.4 - 1.7 * s ** 0.8, lambda s: 5.0 - 1.4 * s ** 0.8,
                      R_BLACK, ring=12))
    # pale bead between the bands and the ferrule
    bead = smooth_curve([(259, 158), (259.5, 165), (260.5, 172)], 9)
    parts.append(loft("neck_bead", bead,
                      lambda s: 0.6 + 4.6 * math.sin(math.pi * s) ** 0.6,
                      lambda s: 0.6 + 4.6 * math.sin(math.pi * s) ** 0.6,
                      R_GEM, ring=12))
    # rings on the butt of the shaft
    for i, y in enumerate((524, 558)):
        parts.append(shaft_segment(f"butt_ring_{i + 1}", y - 1, y + 5, 4.6, 4.6, R_DARKSIL, n=3,
                                   ring=12))
    return parts


# --------------------------------------------------------------------------
# D. Chains
# --------------------------------------------------------------------------
LINK_L, LINK_W, WIRE = 7.4, 4.4, 0.95     # pixels (outer length, outer width, wire radius)


def chain_link(name, center, axis, side, ring=10, tube=4):
    """Oval torus. axis = unit long direction (3D, image-px space with y down),
    side = unit direction of the link's width."""
    m = Mesh(name, img(*center[:2], center[2]))
    a = np.asarray(axis, float)
    b = np.asarray(side, float)
    nrm = np.cross(a, b)
    hl, hw = LINK_L / 2 - WIRE, LINK_W / 2 - WIRE
    rows = []
    for k in range(ring):
        t = 2 * math.pi * k / ring
        # stadium-ish oval: superellipse in the link plane
        ca, sb = math.cos(t), math.sin(t)
        pa = math.copysign(abs(ca) ** 0.8, ca) * hl
        pb = math.copysign(abs(sb) ** 0.8, sb) * hw
        # tangent for the tube frame
        dt = 1e-3
        ca2, sb2 = math.cos(t + dt), math.sin(t + dt)
        pa2 = math.copysign(abs(ca2) ** 0.8, ca2) * hl
        pb2 = math.copysign(abs(sb2) ** 0.8, sb2) * hw
        tan = (pa2 - pa) * a + (pb2 - pb) * b
        tan /= np.linalg.norm(tan)
        out = np.cross(tan, nrm)
        row = []
        base = np.asarray(center, float) + pa * a + pb * b
        for j in range(tube):
            u = 2 * math.pi * j / tube + math.pi / 4
            p = base + WIRE * (math.cos(u) * out + math.sin(u) * nrm)
            row.append(m.v(img(p[0], p[1], p[2])))
        rows.append(row)
    rows.append(rows[0])
    s_list = [k / ring for k in range(ring + 1)]
    v_list = [j / tube for j in range(tube + 1)]
    grid(m, rows, R_SILVER, s_list, v_list, closed=True, flip=_link_flip(m, rows, center))
    return m


def _link_flip(m, rows, center):
    p00, p10, p11 = m.verts[rows[0][0]], m.verts[rows[1][0]], m.verts[rows[1][1]]
    nrm = np.cross(p10 - p00, p11 - p00)
    ctr = np.mean([m.verts[k] for k in rows[0]], axis=0)
    return float(np.dot(nrm, p00 - ctr)) < 0


def chain_along(prefix, path3d, start_twist=0.0, max_links=200):
    """Lay links along a 3D image-space path (x, y, z in px)."""
    pts = smooth_curve(path3d, 400)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    d = np.concatenate([[0], np.cumsum(seg)])
    step = LINK_L - 2 * WIRE - 0.25
    links = []
    k = 0
    pos = step / 2
    while pos < d[-1] - step / 2 + 1e-6 and k < max_links:
        i = int(np.searchsorted(d, pos))
        i = min(max(i, 1), len(pts) - 1)
        c = pts[i]
        a = pts[min(i + 3, len(pts) - 1)] - pts[max(i - 3, 0)]
        a /= np.linalg.norm(a)
        # reference "up" for the link plane: viewer direction (z), alternated 90deg
        ref = np.array([0.0, 0.0, 1.0])
        if abs(np.dot(ref, a)) > 0.9:
            ref = np.array([1.0, 0.0, 0.0])
        b0 = np.cross(a, ref)
        b0 /= np.linalg.norm(b0)
        n0 = np.cross(a, b0)
        ang = start_twist + (math.pi / 2 if k % 2 else 0.0) + 0.25 * math.sin(k * 1.7)
        b = math.cos(ang) * b0 + math.sin(ang) * n0
        links.append(chain_link(f"{prefix}_{k + 1:02d}", c, a, b))
        k += 1
        pos += step
    return links


def ring_path(center, rx, rz, y_tilt, n=24, start=0.0):
    """Closed loop around the shaft/frame (image px): circle in the x/z plane,
    tilted so it follows the slanted shaft."""
    pts = []
    for i in range(n + 1):
        t = start + 2 * math.pi * i / n
        x = center[0] + rx * math.cos(t)
        z = rz * math.sin(t)
        y = center[1] + y_tilt * math.cos(t) + 0.04 * i
        pts.append((x, y, z))
    return pts


def build_head_chain():
    # main swag: hooks over the blade spine on the left, sags across the
    # blade face and climbs back to the frame
    swag = [(165, 59, -2.0), (166, 64, 6.0), (168, 75, 7.5), (171, 87, 7.5), (175, 98, 7.3),
            (181, 109, 7.0), (190, 118, 6.8), (201, 125, 6.6), (213, 130, 6.4),
            (225, 131, 6.3), (236, 128, 6.4), (245, 122, 6.8), (251, 116, 7.2),
            (255, 121, 7.6), (257, 130, 7.8), (258, 139, 7.5)]
    links = chain_along("head_link", swag)
    # loop of chain wrapped around the neck bands
    links += chain_along("neck_wrap", ring_path((258, 148), 7.0, 6.6, 3.0, start=0.3),
                         start_twist=0.3)
    # short loose end dangling from where the chain crosses the blade
    links += chain_along("head_dangle", [(171, 92, 8.0), (171, 101, 8.6), (172, 110, 8.8),
                                         (172, 118, 8.8)], start_twist=1.2)
    return links


def build_hanging_chain():
    path = [(252, 158, 7.0), (249, 172, 7.0), (250, 188, 7.0), (255, 204, 6.8), (262, 222, 6.5),
            (267, 240, 6.2), (271, 260, 6.0), (273, 280, 5.8), (273, 300, 5.6),
            (272, 322, 5.5), (272, 345, 5.4), (272.3, 364, 5.4)]
    return chain_along("hang_link", path, start_twist=0.6)


# --------------------------------------------------------------------------
# E. Pendant (small silver cross-dagger at the end of the hanging chain)
# --------------------------------------------------------------------------
def diamond(name, a, b, half_w, half_z, region=R_SILVER, n=8, shape=None):
    """Four-sided (lozenge section) spike from a to b (image px, z=pendant plane)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    c = [a + (b - a) * t for t in np.linspace(0, 1, n)]
    shape = shape or (lambda s: 1 - s)
    z0 = a[2] if len(a) > 2 else 0.0
    c2 = [p[:2] for p in c]
    return loft(name, c2, lambda s: half_w * shape(s), lambda s: half_z * shape(s), region,
                ring=4, n_exp=1.0, z_off=z0, cap1=False, origin=img(*a[:2], z0))


def build_pendant():
    z = 5.4
    cx, cy = 272.5, 378.5
    parts = [
        chain_link("pendant_bail", (272.3, 369.5, z), (0, 1, 0), (0, 0, 1)),
        # centre boss
        loft("pendant_boss", [(cx, cy - 2.6), (cx, cy), (cx, cy + 2.6)],
             lambda s: 0.5 + 2.2 * math.sin(math.pi * s), lambda s: 0.5 + 1.6 * math.sin(math.pi * s),
             R_SILVER, ring=8, z_off=z),
        diamond("pendant_blade_down", (cx, cy + 1.5, z), (cx + 0.6, 402, z), 2.0, 1.2, n=8,
                shape=lambda s: (1 - s) ** 0.9),
        diamond("pendant_tip_up", (cx, cy - 1.5, z), (cx, 372, z), 1.6, 1.0, n=4),
        diamond("pendant_arm_left", (cx - 1.5, cy, z), (263, cy - 0.5, z), 1.8, 1.0, n=5),
        diamond("pendant_arm_right", (cx + 1.5, cy, z), (282, cy - 0.5, z), 1.8, 1.0, n=5),
    ]
    return parts


# --------------------------------------------------------------------------
# Assemble the project
# --------------------------------------------------------------------------
def group(name, origin, children):
    return {
        "name": name,
        "origin": [round(float(c), 4) for c in origin],
        "color": 0,
        "uuid": uid("group_" + name),
        "export": True,
        "mirror_uv": False,
        "isOpen": name == "Scythe_Root",
        "locked": False,
        "visibility": True,
        "autouv": 0,
        "children": children,
    }


def build():
    os.makedirs(os.path.join(OUT, "textures"), exist_ok=True)
    tex = make_texture()
    tex_path = os.path.join(OUT, TEX_REL)
    tex.save(tex_path)
    buf = io.BytesIO()
    tex.save(buf, "PNG")
    data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    sections = [
        ("Main_Blade", img(250, 60), build_blade()),
        ("Upper_Frame", img(261, 100), build_frame()),
        ("Upper_Horns", img(264, 40), build_horns()),
        ("Main_Shaft", img(*shaft_point(400)), build_shaft()),
        ("Metal_Connectors", img(262, 160), build_connectors()),
        ("Head_Chain", img(210, 120), build_head_chain()),
        ("Hanging_Chain", img(258, 160), build_hanging_chain()),
        ("Chain_Pendant", img(272.5, 370), build_pendant()),
    ]

    elements, children = [], []
    for gname, origin, meshes in sections:
        els = [m.element() for m in meshes]
        elements += els
        children.append(group(gname, origin, [e["uuid"] for e in els]))
    root = group("Scythe_Root", img(*shaft_point(300)), children)

    model = {
        "meta": {"format_version": "4.10", "model_format": "free", "box_uv": False},
        "name": "grim_reaper_scythe",
        "model_identifier": "",
        "visible_box": [1, 1, 0],
        "variable_placeholders": "",
        "variable_placeholder_buttons": [],
        "timeline_setups": [],
        "unhandled_root_fields": {},
        "resolution": {"width": TEX, "height": TEX},
        "elements": elements,
        "outliner": [root],
        "textures": [{
            "path": "",
            "name": "scythe_texture.png",
            "folder": "",
            "namespace": "",
            "id": "0",
            "group": "",
            "width": TEX,
            "height": TEX,
            "uv_width": TEX,
            "uv_height": TEX,
            "particle": False,
            "use_as_default": False,
            "layers_enabled": False,
            "sync_to_project": "",
            "render_mode": "default",
            "render_sides": "auto",
            "frame_time": 1,
            "frame_order_type": "loop",
            "frame_order": "",
            "frame_interpolate": False,
            "visible": True,
            "internal": True,
            "saved": True,
            "uuid": uid("texture"),
            "relative_path": TEX_REL,
            "source": data_url,
        }],
    }
    path = os.path.join(OUT, "grim_reaper_scythe.bbmodel")
    with open(path, "w") as f:
        json.dump(model, f, indent="\t")
    validate(model)
    nv = sum(len(e["vertices"]) for e in elements)
    nf = sum(len(e["faces"]) for e in elements)
    print(f"wrote {path}: {len(elements)} meshes, {nv} vertices, {nf} faces")
    return model


def validate(model):
    """Structural checks that mirror what Blockbench's loader relies on."""
    uuids = set()
    for e in model["elements"]:
        assert e["type"] == "mesh" and e["uuid"] not in uuids
        uuids.add(e["uuid"])
        for fk, f in e["faces"].items():
            vs = f["vertices"]
            assert 3 <= len(vs) <= 4, (e["name"], fk)
            assert len(set(vs)) == len(vs), (e["name"], fk)
            assert set(f["uv"]) == set(vs), (e["name"], fk)
            for k in vs:
                assert k in e["vertices"], (e["name"], k)
                u, v = f["uv"][k]
                assert 0 <= u <= TEX and 0 <= v <= TEX, (e["name"], fk, u, v)
            assert f["texture"] == 0
        for p in e["vertices"].values():
            assert all(math.isfinite(c) for c in p)
    seen = set()

    def walk(node):
        for ch in node["children"]:
            if isinstance(ch, str):
                assert ch in uuids, ch
                seen.add(ch)
            else:
                walk(ch)
    for root in model["outliner"]:
        walk(root)
    assert seen == uuids, "every element must be in the outliner exactly once"
    json.loads(json.dumps(model))


if __name__ == "__main__":
    build()
