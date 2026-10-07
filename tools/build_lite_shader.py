#!/usr/bin/env python3
"""Generate "Idex Lite Shader" – a zero-cost lighting/atmosphere resource pack
for Minecraft Bedrock on low-end phones (e.g. Helio G99 / Mali-G57 MC2).

It does NOT replace the game's shaders (that needs a patched client), so it
runs on the normal renderer at the same FPS as vanilla. The "shader look"
comes from things the engine already draws every frame anyway:

  * fogs/            soft atmospheric distance fog that also hides chunk edges
                     at low render distance, rain haze, clear underwater fog
  * biomes_client    clearer, deeper water colours per biome
  * environment/     sun & moon with a soft glow halo (fake bloom), thinner
                     clouds
  * colormap/        warmer, slightly more saturated grass & leaves

Run:  python3 tools/build_lite_shader.py
"""
import json
import math
import os
import shutil
import uuid
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "idex_lite_shader")
RP = os.path.join(OUT, "Idex_Lite_Shader_RP")
DIST = os.path.join(ROOT, "dist")
PREVIEW = os.path.join(ROOT, "preview_shader")

NS = "idex"
VERSION = [1, 0, 0]
MIN_ENGINE = [1, 21, 40]


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def save_png(path, arr):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(path, optimize=True)


def make_uuid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"idex/lite_shader/{name}"))


def hexc(rgb):
    return "#%02X%02X%02X" % tuple(int(round(c)) for c in rgb)


# --------------------------------------------------------------------------
# Fog + water
# --------------------------------------------------------------------------
# Air fog: starts at 55% of render distance and fades to the sky colour at the
# edge. On a phone running 6-10 chunks this hides the hard chunk border and
# gives depth ("aerial perspective") for free. The engine darkens fog colour
# at night by itself, the same way it does for vanilla's #ABD2FF.
AIR = dict(fog_start=0.55, fog_end=1.0, fog_color="#B4CDEB", render_distance_type="render")
RAIN = dict(fog_start=0.18, fog_end=0.75, fog_color="#8D99A6", render_distance_type="render")

# water styles: (surface colour, surface transparency, underwater fog colour,
#                underwater visibility in blocks)
WATER = {
    "clear": ("#3F8FE0", 0.55, "#2E7FC9", 44),
    "warm": ("#33C6D8", 0.45, "#2DB5C8", 56),
    "cold": ("#3667C4", 0.60, "#24519E", 32),
    "river": ("#3E84D6", 0.55, "#2F6FB8", 36),
    "swamp": ("#5C7A4A", 0.75, "#45603A", 14),
    "mangrove": ("#4F7F63", 0.72, "#3D6A50", 16),
    "frozen": ("#3A6BC0", 0.62, "#2C5AA6", 28),
}

# biome name (biomes_client.json key) -> water style. Unlisted biomes keep
# vanilla settings; "default" covers anything that has no entry of its own.
BIOMES = {
    "default": "clear",
    "plains": "clear", "sunflower_plains": "clear", "forest": "clear",
    "flower_forest": "clear", "birch_forest": "clear", "roofed_forest": "clear",
    "taiga": "cold", "mega_taiga": "cold", "cold_taiga": "frozen",
    "extreme_hills": "cold", "savanna": "warm", "mesa": "warm",
    "desert": "warm", "jungle": "warm", "bamboo_jungle": "warm",
    "beach": "clear", "stone_beach": "clear", "cold_beach": "frozen",
    "mushroom_island": "clear", "cherry_grove": "clear", "meadow": "clear",
    "grove": "frozen", "snowy_slopes": "frozen", "jagged_peaks": "frozen",
    "frozen_peaks": "frozen", "stony_peaks": "cold", "ice_plains": "frozen",
    "pale_garden": "cold", "lush_caves": "warm", "dripstone_caves": "clear",
    "river": "river", "frozen_river": "frozen",
    "ocean": "clear", "deep_ocean": "clear",
    "lukewarm_ocean": "warm", "deep_lukewarm_ocean": "warm", "warm_ocean": "warm",
    "cold_ocean": "cold", "deep_cold_ocean": "cold",
    "frozen_ocean": "frozen", "deep_frozen_ocean": "frozen",
    "swampland": "swamp", "mangrove_swamp": "mangrove",
}


