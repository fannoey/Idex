#!/usr/bin/env python3
"""Generate the black grim-reaper scythe as a Blockbench project (.bbmodel).

The model is traced from tools/reference/scythe_reference.png (1075x1463,
RGBA). Every coordinate in this file is in *reference-image pixels*
(x right, y down) and converted to Blockbench units by img():
X = (x - CX) * S, Y = (Y0 - y) * S, so Blockbench's "South" (front)
orthographic view matches the reference picture 1:1.

* Blade: lofted mesh with separate strips for the black flat, the silver
  bevel and the spine, so the bevel line stays crisp. Outline and bevel width
  are measured from the reference column by column.
* Head plate, horns and thorns: the dark silhouette is cut out of the alpha
  mask, triangulated and "inflated" (thickness grows with distance from the
  outline), so tips stay needle sharp and the outline is exact.
* Rod, grip, crystal, shaft, butt: section lofts. Chains: one mesh per link.

Project type: Generic Model ("free"), bbmodel format 4.10 (nested outliner),
which opens in Blockbench 4.10+ and 5.x.

Run:  python3 tools/build_scythe.py
"""
import base64
import io
import json
import math
import os
import uuid

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, map_coordinates
from scipy.spatial import Delaunay

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "Output")
REF = os.path.join(ROOT, "tools", "reference", "scythe_reference.png")
TEX_REL = "textures/scythe_texture.png"

S = 0.05            # Blockbench units per reference pixel (total height ~71 units)
CX, Y0 = 532, 1441  # reference pixel mapped to X=0 / Y=0 (bottom spike tip)
TEX = 512           # texture size in pixels (= UV size)

_NS = uuid.UUID("6d1f3b9e-2a4c-4f7e-9b1d-5c3a7e8f0a12")
_counter = [0]


def uid(name):
    _counter[0] += 1
    return str(uuid.uuid5(_NS, f"{name}:{_counter[0]}"))


def img(x, y, z=0.0):
    """Reference pixel (z also in pixels, + towards the viewer) -> Blockbench units."""
    return np.array([(x - CX) * S, (Y0 - y) * S, z * S])


# --------------------------------------------------------------------------
# Reference image
# --------------------------------------------------------------------------
_ref = np.array(Image.open(REF)).astype(np.float32)
ALPHA = _ref[..., 3] > 128
LUM = _ref[..., :3].mean(-1) * (_ref[..., 3] / 255) + 255 * (1 - _ref[..., 3] / 255)


# --------------------------------------------------------------------------
# Texture atlas (512x512). Regions in pixels: (u0, v0, u1, v1)
# --------------------------------------------------------------------------
R_FACE = (0, 0, 512, 96)        # blade flat: u = base->tip, v = bevel line->spine
R_BEVEL = (0, 96, 512, 144)     # blade bevel: u = base->tip, v = edge->bevel line
R_SPINE = (0, 144, 512, 152)    # blade spine strip
R_BLACK = (0, 160, 128, 256)    # glossy black tubes: u = along, v = around
R_PLATE = (128, 160, 256, 256)  # black metal plates: v = distance from the outline
R_SILVER = (256, 160, 384, 256)  # polished silver wire: v = around the wire
R_CRYSTAL = (384, 160, 512, 256)  # faceted crystal: v = around (8 facets)
R_GUNMETAL = (0, 256, 128, 352)
R_GEM = (128, 256, 256, 352)    # black gem with highlight

BLADE_STRIPES = []             # (s, width) of the pale reflection stripes, set by build_blade


