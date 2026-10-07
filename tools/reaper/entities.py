"""Effect entities: crescent wave, phantom scythe, afterimage.

Effect entities use cube geometry: poly_mesh is only reliable on attachables.
"""
import math
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build_scythe as bs  # noqa: E402

NS = "idex"


def r4(v):
    v = round(float(v), 4)
    return int(v) if v == int(v) else v


# ---------------------------------------------------------------- crescent wave
CR_CELL = 1.0     # px per cell
CR_TPC = 4        # texels per cell


def crescent_mask(R=28, R2=26, d=10):
    n = int(math.ceil(R + 2))
    xs = np.arange(-n, n) + 0.5
    zs = np.arange(-n, n) + 0.5                  # +z = forward here (convex side)
    X, Z = np.meshgrid(xs, zs)
    m = (np.hypot(X, Z) < R) & (np.hypot(X, Z + d) > R2) & (Z > -R * 0.2)
    rows = np.where(m.any(1))[0]
    cols = np.where(m.any(0))[0]
    m = m[rows.min():rows.max() + 1, cols.min():cols.max() + 1]
    x0 = xs[cols.min()] - 0.5
    z0 = zs[rows.min()] - 0.5
    return m, x0, z0


def crescent_textures(m):
    up = np.kron(m, np.ones((CR_TPC, CR_TPC), bool))
    d = ndi.distance_transform_edt(np.pad(up, 2))[2:-2, 2:-2] / CR_TPC      # px to the rim
    h, w = up.shape
    rng = np.random.default_rng(4)
    streak = ndi.gaussian_filter(rng.random((h, w)), (1.0, 6.0))
    streak = (streak - streak.min()) / (streak.max() - streak.min())
    out = {}

    def img(rgb, alpha):
        a = np.where(up, alpha, 0.0)
        rgb = np.where(up[..., None], rgb, 0.0)
        return Image.fromarray((np.dstack([np.clip(rgb, 0, 1), np.clip(a, 0, 1)]) * 255).astype(np.uint8), "RGBA")

    rim = np.clip(1.0 - d / 1.8, 0, 1)
    core = np.clip(1.0 - d / 0.8, 0, 1)
    # alpha < 1 = emissive in entity_emissive_alpha
    base = np.dstack([0.04 + 0.1 * streak, 0.02 + 0.02 * streak, 0.04 + 0.03 * streak])
    red = np.dstack([np.ones_like(d), 0.08 + 0.4 * core, 0.1 + 0.3 * core])
    out["normal"] = img(base * (1 - rim[..., None]) + red * rim[..., None], 1.0 - rim * 1.0 + 0.0)
    out["normal"] = fix_alpha(out["normal"], up, rim)
    thin = np.clip(1.0 - d / 0.9, 0, 1)
    out["outer"] = fix_alpha(img(base * (1 - thin[..., None]) + np.dstack([0.7 * thin, 0 * thin, 0.05 * thin]) + 0 * red, 1), up, thin)
    mid = np.dstack([0.75 + 0.25 * rim, 0.03 + 0.25 * core + 0.08 * streak, 0.05 + 0.1 * core])
    out["mid"] = fix_alpha(img(mid, 1), up, np.ones_like(d))
    inner = np.dstack([np.ones_like(d), 0.55 + 0.45 * (1 - rim), 0.55 + 0.45 * (1 - rim)])
    out["inner"] = fix_alpha(img(inner, 1), up, np.ones_like(d))
    return out


def fix_alpha(im, mask, glow):
    """Encode emissive amount in alpha (1 - glow) while keeping non-mask pixels opaque-black."""
    a = np.asarray(im).astype(float) / 255.0
    alpha = np.where(mask, 1.0 - np.clip(glow, 0, 1), 1.0)
    alpha = np.maximum(alpha, 0.0)
    a[..., 3] = alpha
    return Image.fromarray((a * 255).astype(np.uint8), "RGBA")


