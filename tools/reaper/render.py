"""Tiny offline z-buffer renderer for previews (orthographic, textured, smooth shaded).

Items are dicts: {"pos": (N,3), "nrm": (N,3), "uv": (N,2) texture px, "polys": [[i..]],
"tex": np.ndarray HxWx3 float, optional "tint": (r,g,b)}; or flat-colour items with
"color" instead of "tex"/"uv". Coordinates are Blockbench space (y up, +z to viewer).
"""
import math

import numpy as np
from PIL import Image

BG = (238, 236, 232)


def rot(yaw, pitch):
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    return rx @ ry


def render(items, yaw=0, pitch=0, size=(600, 800), scale=None, centre=None, bg=BG,
           light=(-0.4, 0.7, 0.6), ss=2):
    W, H = size[0] * ss, size[1] * ss
    R = rot(yaw, pitch)
    allp = np.concatenate([it["pos"] for it in items]) @ R.T
    lo, hi = allp.min(0), allp.max(0)
    if centre is None:
        centre = (lo + hi) / 2
    else:
        centre = np.asarray(centre, float) @ R.T
    if scale is None:
        ext = hi - lo
        scale = min(W * 0.9 / max(ext[0], 1e-6), H * 0.9 / max(ext[1], 1e-6))
    else:
        scale *= ss
    img = np.zeros((H, W, 3)) + bg
    zbuf = np.full((H, W), -1e9)
    L = np.asarray(light, float)
    L /= np.linalg.norm(L)
    for it in items:
        P = it["pos"] @ R.T
        N = it["nrm"] @ R.T
        S = np.c_[(P[:, 0] - centre[0]) * scale + W / 2, (centre[1] - P[:, 1]) * scale + H / 2, P[:, 2]]
        tex = it.get("tex")
        for poly in it["polys"]:
            for k in range(1, len(poly) - 1):
                tri = [poly[0], poly[k], poly[k + 1]]
                if len(set(tri)) < 3:
                    continue
                _raster(img, zbuf, S[tri], N[tri], it["uv"][tri] if tex is not None else None,
                        tex, it.get("color"), L)
    out = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    return out.resize(size, Image.LANCZOS) if ss > 1 else out


def _raster(img, zbuf, S, N, UV, tex, color, L):
    H, W = zbuf.shape
    x0, x1 = max(int(S[:, 0].min()), 0), min(int(S[:, 0].max()) + 1, W - 1)
    y0, y1 = max(int(S[:, 1].min()), 0), min(int(S[:, 1].max()) + 1, H - 1)
    if x1 < x0 or y1 < y0:
        return
    ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1] + 0.5
    (ax, ay), (bx, by), (cx, cy) = S[0, :2], S[1, :2], S[2, :2]
    den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(den) < 1e-9:
        return
    w0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
    w1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
    w2 = 1 - w0 - w1
    inside = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
    if not inside.any():
        return
    z = w0 * S[0, 2] + w1 * S[1, 2] + w2 * S[2, 2]
    sub = zbuf[y0:y1 + 1, x0:x1 + 1]
    vis = inside & (z > sub)
    if not vis.any():
        return
    n = (w0[..., None] * N[0] + w1[..., None] * N[1] + w2[..., None] * N[2])[vis]
    n /= np.linalg.norm(n, axis=1)[:, None] + 1e-9
    n[n[:, 2] < 0] *= -1                      # two-sided like entity_alphatest
    diff = np.clip(n @ L, 0, 1)
    hv = L + np.array([0, 0, 1.0])
    hv /= np.linalg.norm(hv)
    spec = np.clip(n @ hv, 0, 1) ** 28 * 0.35
    shade = (0.42 + 0.62 * diff)[:, None]
    if tex is not None:
        th, tw = tex.shape[:2]
        u = (w0 * UV[0, 0] + w1 * UV[1, 0] + w2 * UV[2, 0])[vis]
        v = (w0 * UV[0, 1] + w1 * UV[1, 1] + w2 * UV[2, 1])[vis]
        c = tex[np.clip(v.astype(int), 0, th - 1), np.clip(u.astype(int), 0, tw - 1)]
    else:
        c = np.asarray(color, float)[None].repeat(vis.sum(), 0)
    sub[vis] = z[vis]
    img[y0:y1 + 1, x0:x1 + 1][vis] = c * shade + spec[:, None] * 255


def sheet(images, bg=BG):
    w = sum(i.width for i in images)
    h = max(i.height for i in images)
    out = Image.new("RGB", (w, h), bg)
    x = 0
    for i in images:
        out.paste(i, (x, 0))
        x += i.width
    return out