def make_texture():
    t = np.zeros((TEX, TEX, 4), np.float32)
    t[..., 3] = 1
    rng = np.random.default_rng(7)

    def paint(region, fn):
        u0, v0, u1, v1 = region
        for py in range(v0, v1):
            v = (py - v0 + 0.5) / (v1 - v0)
            for px in range(u0, u1):
                s = (px - u0 + 0.5) / (u1 - u0)
                c = fn(s, v)
                if not isinstance(c, tuple):
                    c = (c, c, c * 1.03)
                t[py, px, :3] = c

    def face(s, v):
        c = 0.045 + 0.05 * v                                   # lighter towards the spine
        c += 0.09 * math.exp(-((v - 0.62) / 0.10) ** 2)        # long soft sheen
        c *= min(1.0, 0.35 + s / 0.06)                         # root fades into the black plate
        for s0, w in BLADE_STRIPES:                            # slanted reflection stripes
            d = s - (s0 + 0.03 * (1 - v))
            c += 0.42 * math.exp(-(d / w) ** 2) * (0.4 + 0.6 * v)
        if v < 0.06:
            c += 0.25                                          # thin light line at the bevel
        return c + rng.normal(0, 0.004)

    def bevel(s, v):
        base = 0.93 - 0.40 * v                                 # bright at the edge
        root = max(0.0, 1 - s / 0.16)                          # wide pale bevel near the root
        c = base + (0.80 - base) * root * 0.7
        if v > 0.9:
            c *= 0.7
        return c + rng.normal(0, 0.006)

    def tube(base, hi, var, dark=0.0):
        def f(s, v):
            c = base + hi * math.exp(-((v - 0.28) / 0.07) ** 2) \
                + 0.4 * hi * math.exp(-((v - 0.78) / 0.05) ** 2) \
                - dark * math.exp(-((v - 0.62) / 0.10) ** 2)
            return c + rng.normal(0, var)
        return f

    facets = [0.97, 0.62, 0.88, 0.48, 0.80, 0.58, 1.0, 0.70]

    def crystal(s, v):
        c = facets[min(7, int(v * 8))]
        c = c * (0.85 + 0.15 * math.sin(math.pi * s)) - 0.18 * math.exp(-((s - 0.5) / 0.06) ** 2)
        return (c, c, min(1.0, c + 0.05))

    def plate(s, v):
        return 0.05 + 0.42 * math.exp(-(v / 0.16) ** 2) + 0.03 * math.sin(9 * s) \
            + rng.normal(0, 0.005)

    paint(R_FACE, face)
    paint(R_BEVEL, bevel)
    paint(R_SPINE, lambda s, v: 0.16 + rng.normal(0, 0.005))
    paint(R_BLACK, tube(0.03, 0.30, 0.003))
    paint(R_PLATE, plate)
    paint(R_SILVER, tube(0.62, 0.42, 0.01, dark=0.42))
    paint(R_GUNMETAL, tube(0.22, 0.30, 0.01))
    paint(R_CRYSTAL, crystal)
    paint(R_GEM, lambda s, v: 0.04 + 0.6 * math.exp(-(((s - 0.35) ** 2 + (v - 0.3) ** 2) / 0.01)))
    t = np.clip(t, 0, 1)
    return Image.fromarray((t * 255).round().astype(np.uint8), "RGBA")


def ruv(region, s, v, pad=0.5):
    u0, v0, u1, v1 = region
    return [round(u0 + pad + (u1 - u0 - 2 * pad) * min(max(s, 0), 1), 3),
            round(v0 + pad + (v1 - v0 - 2 * pad) * min(max(v, 0), 1), 3)]


# --------------------------------------------------------------------------
# Mesh builder
# --------------------------------------------------------------------------
class Mesh:
    def __init__(self, name, origin, shading="smooth"):
        self.name = name
        self.origin = np.asarray(origin, float)
        self.shading = shading
        self.verts = []
        self.faces = []

    def v(self, p):
        self.verts.append(np.asarray(p, float))
        return len(self.verts) - 1

    def face(self, idx, uvs):
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
            faces[f"f{n}"] = {"uv": {keys[i]: u for i, u in zip(idx, uvs)},
                              "vertices": [keys[i] for i in idx], "texture": 0}
        return {"name": self.name, "color": 0,
                "origin": [round(float(c), 4) for c in self.origin], "rotation": [0, 0, 0],
                "export": True, "visibility": True, "locked": False, "render_order": "default",
                "allow_mirror_modeling": True, "shading": self.shading,
                "vertices": verts, "faces": faces, "type": "mesh", "uuid": uid(self.name)}


def grid(m, rows, region, s_list, v_list, flip=False):
    """Quads between consecutive rows (rows[i][j]); UVs from s_list[i], v_list[j]."""
    for i in range(len(rows) - 1):
        for j in range(len(rows[0]) - 1):
            q = [rows[i][j], rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]]
            uv = [ruv(region, s_list[i], v_list[j]), ruv(region, s_list[i + 1], v_list[j]),
                  ruv(region, s_list[i + 1], v_list[j + 1]), ruv(region, s_list[i], v_list[j + 1])]
            if flip:
                q, uv = q[::-1], uv[::-1]
            m.face(q, uv)


def resample(points, n):
    p = np.asarray(points, float)
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    d = np.concatenate([[0], np.cumsum(seg)])
    t = np.linspace(0, d[-1], n)
    return np.stack([np.interp(t, d, p[:, k]) for k in range(p.shape[1])], 1)


def smooth_curve(points, n):
    """Catmull-Rom through points, resampled evenly by arc length."""
    p = np.asarray(points, float)
    if len(p) == 2:
        return resample(p, n)
    ext = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for t in np.linspace(0, 1, 12, endpoint=False):
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(p[-1])
    return resample(out, n)


def _outward(m, rows):
    for i in range(len(rows) - 1):
        a, b = rows[i], rows[i + 1]
        if len(set(a)) > 1 and len(set(b)) > 1:
            p00, p10, p11 = m.verts[a[0]], m.verts[b[0]], m.verts[b[1]]
            nrm = np.cross(p10 - p00, p11 - p00)
            ctr = np.mean([m.verts[k] for k in a], axis=0)
            return float(np.dot(nrm, p00 - ctr)) < 0
    return False


