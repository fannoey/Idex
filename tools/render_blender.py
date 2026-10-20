#!/usr/bin/env python3
"""Render a .bbmodel with Blender (bpy, headless) for high-quality previews.

The meshes are rebuilt straight from the .bbmodel JSON (same vertices, faces
and UVs Blockbench loads), so the render shows exactly the delivered model.

    pip install bpy        # Blender as a Python module (needs Python 3.13)
    python3 tools/render_blender.py Output/grim_reaper_scythe.bbmodel Output
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

src, out_dir = sys.argv[1], sys.argv[2]
model = json.load(open(src))
tex_w = model["resolution"]["width"]
tex_h = model["resolution"]["height"]
tex_path = os.path.join(os.path.dirname(os.path.abspath(src)), model["textures"][0]["relative_path"])

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def bb_to_blender(p):
    # Blockbench: Y up, +Z towards the front camera. Blender: Z up, front camera looks along +Y.
    return Vector((p[0], -p[2], p[1]))


# material: the delivered texture + glossy metal response
mat = bpy.data.materials.new("scythe")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
teximg = nt.nodes.new("ShaderNodeTexImage")
teximg.image = bpy.data.images.load(tex_path)
teximg.interpolation = "Linear"
nt.links.new(teximg.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Metallic"].default_value = 0.55
bsdf.inputs["Roughness"].default_value = 0.22

for el in model["elements"]:
    origin = el["origin"]
    keys = list(el["vertices"])
    index = {k: i for i, k in enumerate(keys)}
    verts = [bb_to_blender([origin[i] + el["vertices"][k][i] for i in range(3)]) for k in keys]
    faces, uvs = [], []
    for f in el["faces"].values():
        faces.append([index[k] for k in f["vertices"]])
        uvs.append([(f["uv"][k][0] / tex_w, 1 - f["uv"][k][1] / tex_h) for k in f["vertices"]])
    me = bpy.data.meshes.new(el["name"])
    me.from_pydata(verts, [], faces)
    uvl = me.uv_layers.new()
    li = 0
    for poly, puv in zip(me.polygons, uvs):
        for j in range(poly.loop_total):
            uvl.data[poly.loop_start + j].uv = puv[j]
        li += poly.loop_total
    if el.get("shading") == "smooth":
        me.shade_smooth()
    me.materials.append(mat)
    ob = bpy.data.objects.new(el["name"], me)
    scene.collection.objects.link(ob)

# world + lights (studio: key from upper left, rim from the right, soft fill)
world = bpy.data.worlds.new("w")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (0.82, 0.82, 0.84, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
scene.world = world


def light(name, loc, energy, size):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.size = size
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    scene.collection.objects.link(ob)
    d = Vector((0, 0, 36)) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


light("key", (-60, -80, 90), 60000, 40)
light("rim", (70, 40, 70), 30000, 30)
light("fill", (30, -90, 10), 12000, 60)

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 48
scene.cycles.use_denoising = True
scene.render.film_transparent = False
scene.view_settings.view_transform = "Standard"


def render(name, loc, target, ortho=None, res=(1000, 1400)):
    cam_d = bpy.data.cameras.new(name)
    cam = bpy.data.objects.new(name, cam_d)
    scene.collection.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    if ortho:
        cam_d.type = "ORTHO"
        cam_d.ortho_scale = ortho
    else:
        cam_d.lens = 50
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.filepath = os.path.join(out_dir, name)
    bpy.ops.render.render(write_still=True)


render("preview_blender_front.png", (0, -150, 36), (0, 0, 36), ortho=76)
render("preview_blender_3quarter.png", (78, -98, 56), (1, 0, 35))
print("done")
