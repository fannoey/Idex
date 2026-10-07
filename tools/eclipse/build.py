#!/usr/bin/env python3
"""Build the ECLIPSE TWIN SWORDS Minecraft Bedrock add-on.

Generates everything except the hand-written scripts in
EclipseTwinSwords/behavior_pack/scripts/:
  particle textures + 60 particle effects, sword models (poly_mesh) + atlas +
  icons, attachables, animations, synthesized sounds, fog, lang, items,
  recipes, functions, manifests, previews, then validates the packs and
  writes dist/EclipseTwinSwords.mcaddon.

Run:  python3 tools/eclipse/build.py          (needs numpy, Pillow, ffmpeg)
"""
import glob
import json
import os
import re
import shutil
import sys
import uuid
import zipfile

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import anims  # noqa: E402
import fxtex  # noqa: E402
import particles  # noqa: E402
import preview  # noqa: E402
import sounds  # noqa: E402
import swords  # noqa: E402
from common import ADDON, BP, DIST, NS, PREVIEW, RP, ensure_dir, save_rgba, write_json, write_text  # noqa: E402
from mesh import render, rot_z  # noqa: E402

VERSION = [1, 0, 0]
MIN_ENGINE = [1, 21, 90]
SCRIPT_API = "2.0.0"           # @minecraft/server stable, Minecraft 1.21.90+
UUID_NS = uuid.UUID("6f0c2a61-55a4-4f4c-9f8e-ec11b5e0a7d1")
SWORD_TEX = "textures/models/eclipse/eclipse_swords"


def uid(name):
    return str(uuid.uuid5(UUID_NS, name))


# ================================================================== cleanup

def clean():
    if os.path.isdir(RP):
        shutil.rmtree(RP)
    for sub in ("items", "recipes", "functions", "texts"):
        p = os.path.join(BP, sub)
        if os.path.isdir(p):
            shutil.rmtree(p)
    for f in ("manifest.json", "pack_icon.png"):
        p = os.path.join(BP, f)
        if os.path.exists(p):
            os.remove(p)
    ensure_dir(RP)
    ensure_dir(PREVIEW)


# =================================================================== models

def build_models():
    S = swords.build_solaris()
    N = swords.build_noctis()
    atlas = swords.paint_atlas()
    save_rgba(os.path.join(RP, SWORD_TEX + ".png"), atlas)
    gs, gn = swords.SWORD_INFO["solaris"]["grip"], swords.SWORD_INFO["noctis"]["grip"]
    geo_dir = os.path.join(RP, "models", "entity")
    write_json(os.path.join(geo_dir, "eclipse_solaris.geo.json"), swords.geometry_main(f"geometry.{NS}.solaris", S, gs, N, gn), compact=True)
    write_json(os.path.join(geo_dir, "eclipse_solaris_offhand.geo.json"), swords.geometry_offhand(f"geometry.{NS}.solaris_offhand", S, gs), compact=True)
    write_json(os.path.join(geo_dir, "eclipse_noctis.geo.json"), swords.geometry_main(f"geometry.{NS}.noctis", N, gn, S, gs), compact=True)
    write_json(os.path.join(geo_dir, "eclipse_noctis_offhand.geo.json"), swords.geometry_offhand(f"geometry.{NS}.noctis_offhand", N, gn), compact=True)

    icons = {}
    for name, mesh in (("solaris", S), ("noctis", N)):
        im = swords.icon(mesh, atlas, 64)
        path = os.path.join(RP, "textures", "items", f"{name}.png")
        ensure_dir(os.path.dirname(path))
        im.save(path)
        icons[name] = im
    write_json(os.path.join(RP, "textures", "item_texture.json"), {
        "resource_pack_name": "eclipse_twin_swords",
        "texture_name": "atlas.items",
        "texture_data": {
            f"{NS}_solaris": {"textures": "textures/items/solaris"},
            f"{NS}_noctis": {"textures": "textures/items/noctis"},
        },
    })
    return S, N, atlas, icons