def loft(name, center, rx, rz, region, ring=12, n_exp=2.0, cap0=True, cap1=True,
         z_off=0.0, origin=None, shading="smooth"):
    """Tube along an image-space curve. center: (N,2) or (N,3) image points.
    rx, rz: callables of s (pixels): in-plane half width and depth half width."""
    c = np.asarray(center, float)
    if c.shape[1] == 2:
        c = np.hstack([c, np.full((len(c), 1), z_off)])
    nseg = len(c)
    mid = c[nseg // 2]
    m = Mesh(name, origin if origin is not None else img(*mid), shading)
    rows, s_list = [], []
    for i in range(nseg):
        s = i / (nseg - 1)
        s_list.append(s)
        a = c[min(i + 1, nseg - 1)] - c[max(i - 1, 0)]
        a2 = a[:2] / (np.linalg.norm(a[:2]) + 1e-9)
        nrm = np.array([-a2[1], a2[0], 0.0])
        hx, hz = rx(s), rz(s)
        if hx < 1e-4 and hz < 1e-4:
            vi = m.v(img(*c[i]))
            rows.append([vi] * ring)
            continue
        row = []
        for k in range(ring):
            ph = 2 * math.pi * k / ring
            cs, sn = math.cos(ph), math.sin(ph)
            ex = math.copysign(abs(cs) ** (2 / n_exp), cs)
            ez = math.copysign(abs(sn) ** (2 / n_exp), sn)
            p = c[i] + nrm * hx * ex + np.array([0, 0, hz * ez])
            row.append(m.v(img(*p)))
        rows.append(row)
    flip = _outward(m, rows)
    v_list = [k / ring for k in range(ring + 1)]
    grid(m, [r + [r[0]] for r in rows], region, s_list, v_list, flip=flip)
    for end, do in ((0, cap0), (nseg - 1, cap1)):
        r = rows[end]
        if not do or len(set(r)) == 1:
            continue
        ctr = m.v(np.mean([m.verts[k] for k in r], axis=0))
        for k in range(ring):
            tri = [r[k], r[(k + 1) % ring], ctr]
            if (end == 0) != flip:
                tri = tri[::-1]
            m.face(tri, [ruv(region, s_list[end], 0.5)] * 3)
    return m


# --------------------------------------------------------------------------
# Inflated silhouette meshes (head plate, horns, thorns)
# --------------------------------------------------------------------------
def inflate(name, sub, dist, region, half_t=5.0, falloff=4.5, step=5, z0=0.0, origin=None,
            parent=None, rim=9.0):
    """Triangulate the boolean mask `sub` (full image size) and give it
    thickness z = half_t * (1 - exp(-d / falloff)), d = distance (px) from the
    outline of the parent silhouette `dist`. Cut lines shared with a sibling
    piece keep their thickness so pieces join without a seam. UV v encodes the
    distance from the outline (0..rim px) so the texture paints a glossy rim."""
    if parent is not None:          # overlap siblings by 2 px so the cut leaves no gap
        sub = cv2.dilate(sub.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool) & parent
    contours, _ = cv2.findContours(sub.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    pts = []
    for c in contours:
        c = c[:, 0, :].astype(float)
        if len(c) < 6:
            continue
        pts += [tuple(p) for p in c[::max(1, int(round(step / 2.2)))]]
    d_sub = distance_transform_edt(sub)
    ys, xs = np.mgrid[0:sub.shape[0]:step, 0:sub.shape[1]:step]
    ys, xs = ys.ravel(), xs.ravel()
    sel = sub[ys, xs] & (d_sub[ys, xs] >= step * 0.55)
    pts += list(zip(xs[sel].astype(float), ys[sel].astype(float)))
    P = np.array(pts)
    tri = Delaunay(P)
    x0, y0 = P.min(0)
    x1, y1 = P.max(0)

    m = Mesh(name, origin if origin is not None else img((x0 + x1) / 2, (y0 + y1) / 2, z0))
    d = map_coordinates(dist, [P[:, 1], P[:, 0]], order=1) - 1.0
    z = half_t * (1 - np.exp(-np.maximum(d, 0) / falloff))
    front, back = [], []
    for (px, py), zz in zip(P, z):
        if zz < 0.05:
            vi = m.v(img(px, py, z0))
            front.append(vi)
            back.append(vi)
        else:
            front.append(m.v(img(px, py, z0 + zz)))
            back.append(m.v(img(px, py, z0 - zz)))

    def uv(i):
        return ruv(region, (P[i, 0] - x0) / max(x1 - x0, 1), max(d[i], 0) / rim)

    for t in tri.simplices:
        cpt = P[t].mean(0)
        if not sub[int(round(cpt[1])), int(round(cpt[0]))]:
            continue
        e = max(np.linalg.norm(P[t[0]] - P[t[1]]), np.linalg.norm(P[t[1]] - P[t[2]]),
                np.linalg.norm(P[t[2]] - P[t[0]]))
        if e > step * 2.6:
            continue
        a, b, c = t
        # image y points down, model y up: make every front triangle face +z
        cr = (P[b, 0] - P[a, 0]) * (P[c, 1] - P[a, 1]) - (P[b, 1] - P[a, 1]) * (P[c, 0] - P[a, 0])
        if cr > 0:
            b, c = c, b
        m.face([front[a], front[b], front[c]], [uv(a), uv(b), uv(c)])
        m.face([back[a], back[c], back[b]], [uv(a), uv(c), uv(b)])
    return m


def head_masks():
    dark = (ALPHA & (LUM < 135)).astype(np.uint8)
    reg = np.zeros_like(dark)
    reg[8:262, 528:775] = 1
    m = cv2.morphologyEx(dark * reg, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    m = lab == 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])
    # fill small holes (chain shadows) but keep the teardrop window (~250 px)
    n, lab, st, _ = cv2.connectedComponentsWithStats((~m).astype(np.uint8), connectivity=4)
    for k in range(1, n):
        if st[k, cv2.CC_STAT_AREA] < 150:
            m[lab == k] = True
    # distance is measured on the plate joined with the blade so the left cut
    # (where the blade enters) keeps its thickness
    joined = m.copy()
    joined[60:170, 480:530] |= ALPHA[60:170, 480:530]
    dist = distance_transform_edt(joined)
    yy, xx = np.mgrid[0:m.shape[0], 0:m.shape[1]]
    # the chain hides the lower edge in the picture: smooth the ragged bits
    low = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    m = np.where(yy > 215, low.astype(bool), m)
    horn = m & (yy < 78)
    thorn = m & (xx >= 614) & (yy >= 140) & (yy <= 215)
    plate = m & ~horn & ~thorn
    return plate, horn, thorn, dist, m


def split_components(mask, min_area=30):
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8))
    out = [lab == k for k in range(1, n) if st[k, cv2.CC_STAT_AREA] >= min_area]
    return sorted(out, key=lambda c: np.argwhere(c)[:, 0].mean())


