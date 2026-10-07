"""Cursed Reaper Scythe as a real triangle mesh.

The silhouette is cut out of the reference art (same cutout as build_scythe.py),
stood upright, traced into smooth contours and triangulated. Every vertex is then
pushed out to a thickness that depends on where it is:

* shaft  - circular cross-section (a real round pole)
* blade  - thin wedge, sharp at the rim
* head / pommel - pillowy, capped thickness

Front and back surfaces get smooth normals from the analytic height field, the rim
is closed with a wall strip. UVs are a planar projection of the cleaned artwork, so
the painted detail sits exactly where it is in the reference.

Model frame (Blockbench space): x right, y up, z towards the viewer.
Pommel tip at y = 0, shaft centred on x = 0, blade hangs to -x.
"""
import math
import os
import sys

import numpy as np
import triangle
from PIL import Image
from scipy import ndimage as ndi
from skimage import measure
from skimage.morphology import skeletonize

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build_scythe as bs  # noqa: E402

HEIGHT = 46.0          # model px, pommel tip -> top of head (~2.9 blocks)
TEX_PER_PX = 16        # texture px per model px
SIMPLIFY = 1.1         # contour simplification tolerance (reference px)
MAX_EDGE = 0.65        # max rim edge length (model px)
MAX_AREA = 0.6         # max triangle area (model px^2)

BLADE, HEAD, SHAFT, POMMEL = bs.BLADE, bs.HEAD, bs.SHAFT, bs.POMMEL
PART_NAMES = {BLADE: "blade", HEAD: "head", SHAFT: "shaft", POMMEL: "pommel"}


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


class Silhouette:
    """Upright, scaled cutout of the reference art plus its thickness field."""

    def __init__(self, height=HEIGHT):
        src = np.asarray(Image.open(bs.REF).convert("RGB")).astype(float)
        mask = bs.cutout(src)
        col = bs.grade(bs.fill_outside(src, mask))
        zone = bs.zones(mask.shape)
        rot = lambda im, rs: im.rotate(bs.ANGLE, resample=rs, expand=True)
        m = np.asarray(rot(Image.fromarray((mask * 255).astype(np.uint8)), Image.BILINEAR)) / 255.0
        self.mask = ndi.gaussian_filter(m, 1.0)
        self.zone = np.asarray(rot(Image.fromarray(zone), Image.NEAREST))
        self.color = rot(Image.fromarray(col), Image.BICUBIC)
        inside = self.mask > 0.5
        ys, xs = np.nonzero(inside)
        self.k = height / (ys.max() - ys.min())          # model px per image px
        self.ox = xs[self.zone[ys, xs] == SHAFT].mean()
        self.oy = ys.max()
        self.bbox = self._bbox(xs, ys)
        self._height_field(inside)

    # image px <-> model px
    def to_model(self, px, py):
        return (np.asarray(px) - self.ox) * self.k, (self.oy - np.asarray(py)) * self.k

    def to_img(self, x, y):
        return self.ox + np.asarray(x) / self.k, self.oy - np.asarray(y) / self.k

    def _bbox(self, xs, ys):
        x0, y1 = self.to_model(xs.min(), ys.min())
        x1, y0 = self.to_model(xs.max(), ys.max())
        pad = 0.5
        return (math.floor(x0 - pad), math.floor(y0 - pad), math.ceil(x1 + pad), math.ceil(y1 + pad))

    def _height_field(self, inside):
        k = self.k
        d = ndi.distance_transform_edt(inside) * k            # model px to the rim
        R = ndi.maximum_filter(d, size=int(1.6 / k))          # local half-width
        circ = np.sqrt(np.clip(R * R - (R - d) ** 2, 0, None))
        h = {
            SHAFT: 0.03 + 0.97 * circ,
            BLADE: 0.025 + 0.30 * smoothstep(0.0, 0.9, d),
            HEAD: 0.04 + 0.95 * np.tanh(circ * 0.85 / 0.95),
            POMMEL: 0.04 + 0.80 * np.tanh(circ * 0.95 / 0.80),
        }
        w = {z: ndi.gaussian_filter((self.zone == z).astype(float), 9) for z in h}
        tot = sum(w.values()) + 1e-9
        field = sum(h[z] * w[z] for z in h) / tot
        self.h = ndi.gaussian_filter(field, 1.2)
        gy, gx = np.gradient(self.h)
        self.hx = gx / k            # d h / d x_model
        self.hy = -gy / k           # d h / d y_model

    def sample(self, arr, x, y, order=1):
        px, py = self.to_img(x, y)
        return ndi.map_coordinates(arr, [py, px], order=order, mode="nearest")

    def texture(self):
        """Artwork projected on the model bbox, TEX_PER_PX texels per model px."""
        x0, y0, x1, y1 = self.bbox
        w, h = (x1 - x0) * TEX_PER_PX, (y1 - y0) * TEX_PER_PX
        box = (*self.to_img(x0, y1), *self.to_img(x1, y0))
        tex = self.color.resize((w, h), Image.LANCZOS, box=box)
        m = np.asarray(Image.fromarray((self.mask * 255).astype(np.uint8)).resize(
            (w, h), Image.BILINEAR, box=box)) > 140
        return Image.fromarray(bs.fill_outside(np.asarray(tex), m)), m

    def uv(self, x, y):
        """Texture pixel coordinates (origin top-left) for model x, y."""
        x0, y0, x1, y1 = self.bbox
        return np.c_[(np.asarray(x) - x0) * TEX_PER_PX, (y1 - np.asarray(y)) * TEX_PER_PX]


