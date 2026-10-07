#!/usr/bin/env python3
"""Build the Crimson Thorn Scythe as a cube-based Bedrock geometry (.geo.json)
that opens directly in Blockbench (Bedrock Entity / Bedrock Model).

Blockbench's Bedrock formats do not import `poly_mesh`, so the scythe is built
from axis-aligned cubes:

1. The scythe is cut out of the reference art (scythe/reference/scythe_ref.jpg).
2. The cutout is rotated so the shaft stands upright, scaled to model pixels and
   sampled on a 0.25 px grid.
3. Each grid cell gets a half-thickness from its distance to the silhouette edge
   (thin blade edge, round shaft, chunky head and pommel). Thickness is split into
   stacked layers and every layer is greedy-merged into as few cubes as possible.
4. The texture is the cleaned-up artwork projected straight onto the front and
   back faces, so the painted detail lines up across all cubes. Side faces sample
   the colour along the cube's edge.

Coordinates below are Blockbench's (x right, y up, south face = +z). The JSON
writer converts to Bedrock's mirrored x on export, the same way Blockbench does.

Run:  python3 tools/build_scythe.py
"""
import json
import math
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = os.path.join(ROOT, "scythe", "reference", "scythe_ref.jpg")
OUT = os.path.join(ROOT, "scythe")
NAME = "crimson_scythe"
GEO_ID = "geometry.idex.crimson_scythe"

ANGLE = 33.2        # deg, rotates the reference so the shaft is vertical
HEIGHT = 52.0       # model px from pommel tip to the top of the head (~3.25 blocks)
G = 0.25            # grid cell (model px)
TPC = 4             # texture px per cell -> 16 texture px per model px
LAYER = 0.125       # thickness step (half-depth, model px)

# zone ids -> bone names
BLADE, HEAD, SHAFT, POMMEL = 1, 2, 3, 4
BONES = {BLADE: "blade", HEAD: "head", SHAFT: "shaft", POMMEL: "pommel"}

# half-depth = clip(a + b * dist_to_edge, lo, hi) per zone (model px)
DEPTH = {
    BLADE: (0.10, 0.55, 0.125, 0.375),
    HEAD: (0.15, 0.55, 0.125, 1.125),
    SHAFT: (0.30, 0.75, 0.25, 0.75),
    POMMEL: (0.20, 0.65, 0.125, 0.875),
}


# ---------------------------------------------------------------- cutout
def cutout(im):
    lum = im @ [0.299, 0.587, 0.114]
    sat = im.max(2) - im.min(2)
    strong = (lum < 175) | (sat > 55)
    weak = (lum < 218) | (sat > 30)
    strong[930:, 560:] = False      # watermark corner
    weak[930:, 560:] = False
    lab, _ = ndi.label(weak)
    ids = np.unique(lab[strong])
    m = np.isin(lab, ids[ids > 0])
    lab, n = ndi.label(m)
    sz = ndi.sum(m, lab, range(1, n + 1))
    m = np.isin(lab, 1 + np.where(sz > 300)[0])
    yy, xx = np.mgrid[-4:5, -4:5]
    m = ndi.binary_closing(np.pad(m, 8), (xx ** 2 + yy ** 2) <= 16)[8:-8, 8:-8]
    m = ndi.binary_fill_holes(m)
    m = ndi.binary_opening(m, np.ones((2, 2)))
    lab, n = ndi.label(m)
    sz = ndi.sum(m, lab, range(1, n + 1))
    return np.isin(lab, 1 + np.argmax(sz))


def zones(shape):
    h, w = shape
    y, x = np.mgrid[0:h, 0:w]
    z = np.full(shape, HEAD, np.uint8)
    z[(y < 165) & (x < 505)] = BLADE
    z[(y > 330) & (y <= 705) & ~((x > 460) & (y < 345))] = SHAFT
    z[y > 705] = POMMEL
    return z


def fill_outside(img, mask):
    """Replace every pixel outside the mask with the nearest pixel inside it."""
    _, (iy, ix) = ndi.distance_transform_edt(~mask, return_indices=True)
    return img[iy, ix]


def grade(img):
    """Slightly deeper blacks and richer reds than the soft JPEG."""
    f = img / 255.0
    lum = f @ [0.299, 0.587, 0.114]
    red = np.clip((f[..., 0] - np.maximum(f[..., 1], f[..., 2])) * 2.0, 0, 1)[..., None]
    f = np.clip((f - 0.5) * 1.12 + 0.5 - 0.03 * (lum < 0.35)[..., None], 0, 1)
    f = f * (1 - 0.25 * red) + red * 0.25 * np.array([0.86, 0.05, 0.08])
    return (np.clip(f, 0, 1) * 255).astype(np.uint8)