# --------------------------------------------------------------------------
# A. Main blade (traced)
# --------------------------------------------------------------------------
BLADE_ROOT_X = 548


def trace_blade():
    """Spine & edge polylines (image px, base -> tip) traced from the alpha mask."""
    spine, edge = [], []
    for x in range(BLADE_ROOT_X, 84, -4):
        col = ALPHA[:700, x].astype(np.int8)
        # longest vertical run = the blade (skips the horn tip and chain links)
        d = np.diff(np.concatenate([[0], col, [0]]))
        starts, ends = np.where(d == 1)[0], np.where(d == -1)[0] - 1
        k = int(np.argmax(ends - starts))
        spine.append((x, starts[k]))
        edge.append((x, ends[k]))
    # columns 368..404: the chain crosses the spine -> interpolate the top
    sp = np.array(spine, float)
    bad = (sp[:, 0] >= 368) & (sp[:, 0] <= 404)
    sp[bad, 1] = np.interp(sp[bad, 0], sp[~bad, 0][::-1], sp[~bad, 1][::-1])
    spine = [tuple(p) for p in sp]
    # tip part: scan rows (the blade is steep there)
    for y in range(int(edge[-1][1]) + 4, 608, 4):
        xs = np.where(ALPHA[y, :140])[0]
        if len(xs) == 0:
            break
        x = xs[0]
        spine.append((x, y))
        while x < 139 and ALPHA[y, x + 1]:
            x += 1
        edge.append((x, y))
    spine.append((22, 611))
    edge.append((22, 611))
    return np.array(spine, float), np.array(edge, float)


def bevel_fraction(spine, edge):
    """Fraction of the width (measured from the edge) covered by the pale bevel."""
    fr = []
    for s, e in zip(spine, edge):
        w = np.linalg.norm(s - e)
        if w < 3:
            fr.append(0.3)
            continue
        n, lit = int(w), 0
        for k in range(n):
            p = e + (s - e) * (k / n)
            if LUM[int(round(p[1])), int(round(p[0]))] > 105:
                lit += 1
            else:
                break
        fr.append(min(0.85, max(0.16, (lit + 1.5) / w)))
    return np.convolve(np.pad(fr, 3, mode="edge"), np.ones(7) / 7, mode="valid")


