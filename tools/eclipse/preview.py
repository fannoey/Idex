"""Offline preview renders (model space with a player stand-in, close-ups, icons)."""
import numpy as np
from PIL import Image

from mesh import Mesh, render, rot_x, rot_y


def box(lo, hi, color_uv):
    """Axis-aligned box as 6 quads using a single uv point (solid colour)."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    m = Mesh()
    faces = [
        ((0, -1), [(lo[0], lo[1], lo[2]), (hi[0], lo[1], lo[2]), (hi[0], hi[1], lo[2]), (lo[0], hi[1], lo[2])]),
        ((0, 1), [(lo[0], lo[1], hi[2]), (lo[0], hi[1], hi[2]), (hi[0], hi[1], hi[2]), (hi[0], lo[1], hi[2])]),
        ((1, -1), [(lo[0], lo[1], lo[2]), (lo[0], hi[1], lo[2]), (lo[0], hi[1], hi[2]), (lo[0], lo[1], hi[2])]),
        ((1, 1), [(hi[0], lo[1], lo[2]), (hi[0], lo[1], hi[2]), (hi[0], hi[1], hi[2]), (hi[0], hi[1], lo[2])]),
        ((2, -1), [(lo[0], lo[1], lo[2]), (lo[0], lo[1], hi[2]), (hi[0], lo[1], hi[2]), (hi[0], lo[1], lo[2])]),
        ((2, 1), [(lo[0], hi[1], lo[2]), (hi[0], hi[1], lo[2]), (hi[0], hi[1], hi[2]), (lo[0], hi[1], hi[2])]),
    ]
    normals = {(0, -1): (0, 0, -1), (0, 1): (0, 0, 1), (1, -1): (-1, 0, 0), (1, 1): (1, 0, 0), (2, -1): (0, -1, 0), (2, 1): (0, 1, 0)}
    for key, quad in faces:
        pts = np.array(quad, float).reshape(2, 2, 3)[[0, 1]][:, :]
        p = np.array([[quad[0], quad[3]], [quad[1], quad[2]]], float)
        n = np.broadcast_to(np.array(normals[key], float), (2, 2, 3)).copy()
        uv = np.broadcast_to(np.array(color_uv, float), (2, 2, 2)).copy()
        m.add_grid(p, n, uv)
    return m


def player_boxes(uv):
    parts = [((-4, 24, -4), (4, 32, 4)), ((-4, 12, -2), (4, 24, 2)), ((-8, 12, -2), (-4, 24, 2)),
             ((4, 12, -2), (8, 24, 2)), ((-3.9, 0, -2), (0.1, 12, 2)), ((-0.1, 0, -2), (3.9, 12, 2))]
    m = Mesh()
    for lo, hi in parts:
        m.merge(box(lo, hi, uv))
    return m


def skin_texture():
    t = np.zeros((4, 4, 4))
    t[..., :3] = (0.55, 0.58, 0.66)
    t[..., 3] = 1.0
    return t


def model_space_sheet(sword_meshes, atlas, path):
    """Three views of the rigged swords next to a player-sized stand-in."""
    skin = skin_texture()
    body = player_boxes((0.5, 0.5))
    views = [("front", rot_y(180)), ("side", rot_y(90)), ("3/4 back", rot_x(-20) @ rot_y(35))]
    tiles = []
    for name, R in views:
        items = [(body, skin, False)] + [(m, atlas, True) for m in sword_meshes]
        img, _ = render(items, R, size=(420, 420), scale=7.5, center=(R @ np.array([0, 16, -4.0])), bg=(36, 24, 56))
        tiles.append(Image.fromarray(img))
    sheet = Image.new("RGB", (420 * len(tiles), 420))
    for i, t in enumerate(tiles):
        sheet.paste(t, (420 * i, 0))
    sheet.save(path)