# ---------------------------------------------------------------- grid
def build_grid():
    src = np.asarray(Image.open(REF).convert("RGB")).astype(float)
    mask = cutout(src)
    col = grade(fill_outside(src, mask))
    zone = zones(mask.shape)

    rot = lambda im, rs: im.rotate(ANGLE, resample=rs, expand=True)
    m_r = np.asarray(rot(Image.fromarray((mask * 255).astype(np.uint8)), Image.BILINEAR)) / 255.0
    z_r = np.asarray(rot(Image.fromarray(zone), Image.NEAREST))
    c_r = rot(Image.fromarray(col), Image.BICUBIC)

    ys, xs = np.nonzero(m_r > 0.5)
    k = HEIGHT / (ys.max() - ys.min())               # model px per rotated image px
    shaft_x = xs[z_r[ys, xs] == SHAFT].mean()
    bottom = ys.max()
    to_px = lambda x, y: (shaft_x + x / k, bottom - y / k)   # model -> rotated image

    x_min = math.floor((xs.min() - shaft_x) * k / G - 2) * G
    x_max = math.ceil((xs.max() - shaft_x) * k / G + 2) * G
    y_max = math.ceil((bottom - ys.min()) * k / G + 2) * G
    y_min = -2 * G
    ncol, nrow = round((x_max - x_min) / G), round((y_max - y_min) / G)
    box = (*to_px(x_min, y_max), *to_px(x_max, y_min))

    cover = np.asarray(Image.fromarray((m_r * 255).astype(np.uint8)).resize(
        (ncol, nrow), Image.BOX, box=box)) / 255.0
    zone_c = np.asarray(Image.fromarray(z_r).resize((ncol, nrow), Image.NEAREST, box=box))
    tex = c_r.resize((ncol * TPC, nrow * TPC), Image.LANCZOS, box=box)

    cells = cover > 0.5
    lab, n = ndi.label(cells)
    sz = ndi.sum(cells, lab, range(1, n + 1))
    cells = lab == 1 + np.argmax(sz)
    zone_c = np.where(cells, zone_c, 0)
    # cells whose zone came out empty at the rim take the nearest zone
    _, (iy, ix) = ndi.distance_transform_edt(zone_c == 0, return_indices=True)
    zone_c = np.where(cells, zone_c[iy, ix], 0)

    # texture: re-fill everything outside the cutout so cube rims never pick up white
    tex_mask = np.asarray(Image.fromarray(cells).resize(tex.size, Image.NEAREST)).copy()
    tex_mask &= np.asarray(Image.fromarray((m_r * 255).astype(np.uint8)).resize(
        tex.size, Image.BILINEAR, box=box)) > 96
    tex = Image.fromarray(fill_outside(np.asarray(tex), tex_mask))
    return cells, zone_c, tex, (x_min, y_max), k


def half_depth(cells, zone_c):
    dist = ndi.distance_transform_edt(np.pad(cells, 1))[1:-1, 1:-1] * G - G / 2
    h = np.zeros(cells.shape)
    for z, (a, b, lo, hi) in DEPTH.items():
        sel = cells & (zone_c == z)
        h[sel] = np.clip(a + b * dist[sel], lo, hi)
    h = ndi.median_filter(h, 3) * cells
    h = np.where(cells, np.maximum(np.round(h / LAYER) * LAYER, LAYER), 0)
    return h


def greedy_rects(grid):
    """Merge a boolean grid into rectangles (r0, c0, r1, c1), end-exclusive."""
    g = grid.copy()
    out = []
    nr, nc = g.shape
    for r in range(nr):
        c = 0
        while c < nc:
            if not g[r, c]:
                c += 1
                continue
            c1 = c
            while c1 < nc and g[r, c1]:
                c1 += 1
            r1 = r + 1
            while r1 < nr and g[r1, c:c1].all():
                r1 += 1
            g[r:r1, c:c1] = False
            out.append((r, c, r1, c1))
            c = c1
    return out


def build_cubes(cells, zone_c, h, origin):
    x0, y_top = origin
    cubes = []
    levels = np.unique(h[cells])
    for li, lv in enumerate(levels):
        layer = h >= lv - 1e-9
        if li:
            # drop specks so upper layers stay clean
            lab, n = ndi.label(layer)
            sz = ndi.sum(layer, lab, range(1, n + 1))
            layer = np.isin(lab, 1 + np.where(sz >= 3)[0])
        for z in BONES:
            for r0, c0, r1, c1 in greedy_rects(layer & (zone_c == z)):
                cubes.append({
                    "bone": BONES[z],
                    "from": [x0 + c0 * G, y_top - r1 * G, -lv],
                    "to": [x0 + c1 * G, y_top - r0 * G, lv],
                    "tex": [c0 * TPC, r0 * TPC, c1 * TPC, r1 * TPC],
                })
    return cubes