def build_blade():
    sp_raw, ed_raw = trace_blade()
    n = 70
    spine = smooth_curve(sp_raw, n)
    edge = smooth_curve(ed_raw, n)
    bev = bevel_fraction(spine, edge)
    seg = np.linalg.norm(np.diff(spine, axis=0), axis=1)
    s_list = list(np.concatenate([[0], np.cumsum(seg)]) / seg.sum())
    # the reference shows two pale reflection stripes near x~505 and x~472
    BLADE_STRIPES.clear()
    for xs, w in ((515, 0.006), (492, 0.004)):
        BLADE_STRIPES.append((s_list[int(np.argmin(np.abs(spine[:, 0] - xs)))], w))

    m = Mesh("blade_mesh", img(*spine[0]))
    rows = {k: [] for k in ("e", "bf", "bb", "bf2", "bb2", "sf", "sb", "sf2", "sb2")}
    for i in range(n):
        s = s_list[i]
        e, sp = edge[i], spine[i]
        bl = e + (sp - e) * bev[i]
        T = 4.2 * (1 - s) ** 0.8 + 0.6 if i < n - 1 else 0.0   # spine half thickness (px)
        tb = 0.78 * T
        rows["e"].append(m.v(img(*e, 0)))
        # every strip owns its border vertices -> crisp bevel line and spine
        for key, p, z in (("bf", bl, tb), ("bb", bl, -tb), ("bf2", bl, tb), ("bb2", bl, -tb),
                          ("sf", sp, T), ("sb", sp, -T), ("sf2", sp, T), ("sb2", sp, -T)):
            rows[key].append(m.v(img(*p, z)))

    def strip(a, b, region, flip):
        for i in range(n - 1):
            q = [rows[a][i], rows[a][i + 1], rows[b][i + 1], rows[b][i]]
            uv = [ruv(region, s_list[i], 0), ruv(region, s_list[i + 1], 0),
                  ruv(region, s_list[i + 1], 1), ruv(region, s_list[i], 1)]
            if flip:
                q, uv = q[::-1], uv[::-1]
            m.face(q, uv)

    p = [m.verts[rows["e"][5]], m.verts[rows["e"][6]], m.verts[rows["bf"][6]]]
    flip = float(np.cross(p[1] - p[0], p[2] - p[0])[2]) < 0   # front strips must face +z
    strip("e", "bf", R_BEVEL, flip)
    strip("e", "bb", R_BEVEL, not flip)
    strip("bf2", "sf", R_FACE, flip)
    strip("bb2", "sb", R_FACE, not flip)
    strip("sf2", "sb2", R_SPINE, flip)
    # root cap (hidden inside the head plate)
    e0, bf, sf, sb, bb = (rows[k][0] for k in ("e", "bf", "sf", "sb", "bb"))
    cap_uv = ruv(R_SPINE, 0, 0.5)
    for poly in ([e0, bf, sf, sb], [e0, sb, bb]):
        m.face(poly[::-1] if flip else poly, [cap_uv] * len(poly))
    return [m]


