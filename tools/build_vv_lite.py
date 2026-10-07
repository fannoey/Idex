#!/usr/bin/env python3
"""Generate "Idex VV Lite" – a Vibrant Visuals resource pack tuned for
low-end phones (e.g. Helio G99 / Mali-G57 MC2).

Vibrant Visuals' heavy passes (shadows, reflections, render resolution) are
controlled by the player's video settings, not by packs – see the README for
the settings that matter most. What a pack *can* do is switch off the costly
effects it owns and keep the look nice:

  * water/water.json         caustics + waves off for minecraft:default_water
                             (every vanilla biome uses that water)
  * fogs/*.json              every vanilla fog that has volumetric fog is
                             re-declared with the same distance fog but zero
                             volumetric density (no glowing haze to compute
                             through), so turning "Volumetric Fog" Off in
                             settings doesn't change how the world looks
  * color_grading/           a bit more contrast/saturation and a warmer white
                             (single fullscreen pass the game runs anyway)
  * lighting/global.json     vanilla sun/moon curves with slightly brighter
                             ambient light, so caves/shade aren't pitch black
                             when shadow quality is low

The vanilla fog/lighting data is read from a checkout of Mojang's official
samples (https://github.com/Mojang/bedrock-samples):

  git clone --depth 1 https://github.com/Mojang/bedrock-samples ../mojang/bedrock-samples
  python3 tools/build_vv_lite.py [path/to/bedrock-samples]
"""
import copy
import glob
import json
import os
import shutil
import sys
import uuid
import zipfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "idex_vv_lite")
RP = os.path.join(OUT, "Idex_VV_Lite_RP")
DIST = os.path.join(ROOT, "dist")

VERSION = [1, 0, 0]
MIN_ENGINE = [1, 21, 120]          # "pbr" capability needs 1.21.120+

# Ambient light: vanilla 0.02. A little more keeps shaded areas readable when
# shadow quality is on Low/Off on a phone.
AMBIENT = 0.05

COLOR_GRADING = {
    "contrast": 1.18,
    "saturation": 1.15,
    "gamma": 2.2,
    "temperature": 6000,           # vanilla 6500; lower = warmer image
}


def samples_dir():
    cands = sys.argv[1:] + [os.environ.get("BEDROCK_SAMPLES", ""),
                            os.path.join(ROOT, "..", "mojang", "bedrock-samples"),
                            os.path.join(ROOT, "..", "bedrock-samples")]
    for c in cands:
        if c and os.path.isdir(os.path.join(c, "resource_pack", "fogs")):
            return os.path.join(c, "resource_pack")
    sys.exit("bedrock-samples not found – see the docstring at the top of this file")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def make_uuid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"idex/vv_lite/{name}"))


def lite_fogs(src):
    """Same distance fog as vanilla, volumetric fog emptied."""
    out = {}
    for path in sorted(glob.glob(os.path.join(src, "fogs", "*.json"))):
        data = load(path)
        fog = data["minecraft:fog_settings"]
        vol = fog.get("volumetric")
        if not vol:
            continue
        lite = copy.deepcopy(data)
        v = lite["minecraft:fog_settings"]["volumetric"]
        for medium in v.get("density", {}).values():
            medium["max_density"] = 0.0
        for medium in v.get("media_coefficients", {}).values():
            medium["scattering"] = [0.0, 0.0, 0.0]
            medium["absorption"] = [0.0, 0.0, 0.0]
        lite["format_version"] = "1.21.90"
        out[os.path.basename(path)] = lite
    return out


def lite_water(src):
    data = load(os.path.join(src, "water", "water.json"))
    w = data["minecraft:water_settings"]
    w["caustics"]["enabled"] = False
    w["waves"]["enabled"] = False
    return data


def lite_lighting(src):
    data = load(os.path.join(src, "lighting", "global.json"))
    data["minecraft:lighting_settings"]["ambient"]["illuminance"] = AMBIENT
    return data


def lite_color_grading(src):
    data = load(os.path.join(src, "color_grading", "color_grading.json"))
    cg = data["minecraft:color_grading_settings"]["color_grading"]
    mid = cg["midtones"]
    mid["contrast"] = [COLOR_GRADING["contrast"]] * 3
    mid["saturation"] = [COLOR_GRADING["saturation"]] * 3
    mid["gamma"] = [COLOR_GRADING["gamma"]] * 3
    cg["temperature"]["temperature"] = COLOR_GRADING["temperature"]
    return data


def font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def pack_icon():
    s = 256
    im = Image.new("RGB", (s, s))
    d = ImageDraw.Draw(im)
    for y in range(s):
        t = y / (s - 1)
        d.line([(0, y), (s, y)], fill=(int(30 + 200 * t), int(60 + 90 * t), int(150 - 40 * t)))
    d.ellipse([88, 96, 168, 176], fill=(255, 238, 200))
    d.polygon([(0, 196), (70, 170), (140, 192), (200, 165), (256, 185), (256, 256), (0, 256)],
              fill=(28, 56, 44))
    d.text((128, 40), "VV LITE", font=font(46), fill=(255, 255, 255), anchor="mm",
           stroke_width=3, stroke_fill=(20, 30, 60))
    d.text((128, 226), "low-end", font=font(30), fill=(255, 236, 200), anchor="mm",
           stroke_width=2, stroke_fill=(20, 30, 40))
    return im


def main():
    src = samples_dir()
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(DIST, exist_ok=True)

    write_json(os.path.join(RP, "manifest.json"), {
        "format_version": 2,
        "header": {
            "name": "Idex VV Lite",
            "description": "Vibrant Visuals เบาสำหรับมือถือสเปคต่ำ\nNo caustics / no volumetric fog, warmer grading",
            "uuid": make_uuid("rp"),
            "version": VERSION,
            "min_engine_version": MIN_ENGINE,
        },
        "modules": [{"type": "resources", "uuid": make_uuid("rp/module"), "version": VERSION}],
        "capabilities": ["pbr"],
    })

    fogs = lite_fogs(src)
    for name, data in fogs.items():
        write_json(os.path.join(RP, "fogs", name), data)
    write_json(os.path.join(RP, "water", "water.json"), lite_water(src))
    write_json(os.path.join(RP, "lighting", "global.json"), lite_lighting(src))
    write_json(os.path.join(RP, "color_grading", "color_grading.json"), lite_color_grading(src))
    pack_icon().save(os.path.join(RP, "pack_icon.png"))

    out = os.path.join(DIST, "Idex_VV_Lite.mcpack")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _, files in sorted(os.walk(RP)):
            for fn in sorted(files):
                full = os.path.join(dp, fn)
                z.write(full, os.path.join("Idex_VV_Lite_RP", os.path.relpath(full, RP)))
    print(f"{len(fogs)} fogs; wrote {out}")


if __name__ == "__main__":
    main()