# ---------------------------------------------------------------- export
def face_uvs(t):
    """Per-face UVs in Blockbench terms: (u0, v0, u1, v1) on the texture."""
    u0, v0, u1, v1 = t
    return {
        "south": (u0, v0, u1, v1),
        "north": (u1, v0, u0, v1),      # mirrored so the art lines up through the model
        "east": (u1 - 1, v0, u1, v1),
        "west": (u0, v0, u0 + 1, v1),
        "up": (u0, v0, u1, v0 + 1),
        "down": (u0, v1 - 1, u1, v1),
    }


def r4(v):
    v = round(v, 4)
    return int(v) if v == int(v) else v


def geo_json(cubes, tex_size):
    bones = [{"name": "scythe", "pivot": [0, 0, 0]}]
    by_bone = {}
    for c in cubes:
        f, t = c["from"], c["to"]
        size = [t[i] - f[i] for i in range(3)]
        uv = {}
        for key, (a, b, cc, d) in face_uvs(c["tex"]).items():
            if key in ("up", "down"):      # Bedrock stores up/down flipped (as Blockbench exports)
                uv[key] = {"uv": [r4(cc), r4(d)], "uv_size": [r4(a - cc), r4(b - d)]}
            else:
                uv[key] = {"uv": [r4(a), r4(b)], "uv_size": [r4(cc - a), r4(d - b)]}
        by_bone.setdefault(c["bone"], []).append({
            "origin": [r4(-t[0]), r4(f[1]), r4(f[2])],   # Bedrock x is mirrored
            "size": [r4(s) for s in size],
            "uv": uv,
        })
    for name in ("shaft", "pommel", "head", "blade"):
        bones.append({"name": name, "parent": "scythe", "pivot": [0, 0, 0],
                      "cubes": by_bone.get(name, [])})
    xs = [v for c in cubes for v in (c["from"][0], c["to"][0])]
    ys = [v for c in cubes for v in (c["from"][1], c["to"][1])]
    span = max(max(map(abs, xs)), max(ys)) / 16
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {
                "identifier": GEO_ID,
                "texture_width": tex_size[0],
                "texture_height": tex_size[1],
                "visible_bounds_width": math.ceil(span * 2 + 1),
                "visible_bounds_height": math.ceil(span * 2 + 1),
                "visible_bounds_offset": [0, round(max(ys) / 32, 2), 0],
            },
            "bones": bones,
        }],
    }


def write_geo(path, geo):
    """Compact JSON: one cube per line, still readable."""
    lines = ["{", '\t"format_version": "1.12.0",', '\t"minecraft:geometry": [', "\t\t{"]
    g = geo["minecraft:geometry"][0]
    lines.append('\t\t\t"description": ' + json.dumps(g["description"]) + ",")
    lines.append('\t\t\t"bones": [')
    for bi, b in enumerate(g["bones"]):
        head = {k: v for k, v in b.items() if k != "cubes"}
        if "cubes" not in b:
            lines.append("\t\t\t\t" + json.dumps(head) + ",")
            continue
        s = json.dumps(head)[:-1] + ', "cubes": ['
        lines.append("\t\t\t\t" + s)
        for ci, c in enumerate(b["cubes"]):
            lines.append("\t\t\t\t\t" + json.dumps(c, separators=(",", ":"))
                         + ("," if ci < len(b["cubes"]) - 1 else ""))
        lines.append("\t\t\t\t]}" + ("," if bi < len(g["bones"]) - 1 else ""))
    lines += ["\t\t\t]", "\t\t}", "\t]", "}"]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    json.load(open(path))   # sanity


# ---------------------------------------------------------------- preview
def rot_m(yaw, pitch):
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    return rx @ ry


FACES = {  # corner order: (top-left, top-right, bottom-right, bottom-left) as seen from outside
    "south": ([0, 1, 1], [1, 1, 1], [1, 0, 1], [0, 0, 1]),
    "north": ([1, 1, 0], [0, 1, 0], [0, 0, 0], [1, 0, 0]),
    "east": ([1, 1, 1], [1, 1, 0], [1, 0, 0], [1, 0, 1]),
    "west": ([0, 1, 0], [0, 1, 1], [0, 0, 1], [0, 0, 0]),
    "up": ([0, 1, 0], [1, 1, 0], [1, 1, 1], [0, 1, 1]),
    "down": ([0, 0, 1], [1, 0, 1], [1, 0, 0], [0, 0, 0]),
}
NORMALS = {"south": (0, 0, 1), "north": (0, 0, -1), "east": (1, 0, 0),
           "west": (-1, 0, 0), "up": (0, 1, 0), "down": (0, -1, 0)}