# --------------------------------------------------------------------------
# B. Head: plate, horns, thorns, rod
# --------------------------------------------------------------------------
def star(name, x, y, z, r, region=R_SILVER, thin=0.35):
    """Small four-point star stud lying in the view plane (slightly domed)."""
    m = Mesh(name, img(x, y, z), "flat")
    ctr = m.v(img(x, y, z + r * 0.35))
    ring = []
    for k in range(8):
        a = math.pi / 2 * (k // 2) + (math.pi / 4 if k % 2 else 0)
        rr = r if k % 2 == 0 else r * thin
        ring.append(m.v(img(x + rr * math.cos(a), y - rr * math.sin(a), z)))
    for k in range(8):
        m.face([ctr, ring[k], ring[(k + 1) % 8]],
               [ruv(region, 0.5, 0.25), ruv(region, 0.5, 0.3), ruv(region, 0.5, 0.3)])
    return m


ROD = [(614, 62), (611, 100), (607, 150), (603, 205), (600, 262)]


def build_frame(plate, dist, full):
    return [
        inflate("head_plate", plate, dist, R_PLATE, half_t=6.0, falloff=5.0, step=5,
                origin=img(575, 160), parent=full),
        loft("head_rod", smooth_curve(ROD, 14), lambda s: 8.5, lambda s: 8.5, R_BLACK,
             ring=14, z_off=1.0, origin=img(607, 160)),
    ]


def build_horns(horn, thorn, dist, full):
    parts = [inflate("horn_crescent_and_spike", horn, dist, R_PLATE, half_t=5.5, falloff=4.0,
                     step=4, origin=img(640, 40), parent=full)]
    for k, c in enumerate(split_components(thorn)):
        parts.append(inflate(f"thorn_right_{k + 1}", c, dist, R_PLATE, half_t=5.0, falloff=3.5,
                             step=4, origin=img(616, 180), parent=full))
    parts.append(star("horn_star", 651, 27, 4.6, 7.0))
    return parts


# --------------------------------------------------------------------------
# C. Shaft and metal connectors
# --------------------------------------------------------------------------
def shaft_x(y):
    """Shaft centre line measured from the reference (22.8 deg from vertical)."""
    return 649.5 + 0.42 * (y - 525)


def shaft_pts(y0, y1, n):
    return [(shaft_x(y), y) for y in np.linspace(y0, y1, n)]


def build_shaft():
    R = 9.8

    def bulge(s):
        return 10.5 + 3.2 * abs(math.sin(3 * math.pi * s)) ** 0.7 - 3.0 * s

    return [
        loft("shaft_upper", shaft_pts(470, 850, 12), lambda s: R, lambda s: R, R_BLACK,
             ring=14, cap1=False),
        loft("shaft_lower", shaft_pts(850, 1238, 12), lambda s: R, lambda s: R, R_BLACK,
             ring=14, cap0=False),
        loft("butt_segments", shaft_pts(1236, 1346, 24), bulge, bulge, R_BLACK, ring=14),
        loft("butt_spike", [(shaft_x(1344), 1344), (1012, 1390), (1041, 1441)],
             lambda s: 7.5 * (1 - s) ** 1.1, lambda s: 7.5 * (1 - s) ** 1.1, R_BLACK,
             ring=10, cap1=False),
    ]


def build_connectors():
    parts = []
    for i, y in enumerate((118, 150, 205)):
        x = np.interp(y, [p[1] for p in ROD], [p[0] for p in ROD])
        parts.append(loft(f"rod_ring_{i + 1}", [(x + 0.2, y - 3), (x, y + 3)],
                          lambda s: 10.2, lambda s: 10.2, R_GUNMETAL, ring=14, z_off=1.0))
    # wrapped grip under the head, with silver star studs
    grip = smooth_curve([(600, 258), (598, 290), (597, 320), (598, 346)], 12)
    parts.append(loft("grip_wrap", grip, lambda s: 11 + 0.8 * math.sin(math.pi * s * 4) ** 2,
                      lambda s: 11, R_BLACK, ring=14))
    for k, (x, y) in enumerate(((598, 286), (597, 306), (597, 326))):
        parts.append(star(f"grip_star_{k + 1}", x, y, 11.3, 4.2))
    parts.append(loft("grip_cap", [(598.5, 344), (599.5, 352)], lambda s: 12.5 - 3 * s,
                      lambda s: 12.5 - 3 * s, R_GUNMETAL, ring=14))
    # faceted clear crystal
    rows = [(600, 349, 6), (600, 354, 13), (600.5, 364, 17.5), (601, 378, 17), (601.5, 389, 11),
            (602, 395, 6)]
    rr = [r[2] for r in rows]
    parts.append(loft("crystal", [r[:2] for r in rows],
                      lambda s: np.interp(s, np.linspace(0, 1, 6), rr),
                      lambda s: np.interp(s, np.linspace(0, 1, 6), rr) * 0.9,
                      R_CRYSTAL, ring=8, shading="flat"))
    # knuckled black section joining the crystal to the shaft
    parts.append(loft("neck_knuckle", smooth_curve([(602, 394), (606, 405), (603, 418),
                                                   (609, 432), (shaft_x(472), 472)], 14),
                      lambda s: 10.5 + 2.2 * math.sin(math.pi * s * 2) ** 2,
                      lambda s: 10.5 + 2.2 * math.sin(math.pi * s * 2) ** 2, R_BLACK, ring=14))
    # silver diamond cage clasped to the right of the shaft
    cage = [(606, 432, 7), (650, 443, 9), (641, 476, 7), (612, 462, 9), (606, 432, 7)]
    parts.append(loft("diamond_cage", resample(np.array(cage, float), 40), lambda s: 1.8,
                      lambda s: 1.8, R_SILVER, ring=6, cap0=False, cap1=False))
    parts.append(loft("diamond_cage_brace", resample(np.array([(606, 432, 8), (641, 476, 8)],
                                                               float), 6),
                      lambda s: 1.5, lambda s: 1.5, R_SILVER, ring=6))
    parts.append(loft("shaft_collar", shaft_pts(486, 500, 3), lambda s: 11.2, lambda s: 11.2,
                      R_GUNMETAL, ring=14))
    for k, y in enumerate((1258, 1290, 1320)):
        parts.append(star(f"butt_star_{k + 1}", shaft_x(y) + 1, y, 12.6, 4.0))
    return parts


# --------------------------------------------------------------------------
# D. Chains
# --------------------------------------------------------------------------
def chain_link(name, center, axis, side, L, W, wire, ring=12, tube=6):
    """Oval link with a real hole. axis: long direction, side: width direction."""
    m = Mesh(name, img(*center[:2], center[2]))
    a = np.asarray(axis, float)
    b = np.asarray(side, float)
    nrm = np.cross(a, b)
    hl, hw = L / 2 - wire, W / 2 - wire

    def pt(t):
        ca, sb = math.cos(t), math.sin(t)
        return math.copysign(abs(ca) ** 0.7, ca) * hl, math.copysign(abs(sb) ** 0.7, sb) * hw

    rows = []
    for k in range(ring):
        t = 2 * math.pi * k / ring
        pa, pb = pt(t)
        pa2, pb2 = pt(t + 1e-3)
        tan = (pa2 - pa) * a + (pb2 - pb) * b
        tan /= np.linalg.norm(tan)
        out = np.cross(tan, nrm)
        base = np.asarray(center, float) + pa * a + pb * b
        row = [m.v(img(*(base + wire * (math.cos(u) * out + math.sin(u) * nrm))))
               for u in (2 * math.pi * j / tube for j in range(tube))]
        rows.append(row + [row[0]])
    rows.append(rows[0])
    p00, p10, p11 = m.verts[rows[0][0]], m.verts[rows[1][0]], m.verts[rows[1][1]]
    ctr = np.mean([m.verts[k] for k in rows[0][:-1]], axis=0)
    flip = float(np.dot(np.cross(p10 - p00, p11 - p00), p00 - ctr)) < 0
    grid(m, rows, R_SILVER, [k / ring for k in range(ring + 1)],
         [j / tube for j in range(tube + 1)], flip=flip)
    return m


def chain_along(prefix, path3d, L=26, W=12.5, wire=2.6, twist=0.0):
    """Lay interlocking links along a 3D image-space path (x, y, z in px)."""
    pts = smooth_curve(path3d, 600)
    d = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])
    step = L - 2 * wire - 0.6
    links, k, pos = [], 0, step / 2
    while pos < d[-1] - step / 2 + 1e-6:
        i = min(max(int(np.searchsorted(d, pos)), 1), len(pts) - 1)
        c = pts[i]
        a = pts[min(i + 4, len(pts) - 1)] - pts[max(i - 4, 0)]
        a /= np.linalg.norm(a)
        ref = np.array([0.0, 0.0, 1.0])
        if abs(np.dot(ref, a)) > 0.9:
            ref = np.array([1.0, 0.0, 0.0])
        b0 = np.cross(a, ref)
        b0 /= np.linalg.norm(b0)
        n0 = np.cross(a, b0)
        ang = twist + (math.pi / 2 if k % 2 else 0.0) + 0.15 * math.sin(k * 1.7)
        b = math.cos(ang) * b0 + math.sin(ang) * n0
        links.append(chain_link(f"{prefix}_{k + 1:02d}", c, a, b, L, W, wire))
        k += 1
        pos += step
    return links