def crescent_geo(identifier):
    m, x0, z0 = crescent_mask()
    d = ndi.distance_transform_edt(np.pad(m, 1))[1:-1, 1:-1] * CR_CELL
    h = np.clip(0.25 + 0.32 * d, 0.25, 2.25)
    h = np.where(m, np.round(h / 0.25) * 0.25, 0)
    cubes = []
    for lv in sorted(np.unique(h[m])):
        layer = h >= lv - 1e-9
        for r in range(m.shape[0]):
            c = 0
            row = layer[r]
            while c < m.shape[1]:
                if not row[c]:
                    c += 1
                    continue
                c1 = c
                while c1 < m.shape[1] and row[c1]:
                    c1 += 1
                # Blockbench space: x = x0 + c, z = -(z0 + r)  (forward is -z)
                bx0, bx1 = x0 + c * CR_CELL, x0 + c1 * CR_CELL
                bz1 = -(z0 + r * CR_CELL)
                bz0 = bz1 - CR_CELL
                u0, u1 = c * CR_TPC, c1 * CR_TPC
                v0, v1 = r * CR_TPC, (r + 1) * CR_TPC
                cubes.append({
                    "origin": [r4(-bx1), r4(-lv), r4(bz0)],
                    "size": [r4(bx1 - bx0), r4(2 * lv), r4(CR_CELL)],
                    "uv": {
                        "up": {"uv": [u1, v1], "uv_size": [u0 - u1, v0 - v1]},
                        "down": {"uv": [u1, v1], "uv_size": [u0 - u1, v0 - v1]},
                        "north": {"uv": [u0, v1 - 1], "uv_size": [u1 - u0, 1]},
                        "south": {"uv": [u0, v0], "uv_size": [u1 - u0, 1]},
                        "east": {"uv": [u1 - 1, v0], "uv_size": [1, v1 - v0]},
                        "west": {"uv": [u0, v0], "uv_size": [1, v1 - v0]},
                    },
                })
                c = c1
    geo = {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {"identifier": identifier, "texture_width": m.shape[1] * CR_TPC,
                            "texture_height": m.shape[0] * CR_TPC, "visible_bounds_width": 6,
                            "visible_bounds_height": 3, "visible_bounds_offset": [0, 0, 0]},
            "bones": [
                {"name": "root", "pivot": [0, 0, 0]},
                {"name": "spin", "parent": "root", "pivot": [0, 0, 0], "cubes": cubes},
            ],
        }],
    }
    return geo, crescent_textures(m), len(cubes)


# ---------------------------------------------------------------- phantom scythe
def phantom_assets(identifier):
    cells, zone_c, tex, origin, k = bs.build_grid()
    h = bs.half_depth(cells, zone_c)
    cubes = bs.build_cubes(cells, zone_c, h, origin)
    geo = bs.geo_json(cubes, tex.size)
    g = geo["minecraft:geometry"][0]
    g["description"]["identifier"] = identifier
    g["description"]["visible_bounds_width"] = 10
    g["description"]["visible_bounds_height"] = 10
    for b in g["bones"]:
        if b["name"] == "scythe":
            b["parent"] = "root"
            b["pivot"] = [0, 14, 0]
    g["bones"].insert(0, {"name": "root", "pivot": [0, 14, 0]})
    # shadow texture: near-black body, glowing red rim and red runes (alpha < 1 = emissive)
    src = np.asarray(tex.convert("RGB")).astype(float) / 255
    lum = src @ [0.299, 0.587, 0.114]
    redness = np.clip((src[..., 0] - np.maximum(src[..., 1], src[..., 2])) * 2.2, 0, 1)
    tpc = bs.TPC
    m = np.kron(cells, np.ones((tpc, tpc), bool))
    m = m[:src.shape[0], :src.shape[1]]
    rim = m & ~ndi.binary_erosion(m, iterations=3)
    body = np.dstack([0.05 + 0.12 * lum, 0.02 + 0.05 * lum, 0.06 + 0.12 * lum])
    glow = np.clip(redness + rim * 1.0, 0, 1)
    rgb = body * (1 - glow[..., None]) + np.dstack([np.ones_like(lum), 0.1 + 0.15 * redness, 0.12 + 0.1 * redness]) * glow[..., None]
    alpha = 1 - glow * 0.95
    img = Image.fromarray((np.dstack([rgb, alpha]) * 255).astype(np.uint8), "RGBA")
    return geo, img, len(cubes)