def build_attachables():
    for name in ("solaris", "noctis"):
        write_json(os.path.join(RP, "attachables", f"{name}.json"), {
            "format_version": "1.10.0",
            "minecraft:attachable": {
                "description": {
                    "identifier": f"{NS}:{name}",
                    "materials": {"default": "entity_emissive_alpha"},
                    "textures": {"default": SWORD_TEX},
                    "geometry": {"default": f"geometry.{NS}.{name}", "offhand": f"geometry.{NS}.{name}_offhand"},
                    "animations": {
                        "wield": f"controller.animation.{NS}.blade",
                        "third_person": f"animation.{NS}.blade.third_person",
                        "first_person": f"animation.{NS}.blade.first_person",
                    },
                    "scripts": {"animate": ["wield"]},
                    "render_controllers": [
                        {f"controller.render.{NS}.blade_main": "c.item_slot == 'main_hand'"},
                        {f"controller.render.{NS}.blade_offhand": "c.item_slot == 'off_hand'"},
                    ],
                }
            },
        })
    write_json(os.path.join(RP, "render_controllers", "eclipse_blade.render_controllers.json"), {
        "format_version": "1.10.0",
        "render_controllers": {
            f"controller.render.{NS}.blade_main": {
                "geometry": "Geometry.default", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"],
            },
            f"controller.render.{NS}.blade_offhand": {
                "geometry": "Geometry.offhand", "materials": [{"*": "Material.default"}], "textures": ["Texture.default"],
            },
        },
    })
    write_json(os.path.join(RP, "animations", "eclipse_blade.animation.json"), anims.attachable_animations())
    write_json(os.path.join(RP, "animation_controllers", "eclipse_blade.animation_controllers.json"), anims.attachable_controller())
    write_json(os.path.join(RP, "animations", "eclipse_player.animation.json"), anims.player_animations())


# =================================================================== sounds

def build_sounds():
    defs = sounds.build_all(os.path.join(RP, "sounds", "eclipse"))
    write_json(os.path.join(RP, "sounds", "sound_definitions.json"), {"format_version": "1.20.20", "sound_definitions": defs})
    return defs


# ===================================================================== misc

def build_fog():
    air = {"fog_start": 3.0, "fog_end": 26.0, "fog_color": "#14061f", "render_distance_type": "fixed"}
    write_json(os.path.join(RP, "fogs", "black_eclipse.json"), {
        "format_version": "1.16.100",
        "minecraft:fog_settings": {
            "description": {"identifier": f"{NS}:black_eclipse"},
            "distance": {"air": air, "weather": dict(air),
                         "water": {"fog_start": 0.0, "fog_end": 14.0, "fog_color": "#0c0418", "render_distance_type": "fixed"}},
        },
    })


LANG = {
    "en_US": {
        "pack.name": "Eclipse Twin Swords",
        "pack.description": "SOLARIS & NOCTIS - legendary twin blades of the Sun and the Void",
        f"item.{NS}.solaris.name": "§6§lSOLARIS§r",
        f"item.{NS}.noctis.name": "§5§lNOCTIS§r",
    },
    "th_TH": {
        "pack.name": "Eclipse Twin Swords - ดาบคู่สุริยุปราคา",
        "pack.description": "SOLARIS & NOCTIS ดาบคู่ระดับตำนานแห่งดวงอาทิตย์และความว่างเปล่า",
        f"item.{NS}.solaris.name": "§6§lSOLARIS§r",
        f"item.{NS}.noctis.name": "§5§lNOCTIS§r",
    },
}


def build_texts():
    for pack in (RP, BP):
        for lang, entries in LANG.items():
            write_text(os.path.join(pack, "texts", f"{lang}.lang"), "".join(f"{k}={v}\n" for k, v in entries.items()))
        write_json(os.path.join(pack, "texts", "languages.json"), list(LANG))


