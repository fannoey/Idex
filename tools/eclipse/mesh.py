"""Tiny quad-mesh builder for Bedrock poly_mesh + an offline preview renderer.

Parts are authored in a local sword frame:
    a = along the blade (tip is +a), b = across the blade (in the blade plane),
    c = blade thickness.
A Mesh stores quads with per-vertex position / normal / uv, so it maps 1:1
onto Bedrock's poly_mesh (positions, normals, uvs, polys).
"""
import math

import numpy as np


class Mesh:
    def __init__(self):
        self.P = []      # list of (N,3) arrays
        self.Nrm = []
        self.UV = []
        self.Q = []      # list of (M,4) index arrays
        self.count = 0

    # ---------------------------------------------------------------- core
    def add_grid(self, pts, nrm, uv, wrap=False):
        """pts/nrm: (I,J,3), uv: (I,J,2). Quads between consecutive rows/cols.
        wrap=True closes the J direction (the last column must NOT duplicate the first
        for positions; uv continuity is handled by passing J+1 columns with wrap=False)."""
        I, J = pts.shape[:2]
        base = self.count
        self.P.append(pts.reshape(-1, 3))
        self.Nrm.append(nrm.reshape(-1, 3))
        self.UV.append(uv.reshape(-1, 2))
        self.count += I * J
        idx = np.arange(I * J).reshape(I, J) + base
        jmax = J if wrap else J - 1
        quads = []
        for i in range(I - 1):
            for j in range(jmax):
                j2 = (j + 1) % J
                quads.append((idx[i, j], idx[i + 1, j], idx[i + 1, j2], idx[i, j2]))
        if quads:
            self.Q.append(np.array(quads, dtype=np.int64))

    def merge(self, other):
        base = self.count
        self.P += other.P
        self.Nrm += other.Nrm
        self.UV += other.UV
        self.Q += [q + base for q in other.Q]
        self.count += other.count

    def arrays(self):
        P = np.concatenate(self.P) if self.P else np.zeros((0, 3))
        N = np.concatenate(self.Nrm) if self.Nrm else np.zeros((0, 3))
        UV = np.concatenate(self.UV) if self.UV else np.zeros((0, 2))
        Q = np.concatenate(self.Q) if self.Q else np.zeros((0, 4), dtype=np.int64)
        return P, N, UV, Q

    def transformed(self, fn_pos, fn_nrm):
        m = Mesh()
        P, N, UV, Q = self.arrays()
        m.P = [fn_pos(P)]
        n = fn_nrm(N)
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
        m.Nrm = [n]
        m.UV = [UV.copy()]
        m.Q = [Q.copy()]
        m.count = len(P)
        return m

    @property
    def quad_count(self):
        return sum(len(q) for q in self.Q)


# ------------------------------------------------------------------ normals

def grid_normals(pts, wrap=False, center=None, flip=False):
    """Normals of a (I,J,3) grid via central differences.
    wrap: J direction is closed (columns 0..J-1 unique, or last == first if dup).
    center: optional (I,3) or (3,) points used to orient normals outward."""
    I, J = pts.shape[:2]
    if wrap:
        dj = np.roll(pts, -1, axis=1) - np.roll(pts, 1, axis=1)
    else:
        dj = np.gradient(pts, axis=1)
    di = np.gradient(pts, axis=0) if I > 1 else np.zeros_like(pts)
    n = np.cross(dj, di)
    ln = np.linalg.norm(n, axis=2, keepdims=True)
    # rows that collapse to a point: borrow from neighbours
    bad = ln[..., 0] < 1e-9
    n = n / np.maximum(ln, 1e-12)
    for i in range(I):
        if bad[i].all():
            src = i + 1 if i + 1 < I else i - 1
            n[i] = n[src]
    if center is not None:
        c = np.asarray(center)
        if c.ndim == 1:
            c = np.broadcast_to(c, (I, 3))
        out = pts - c[:, None, :]
        s = np.sign(np.sum(out * n, axis=2, keepdims=True))
        s[s == 0] = 1
        n = n * s
    if flip:
        n = -n
    return n


def map_uv(u, v, region, atlas_w, atlas_h):
    """u,v in 0..1 inside region (x0,y0,x1,y1) of the content area (top half)."""
    x0, y0, x1, y1 = region
    pad = 0.5
    U = (x0 + pad + np.asarray(u) * (x1 - x0 - 2 * pad)) / atlas_w
    V = (y0 + pad + np.asarray(v) * (y1 - y0 - 2 * pad)) / atlas_h
    return np.stack([U, V], axis=-1)


# -------------------------------------------------------------- primitives

