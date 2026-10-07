"""Shared paths and helpers for the ECLIPSE TWIN SWORDS build."""
import json
import os

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ADDON = os.path.join(ROOT, "EclipseTwinSwords")
BP = os.path.join(ADDON, "behavior_pack")
RP = os.path.join(ADDON, "resource_pack")
DIST = os.path.join(ROOT, "dist")
PREVIEW = os.path.join(ROOT, "preview", "eclipse")

NS = "eclipse"
PARTICLE_TEX_DIR = "textures/particle/eclipse"


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def write_json(path, data, compact=False):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        if compact:
            json.dump(data, f, separators=(",", ":"), ensure_ascii=False)
        else:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")


def write_text(path, text):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def save_rgba(path, arr):
    """arr: float HxWx4 in 0..1 (or uint8)."""
    ensure_dir(os.path.dirname(path))
    if arr.dtype != np.uint8:
        arr = (np.clip(arr, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    Image.fromarray(arr, "RGBA").save(path, optimize=True)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)
