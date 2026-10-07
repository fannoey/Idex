#!/usr/bin/env python3
"""Build the Cursed Reaper Scythe add-on.

Outputs
  cursed_reaper/model/         .bbmodel files (poly mesh scythe + animation preview rig) and texture
  cursed_reaper/Cursed_Reaper_BP, Cursed_Reaper_RP   the packs
  cursed_reaper/preview/       renders
  dist/Cursed_Reaper_Scythe.mcaddon

Run:  python3 tools/reaper/build.py
"""
import json
import math
import os
import shutil
import sys
import uuid
import zipfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import entities as ent  # noqa: E402
import mesh  # noqa: E402
import models  # noqa: E402
import poses  # noqa: E402
import preview  # noqa: E402
import render  # noqa: E402
import rig  # noqa: E402
import vfx  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "cursed_reaper")
BP = os.path.join(OUT, "Cursed_Reaper_BP")
RP = os.path.join(OUT, "Cursed_Reaper_RP")
MODEL = os.path.join(OUT, "model")
PREV = os.path.join(OUT, "preview")
DIST = os.path.join(ROOT, "dist", "Cursed_Reaper_Scythe.mcaddon")
ITEM = "idex:cursed_reaper_scythe"
GEO = "geometry.idex.cursed_reaper_scythe"
VERSION = [1, 0, 0]
GRIP_Y = 13.0


def uid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"idex/cursed_reaper/{name}"))


def wjson(path, obj, compact=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        if compact:
            json.dump(obj, f, separators=(",", ":"))
        else:
            json.dump(obj, f, indent=2, ensure_ascii=False)


def wimg(path, img):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)