def item_json(name, repair_item):
    return {
        "format_version": "1.21.90",
        "minecraft:item": {
            "description": {
                "identifier": f"{NS}:{name}",
                "menu_category": {"category": "equipment", "group": "minecraft:itemGroup.name.sword"},
            },
            "components": {
                "minecraft:icon": f"{NS}_{name}",
                "minecraft:display_name": {"value": f"item.{NS}.{name}.name"},
                "minecraft:max_stack_size": 1,
                "minecraft:hand_equipped": True,
                "minecraft:allow_off_hand": True,
                "minecraft:damage": 9,
                "minecraft:durability": {"max_durability": 3000},
                "minecraft:enchantable": {"slot": "sword", "value": 15},
                "minecraft:repairable": {"repair_items": [
                    {"items": [repair_item], "repair_amount": 750},
                    {"items": [f"{NS}:{name}"], "repair_amount": "context.other->query.remaining_durability + 0.12 * context.other->query.max_durability"},
                ]},
                "minecraft:rarity": "epic",
                "minecraft:glint": False,
                "minecraft:can_destroy_in_creative": False,
                "minecraft:tags": {"tags": ["minecraft:is_sword", f"{NS}:twin_blade"]},
                "minecraft:interact_button": "Cast Skill",
                "minecraft:use_modifiers": {"use_duration": 3600, "movement_modifier": 1.0},
            },
        },
    }


def recipe(name, pattern, key, unlock):
    return {
        "format_version": "1.20.10",
        "minecraft:recipe_shaped": {
            "description": {"identifier": f"{NS}:{name}"},
            "tags": ["crafting_table"],
            "pattern": pattern,
            "key": {k: {"item": v} for k, v in key.items()},
            "unlock": [{"item": unlock}],
            "result": {"item": f"{NS}:{name}"},
        },
    }


FUNCTIONS = {
    "eclipse/give": [
        "give @s eclipse:solaris",
        "give @s eclipse:noctis",
        "tellraw @s {\"rawtext\":[{\"text\":\"§6SOLARIS §7& §5NOCTIS §7received. §fHold one and press Use.\"}]}",
    ],
    "eclipse/energy_full": [
        "scoreboard objectives add eclipse_solar dummy \"Solar Energy\"",
        "scoreboard objectives add eclipse_void dummy \"Void Energy\"",
        "scoreboard objectives add eclipse_energy dummy \"Eclipse Energy\"",
        "scoreboard players set @s eclipse_solar 50",
        "scoreboard players set @s eclipse_void 50",
        "scoreboard players set @s eclipse_energy 100",
    ],
    "eclipse/reset": [
        "scoreboard players set @s eclipse_solar 0",
        "scoreboard players set @s eclipse_void 0",
        "scoreboard players set @s eclipse_energy 0",
        "tag @s remove eclipse_state",
        "fog @s remove eclipse_ult",
    ],
    "eclipse/help": [
        "tellraw @s {\"rawtext\":[{\"text\":\"§l§6ECLIPSE TWIN SWORDS§r\"}]}",
        "tellraw @s {\"rawtext\":[{\"text\":\"§eSneak§7 = change skill   §eUse / right click§7 = cast selected skill\"}]}",
        "tellraw @s {\"rawtext\":[{\"text\":\"§6SOLARIS§7  Solar Slash > Radiant Spear > Solar Crown\"}]}",
        "tellraw @s {\"rawtext\":[{\"text\":\"§5NOCTIS§7  Void Crescent > Abyss Field > Moonfall\"}]}",
        "tellraw @s {\"rawtext\":[{\"text\":\"§dECLIPSE§7  at 100 energy Eclipse State and Heaven's Abyss join the skill wheel\"}]}",
    ],
}


def build_bp():
    write_json(os.path.join(BP, "items", "solaris.json"), item_json("solaris", "minecraft:gold_block"))
    write_json(os.path.join(BP, "items", "noctis.json"), item_json("noctis", "minecraft:crying_obsidian"))
    write_json(os.path.join(BP, "recipes", "solaris.json"), recipe(
        "solaris", [" G ", "GNG", " B "], {"G": "minecraft:gold_block", "N": "minecraft:nether_star", "B": "minecraft:blaze_rod"},
        "minecraft:nether_star"))
    write_json(os.path.join(BP, "recipes", "noctis.json"), recipe(
        "noctis", [" C ", "CNC", " E "], {"C": "minecraft:crying_obsidian", "N": "minecraft:nether_star", "E": "minecraft:echo_shard"},
        "minecraft:nether_star"))
    for name, lines in FUNCTIONS.items():
        write_text(os.path.join(BP, "functions", name + ".mcfunction"), "\n".join(lines) + "\n")