# ---------------------------------------------------------------- afterimage
def afterimage_texture():
    """64x64 skin: translucent crimson silhouette on the base layer, overlay empty."""
    a = np.zeros((64, 64, 4))
    base = [(0, 0, 32, 16), (16, 16, 40, 32), (40, 16, 56, 32), (32, 48, 48, 64), (0, 16, 16, 32), (16, 48, 32, 64)]
    rng = np.random.default_rng(2)
    for x0, y0, x1, y1 in base:
        h = y1 - y0
        for y in range(y0, y1):
            t = (y - y0) / max(h - 1, 1)
            for x in range(x0, x1):
                n = rng.random() * 0.15
                a[y, x] = [0.55 - 0.35 * t + n, 0.02, 0.06 + 0.04 * t, 0.55]
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8), "RGBA")


# ---------------------------------------------------------------- json
def bp_entity(eid, family, life_s, props=None):
    desc = {"identifier": f"{NS}:{eid}", "is_spawnable": False, "is_summonable": True, "is_experimental": False}
    if props:
        desc["properties"] = props
    return {
        "format_version": "1.21.40",
        "minecraft:entity": {
            "description": desc,
            "component_groups": {"idex:despawn": {"minecraft:instant_despawn": {}}},
            "components": {
                "minecraft:type_family": {"family": family},
                "minecraft:collision_box": {"width": 0.1, "height": 0.1},
                "minecraft:physics": {"has_gravity": False, "has_collision": False},
                "minecraft:pushable": {"is_pushable": False, "is_pushable_by_piston": False},
                "minecraft:damage_sensor": {"triggers": [{"cause": "all", "deals_damage": "no"}]},
                "minecraft:knockback_resistance": {"value": 1.0},
                "minecraft:fire_immune": {},
                "minecraft:health": {"value": 1, "max": 1},
                "minecraft:conditional_bandwidth_optimization": {},
                "minecraft:timer": {"looping": False, "time": life_s, "time_down_event": {"event": "idex:despawn"}},
            },
            "events": {"idex:despawn": {"add": {"component_groups": ["idex:despawn"]}}},
        },
    }


def rp_entity(eid, materials, textures, geometry, render_controllers, animations=None, animate=None,
              scale=None, particles=None):
    scripts = {}
    if animate:
        scripts["animate"] = animate
    if scale:
        scripts["scale"] = scale
    desc = {"identifier": f"{NS}:{eid}", "materials": materials, "textures": textures, "geometry": geometry,
            "render_controllers": render_controllers}
    if animations:
        desc["animations"] = animations
    if scripts:
        desc["scripts"] = scripts
    if particles:
        desc["particle_effects"] = particles
    return {"format_version": "1.10.0", "minecraft:client_entity": {"description": desc}}


def anim(length, loop, bones, **extra):
    a = {"loop": loop, "animation_length": length, "bones": bones}
    a.update(extra)
    return a


def kf(pairs, mode="catmullrom"):
    from rig import fmt_t
    return {fmt_t(t): {"post": list(v), "lerp_mode": mode} for t, v in pairs}