def superellipse(phi, hy, hz, n=2.0):
    s, c = np.sin(phi), np.cos(phi)
    return hy * np.sign(s) * np.abs(s) ** (2 / n), hz * np.sign(c) * np.abs(c) ** (2 / n)


def loft(stations, half_b, half_c, n_around, region, uvc, power=2.0, ring_fn=None, center_fn=None):
    """Closed loft along +a. half_b/half_c: callables of a. Returns Mesh.
    The loop has a duplicated seam column for continuous UVs."""
    a = np.asarray(stations, dtype=float)
    J = n_around
    phi = -math.pi / 2 + 2 * math.pi * np.arange(J + 1) / J
    pts = np.zeros((len(a), J + 1, 3))
    for i, ai in enumerate(a):
        hb, hc = half_b(ai), half_c(ai)
        y, z = superellipse(phi, hb, hc, power)
        cb, cc = (center_fn(ai) if center_fn else (0.0, 0.0))
        pts[i, :, 0] = ai
        pts[i, :, 1] = y + cb
        pts[i, :, 2] = z + cc
    centers = np.stack([a, np.array([center_fn(x)[0] if center_fn else 0 for x in a]),
                        np.array([center_fn(x)[1] if center_fn else 0 for x in a])], axis=1)
    nrm = grid_normals(pts[:, :J], wrap=True, center=centers)
    nrm = np.concatenate([nrm, nrm[:, :1]], axis=1)
    u = (a - a.min()) / max(np.ptp(a), 1e-9)
    U, V = np.meshgrid(u, np.arange(J + 1) / J, indexing="ij")
    m = Mesh()
    m.add_grid(pts, nrm, map_uv(U, V, region, *uvc))
    return m


def blade(stations, half_w, half_t, region, uvc, ridge_frac=0.0):
    """Diamond-section blade made of 4 strips (hard edges at ridge and cutting edges).
    UV: u along length, v from edge (0) to ridge (1)."""
    a = np.asarray(stations, dtype=float)
    L = a.max()
    m = Mesh()
    for sb in (1, -1):
        for sc in (1, -1):
            pts = np.zeros((len(a), 3, 3))
            for i, ai in enumerate(a):
                w, t = half_w(ai), half_t(ai)
                edge = (ai, sb * w, 0.0)
                mid = (ai, sb * w * 0.45, sc * t * 0.82)
                ridge = (ai, 0.0, sc * t)
                pts[i] = [edge, mid, ridge]
            # flat-ish strip normal
            nrm = grid_normals(pts)
            out = np.zeros_like(pts)
            out[..., 1] = sb
            out[..., 2] = sc * 2.0
            s = np.sign(np.sum(nrm * out, axis=2, keepdims=True))
            s[s == 0] = 1
            nrm = nrm * s
            u = a / L
            U, V = np.meshgrid(u, np.array([0.0, 0.55, 1.0]), indexing="ij")
            m.add_grid(pts, nrm, map_uv(U, V, region, *uvc))
    return m


def torus(center, axis_u, axis_v, R, r, n_major, n_minor, region, uvc, arc=(0, 2 * math.pi)):
    """Torus in the plane spanned by axis_u/axis_v (local frame vectors)."""
    center, au, av = (np.asarray(x, float) for x in (center, axis_u, axis_v))
    an = np.cross(au, av)
    closed = abs(arc[1] - arc[0] - 2 * math.pi) < 1e-6
    I = n_major + 1
    th = arc[0] + (arc[1] - arc[0]) * np.arange(I) / n_major
    ph = 2 * math.pi * np.arange(n_minor + 1) / n_minor
    TH, PH = np.meshgrid(th, ph, indexing="ij")
    radial = np.cos(TH)[..., None] * au + np.sin(TH)[..., None] * av
    nrm = np.cos(PH)[..., None] * radial + np.sin(PH)[..., None] * an
    pts = center + R * radial + r * nrm
    U, V = np.meshgrid(np.arange(I) / n_major, np.arange(n_minor + 1) / n_minor, indexing="ij")
    m = Mesh()
    m.add_grid(pts, nrm, map_uv(U, V, region, *uvc))
    return m


def ellipsoid(center, radii, nu, nv, region, uvc, axes=None):
    center = np.asarray(center, float)
    ax = np.eye(3) if axes is None else np.asarray(axes, float)
    th = math.pi * np.arange(nv + 1) / nv                 # pole to pole
    ph = 2 * math.pi * np.arange(nu + 1) / nu
    TH, PH = np.meshgrid(th, ph, indexing="ij")
    unit = np.stack([np.cos(TH), np.sin(TH) * np.cos(PH), np.sin(TH) * np.sin(PH)], -1)
    local = unit * np.asarray(radii)
    pts = center + local @ ax
    nrm_local = unit / np.asarray(radii)
    nrm = nrm_local @ ax
    nrm /= np.maximum(np.linalg.norm(nrm, axis=-1, keepdims=True), 1e-9)
    U, V = np.meshgrid(np.arange(nv + 1) / nv, np.arange(nu + 1) / nu, indexing="ij")
    m = Mesh()
    m.add_grid(pts, nrm, map_uv(V, U, region, *uvc))
    return m