def build_manifests():
    rp_uuid, bp_uuid = uid("rp-header"), uid("bp-header")
    write_json(os.path.join(RP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": "pack.name", "description": "pack.description", "uuid": rp_uuid,
                   "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [{"type": "resources", "uuid": uid("rp-resources"), "version": VERSION}],
        "metadata": {"authors": ["Idex"]},
    })
    write_json(os.path.join(BP, "manifest.json"), {
        "format_version": 2,
        "header": {"name": "pack.name", "description": "pack.description", "uuid": bp_uuid,
                   "version": VERSION, "min_engine_version": MIN_ENGINE},
        "modules": [
            {"type": "data", "uuid": uid("bp-data"), "version": VERSION},
            {"type": "script", "language": "javascript", "uuid": uid("bp-script"), "version": VERSION, "entry": "scripts/main.js"},
        ],
        "dependencies": [
            {"uuid": rp_uuid, "version": VERSION},
            {"module_name": "@minecraft/server", "version": SCRIPT_API},
        ],
        "metadata": {"authors": ["Idex"]},
    })


def pack_icon(S, N, atlas):
    size = 256
    bg = np.zeros((size, size, 3))
    yy, xx = np.mgrid[0:size, 0:size] / size * 2 - 1
    r = np.hypot(xx, yy)
    bg[:] = np.array([0.07, 0.03, 0.13])
    corona = np.exp(-np.clip(r - 0.42, 0, None) / 0.12) * (r > 0.4)
    bg += corona[..., None] * np.array([1.0, 0.72, 0.3]) * 0.75
    bg *= (r > 0.4)[..., None] * 0.9 + (r <= 0.4)[..., None] * 0.08
    bg += np.exp(-((r - 0.62) / 0.02) ** 2)[..., None] * np.array([0.55, 0.3, 1.0]) * 0.8
    base = Image.fromarray((np.clip(bg, 0, 1) * 255).astype(np.uint8), "RGB").convert("RGBA")
    for mesh, roll, dx in ((S, -38, -24), (N, 38, 24)):
        front = mesh.transformed(lambda P: np.stack([P[:, 1], P[:, 0], P[:, 2]], 1), lambda Nn: np.stack([Nn[:, 1], Nn[:, 0], Nn[:, 2]], 1))
        img, mask = render([(front, atlas, True)], rot_z(roll), size=(512, 512), bg=(0, 0, 0), light=(0.3, 0.6, 0.9))
        im = Image.fromarray(np.dstack([img, (np.clip(mask, 0, 1) * 255).astype(np.uint8)]), "RGBA").resize((size, size), Image.LANCZOS)
        layer = Image.new("RGBA", (size, size))
        layer.paste(im, (dx, 0), im)
        base.alpha_composite(layer)
    for pack in (RP, BP):
        base.save(os.path.join(pack, "pack_icon.png"))
    return base


# ================================================================ previews