def fog_file(style):
    surface, _, fog_col, dist = WATER[style]
    return {
        "format_version": "1.16.100",
        "minecraft:fog_settings": {
            "description": {"identifier": f"{NS}:lite_{style}"},
            "distance": {
                "air": dict(AIR),
                "weather": dict(RAIN),
                "water": dict(fog_start=0.0, fog_end=dist, fog_color=fog_col,
                              render_distance_type="fixed"),
            },
        },
    }


def biomes_client():
    out = {}
    for biome, style in BIOMES.items():
        surface, transp, fog_col, dist = WATER[style]
        out[biome] = {
            "water_surface_color": surface,
            "water_surface_transparency": transp,
            "water_fog_color": fog_col,
            "water_fog_distance": dist,
            "fog_identifier": f"{NS}:lite_{style}",
        }
    return {"biomes": out}


# --------------------------------------------------------------------------
# Sky textures
# --------------------------------------------------------------------------
def radial(size):
    c = (size - 1) / 2
    y, x = np.mgrid[0:size, 0:size]
    return np.hypot(x - c, y - c) / (size / 2)


def glow_rgba(rgb_core, rgb_halo, r, core=0.30, halo_pow=2.2, halo_gain=0.55):
    """Disc + soft halo. RGB is pre-multiplied by alpha so it looks right with
    both additive and alpha blending (black stays invisible either way)."""
    disc = np.clip((core - r) / 0.03 + 0.5, 0, 1)          # anti-aliased edge
    halo = np.clip(1 - r, 0, 1) ** halo_pow * halo_gain
    a = np.clip(disc + halo * (1 - disc), 0, 1)
    rgb = (np.array(rgb_core)[None, None] * disc[..., None]
           + np.array(rgb_halo)[None, None] * (halo * (1 - disc))[..., None])
    rgb = rgb / np.maximum(a, 1e-6)[..., None]
    out = np.zeros(r.shape + (4,))
    out[..., :3] = rgb * a[..., None]
    out[..., 3] = a * 255
    return out


def sun_texture(size=64):
    r = radial(size)
    return glow_rgba((255, 247, 214), (255, 196, 120), r, core=0.30)