def render(cubes, tex, yaw=0, pitch=0, size=(560, 900), scale=None, bg=(246, 244, 240)):
    tex = np.asarray(tex.convert("RGB")).astype(float)
    th, tw = tex.shape[:2]
    R = rot_m(yaw, pitch)
    W, H = size
    pts = np.array([[c[k][i] for k in ("from", "to") for i in range(3)] for c in cubes])
    lo = pts.reshape(-1, 2, 3).min(1).min(0)
    hi = pts.reshape(-1, 2, 3).max(1).max(0)
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    pc = corners @ R.T
    centre = (pc.min(0) + pc.max(0)) / 2
    if scale is None:
        ext = pc.max(0) - pc.min(0)
        scale = min(W * 0.9 / ext[0], H * 0.9 / ext[1])
    img = np.zeros((H, W, 3)) + bg
    zbuf = np.full((H, W), -1e9)
    light = np.array([-0.45, 0.65, 0.62])
    light /= np.linalg.norm(light)
    for c in cubes:
        f, t = np.array(c["from"]), np.array(c["to"])
        for key, quad in FACES.items():
            n = R @ np.array(NORMALS[key], float)
            if n[2] <= 0:
                continue
            P = np.array([f + (t - f) * np.array(q) for q in quad]) @ R.T
            S = np.c_[(P[:, 0] - centre[0]) * scale + W / 2, (centre[1] - P[:, 1]) * scale + H / 2, P[:, 2]]
            u0, v0, u1, v1 = face_uvs(c["tex"])[key]
            UV = np.array([[u0, v0], [u1, v0], [u1, v1], [u0, v1]], float)
            shade = 0.55 + 0.45 * max(0.0, float(n @ light))
            for tri in ((0, 1, 2), (0, 2, 3)):
                raster(img, zbuf, S[list(tri)], UV[list(tri)], tex, tw, th, shade)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def raster(img, zbuf, S, UV, tex, tw, th, shade):
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
    u = w0 * UV[0, 0] + w1 * UV[1, 0] + w2 * UV[2, 0]
    v = w0 * UV[0, 1] + w1 * UV[1, 1] + w2 * UV[2, 1]
    ui = np.clip(u.astype(int), 0, tw - 1)
    vi = np.clip(v.astype(int), 0, th - 1)
    sub[vis] = z[vis]
    img[y0:y1 + 1, x0:x1 + 1][vis] = tex[vi[vis], ui[vis]] * shade


def main():
    cells, zone_c, tex, origin, k = build_grid()
    h = half_depth(cells, zone_c)
    cubes = build_cubes(cells, zone_c, h, origin)
    os.makedirs(OUT, exist_ok=True)
    tex.save(os.path.join(OUT, NAME + ".png"))
    write_geo(os.path.join(OUT, NAME + ".geo.json"), geo_json(cubes, tex.size))

    counts = {}
    for c in cubes:
        counts[c["bone"]] = counts.get(c["bone"], 0) + 1
    xs = [v for c in cubes for v in (c["from"][0], c["to"][0])]
    ys = [v for c in cubes for v in (c["from"][1], c["to"][1])]
    print(f"cubes: {len(cubes)} {counts}")
    print(f"size: x {min(xs):.2f}..{max(xs):.2f}  y {min(ys):.2f}..{max(ys):.2f}  "
          f"max depth {2 * h.max():.2f} px   texture {tex.size}")

    prev = os.path.join(OUT, "preview")
    os.makedirs(prev, exist_ok=True)
    front = render(cubes, tex, 0, 0)
    angled = render(cubes, tex, 35, 12)
    side = render(cubes, tex, 90, 0, size=(240, 900))
    sheet = Image.new("RGB", (front.width + angled.width + side.width, front.height), (246, 244, 240))
    sheet.paste(front, (0, 0))
    sheet.paste(angled, (front.width, 0))
    sheet.paste(side, (front.width + angled.width, 0))
    sheet.save(os.path.join(prev, "scythe_views.png"))
    render(cubes, tex, -30, 25, size=(900, 900)).save(os.path.join(prev, "scythe_back.png"))


if __name__ == "__main__":
    main()