def build_previews(S, N, atlas, icons, fx_built):
    from mesh import render as rnd
    front = lambda m, dx: m.transformed(lambda P: np.stack([P[:, 1] + dx, P[:, 0], P[:, 2]], 1),
                                        lambda Nn: np.stack([Nn[:, 1], Nn[:, 0], Nn[:, 2]], 1))
    img, _ = rnd([(front(S, -2.8), atlas, True), (front(N, 2.8), atlas, True)], np.eye(3), size=(600, 1300), bg=(44, 24, 72))
    ref = os.environ.get("ECLIPSE_REFERENCE", "")  # optional concept art for a local side-by-side check
    out = Image.fromarray(img)
    out.save(os.path.join(PREVIEW, "swords_front.png"))
    if ref and os.path.exists(ref):
        r = Image.open(ref).convert("RGB")
        r = r.resize((int(r.width * 1300 / r.height), 1300))
        sheet = Image.new("RGB", (r.width + out.width, 1300), (20, 12, 34))
        sheet.paste(r, (0, 0))
        sheet.paste(out, (r.width, 0))
        sheet.save(os.path.join(PREVIEW, "swords_vs_reference.png"))  # git-ignored (third-party art)
    preview.model_space_sheet([swords.third_person(S, swords.SWORD_INFO["solaris"]["grip"], "right"),
                               swords.third_person(N, swords.SWORD_INFO["noctis"]["grip"], "left")],
                              atlas, os.path.join(PREVIEW, "held_model_space.png"))
    ic = Image.new("RGBA", (300, 150), (30, 18, 50, 255))
    for i, k in enumerate(("solaris", "noctis")):
        ic.alpha_composite(icons[k].resize((128, 128), Image.NEAREST), (11 + 150 * i, 11))
    ic.save(os.path.join(PREVIEW, "icons.png"))
    Image.open(os.path.join(RP, SWORD_TEX + ".png")).save(os.path.join(PREVIEW, "sword_atlas.png"))
    fx_sheet(fx_built, os.path.join(PREVIEW, "vfx_textures.png"))