def helix(x0, y0, x1, y1, r, turns, z_front=1.0, n=60):
    pts = []
    for i in range(n + 1):
        t = i / n
        ang = 2 * math.pi * turns * t
        pts.append((x0 + (x1 - x0) * t + r * math.cos(ang),
                    y0 + (y1 - y0) * t + 0.18 * r * math.sin(ang),
                    z_front + r * math.sin(ang)))
    return pts


def build_head_chain():
    links = []
    # swag: hooks over the blade spine, hangs across the blade, climbs to the rod
    links += chain_along("swag_link", [
        (378, 114, -8), (384, 126, 8), (385, 150, 10), (389, 178, 10), (397, 202, 10),
        (410, 224, 10), (428, 242, 10), (450, 259, 10), (474, 274, 10), (500, 285, 10),
        (526, 290, 10), (550, 287, 10), (572, 278, 11), (592, 262, 12), (606, 246, 13)])
    # wrapped around the grip
    links += chain_along("grip_wrap_link", helix(598, 252, 597, 338, 14, 2.6, z_front=0.5),
                         L=22, W=11, wire=2.4, twist=0.4)
    # loose strand from the grip down to the diamond cage
    links += chain_along("neck_link", [(580, 340, 12), (568, 356, 12), (565, 378, 12),
                                       (566, 400, 12), (572, 418, 12), (588, 430, 12),
                                       (606, 434, 10)], twist=1.1)
    # short dangling end carrying the little twin-spike charm
    links += chain_along("dangle_link", [(392, 196, 12), (392, 214, 13), (392, 232, 13)],
                         L=22, W=11, wire=2.3, twist=0.5)
    return links


def build_hanging_chain():
    path = [(618, 470, 12), (622, 490, 12), (624, 520, 11)] + \
           [(625 + 0.25 * k, 560 + 35 * k, 11) for k in range(8)] + [(627, 838, 11)]
    return chain_along("hang_link", path, L=31, W=14, wire=3.0, twist=0.3)