def frames_along(path, up_hint=None):
    """Parallel-transport frames (T, N, B) along a polyline (K,3)."""
    path = np.asarray(path, float)
    K = len(path)
    T = np.gradient(path, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    N = np.zeros_like(T)
    ref = np.array([0.0, 0.0, 1.0]) if up_hint is None else np.asarray(up_hint, float)
    n0 = np.cross(T[0], ref)
    if np.linalg.norm(n0) < 1e-6:
        n0 = np.cross(T[0], [0, 1, 0])
    N[0] = n0 / np.linalg.norm(n0)
    for k in range(1, K):
        v = N[k - 1] - np.dot(N[k - 1], T[k]) * T[k]
        nv = np.linalg.norm(v)
        N[k] = v / nv if nv > 1e-9 else N[k - 1]
    B = np.cross(T, N)
    return T, N, B


def tube(path, radius, n_sides, region, uvc, flat=1.0, normal_fn=None, up_hint=None):
    """Tube along a polyline. radius: array (K,) or scalar. flat<1 squashes the
    section along N (ribbon). normal_fn(k) -> preferred N direction (optional)."""
    path = np.asarray(path, float)
    K = len(path)
    rad = np.broadcast_to(np.asarray(radius, float), (K,))
    T, N, B = frames_along(path, up_hint)
    if normal_fn is not None:
        for k in range(K):
            pref = np.asarray(normal_fn(k), float)
            v = pref - np.dot(pref, T[k]) * T[k]
            if np.linalg.norm(v) > 1e-6:
                N[k] = v / np.linalg.norm(v)
        B = np.cross(T, N)
    ph = 2 * math.pi * np.arange(n_sides + 1) / n_sides
    cs, sn = np.cos(ph), np.sin(ph)
    offs = (cs[None, :, None] * N[:, None, :] * flat + sn[None, :, None] * B[:, None, :])
    pts = path[:, None, :] + rad[:, None, None] * offs
    nrm_dir = cs[None, :, None] * N[:, None, :] / max(flat, 1e-3) + sn[None, :, None] * B[:, None, :]
    nrm = nrm_dir / np.maximum(np.linalg.norm(nrm_dir, axis=-1, keepdims=True), 1e-9)
    seglen = np.r_[0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
    u = seglen / max(seglen[-1], 1e-9)
    U, V = np.meshgrid(u, np.arange(n_sides + 1) / n_sides, indexing="ij")
    m = Mesh()
    m.add_grid(pts, nrm, map_uv(U, V, region, *uvc))
    return m


def lens_strip(center_ab, half_width, thickness, n_len, n_across, region, uvc, c0=0.0):
    """Flat lens-section strip in the a-b plane following a 2D curve.
    center_ab(s)->(a,b); half_width(s), thickness(s) half thickness (c)."""
    s = np.linspace(0, 1, n_len)
    C = np.array([center_ab(x) for x in s])
    d = np.gradient(C, axis=0)
    d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
    perp = np.stack([-d[:, 1], d[:, 0]], 1)       # in-plane normal
    x = np.linspace(-1, 1, n_across + 1)
    m = Mesh()
    for side in (1, -1):
        pts = np.zeros((n_len, n_across + 1, 3))
        for i in range(n_len):
            w = half_width(s[i])
            t = thickness(s[i])
            prof = np.sqrt(np.clip(1 - x * x, 0, 1))
            pts[i, :, 0] = C[i, 0] + perp[i, 0] * w * x
            pts[i, :, 1] = C[i, 1] + perp[i, 1] * w * x
            pts[i, :, 2] = c0 + side * t * prof
        nrm = grid_normals(pts)
        # orient: +c side up
        sgn = np.sign(nrm[..., 2:3] * side)
        sgn[sgn == 0] = 1
        nrm = nrm * sgn
        U, V = np.meshgrid(s, (x + 1) / 2, indexing="ij")
        m.add_grid(pts, nrm, map_uv(U, V, region, *uvc))
    return m


# ------------------------------------------------------------- rasterizer

def render(meshes, view_rot, size=(512, 512), scale=None, center=None, light=(0.4, 0.8, 0.6),
           bg=(20, 12, 34), supersample=2):
    """meshes: list of (Mesh, texture HxWx4 float, emissive_from_alpha bool).
    view_rot: 3x3 rotation (model -> camera, camera looks along -z).
    Returns RGBA uint8 image and alpha mask."""
    W, H = size[0] * supersample, size[1] * supersample
    allP = np.concatenate([m.arrays()[0] for m, _, _ in meshes]) @ view_rot.T
    lo, hi = allP.min(0), allP.max(0)
    if center is None:
        center = (lo + hi) / 2
    if scale is None:
        scale = 0.9 * min(W / max(hi[0] - lo[0], 1e-6), H / max(hi[1] - lo[1], 1e-6))
    else:
        scale = scale * supersample
    img = np.zeros((H, W, 3))
    img[:] = np.asarray(bg) / 255.0
    zbuf = np.full((H, W), -np.inf)
    mask = np.zeros((H, W))
    L = np.asarray(light, float)
    L /= np.linalg.norm(L)
    for mesh, tex, emissive in meshes:
        P, N, UV, Q = mesh.arrays()
        Pc = P @ view_rot.T
        Nc = N @ view_rot.T
        sx = (Pc[:, 0] - center[0]) * scale + W / 2
        sy = -(Pc[:, 1] - center[1]) * scale + H / 2
        sz = Pc[:, 2]
        th, tw = tex.shape[:2]
        for q in Q:
            for tri in ((q[0], q[1], q[2]), (q[0], q[2], q[3])):
                _raster_tri(tri, sx, sy, sz, Nc, UV, tex, tw, th, emissive, img, zbuf, mask, L)
    out = np.clip(img, 0, 1)
    if supersample > 1:
        out = out.reshape(size[1], supersample, size[0], supersample, 3).mean(axis=(1, 3))
        mask = mask.reshape(size[1], supersample, size[0], supersample).mean(axis=(1, 3))
    return (out * 255).astype(np.uint8), mask


def _raster_tri(tri, sx, sy, sz, Nc, UV, tex, tw, th, emissive, img, zbuf, mask, L):
    i0, i1, i2 = tri
    x0, y0, x1, y1, x2, y2 = sx[i0], sy[i0], sx[i1], sy[i1], sx[i2], sy[i2]
    minx, maxx = int(max(0, math.floor(min(x0, x1, x2)))), int(min(img.shape[1] - 1, math.ceil(max(x0, x1, x2))))
    miny, maxy = int(max(0, math.floor(min(y0, y1, y2)))), int(min(img.shape[0] - 1, math.ceil(max(y0, y1, y2))))
    if minx > maxx or miny > maxy:
        return
    den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    if abs(den) < 1e-12:
        return
    xs = np.arange(minx, maxx + 1) + 0.5
    ys = np.arange(miny, maxy + 1) + 0.5
    X, Y = np.meshgrid(xs, ys)
    w0 = ((y1 - y2) * (X - x2) + (x2 - x1) * (Y - y2)) / den
    w1 = ((y2 - y0) * (X - x2) + (x0 - x2) * (Y - y2)) / den
    w2 = 1 - w0 - w1
    inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
    if not inside.any():
        return
    z = w0 * sz[i0] + w1 * sz[i1] + w2 * sz[i2]
    zb = zbuf[miny:maxy + 1, minx:maxx + 1]
    vis = inside & (z > zb)
    if not vis.any():
        return
    n = (w0[..., None] * Nc[i0] + w1[..., None] * Nc[i1] + w2[..., None] * Nc[i2])
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9)
    uv = w0[..., None] * UV[i0] + w1[..., None] * UV[i1] + w2[..., None] * UV[i2]
    tx = np.clip((uv[..., 0] * tw).astype(int), 0, tw - 1)
    ty = np.clip((uv[..., 1] * th).astype(int), 0, th - 1)
    texel = tex[ty, tx]
    col = texel[..., :3]
    ndl = np.abs(np.sum(n * L, axis=-1))
    spec = np.clip(np.sum(n * (L + np.array([0, 0, 1])) / np.linalg.norm(L + np.array([0, 0, 1])), axis=-1), 0, 1) ** 24
    lit = col * (0.38 + 0.72 * ndl[..., None]) + 0.35 * spec[..., None]
    if emissive:
        glow = 1 - texel[..., 3:4]
        lit = lit * (1 - glow) + col * glow * 1.05
    region = img[miny:maxy + 1, minx:maxx + 1]
    region[vis] = lit[vis]
    zb[vis] = z[vis]
    mask[miny:maxy + 1, minx:maxx + 1][vis] = 1.0


def rot_y(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_x(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_z(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