# ---------------------------------------------------------------- triangulation
def contours(sil):
    out = []
    for c in measure.find_contours(sil.mask, 0.5):
        c = measure.approximate_polygon(c, SIMPLIFY)
        if len(c) < 5:
            continue
        if np.allclose(c[0], c[-1]):
            c = c[:-1]
        x, y = sil.to_model(c[:, 1], c[:, 0])
        pts = np.c_[x, y]
        # resample so no rim edge is longer than MAX_EDGE
        dense = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            n = max(1, int(math.ceil(np.linalg.norm(b - a) / MAX_EDGE)))
            dense += [a + (b - a) * t for t in np.arange(n) / n]
        out.append(np.array(dense))
    return out


def hole_seeds(sil):
    bg = sil.mask <= 0.5
    lab, n = ndi.label(bg)
    border = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    seeds = []
    for i in range(1, n + 1):
        if i in border:
            continue
        comp = lab == i
        if comp.sum() < 12:
            continue
        dt = ndi.distance_transform_edt(comp)
        py, px = np.unravel_index(np.argmax(dt), dt.shape)
        seeds.append(sil.to_model(px, py))
    return np.array(seeds, float).reshape(-1, 2)


def interior_points(sil, loops):
    """Extra vertices on offset curves and the medial axis so round parts get a
    real cross-section (not just rim + one row)."""
    inside = sil.mask > 0.5
    d = ndi.distance_transform_edt(inside) * sil.k
    pts = []
    for lvl in (0.13, 0.4):
        for c in measure.find_contours(d, lvl):
            x, y = sil.to_model(c[:, 1], c[:, 0])
            p = np.c_[x, y]
            seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
            for s in np.arange(0, seg[-1], 0.5):
                i = np.searchsorted(seg, s)
                pts.append(p[min(i, len(p) - 1)])
    sk = skeletonize(inside & (d > 0.2))
    py, px = np.nonzero(sk)
    step = max(1, int(0.5 / sil.k / 1.5))
    order = np.lexsort((px, py))[::step]
    x, y = sil.to_model(px[order], py[order])
    pts += list(np.c_[x, y])
    pts = np.array(pts)
    # keep away from the rim vertices
    rim = np.concatenate(loops)
    from scipy.spatial import cKDTree
    keep = cKDTree(rim).query(pts)[0] > 0.12
    pts = pts[keep]
    # thin out duplicates
    tree = cKDTree(pts)
    taken = np.zeros(len(pts), bool)
    out = []
    for i in range(len(pts)):
        if taken[i]:
            continue
        out.append(pts[i])
        taken[tree.query_ball_point(pts[i], 0.3)] = True
    return np.array(out)