# --------------------------------------------------------------------------
# E. Pendants
# --------------------------------------------------------------------------
def spike(name, a, b, half_w, half_z, n=6, region=R_SILVER, power=1.0):
    """Four-sided (lozenge section) spike from a to b, tapering to a point."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    c = [a + (b - a) * t for t in np.linspace(0, 1, n)]
    return loft(name, c, lambda s: half_w * (1 - s) ** power, lambda s: half_z * (1 - s) ** power,
                region, ring=4, n_exp=1.0, cap1=power == 0.0, origin=img(*a), shading="flat")


def build_pendant():
    z = 11
    cx, cy = 626, 862
    parts = [
        chain_link("pendant_bail", (626.5, 846, z), (0, 1, 0), (0, 0, 1), 16, 9, 2.2),
        spike("cross_down", (cx, cy + 4, z), (cx + 1, 945, z), 5.0, 3.0, n=10, power=0.9),
        spike("cross_up", (cx, cy - 4, z), (cx, 851, z), 4.0, 2.6, n=4),
        spike("cross_left", (cx - 4, cy, z), (593, cy, z), 4.0, 2.6, n=6),
        spike("cross_right", (cx + 4, cy, z), (660, cy, z), 4.0, 2.6, n=6),
    ]
    for k, (dx, dy) in enumerate(((-1, -1), (1, -1), (-1, 1), (1, 1))):
        parts.append(spike(f"cross_flourish_{k + 1}", (cx + 3 * dx, cy + 3 * dy, z),
                           (cx + 11 * dx, cy + 11 * dy, z), 2.4, 1.6, n=4))
    parts.append(loft("cross_gem", [(cx, cy - 5.5), (cx, cy), (cx, cy + 5.5)],
                      lambda s: 0.8 + 5.2 * math.sin(math.pi * s),
                      lambda s: 0.8 + 3.8 * math.sin(math.pi * s), R_GEM, ring=8,
                      z_off=z + 1.5, shading="flat"))
    # twin spikes hanging from the short blade-side chain
    zc = 13
    parts.append(spike("charm_spike_left", (387, 236, zc), (386, 266, zc), 3.4, 2.2, n=6))
    parts.append(spike("charm_spike_right", (397, 238, zc), (397, 274, zc), 3.4, 2.2, n=6))
    parts.append(spike("charm_bar", (381, 240, zc), (403, 240, zc), 1.6, 1.4, n=3, power=0.0))
    return parts


# --------------------------------------------------------------------------
# Assemble
# --------------------------------------------------------------------------
def group(name, origin, children):
    return {"name": name, "origin": [round(float(c), 4) for c in origin], "color": 0,
            "uuid": uid("group_" + name), "export": True, "mirror_uv": False,
            "isOpen": name == "Scythe_Root", "locked": False, "visibility": True,
            "autouv": 0, "children": children}


def build():
    os.makedirs(os.path.join(OUT, "textures"), exist_ok=True)
    plate, horn, thorn, dist, full = head_masks()
    sections = [
        ("Main_Blade", img(548, 120), build_blade()),
        ("Upper_Frame", img(575, 160), build_frame(plate, dist, full)),
        ("Upper_Horns", img(640, 40), build_horns(horn, thorn, dist, full)),
        ("Main_Shaft", img(shaft_x(900), 900), build_shaft()),
        ("Metal_Connectors", img(600, 370), build_connectors()),
        ("Head_Chain", img(500, 260), build_head_chain()),
        ("Hanging_Chain", img(625, 650), build_hanging_chain()),
        ("Chain_Pendant", img(626, 862), build_pendant()),
    ]
    tex = make_texture()           # after build_blade(): stripes depend on the traced blade
    tex.save(os.path.join(OUT, TEX_REL))
    buf = io.BytesIO()
    tex.save(buf, "PNG")
    data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    elements, children = [], []
    for gname, origin, meshes in sections:
        els = [m.element() for m in meshes]
        elements += els
        children.append(group(gname, origin, [e["uuid"] for e in els]))
    root = group("Scythe_Root", img(shaft_x(700), 700), children)

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
            "path": "", "name": "scythe_texture.png", "folder": "", "namespace": "", "id": "0",
            "group": "", "width": TEX, "height": TEX, "uv_width": TEX, "uv_height": TEX,
            "particle": False, "use_as_default": False, "layers_enabled": False,
            "sync_to_project": "", "render_mode": "default", "render_sides": "auto",
            "frame_time": 1, "frame_order_type": "loop", "frame_order": "",
            "frame_interpolate": False, "visible": True, "internal": True, "saved": True,
            "uuid": uid("texture"), "relative_path": TEX_REL, "source": data_url,
        }],
    }
    path = os.path.join(OUT, "grim_reaper_scythe.bbmodel")
    with open(path, "w") as f:
        json.dump(model, f, separators=(",", ":"))
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
        assert e["faces"], e["name"]
        for fk, f in e["faces"].items():
            vs = f["vertices"]
            assert 3 <= len(vs) <= 4, (e["name"], fk)
            assert len(set(vs)) == len(vs), (e["name"], fk)
            assert set(f["uv"]) == set(vs), (e["name"], fk)
            for k in vs:
                assert k in e["vertices"], (e["name"], k)
                u, v = f["uv"][k]
                assert 0 <= u <= TEX and 0 <= v <= TEX, (e["name"], fk, u, v)
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
    for r in model["outliner"]:
        walk(r)
    assert seen == uuids, "every element must be in the outliner exactly once"


if __name__ == "__main__":
    build()