def wtext(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


# ---------------------------------------------------------------- scythe facts
def blade_points(parts):
    """Tip, middle and inner-edge points of the blade in the scythe model frame."""
    b = parts["blade"]["pos"]
    hub = np.array([0.0, 41.0, 0.0])
    tip = b[np.argmax(np.linalg.norm(b[:, :2] - hub[:2], axis=1))].copy()
    tip[2] = 0
    edge = []
    for u in np.linspace(0.12, 0.95, 6):
        x = hub[0] + (tip[0] - hub[0]) * u
        sel = b[np.abs(b[:, 0] - x) < 0.5]
        if len(sel):
            p = sel[np.argmin(sel[:, 1])].copy()
            p[2] = 0
            edge.append(p)
    mid = np.array([(tip[0] + hub[0]) / 2, 0, 0])
    sel = b[np.abs(b[:, 0] - mid[0]) < 0.6]
    mid = np.array([mid[0], sel[:, 1].mean() if len(sel) else 30.0, 0])
    return tip, mid, edge


def game_texture(plain):
    """Emissive mask in alpha (alpha < 1 glows in entity_emissive_alpha), mirrored atlas."""
    a = np.asarray(plain.convert("RGB")).astype(float) / 255
    red = np.clip((a[..., 0] - np.maximum(a[..., 1], a[..., 2]) - 0.18) * 2.6, 0, 1)
    red *= a[..., 0] > 0.42
    alpha = 1 - 0.85 * red
    img = Image.fromarray((np.dstack([a, alpha]) * 255).astype(np.uint8), "RGBA")
    return models.mirror_texture(img)


def icon(parts, tex):
    items = []
    th = math.radians(-38)
    Rz = np.array([[math.cos(th), -math.sin(th), 0], [math.sin(th), math.cos(th), 0], [0, 0, 1]])
    for p in parts.values():
        items.append(dict(p, pos=p["pos"] @ Rz.T, nrm=p["nrm"] @ Rz.T, tex=tex))
    a = np.asarray(render.render(items, 0, 0, (512, 512), bg=(0, 0, 0), ss=1)).astype(float)
    b = np.asarray(render.render(items, 0, 0, (512, 512), bg=(255, 255, 255), ss=1)).astype(float)
    alpha = np.clip(1 - (b - a).mean(2) / 255, 0, 1)
    col = np.where(alpha[..., None] > 0.01, a / np.maximum(alpha[..., None], 1e-3), 0)
    img = Image.fromarray(np.dstack([np.clip(col, 0, 255), alpha * 255]).astype(np.uint8), "RGBA")
    big = img.resize((64, 64), Image.LANCZOS)
    return img.resize((32, 32), Image.LANCZOS), big


# ---------------------------------------------------------------- script data
def script_data(clips, scythe, tip, mid):
    by = {c.name.split(".")[-1]: c for c in clips}
    trails = {}
    for key, ev in poses.EVENTS.items():
        wins = ev.get("trail")
        if not wins:
            continue
        if isinstance(wins[0], (int, float)):
            wins = [wins]
        segs = []
        for t0, t1 in wins:
            pts = []
            for t in np.arange(t0, t1 + 1e-6, 0.05):
                w = rig.world_of(by[key], float(t), scythe, np.array([tip, mid]))
                lo = rig.to_world_offset(w)
                pts.append([round(float(v), 3) for v in np.r_[lo[0], lo[1]]])
            segs.append({"start": int(round(t0 * 20)), "pts": pts})
        trails[key] = segs
    # attack trails reuse the combo clips
    anchors = {}
    w = rig.world_of(by["reapers_chain"], poses.EVENTS["reapers_chain"]["circle"], scythe, np.array([mid]))
    anchors["chain_circle"] = [round(float(v), 3) for v in rig.to_world_offset(w)[0]]
    # awakening glow path: shaft from the pommel up, then along the blade to the tip
    shaft = [scythe.shaft_point(y) for y in np.arange(0.5, 40.5, 1.0)]
    blade = [np.array([0, 41.0, 0]) + (tip - np.array([0, 41.0, 0])) * u for u in np.linspace(0, 1, 16)]
    w = rig.world_of(by["eclipse_requiem"], 1.0, scythe, np.array(shaft + blade))
    glow = [[round(float(v), 3) for v in p] for p in rig.to_world_offset(w)]
    ticks = {k: int(round(c.length * 20)) for k, c in by.items()}
    js = "// Generated by tools/reaper/build.py - do not edit by hand.\n"
    js += "// Player-local blocks: x = right, y = up, z = forward. Trails: [tipX,tipY,tipZ, midX,midY,midZ] per tick.\n"
    js += f"export const TRAILS = {json.dumps(trails, separators=(',', ':'))};\n"
    js += f"export const ANCHORS = {json.dumps(anchors)};\n"
    js += f"export const GLOW = {json.dumps(glow, separators=(',', ':'))};\n"
    js += f"export const CLIP_TICKS = {json.dumps(ticks)};\n"
    return js


# ---------------------------------------------------------------- packs
def manifests():
    rp = {
        "format_version": 2,
        "header": {"name": "Cursed Reaper Scythe (RP)", "description": "Cursed Reaper Scythe - model, animations, VFX",
                   "uuid": uid("rp-header"), "version": VERSION, "min_engine_version": [1, 21, 40]},
        "modules": [{"type": "resources", "uuid": uid("rp-module"), "version": VERSION}],
    }
    bp = {
        "format_version": 2,
        "header": {"name": "Cursed Reaper Scythe (BP)", "description": "Cursed Reaper Scythe - skills and combo",
                   "uuid": uid("bp-header"), "version": VERSION, "min_engine_version": [1, 21, 40]},
        "modules": [
            {"type": "data", "uuid": uid("bp-data"), "version": VERSION},
            {"type": "script", "language": "javascript", "uuid": uid("bp-script"), "version": VERSION, "entry": "scripts/main.js"},
        ],
        "dependencies": [
            {"uuid": rp["header"]["uuid"], "version": VERSION},
            {"module_name": "@minecraft/server", "version": "1.11.0"},
        ],
    }
    return rp, bp


def item_json():
    return {
        "format_version": "1.21.40",
        "minecraft:item": {
            "description": {"identifier": ITEM, "menu_category": {"category": "equipment", "group": "itemGroup.name.sword"}},
            "components": {
                "minecraft:icon": "idex_cursed_reaper_scythe",
                "minecraft:display_name": {"value": "§4Cursed Reaper Scythe"},
                "minecraft:max_stack_size": 1,
                "minecraft:hand_equipped": True,
                "minecraft:damage": {"value": 9},
                "minecraft:enchantable": {"slot": "sword", "value": 15},
                "minecraft:can_destroy_in_creative": False,
                "minecraft:use_modifiers": {"use_duration": 1.0, "movement_modifier": 1.0},
            },
        },
    }


def recipe_json():
    return {
        "format_version": "1.20.10",
        "minecraft:recipe_shaped": {
            "description": {"identifier": ITEM},
            "tags": ["crafting_table"],
            "pattern": ["NNW", " SR", "S  "],
            "key": {"N": {"item": "minecraft:netherite_ingot"}, "W": {"item": "minecraft:wither_rose"},
                    "S": {"item": "minecraft:blaze_rod"}, "R": {"item": "minecraft:redstone_block"}},
            "result": {"item": ITEM},
        },
    }


def attachable_json():
    return {
        "format_version": "1.10.0",
        "minecraft:attachable": {
            "description": {
                "identifier": ITEM,
                "materials": {"default": "entity_emissive_alpha", "enchanted": "entity_alphatest_glint"},
                "textures": {"default": "textures/entity/reaper/cursed_reaper_scythe",
                             "enchanted": "textures/misc/enchanted_item_glint"},
                "geometry": {"default": GEO},
                "animations": {"fp_hide": "animation.idex.reaper_item.fp_hide",
                               "edge_glow": "animation.idex.reaper_item.edge_glow"},
                "particle_effects": {"edge": "idex:reaper_edge_ember"},
                "scripts": {"animate": [{"fp_hide": "c.is_first_person"}, {"edge_glow": "!c.is_first_person"}]},
                "render_controllers": ["controller.render.item_default"],
            }
        },
    }


def attachable_animations(n_edge):
    keys = {}
    for i in range(n_edge):
        keys[rig.fmt_t(0.1 * i)] = {"effect": "edge", "locator": f"edge_{i}"}
    keys[rig.fmt_t(0.1 * n_edge)] = {"effect": "edge", "locator": "blade_tip"}
    return {
        "format_version": "1.8.0",
        "animations": {
            "animation.idex.reaper_item.fp_hide": {"loop": True, "bones": {"reaper": {"scale": 0}}},
            "animation.idex.reaper_item.edge_glow": {"loop": True, "animation_length": 0.1 * (n_edge + 2),
                                                      "particle_effects": keys},
        },
    }


def fog(fid, color, start, end):
    d = {"fog_start": start, "fog_end": end, "fog_color": color, "render_distance_type": "fixed"}
    return {"format_version": "1.16.100", "minecraft:fog_settings": {
        "description": {"identifier": fid},
        "distance": {"air": d, "weather": d}}}


LANG_EN = """item.idex:cursed_reaper_scythe=§4Cursed Reaper Scythe
entity.idex:reaper_crescent.name=Crimson Crescent
entity.idex:reaper_phantom.name=Phantom Scythe
entity.idex:reaper_afterimage.name=Afterimage
"""
LANG_TH = """item.idex:cursed_reaper_scythe=§4เคียวยมทูตต้องสาป
entity.idex:reaper_crescent.name=จันทร์เสี้ยวโลหิต
entity.idex:reaper_phantom.name=เคียวเงา
entity.idex:reaper_afterimage.name=ภาพติดตา
"""


def build():
    for d in (BP, RP, MODEL, PREV):
        if os.path.isdir(d):
            shutil.rmtree(d)
    print("mesh ...")
    sil, parts = mesh.build()
    plain, _ = sil.texture()
    plain = plain.convert("RGB")
    tex_np = np.asarray(plain).astype(float)
    scythe = rig.Scythe(sil, grip_y=GRIP_Y)
    tip, mid, edge = blade_points(parts)
    scythe.tip = tip
    print("rig ...")
    clips = poses.clips(scythe)

    # ---- Blockbench files
    wimg(os.path.join(MODEL, "cursed_reaper_scythe.png"), plain)
    wjson(os.path.join(MODEL, "cursed_reaper_scythe.bbmodel"), models.static_bbmodel(parts, plain), compact=True)
    wjson(os.path.join(MODEL, "cursed_reaper_animations.bbmodel"),
          models.rig_bbmodel(parts, plain, scythe, clips), compact=True)

    # ---- RP
    rp_man, bp_man = manifests()
    wjson(os.path.join(RP, "manifest.json"), rp_man)
    gtex = game_texture(plain)
    wimg(os.path.join(RP, "textures/entity/reaper/cursed_reaper_scythe.png"), gtex)
    locs = {"blade_tip": tip, "blade_mid": mid, "pommel": scythe.shaft_point(0.5), "head": np.array([0, 41.0, 0])}
    for i, p in enumerate(edge):
        locs[f"edge_{i}"] = p
    geo, allp = models.attachable_geo(parts, scythe, plain.size, locs, GEO)
    wjson(os.path.join(RP, "models/entity/cursed_reaper_scythe.geo.json"), geo, compact=True)
    wjson(os.path.join(RP, "attachables/cursed_reaper_scythe.json"), attachable_json())
    wjson(os.path.join(RP, "animations/reaper_item.animation.json"), attachable_animations(len(edge)))
    wjson(os.path.join(RP, "animations/reaper_player.animation.json"),
          {"format_version": "1.8.0", "animations": {c.name: c.bedrock() for c in clips}})
    ic, ic64 = icon(parts, tex_np)
    wimg(os.path.join(RP, "textures/items/cursed_reaper_scythe.png"), ic)
    wimg(os.path.join(RP, "pack_icon.png"), ic64.resize((128, 128), Image.LANCZOS))
    wjson(os.path.join(RP, "textures/item_texture.json"), {
        "resource_pack_name": "cursed_reaper", "texture_name": "atlas.items",
        "texture_data": {"idex_cursed_reaper_scythe": {"textures": "textures/items/cursed_reaper_scythe"}}})

    # effect entities
    cgeo, ctex, n_cres = ent.crescent_geo("geometry.idex.reaper_crescent")
    wjson(os.path.join(RP, "models/entity/reaper_crescent.geo.json"), cgeo, compact=True)
    for k, im in ctex.items():
        wimg(os.path.join(RP, f"textures/entity/reaper/crescent_{k}.png"), im)
    pgeo, ptex, n_ph = ent.phantom_assets("geometry.idex.reaper_phantom")
    wjson(os.path.join(RP, "models/entity/reaper_phantom.geo.json"), pgeo, compact=True)
    wimg(os.path.join(RP, "textures/entity/reaper/phantom.png"), ptex)
    wimg(os.path.join(RP, "textures/entity/reaper/afterimage.png"), ent.afterimage_texture())
    wjson(os.path.join(RP, "render_controllers/reaper.render_controllers.json"), ent.render_controllers())
    wjson(os.path.join(RP, "animations/reaper_fx.animation.json"),
          {"format_version": "1.8.0", "animations": ent.entity_animations()})
    T = "textures/entity/reaper/"
    wjson(os.path.join(RP, "entity/reaper_crescent.entity.json"), ent.rp_entity(
        "reaper_crescent", {"default": "entity_emissive_alpha"},
        {k: T + f"crescent_{k}" for k in ("normal", "outer", "mid", "inner")},
        {"default": "geometry.idex.reaper_crescent"}, ["controller.render.idex.reaper_crescent"],
        {"spin": "animation.idex.crescent.spin", "wobble": "animation.idex.crescent.wobble"},
        ["spin", "wobble"], scale="q.property('idex:size')"))
    wjson(os.path.join(RP, "entity/reaper_phantom.entity.json"), ent.rp_entity(
        "reaper_phantom", {"default": "entity_emissive_alpha"}, {"default": T + "phantom"},
        {"default": "geometry.idex.reaper_phantom"}, ["controller.render.idex.reaper_fx"],
        {"idle": "animation.idex.phantom.idle"}, ["idle"], scale="q.property('idex:size')"))
    wjson(os.path.join(RP, "entity/reaper_afterimage.entity.json"), ent.rp_entity(
        "reaper_afterimage", {"default": "entity_alphablend"}, {"default": T + "afterimage"},
        {"default": "geometry.humanoid.custom"}, ["controller.render.idex.reaper_fx"], scale="0.9375"))

    # particles
    for name, im in vfx.textures().items():
        wimg(os.path.join(RP, vfx.TEX, name + ".png"), im)
    for pid, data in vfx.particles().items():
        wjson(os.path.join(RP, "particles", pid + ".particle.json"), data)
    wjson(os.path.join(RP, "fogs/blood_moon.json"), fog("idex:blood_moon_fog", "#3d0710", 3.0, 44.0))
    wjson(os.path.join(RP, "fogs/eclipse.json"), fog("idex:eclipse_fog", "#140207", 2.0, 30.0))
    wtext(os.path.join(RP, "texts/en_US.lang"), LANG_EN)
    wtext(os.path.join(RP, "texts/th_TH.lang"), LANG_TH)
    wjson(os.path.join(RP, "texts/languages.json"), ["en_US", "th_TH"])

    # ---- BP
    wjson(os.path.join(BP, "manifest.json"), bp_man)
    wimg(os.path.join(BP, "pack_icon.png"), ic64.resize((128, 128), Image.LANCZOS))
    wjson(os.path.join(BP, "items/cursed_reaper_scythe.json"), item_json())
    wjson(os.path.join(BP, "recipes/cursed_reaper_scythe.json"), recipe_json())
    props_cres = {"idex:variant": {"type": "int", "range": [0, 3], "default": 0, "client_sync": True},
                  "idex:size": {"type": "float", "range": [0.1, 8.0], "default": 1.0, "client_sync": True}}
    props_ph = {"idex:size": {"type": "float", "range": [0.1, 8.0], "default": 2.2, "client_sync": True}}
    fam = ["reaper_fx", "inanimate"]
    wjson(os.path.join(BP, "entities/reaper_crescent.json"), ent.bp_entity("reaper_crescent", fam, 8.0, props_cres))
    wjson(os.path.join(BP, "entities/reaper_phantom.json"), ent.bp_entity("reaper_phantom", fam, 40.0, props_ph))
    wjson(os.path.join(BP, "entities/reaper_afterimage.json"), ent.bp_entity("reaper_afterimage", fam, 2.0))
    wtext(os.path.join(BP, "scripts/main.js"), 'import "./reaper.js";\n')
    shutil.copy(os.path.join(HERE, "script", "reaper.js"), os.path.join(BP, "scripts", "reaper.js"))
    wtext(os.path.join(BP, "scripts/reaper_data.js"), script_data(clips, scythe, tip, mid))

    # ---- previews
    print("previews ...")
    items = [dict(p, tex=tex_np) for p in parts.values()]
    os.makedirs(PREV, exist_ok=True)
    render.sheet([render.render(items, 0, 0, (420, 720)), render.render(items, 35, 12, (420, 720)),
                  render.render(items, 90, 0, (200, 720))]).save(os.path.join(PREV, "scythe_mesh.png"))
    for c in clips:
        short = c.name.split(".")[-1]
        times = np.linspace(0, c.length, 8 if c.length > 1 else 6)
        preview.clip_strip(c, parts, tex_np, scythe, [float(t) for t in times], size=(220, 320), scale=4.4) \
            .save(os.path.join(PREV, f"anim_{short}.png"))
    ic64.resize((128, 128), Image.NEAREST).save(os.path.join(PREV, "icon.png"))

    stats = {"mesh": mesh.stats(parts), "crescent_cubes": n_cres, "phantom_cubes": n_ph,
             "poly_total": sum(len(p["polys"]) for p in parts.values())}
    print(json.dumps(stats))
    validate()
    pack()
    return stats


# ---------------------------------------------------------------- validation + packing
def validate():
    errs = []
    for base in (BP, RP):
        for dp, _, fs in os.walk(base):
            for f in fs:
                if f.endswith(".json"):
                    try:
                        json.load(open(os.path.join(dp, f)))
                    except Exception as e:  # noqa: BLE001
                        errs.append(f"{f}: {e}")
    geo = json.load(open(os.path.join(RP, "models/entity/cursed_reaper_scythe.geo.json")))
    bones = geo["minecraft:geometry"][0]["bones"]
    names = {b["name"] for b in bones}
    for b in bones:
        if b.get("parent") and b["parent"] not in names:
            errs.append(f"bone {b['name']} parent missing")
        pm = b.get("poly_mesh")
        if pm:
            n = len(pm["positions"])
            if not (n == len(pm["normals"]) == len(pm["uvs"])):
                errs.append(f"{b['name']}: array length mismatch")
            for poly in pm["polys"]:
                if len(poly) != 4 or any(not (0 <= v[0] < n) for v in poly):
                    errs.append(f"{b['name']}: bad poly")
                    break
            uv = np.array(pm["uvs"])
            if uv.min() < 0 or uv.max() > 1:
                errs.append(f"{b['name']}: uv out of range")
    # references
    anims = {}
    for f in os.listdir(os.path.join(RP, "animations")):
        anims.update(json.load(open(os.path.join(RP, "animations", f)))["animations"])
    parts = set(json.load(open(os.path.join(RP, "particles", f)))["particle_effect"]["description"]["identifier"]
                for f in os.listdir(os.path.join(RP, "particles")))
    js = open(os.path.join(BP, "scripts/reaper.js")).read()
    import re
    for a in set(re.findall(r"animation\.idex\.[a-z_]+\.[a-z_0-9]+", js)) | set(
            "animation.idex.reaper." + m for m in re.findall(r'play\(player, "([a-z_0-9]+)"', js)):
        if "${" in a:
            continue
        if a not in anims:
            errs.append(f"script animation missing: {a}")
    for p in set(re.findall(r'"(reaper_[a-z_]+)"', js)):
        if p.startswith("reaper_") and f"idex:{p}" not in parts and not p.startswith(("reaper_fx",)):
            if p not in ("reaper_crescent", "reaper_phantom", "reaper_afterimage"):
                errs.append(f"particle missing: {p}")
    for k in ("swing_left", "swing_up", "chop", "spin"):
        if f"animation.idex.phantom.{k}" not in anims:
            errs.append(f"phantom anim missing: {k}")
    for f in os.listdir(os.path.join(RP, "entity")):
        d = json.load(open(os.path.join(RP, "entity", f)))["minecraft:client_entity"]["description"]
        for t in d["textures"].values():
            if not os.path.exists(os.path.join(RP, t + ".png")):
                errs.append(f"texture missing {t}")
        for a in d.get("animations", {}).values():
            if a not in anims:
                errs.append(f"entity anim missing {a}")
    for f in os.listdir(os.path.join(RP, "particles")):
        t = json.load(open(os.path.join(RP, "particles", f)))["particle_effect"]["description"]["basic_render_parameters"]["texture"]
        if not os.path.exists(os.path.join(RP, t + ".png")):
            errs.append(f"particle texture missing {t}")
    if errs:
        print("VALIDATION FAILED")
        for e in errs:
            print("  -", e)
        raise SystemExit(1)
    print("validation ok")


def pack():
    os.makedirs(os.path.dirname(DIST), exist_ok=True)
    with zipfile.ZipFile(DIST, "w", zipfile.ZIP_DEFLATED) as z:
        for base in (BP, RP):
            for dp, _, fs in os.walk(base):
                for f in sorted(fs):
                    full = os.path.join(dp, f)
                    z.write(full, os.path.relpath(full, OUT).replace(os.sep, "/"))
    print("packed", os.path.relpath(DIST, ROOT), os.path.getsize(DIST) // 1024, "KB")


if __name__ == "__main__":
    build()