def triangulate(sil):
    loops = contours(sil)
    verts, segs = [], []
    for lp in loops:
        base = len(verts)
        verts += list(lp)
        segs += [(base + i, base + (i + 1) % len(lp)) for i in range(len(lp))]
    verts += list(interior_points(sil, loops))
    data = {"vertices": np.array(verts), "segments": np.array(segs)}
    holes = hole_seeds(sil)
    if len(holes):
        data["holes"] = holes
    t = triangle.triangulate(data, f"pq28a{MAX_AREA}Y")
    V, T = t["vertices"], t["triangles"]
    # front faces counter-clockwise in xy (normal +z)
    a, b, c = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    cross = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    T[cross < 0] = T[cross < 0][:, ::-1]
    return V, T


# ---------------------------------------------------------------- mesh assembly
def build(height=HEIGHT):
    """Returns (sil, parts) where parts[name] = dict(pos, nrm, uv, polys)."""
    sil = Silhouette(height)
    V, T = triangulate(sil)
    x, y = V[:, 0], V[:, 1]
    h = np.maximum(sil.sample(sil.h, x, y), 0.025)
    hx, hy = sil.sample(sil.hx, x, y), sil.sample(sil.hy, x, y)
    g = np.hypot(hx, hy)
    lim = np.minimum(1.0, 7.0 / np.maximum(g, 1e-6))
    hx, hy = hx * lim, hy * lim
    nf = np.c_[-hx, -hy, np.ones_like(x)]
    nf /= np.linalg.norm(nf, axis=1)[:, None]
    nb = nf * [1, 1, -1]
    uv = sil.uv(x, y)

    # zone of every triangle (centroid)
    cen = V[T].mean(1)
    tz = sil.sample(sil.zone.astype(float), cen[:, 0], cen[:, 1], order=0).astype(int)
    tz[tz == 0] = HEAD

    # rim edges: used by exactly one triangle
    edges = {}
    for ti, tri in enumerate(T):
        for i in range(3):
            a, b = tri[i], tri[(i + 1) % 3]
            key = (min(a, b), max(a, b))
            edges.setdefault(key, []).append((ti, a, b))
    rim = [v[0] for v in edges.values() if len(v) == 1]

    # outward 2D normal per rim vertex
    rim_n = np.zeros((len(V), 2))
    for ti, a, b in rim:
        d = V[b] - V[a]
        n = np.array([d[1], -d[0]])            # right of a->b = outside for CCW triangles
        rim_n[a] += n
        rim_n[b] += n
    ln = np.linalg.norm(rim_n, axis=1)
    rim_n[ln > 0] /= ln[ln > 0][:, None]

    parts = {}
    for z, name in PART_NAMES.items():
        pos, nrm, uvs, polys = [], [], [], []
        remap_f, remap_b, remap_w = {}, {}, {}

        def vert(i, side):
            table = {"f": remap_f, "b": remap_b, "w+": remap_w, "w-": remap_w}[side]
            key = (i, side)
            if key in table:
                return table[key]
            if side == "f":
                p, n = (x[i], y[i], h[i]), nf[i]
            elif side == "b":
                p, n = (x[i], y[i], -h[i]), nb[i]
            else:
                p = (x[i], y[i], h[i] if side == "w+" else -h[i])
                n = (rim_n[i, 0], rim_n[i, 1], 0.0)
            table[key] = len(pos)
            pos.append(p)
            nrm.append(n)
            uvs.append(uv[i])
            return table[key]

        for ti in np.where(tz == z)[0]:
            a, b, c = T[ti]
            polys.append([vert(a, "f"), vert(b, "f"), vert(c, "f")])
            polys.append([vert(c, "b"), vert(b, "b"), vert(a, "b")])
        for ti, a, b in rim:
            if tz[ti] != z:
                continue
            # quad a->b on the front, back down: outward facing (CCW seen from outside)
            polys.append([vert(b, "w+"), vert(a, "w+"), vert(a, "w-"), vert(b, "w-")])
        parts[name] = {
            "pos": np.array(pos, float),
            "nrm": np.array(nrm, float),
            "uv": np.array(uvs, float),
            "polys": polys,
        }
    return sil, parts


def stats(parts):
    return {k: (len(v["pos"]), len(v["polys"])) for k, v in parts.items()}


if __name__ == "__main__":
    sil, parts = build()
    print(stats(parts), "bbox", sil.bbox)
