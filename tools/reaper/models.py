"""Writers for the scythe mesh: Blockbench .bbmodel files and Bedrock poly_mesh geometry."""
import base64
import io
import json
import uuid

import numpy as np
from PIL import Image

import rig

BB_FORMAT = "4.10"     # pre-5.0: Blockbench converts keyframes from Bedrock-style values on load


def uid():
    return str(uuid.uuid4())


def png_data_url(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def bb_texture(img, name, idx):
    return {
        "path": "", "name": name, "folder": "", "namespace": "", "id": str(idx),
        "width": img.width, "height": img.height, "uv_width": img.width, "uv_height": img.height,
        "particle": False, "layers_enabled": False, "sync_to_project": "", "render_mode": "default",
        "render_sides": "auto", "frame_time": 1, "frame_order_type": "loop", "frame_order": "",
        "frame_interpolate": False, "visible": True, "internal": True, "saved": False,
        "uuid": uid(), "relative_path": "", "source": png_data_url(img),
    }


def bb_mesh(name, pos, uv, polys, origin=(0, 0, 0), tex=0):
    """Blockbench mesh element. pos are absolute; stored relative to origin."""
    origin = np.asarray(origin, float)
    keys = [f"v{i:05d}" for i in range(len(pos))]
    verts = {k: [round(float(c), 4) for c in (p - origin)] for k, p in zip(keys, pos)}
    faces = {}
    for fi, poly in enumerate(polys):
        uniq = []
        for i in poly:
            if keys[i] not in uniq:
                uniq.append(keys[i])
        if len(uniq) < 3:
            continue
        faces[f"f{fi:05d}"] = {
            "uv": {k: [round(float(uv[int(k[1:])][0]), 3), round(float(uv[int(k[1:])][1]), 3)] for k in uniq},
            "vertices": uniq,
            "texture": tex,
        }
    return {
        "name": name, "color": 0, "origin": [float(v) for v in origin], "rotation": [0, 0, 0],
        "export": True, "visibility": True, "locked": False, "render_order": "default",
        "allow_mirror_modeling": True, "vertices": verts, "faces": faces, "type": "mesh", "uuid": uid(),
    }


def bb_cube(name, a, b, origin, uv_rect, tex):
    u0, v0, u1, v1 = uv_rect
    faces = {k: {"uv": [u0, v0, u1, v1], "texture": tex} for k in ("north", "east", "south", "west", "up", "down")}
    return {
        "name": name, "box_uv": False, "rescale": False, "locked": False, "render_order": "default",
        "allow_mirror_modeling": True, "from": list(map(float, a)), "to": list(map(float, b)),
        "autouv": 0, "color": 0, "origin": list(map(float, origin)), "faces": faces,
        "type": "cube", "uuid": uid(),
    }


def bb_group(name, origin, children):
    return {
        "name": name, "origin": [float(v) for v in origin], "color": 0, "uuid": uid(), "export": True,
        "mirror_uv": False, "isOpen": True, "locked": False, "visibility": True, "autouv": 0,
        "children": children,
    }


def bb_project(name, elements, outliner, textures, animations=None):
    res = textures[0]
    return {
        "meta": {"format_version": BB_FORMAT, "model_format": "free", "box_uv": False},
        "name": name, "model_identifier": "", "visible_box": [4, 4, 1],
        "variable_placeholders": "", "variable_placeholder_buttons": [],
        "timeline_setups": [], "unhandled_root_fields": {},
        "resolution": {"width": res["width"], "height": res["height"]},
        "elements": elements, "outliner": outliner, "textures": textures,
        "animations": animations or [],
    }


# ---------------------------------------------------------------- static scythe
def static_bbmodel(parts, tex_img, name="cursed_reaper_scythe"):
    elements = [bb_mesh(n, p["pos"], p["uv"], p["polys"]) for n, p in parts.items()]
    outliner = [bb_group(name, (0, 0, 0), [e["uuid"] for e in elements])]
    return bb_project(name, elements, outliner, [bb_texture(tex_img, name + ".png", 0)])


# ---------------------------------------------------------------- posed rig + animations
PLAYER_TEX = {  # flat colour patches on a 32x32 dummy skin
    "head": ((0, 0, 8, 8), (196, 162, 128)),
    "body": ((8, 0, 16, 8), (28, 22, 30)),
    "arm": ((16, 0, 24, 8), (40, 30, 42)),
    "leg": ((24, 0, 32, 8), (18, 16, 20)),
    "trim": ((0, 8, 8, 16), (140, 18, 26)),
}


def player_texture():
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    px = img.load()
    for (u0, v0, u1, v1), col in PLAYER_TEX.values():
        for y in range(v0, v1):
            for x in range(u0, u1):
                px[x, y] = col + (255,)
    return img


def scythe_in_hand(parts, scythe):
    """Mesh parts posed at rest on rightItem (Blockbench space)."""
    out = {}
    for n, p in parts.items():
        pos = rig.HAND["rightArm"] + scythe.local(p["pos"])
        nrm = p["nrm"] @ rig.N_MOUNT.T
        out[n] = dict(p, pos=pos, nrm=nrm)
    return out


def rig_bbmodel(parts, tex_img, scythe, clips, name="cursed_reaper_animations"):
    held = scythe_in_hand(parts, scythe)
    elements = []
    boxes = {
        "head": (("head", (-4, 24, -4), (4, 32, 4)),),
        "body": (("body", (-4, 12, -2), (4, 24, 2)),),
        "rightArm": (("right_arm", (4, 12, -2), (8, 24, 2)),),
        "leftArm": (("left_arm", (-8, 12, -2), (-4, 24, 2)),),
        "rightLeg": (("right_leg", (-0.1, 0, -2), (3.9, 12, 2)),),
        "leftLeg": (("left_leg", (-3.9, 0, -2), (0.1, 12, 2)),),
    }
    patch = {"head": "head", "body": "body", "rightArm": "arm", "leftArm": "arm", "rightLeg": "leg", "leftLeg": "leg"}
    groups = {}
    children = {b: [] for b in rig.BONES}
    for bone, cubes in boxes.items():
        for cname, a, b in cubes:
            c = bb_cube(cname, a, b, rig.BONES[bone][1], PLAYER_TEX[patch[bone]][0], 1)
            elements.append(c)
            children[bone].append(c["uuid"])
    for n, p in held.items():
        m = bb_mesh("scythe_" + n, p["pos"], p["uv"], p["polys"], origin=rig.HAND["rightArm"], tex=0)
        elements.append(m)
        children["rightItem"].append(m["uuid"])

    def build(bone):
        kids = list(children[bone])
        for child, (parent, _) in rig.BONES.items():
            if parent == bone:
                kids.append(build(child))
        g = bb_group(bone, rig.BONES[bone][1], kids)
        groups[bone] = g["uuid"]
        return g

    outliner = [build("root")]
    anims = [bb_animation(c, groups) for c in clips]
    textures = [bb_texture(tex_img, "cursed_reaper_scythe.png", 0), bb_texture(player_texture(), "dummy_player.png", 1)]
    return bb_project(name, elements, outliner, textures, anims)


def bb_animation(clip, groups):
    animators = {}
    data = clip.bedrock()
    for bone, chans in data["bones"].items():
        kfs = []
        for chan, key in (("rotation", "rotation"), ("position", "position")):
            for t, v in chans.get(key, {}).items():
                interp = "linear"
                if isinstance(v, dict):
                    interp = v.get("lerp_mode", "linear")
                    v = v["post"]
                kfs.append({"channel": chan, "data_points": [{"x": v[0], "y": v[1], "z": v[2]}],
                            "uuid": uid(), "time": float(t), "color": -1, "interpolation": interp})
        animators[groups[bone]] = {"name": bone, "type": "bone", "keyframes": kfs}
    loop = {True: "loop", "hold_on_last_frame": "hold"}.get(clip.loop, "once")
    return {"uuid": uid(), "name": clip.name, "loop": loop, "override": bool(clip.override),
            "length": clip.length, "snapping": 24, "selected": False, "anim_time_update": "",
            "blend_weight": "", "start_delay": "", "loop_delay": "", "animators": animators}


# ---------------------------------------------------------------- Bedrock poly_mesh
def mirror_texture(img):
    """Content in the top half, vertically mirrored copy in the bottom half, so the
    UVs land on the same pixels whichever way the engine reads normalized v."""
    w, h = img.size
    out = Image.new(img.mode, (w, h * 2))
    out.paste(img, (0, 0))
    out.paste(img.transpose(Image.FLIP_TOP_BOTTOM), (0, h))
    return out


def poly_mesh(pos, nrm, uv, polys, tex_w, tex_h):
    """Bedrock poly_mesh (quads only). pos/nrm in Blockbench space -> mirrored x."""
    P = np.c_[-pos[:, 0], pos[:, 1], pos[:, 2]]
    N = np.c_[-nrm[:, 0], nrm[:, 1], nrm[:, 2]]
    N /= np.linalg.norm(N, axis=1)[:, None] + 1e-9
    U = np.c_[uv[:, 0] / tex_w, uv[:, 1] / (2 * tex_h)]        # top half of the mirrored atlas
    out = []
    for poly in polys:
        q = list(poly)[::-1]                                      # mirror flips winding
        if len(q) == 3:
            q = q + [q[-1]]
        out.append([[int(i), int(i), int(i)] for i in q])
    r = lambda a, d: [[round(float(x), d) for x in row] for row in a]
    return {"normalized_uvs": True, "positions": r(P, 4), "normals": r(N, 4), "uvs": r(U, 5), "polys": out}


def attachable_geo(parts, scythe, tex_size, locators, identifier):
    held = scythe_in_hand(parts, scythe)
    m = lambda p: [round(-p[0], 3), round(p[1], 3), round(p[2], 3)]
    bones = [
        {"name": "root", "pivot": [0, 0, 0]},
        {"name": "waist", "parent": "root", "pivot": [0, 12, 0]},
        {"name": "body", "parent": "waist", "pivot": [0, 24, 0]},
        {"name": "rightArm", "parent": "body", "pivot": [-5, 22, 0]},
        {"name": "rightItem", "parent": "rightArm", "pivot": [-6, 15, 1]},
        {"name": "reaper", "parent": "rightItem", "pivot": [-6, 15, 1],
         "locators": {k: m(rig.HAND["rightArm"] + scythe.local(v)[0]) for k, v in locators.items()}},
    ]
    for n, p in held.items():
        bones.append({"name": "reaper_" + n, "parent": "reaper", "pivot": [-6, 15, 1],
                      "poly_mesh": poly_mesh(p["pos"], p["nrm"], p["uv"], p["polys"], *tex_size)})
    allp = np.concatenate([p["pos"] for p in held.values()])
    return {
        "format_version": "1.16.0",
        "minecraft:geometry": [{
            "description": {
                "identifier": identifier, "texture_width": tex_size[0], "texture_height": tex_size[1] * 2,
                "visible_bounds_width": 7, "visible_bounds_height": 7, "visible_bounds_offset": [0, 1.5, 0],
            },
            "bones": bones,
        }],
    }, allp


def dump(obj, path, compact=False):
    with open(path, "w") as f:
        if compact:
            json.dump(obj, f, separators=(",", ":"))
        else:
            json.dump(obj, f, indent="\t")