def entity_animations():
    A = {}
    A["animation.idex.crescent.spin"] = anim(2.0, True, {"spin": {"rotation": {"0.0": [0, 0, 0], "2.0": [0, 0, 360]}}})
    A["animation.idex.crescent.wobble"] = anim(1.0, True, {"root": {"rotation": [
        "math.sin(q.life_time * 540) * 6", "math.sin(q.life_time * 260) * 4", 0]}})
    ph = lambda **b: {"root": b}
    A["animation.idex.phantom.idle"] = anim(3.0, True, {"scythe": {
        "position": [0, "math.sin(q.life_time * 120) * 1.5", 0],
        "rotation": [0, 0, "math.sin(q.life_time * 80) * 4"]}})
    A["animation.idex.phantom.appear"] = anim(1.2, False, ph(
        position=kf([(0, (0, -60, 0)), (0.9, (0, 3, 0)), (1.2, (0, 0, 0))]),
        rotation=kf([(0, (0, -180, 20)), (1.0, (0, 0, -4)), (1.2, (0, 0, 0))]),
        scale=kf([(0, (0.2, 0.2, 0.2)), (0.8, (1.04, 1.04, 1.04)), (1.2, (1, 1, 1))])))
    A["animation.idex.phantom.vanish"] = anim(0.8, "hold_on_last_frame", ph(
        position=kf([(0, (0, 0, 0)), (0.8, (0, 18, 0))]),
        scale=kf([(0, (1, 1, 1)), (0.2, (1.08, 1.08, 1.08)), (0.8, (0, 0, 0))])))
    A["animation.idex.phantom.swing_left"] = anim(0.7, False, ph(
        rotation=kf([(0, (0, 0, 0)), (0.12, (70, 110, 0)), (0.3, (75, -20, 0)), (0.42, (70, -120, 0)), (0.7, (0, 0, 0))])))
    A["animation.idex.phantom.swing_right"] = anim(0.7, False, ph(
        rotation=kf([(0, (0, 0, 0)), (0.12, (70, -110, 0)), (0.3, (75, 20, 0)), (0.42, (70, 120, 0)), (0.7, (0, 0, 0))])))
    A["animation.idex.phantom.swing_up"] = anim(0.7, False, ph(
        rotation=kf([(0, (0, 0, 0)), (0.12, (110, 0, -20)), (0.3, (10, 0, 10)), (0.42, (-60, 0, 25)), (0.7, (0, 0, 0))])))
    A["animation.idex.phantom.chop"] = anim(0.8, False, ph(
        rotation=kf([(0, (0, 0, 0)), (0.2, (-50, 0, 0)), (0.42, (100, 0, 0)), (0.6, (95, 0, 0)), (0.8, (0, 0, 0))])))
    A["animation.idex.phantom.spin"] = anim(0.9, False, ph(
        rotation=kf([(0, (0, 0, 0)), (0.1, (75, 0, 0)), (0.3, (75, 180, 0)), (0.5, (75, 360, 0)), (0.9, (0, 360, 0))])))
    A["animation.idex.phantom.slam"] = anim(1.0, "hold_on_last_frame", ph(
        rotation=kf([(0, (-70, 0, 0)), (0.6, (-80, 0, 0)), (0.8, (100, 0, 0)), (1.0, (96, 0, 0))]),
        position=kf([(0, (0, 0, 0)), (0.6, (0, 4, 0)), (0.8, (0, -6, 0)), (1.0, (0, -6, 0))])))
    A["animation.idex.phantom.fall"] = anim(0.6, "hold_on_last_frame", ph(
        rotation=kf([(0, (0, 0, 180)), (0.15, (0, 0, 180)), (0.35, (0, 0, 180))]),
        position=kf([(0, (0, 0, 0)), (0.15, (0, 6, 0)), (0.35, (0, -70, 0))], "linear")))
    A["animation.idex.phantom.hang"] = anim(1.0, "hold_on_last_frame", ph(
        rotation=kf([(0, (0, 0, 180)), (1.0, (0, 0, 180))]),
        position=kf([(0, (0, -20, 0)), (1.0, (0, 0, 0))])))
    return A


def render_controllers():
    return {
        "format_version": "1.8.0",
        "render_controllers": {
            "controller.render.idex.reaper_crescent": {
                "arrays": {"textures": {"Array.skins": ["Texture.normal", "Texture.outer", "Texture.mid", "Texture.inner"]}},
                "geometry": "Geometry.default",
                "materials": [{"*": "Material.default"}],
                "textures": ["Array.skins[q.property('idex:variant')]"],
            },
            "controller.render.idex.reaper_fx": {
                "geometry": "Geometry.default",
                "materials": [{"*": "Material.default"}],
                "textures": ["Texture.default"],
            },
        },
    }