def fx_sheet(built, path):
    names = list(built)
    cell, cols = 180, 6
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 16)), (18, 12, 30))
    d = ImageDraw.Draw(sheet)
    tints = {"magic_circle_solar": (1, .8, .35), "magic_circle_void": (.6, .3, 1), "void_swirl": (.6, .3, 1),
             "crack_star": (1, .75, .3), "sun_halo": (1, .8, .35), "crown_orbit": (1, .85, .45), "rune_ring": (1, .8, .4),
             "slash_arc": (1, .75, .3), "ring": (1, .85, .5), "shock_ring": (1, .8, .4)}
    for i, n in enumerate(names):
        a = built[n]
        if a.dtype != np.uint8:
            a = (np.clip(a, 0, 1) * 255).astype(np.uint8)
        im = Image.fromarray(a, "RGBA")
        s = min((cell - 8) / im.width, (cell - 8) / im.height)
        im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
        arr = np.asarray(im).astype(float) / 255
        tint = np.array(tints.get(n, (1, 1, 1)))
        if n in ("black_moon", "eclipse_disc", "void_core"):
            bgc = np.array([0.55, 0.55, 0.6])
            rgb = bgc * (1 - arr[..., 3:4]) + arr[..., :3] * arr[..., 3:4]
        else:
            rgb = np.array([18, 12, 30]) / 255 + arr[..., :3] * tint * arr[..., 3:4]
        tile = Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8), "RGB")
        r, c = divmod(i, cols)
        sheet.paste(tile, (c * cell + (cell - tile.width) // 2, r * (cell + 16) + (cell - tile.height) // 2))
        d.text((c * cell + 4, r * (cell + 16) + cell), n, fill=(220, 220, 220))
    sheet.save(path)


# ================================================================ validate

class Problems(list):
    def check(self, cond, msg):
        if not cond:
            self.append(msg)


def load_all_json(root, problems):
    data = {}
    for path in glob.glob(os.path.join(root, "**", "*.json"), recursive=True):
        try:
            with open(path, encoding="utf-8") as f:
                data[os.path.relpath(path, root).replace(os.sep, "/")] = json.load(f)
        except Exception as e:  # noqa: BLE001
            problems.append(f"invalid JSON {path}: {e}")
    return data


def validate():
    P = Problems()
    rp = load_all_json(RP, P)
    bp = load_all_json(BP, P)

    # --- particles: identifiers + textures
    particle_ids = set()
    for rel, d in rp.items():
        if rel.startswith("particles/"):
            desc = d["particle_effect"]["description"]
            particle_ids.add(desc["identifier"])
            tex = desc["basic_render_parameters"]["texture"]
            P.check(os.path.exists(os.path.join(RP, tex + ".png")), f"{rel}: missing texture {tex}")
            bb = d["particle_effect"]["components"].get("minecraft:particle_appearance_billboard", {})
            P.check(bb.get("facing_camera_mode") in {"rotate_xyz", "rotate_y", "lookat_xyz", "lookat_y", "lookat_direction",
                                                     "direction_x", "direction_y", "direction_z", "emitter_transform_xy",
                                                     "emitter_transform_xz", "emitter_transform_yz"}, f"{rel}: bad facing mode")
            if "direction" in bb:
                P.check(bb["direction"]["mode"] in ("custom", "derive_from_velocity"), f"{rel}: bad direction mode")

    # --- geometry
    geo_ids = {}
    for rel, d in rp.items():
        if rel.startswith("models/entity/"):
            for g in d["minecraft:geometry"]:
                gid = g["description"]["identifier"]
                names = {b["name"] for b in g["bones"]}
                geo_ids[gid] = names
                quads = 0
                for b in g["bones"]:
                    P.check(b.get("parent") is None or b["parent"] in names, f"{gid}: bone {b['name']} parent missing")
                    pm = b.get("poly_mesh")
                    if not pm:
                        continue
                    npos, nn, nuv = len(pm["positions"]), len(pm["normals"]), len(pm["uvs"])
                    P.check(pm.get("normalized_uvs") is True, f"{gid}/{b['name']}: normalized_uvs")
                    P.check(npos == nn == nuv, f"{gid}/{b['name']}: array length mismatch")
                    uv = np.array(pm["uvs"])
                    P.check(uv.min() >= 0 and uv.max() <= 1, f"{gid}/{b['name']}: uv out of range")
                    for poly in pm["polys"]:
                        P.check(len(poly) == 4, f"{gid}/{b['name']}: non-quad poly")
                        for vtx in poly:
                            P.check(0 <= vtx[0] < npos and 0 <= vtx[1] < nn and 0 <= vtx[2] < nuv, f"{gid}: index out of range")
                    quads += len(pm["polys"])
                    P.check(np.isfinite(np.array(pm["positions"])).all(), f"{gid}: NaN position")
                print(f"  geometry {gid}: {quads} quads")

    # --- attachables
    anim_ids = set()
    for rel, d in rp.items():
        if rel.startswith("animations/"):
            anim_ids |= set(d["animations"])
        if rel.startswith("animation_controllers/"):
            anim_ids |= set(d["animation_controllers"])
    rc_ids = set()
    for rel, d in rp.items():
        if rel.startswith("render_controllers/"):
            rc_ids |= set(d["render_controllers"])
    for rel, d in rp.items():
        if rel.startswith("attachables/"):
            desc = d["minecraft:attachable"]["description"]
            for g in desc["geometry"].values():
                P.check(g in geo_ids, f"{rel}: geometry {g} missing")
            for a in desc["animations"].values():
                P.check(a in anim_ids, f"{rel}: animation {a} missing")
            for t in desc["textures"].values():
                P.check(os.path.exists(os.path.join(RP, t + ".png")), f"{rel}: texture {t} missing")
            for rc in desc["render_controllers"]:
                key = rc if isinstance(rc, str) else next(iter(rc))
                P.check(key in rc_ids, f"{rel}: render controller {key} missing")

    # --- items
    tex_data = rp["textures/item_texture.json"]["texture_data"]
    lang_keys = set()
    with open(os.path.join(RP, "texts", "en_US.lang"), encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                lang_keys.add(line.split("=", 1)[0])
    item_ids = set()
    for rel, d in bp.items():
        if rel.startswith("items/"):
            it = d["minecraft:item"]
            ident = it["description"]["identifier"]
            item_ids.add(ident)
            icon = it["components"]["minecraft:icon"]
            P.check(icon in tex_data, f"{rel}: icon {icon} not in item_texture.json")
            P.check(os.path.exists(os.path.join(RP, tex_data.get(icon, {}).get("textures", "x") + ".png")), f"{rel}: icon png missing")
            P.check(it["components"]["minecraft:display_name"]["value"] in lang_keys, f"{rel}: display name key missing")
            P.check(os.path.exists(os.path.join(RP, "attachables", ident.split(":")[1] + ".json")), f"{rel}: no attachable")

    # --- manifests
    rpm, bpm = rp["manifest.json"], bp["manifest.json"]
    P.check(any(dep.get("uuid") == rpm["header"]["uuid"] for dep in bpm["dependencies"]), "BP does not depend on RP")
    script_mod = [m for m in bpm["modules"] if m["type"] == "script"]
    P.check(len(script_mod) == 1 and os.path.exists(os.path.join(BP, script_mod[0]["entry"])), "script entry missing")
    uuids = [rpm["header"]["uuid"], bpm["header"]["uuid"]] + [m["uuid"] for m in rpm["modules"] + bpm["modules"]]
    P.check(len(set(uuids)) == len(uuids), "duplicate UUIDs")

    # --- cross-check script references
    js = ""
    for f in glob.glob(os.path.join(BP, "scripts", "*.js")):
        with open(f, encoding="utf-8") as fh:
            js += fh.read()
    not_particles = {"eclipse_solar", "eclipse_void", "eclipse_energy", "eclipse_state", "eclipse_ult", "eclipse_immune",
                     "eclipse_idle", "eclipse_activate", "eclipse_ultimate", "solar_cast", "solar_crown", "void_crescent",
                     "solar_slash", "radiant_spear", "abyss_field", "heavens_abyss"}
    used_fx = {n for n in re.findall(r'"((?:solar|void|eclipse)_[a-z_]+)"', js) if n not in not_particles}
    for name in sorted(used_fx):
        P.check(f"{NS}:{name}" in particle_ids, f"script uses unknown particle eclipse:{name}")
    sdefs = rp["sounds/sound_definitions.json"]["sound_definitions"]
    for sid in set(re.findall(r'sound\([^,]+,\s*"([a-z_.]+)"', js)):
        P.check(sid in sdefs, f"script uses unknown sound {sid}")
    for sid, d in sdefs.items():
        for s in d["sounds"]:
            P.check(os.path.exists(os.path.join(RP, s["name"] + ".ogg")), f"sound file missing for {sid}")
    for a in set(re.findall(r'anim\(\s*player,\s*"([a-z_]+)"', js)) | set(re.findall(r'"(idle_solaris|idle_noctis|eclipse_idle)"', js)):
        P.check(f"animation.{NS}.{a}" in anim_ids, f"script plays unknown animation {a}")
    P.check(f"{NS}:black_eclipse" in {d["minecraft:fog_settings"]["description"]["identifier"] for r, d in rp.items() if r.startswith("fogs/")},
            "fog eclipse:black_eclipse missing")
    for ident in ("eclipse:solaris", "eclipse:noctis"):
        P.check(ident in item_ids, f"item {ident} missing")

    print(f"  particles: {len(particle_ids)} | sounds: {len(sdefs)} | script particle refs: {len(used_fx)}")
    return P


# ================================================================== package

def package():
    ensure_dir(DIST)
    out = os.path.join(DIST, "EclipseTwinSwords.mcaddon")
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for pack, folder in ((BP, "EclipseTwinSwords_BP"), (RP, "EclipseTwinSwords_RP")):
            for path in sorted(glob.glob(os.path.join(pack, "**", "*"), recursive=True)):
                if os.path.isdir(path):
                    continue
                rel = os.path.relpath(path, pack).replace(os.sep, "/")
                z.write(path, f"{folder}/{rel}")
    return out


def main():
    print("cleaning")
    clean()
    print("particle textures")
    fx_built = fxtex.build_all()
    print("particles")
    particles.build_all()
    print("models")
    S, N, atlas, icons = build_models()
    build_attachables()
    print("sounds")
    build_sounds()
    build_fog()
    build_texts()
    build_bp()
    build_manifests()
    pack_icon(S, N, atlas)
    print("previews")
    build_previews(S, N, atlas, icons, fx_built)
    print("validating")
    problems = validate()
    if problems:
        print("VALIDATION FAILED:")
        for p in problems[:50]:
            print("  -", p)
        sys.exit(1)
    out = package()
    print(f"OK -> {out} ({os.path.getsize(out) / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