def moon_texture(cell=32):
    """moon_phases.png: 4x2 grid, phases 0 (full) .. 7 like vanilla."""
    img = np.zeros((cell * 2, cell * 4, 4))
    r = radial(cell)
    c = (cell - 1) / 2
    y, x = np.mgrid[0:cell, 0:cell]
    nx, ny = (x - c) / (cell * 0.28), (y - c) / (cell * 0.28)
    rng = np.random.default_rng(7)
    craters = np.zeros((cell, cell))
    for _ in range(7):
        cx, cy, cr = rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(0.12, 0.25)
        craters += np.clip(1 - np.hypot(nx - cx, ny - cy) / cr, 0, 1) * 0.18
    # phase k: sun direction rotates 45 deg per phase around the moon
    nz = np.sqrt(np.clip(1 - nx ** 2 - ny ** 2, 0, 1))
    inside = np.hypot(nx, ny) <= 1.0
    for k in range(8):
        base = glow_rgba((222, 230, 255), (150, 175, 255), r, core=0.28,
                         halo_pow=2.6, halo_gain=0.35)
        th = k * math.pi / 4
        light = nx * math.sin(th) + nz * math.cos(th)
        lit = np.clip(light / 0.15 + 0.5, 0, 1)            # soft terminator
        shade = np.where(inside, 0.10 + 0.90 * lit * (1.0 - craters), 1.0)
        base[..., :3] *= shade[..., None]
        gx, gy = (k % 4) * cell, (k // 4) * cell
        img[gy:gy + cell, gx:gx + cell] = base
    return img


def value_noise(w, h, cells, seed):
    rng = np.random.default_rng(seed)
    g = rng.random((cells + 1, cells + 1))
    g[-1, :], g[:, -1] = g[0, :], g[:, 0]        # tileable
    y, x = np.mgrid[0:h, 0:w]
    fx, fy = x / w * cells, y / h * cells
    ix, iy = fx.astype(int), fy.astype(int)
    tx, ty = fx - ix, fy - iy
    tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
    a, b = g[iy, ix], g[iy, ix + 1]
    c, d = g[iy + 1, ix], g[iy + 1, ix + 1]
    return (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty


def clouds_texture(size=256):
    """White where there is cloud. Slightly less coverage than vanilla so the
    sky reads cleaner; hard edges keep 'Fancy' 3D clouds working."""
    n = (value_noise(size, size, 8, 1) * 0.6 + value_noise(size, size, 16, 2) * 0.3
         + value_noise(size, size, 32, 3) * 0.1)
    mask = n > 0.60
    img = np.zeros((size, size, 4))
    img[mask] = (255, 255, 255, 255)
    return img


# --------------------------------------------------------------------------
# Colour maps (temperature on x, humidity*temperature on y, like vanilla)
# --------------------------------------------------------------------------
def colormap(hot_wet, hot_dry, cold, sat=1.15, warm=(1.04, 1.0, 0.94)):
    s = 256
    y, x = np.mgrid[0:s, 0:s] / (s - 1)
    temp = 1 - x
    hum = np.clip((1 - y) / np.maximum(temp, 1e-6), 0, 1)
    # barycentric blend across the triangle
    w_cold = 1 - temp
    w_wet = temp * hum
    w_dry = temp * (1 - hum)
    rgb = (np.array(hot_wet)[None, None] * w_wet[..., None]
           + np.array(hot_dry)[None, None] * w_dry[..., None]
           + np.array(cold)[None, None] * w_cold[..., None])
    grey = rgb.mean(axis=2, keepdims=True)
    rgb = grey + (rgb - grey) * sat
    rgb = np.clip(rgb * np.array(warm)[None, None], 0, 255)
    out = np.zeros((s, s, 4))
    out[..., :3] = rgb
    out[..., 3] = 255
    return out


# --------------------------------------------------------------------------
# Icon + preview
# --------------------------------------------------------------------------
def font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def sky_gradient(w, h, top, bottom):
    t = np.linspace(0, 1, h)[:, None, None]
    return np.array(top)[None, None] * (1 - t) + np.array(bottom)[None, None] * t \
        + np.zeros((h, w, 3))


def paste_glow(canvas, tex, cx, cy):
    th, tw = tex.shape[:2]
    x0, y0 = cx - tw // 2, cy - th // 2
    region = canvas[y0:y0 + th, x0:x0 + tw]
    region += tex[..., :3]                    # additive, like the game's sky
    np.clip(region, 0, 255, out=region)


def pack_icon(sun):
    s = 256
    img = sky_gradient(s, s, (40, 70, 140), (255, 170, 110))
    big = np.array(Image.fromarray(sun.astype(np.uint8), "RGBA").resize((200, 200), Image.BICUBIC)).astype(float)
    big[..., :3] *= big[..., 3:4] / 255
    paste_glow(img, big, 128, 150)
    hills = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(hills)
    d.polygon([(0, 200), (60, 175), (120, 195), (190, 168), (256, 190), (256, 256), (0, 256)], fill=255)
    m = np.array(hills)[..., None] / 255
    img = img * (1 - m) + np.array((30, 60, 45)) * m
    im = Image.fromarray(img.astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.text((128, 30), "LITE", font=font(54), fill=(255, 255, 255), anchor="mm",
           stroke_width=3, stroke_fill=(20, 30, 60))
    d.text((128, 228), "SHADER", font=font(34), fill=(255, 236, 200), anchor="mm",
           stroke_width=2, stroke_fill=(20, 30, 40))
    return im


def preview(sun, moon, clouds, grass, foliage):
    W, H = 1100, 560
    im = Image.new("RGB", (W, H), (24, 26, 32))
    d = ImageDraw.Draw(im)
    f, fs = font(22), font(14)

    def panel(x, y, w, h, top, bottom, label):
        g = sky_gradient(w, h, top, bottom)
        return g, (x, y, label)

    # day
    day, _ = panel(0, 0, 520, 300, (70, 125, 215), (180, 205, 235), "")
    paste_glow(day, np.array(Image.fromarray(sun.astype(np.uint8), "RGBA").resize((160, 160))).astype(float), 380, 110)
    cl = clouds[:60, :256, 3:4] / 255
    day[200:260, 130:386] = day[200:260, 130:386] * (1 - cl * 0.85) + 255 * cl * 0.85
    # night
    night, _ = panel(0, 0, 520, 300, (6, 9, 24), (34, 44, 74), "")
    m = np.array(Image.fromarray(moon[:32, :32].astype(np.uint8), "RGBA").resize((128, 128), Image.NEAREST)).astype(float)
    m[..., :3] *= 1.0
    paste_glow(night, m, 150, 110)
    for k in range(8):
        cell = moon[(k // 4) * 32:(k // 4) * 32 + 32, (k % 4) * 32:(k % 4) * 32 + 32]
        paste_glow(night, np.array(Image.fromarray(cell.astype(np.uint8), "RGBA").resize((48, 48), Image.NEAREST)).astype(float),
                   290 + (k % 4) * 56, 80 + (k // 4) * 70)
    im.paste(Image.fromarray(day.astype(np.uint8)), (20, 50))
    im.paste(Image.fromarray(night.astype(np.uint8)), (560, 50))
    d.text((20, 15), "Sun + glow halo / clouds", font=f, fill=(235, 235, 235))
    d.text((560, 15), "Moon phases + glow", font=f, fill=(235, 235, 235))

    # water + colormaps
    y0 = 380
    d.text((20, y0 - 30), "Water (surface / underwater fog)", font=f, fill=(235, 235, 235))
    for i, (name, (surf, tr, fogc, dist)) in enumerate(WATER.items()):
        x = 20 + i * 76
        d.rectangle([x, y0, x + 66, y0 + 50], fill=surf)
        d.rectangle([x, y0 + 50, x + 66, y0 + 100], fill=fogc)
        d.text((x + 33, y0 + 112), name, font=fs, fill=(220, 220, 220), anchor="mm")
        d.text((x + 33, y0 + 132), f"{dist} blk", font=fs, fill=(160, 160, 170), anchor="mm")
    d.text((600, y0 - 30), "Grass / foliage colormap", font=f, fill=(235, 235, 235))
    im.paste(Image.fromarray(grass[..., :3].astype(np.uint8)).resize((140, 140)), (600, y0))
    im.paste(Image.fromarray(foliage[..., :3].astype(np.uint8)).resize((140, 140)), (760, y0))
    d.text((920, y0), "fog: 55%→100%", font=fs, fill=(220, 220, 220))
    d.text((920, y0 + 22), f"air {AIR['fog_color']}", font=fs, fill=AIR["fog_color"])
    d.text((920, y0 + 44), f"rain {RAIN['fog_color']}", font=fs, fill=RAIN["fog_color"])
    return im


# --------------------------------------------------------------------------
def main():
    for p in (OUT, PREVIEW):
        if os.path.isdir(p):
            shutil.rmtree(p)
    os.makedirs(DIST, exist_ok=True)
    os.makedirs(PREVIEW, exist_ok=True)

    write_json(os.path.join(RP, "manifest.json"), {
        "format_version": 2,
        "header": {
            "name": "Idex Lite Shader",
            "description": "แสงเงาเบา ๆ สำหรับมือถือสเปคต่ำ • ไม่กิน FPS\nSoft fog, glow sun/moon, clear water",
            "uuid": make_uuid("rp"),
            "version": VERSION,
            "min_engine_version": MIN_ENGINE,
        },
        "modules": [{"type": "resources", "uuid": make_uuid("rp/module"), "version": VERSION}],
    })

    for style in WATER:
        write_json(os.path.join(RP, "fogs", f"lite_{style}.json"), fog_file(style))
    write_json(os.path.join(RP, "biomes_client.json"), biomes_client())

    sun = sun_texture()
    moon = moon_texture()
    clouds = clouds_texture()
    env = os.path.join(RP, "textures", "environment")
    save_png(os.path.join(env, "sun.png"), sun)
    save_png(os.path.join(env, "moon_phases.png"), moon)
    save_png(os.path.join(env, "clouds.png"), clouds)

    # vanilla corner colours (hot+wet, hot+dry, cold), graded warmer/richer
    grass = colormap((71, 205, 51), (191, 183, 85), (128, 180, 151))
    foliage = colormap((26, 191, 0), (174, 164, 42), (96, 161, 123))
    cm = os.path.join(RP, "textures", "colormap")
    save_png(os.path.join(cm, "grass.png"), grass)
    save_png(os.path.join(cm, "foliage.png"), foliage)

    icon = pack_icon(sun)
    icon.save(os.path.join(RP, "pack_icon.png"))
    preview(sun, moon, clouds, grass, foliage).save(os.path.join(PREVIEW, "lite_shader_preview.png"))
    icon.save(os.path.join(PREVIEW, "pack_icon.png"))

    out = os.path.join(DIST, "Idex_Lite_Shader.mcpack")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _, files in sorted(os.walk(RP)):
            for fn in sorted(files):
                full = os.path.join(dp, fn)
                z.write(full, os.path.join("Idex_Lite_Shader_RP", os.path.relpath(full, RP)))
    print("wrote", out)


if __name__ == "__main__":
    main()
