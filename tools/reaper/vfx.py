"""Particle textures (procedural) and particle definitions for the Cursed Reaper Scythe.

Particles spawned from the script receive Molang variables through a
MolangVariableMap (variable.size, variable.life, variable.count, variable.radius,
variable.spin, variable.cr/cg/cb, variable.dx/dy/dz, variable.red ...). Every
variable has a fallback, so a particle spawned with /particle still looks right.
"""
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

NS = "idex"
TEX = "textures/particle/reaper/"
RNG = np.random.default_rng(7)


# ---------------------------------------------------------------- texture helpers
def radial(size):
    y, x = np.mgrid[0:size, 0:size] + 0.5
    c = size / 2
    return np.hypot(x - c, y - c) / c, np.arctan2(y - c, x - c)


def rgba(arr_rgb, alpha):
    a = np.clip(alpha, 0, 1)
    rgb = np.clip(arr_rgb, 0, 1)
    return Image.fromarray((np.dstack([rgb, a]) * 255).astype(np.uint8), "RGBA")


def white(alpha):
    return rgba(np.ones(alpha.shape + (3,)), alpha)


def tex_glow(s=32):
    r, _ = radial(s)
    return white(np.clip(1 - r, 0, 1) ** 2.2)


def tex_spark():
    w, h = 32, 8      # long along u: lookat_direction stretches x along the motion
    y, x = np.mgrid[0:h, 0:w] + 0.5
    a = np.clip(1 - np.abs(y - h / 2) / (h / 2), 0, 1) ** 1.5 * np.clip(1 - np.abs(x - w / 2) / (w / 2), 0, 1) ** 0.7
    return white(a)


def noise(s, scale, seed):
    rng = np.random.default_rng(seed)
    g = rng.random((scale + 3, scale + 3))
    img = Image.fromarray((g * 255).astype(np.uint8)).resize((s, s), Image.BICUBIC)
    return np.asarray(img) / 255.0


def tex_smoke():
    s = 64
    out = Image.new("RGBA", (s * 4, s))
    for i in range(4):
        r, _ = radial(s)
        n = noise(s, 5, 10 + i) * 0.6 + noise(s, 11, 20 + i) * 0.4
        a = np.clip((1 - r * 1.15) * 1.6 * (0.55 + 0.6 * n) - 0.15, 0, 1)
        out.paste(white(a), (i * s, 0))
    return out


def tex_runes():
    """8 rune glyphs 32x32, white on transparent."""
    s = 32
    out = Image.new("RGBA", (s * 8, s), (0, 0, 0, 0))
    rng = np.random.default_rng(3)
    for i in range(8):
        im = Image.new("L", (s * 4, s * 4), 0)
        d = ImageDraw.Draw(im)
        W = 9
        cx = s * 2
        d.line([(cx, 18), (cx, s * 4 - 18)], fill=255, width=W)               # stave
        for _ in range(2 + i % 3):
            y0 = rng.integers(20, s * 4 - 40)
            y1 = y0 + rng.integers(-30, 30)
            side = rng.choice([-1, 1])
            d.line([(cx, int(y0)), (cx + side * rng.integers(22, 44), int(y1))], fill=255, width=W)
        if i % 2:
            d.arc([cx - 30, 30, cx + 30, 90], 200, 340, fill=255, width=W)
        if i % 3 == 0:
            d.line([(cx - 34, s * 2), (cx + 34, s * 2)], fill=255, width=W)
        im = im.resize((s, s), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.4))
        a = np.asarray(im) / 255.0
        out.paste(white(np.clip(a * 1.3, 0, 1)), (i * s, 0))
    return out


def circle_texture(s=512, rings=True, star=True, glyph_ring=True, crescents=True):
    """Black-red magic circle (blend material: dark translucent fill + red lines)."""
    k = 2
    S = s * k
    line = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(line)
    c = S / 2

    def ring(r, w):
        d.ellipse([c - r, c - r, c + r, c + r], outline=255, width=int(w))

    R = S * 0.48
    if rings:
        ring(R, 7 * k)
        ring(R * 0.94, 3 * k)
        ring(R * 0.74, 4 * k)
        ring(R * 0.70, 2 * k)
        ring(R * 0.30, 4 * k)
    if star:
        pts = [(c + R * 0.70 * math.cos(math.radians(-90 + 144 * i)), c + R * 0.70 * math.sin(math.radians(-90 + 144 * i)))
               for i in range(6)]
        d.line(pts, fill=255, width=4 * k)
    if crescents:
        for i in range(6):
            a = math.radians(i * 60 + 30)
            x, y = c + R * 0.52 * math.cos(a), c + R * 0.52 * math.sin(a)
            r = R * 0.075
            d.ellipse([x - r, y - r, x + r, y + r], outline=255, width=3 * k)
            d.ellipse([x - r * 0.65 + r * 0.45 * math.cos(a), y - r * 0.65 + r * 0.45 * math.sin(a),
                       x + r * 0.65 + r * 0.45 * math.cos(a), y + r * 0.65 + r * 0.45 * math.sin(a)], fill=0)
    if glyph_ring:
        runes = tex_runes()
        rl = runes.split()[3]
        n = 24
        for i in range(n):
            g = rl.crop((32 * (i % 8), 0, 32 * (i % 8) + 32, 32)).resize((int(R * 0.14),) * 2, Image.LANCZOS)
            g = g.rotate(-(i * 360 / n) - 90, expand=True, resample=Image.BICUBIC)
            a = math.radians(i * 360 / n)
            x, y = c + R * 0.84 * math.cos(a), c + R * 0.84 * math.sin(a)
            line.paste(255, (int(x - g.width / 2), int(y - g.height / 2)), g)
    line = line.resize((s, s), Image.LANCZOS)
    L = np.asarray(line) / 255.0
    glow = np.asarray(line.filter(ImageFilter.GaussianBlur(5))) / 255.0
    r, _ = radial(s)
    fill = np.clip(1 - r, 0, 1) ** 0.4 * (r < 0.97) * 0.42
    col = np.zeros((s, s, 3))
    col[..., 0] = 0.06 + 0.94 * np.clip(L + glow * 0.8, 0, 1)
    col[..., 1] = 0.01 + 0.25 * L ** 2
    col[..., 2] = 0.02 + 0.18 * L ** 2
    a = np.clip(fill + L + glow * 0.7, 0, 1)
    return rgba(col, a)


def tex_ring():
    s = 128
    r, _ = radial(s)
    a = np.exp(-((r - 0.86) / 0.06) ** 2) + 0.35 * np.exp(-((r - 0.86) / 0.16) ** 2)
    return white(np.clip(a, 0, 1))


def tex_wave():
    s = 256
    r, th = radial(s)
    n = noise(s, 9, 41)
    a = np.exp(-((r - 0.8) / 0.12) ** 2) * (0.6 + 0.5 * n) + 0.25 * np.clip(1 - r, 0, 1) * (r < 0.8)
    col = np.dstack([0.12 + 0.5 * np.exp(-((r - 0.9) / 0.05) ** 2), np.full_like(r, 0.0), np.full_like(r, 0.03)])
    return rgba(col, np.clip(a, 0, 1))


def tex_moon():
    s = 256
    r, th = radial(s)
    n = noise(s, 7, 51) * 0.6 + noise(s, 23, 52) * 0.4
    disc = r < 0.7
    shade = np.clip(1.05 - np.hypot(*(np.mgrid[0:s, 0:s] / s - [[[0.38]], [[0.4]]])) * 1.3, 0.25, 1)
    col = np.zeros((s, s, 3))
    col[..., 0] = (0.55 + 0.35 * n) * shade
    col[..., 1] = (0.04 + 0.06 * n) * shade
    col[..., 2] = (0.05 + 0.04 * n) * shade
    # craters
    rng = np.random.default_rng(5)
    y, x = np.mgrid[0:s, 0:s] + 0.5
    for _ in range(14):
        cx, cy = rng.uniform(0.25, 0.75, 2) * s
        rr = rng.uniform(0.02, 0.07) * s
        dd = np.hypot(x - cx, y - cy) / rr
        col *= (1 - 0.35 * np.exp(-dd ** 4))[..., None]
    halo = np.clip(1 - (r - 0.7) / 0.3, 0, 1) ** 2 * (r >= 0.7)
    col[~disc] = [0.75, 0.05, 0.06]
    a = np.where(disc, 1.0, halo * 0.55)
    edge = np.clip(1 - np.abs(r - 0.7) / 0.015, 0, 1)
    a = np.maximum(a, edge)
    return rgba(col, a)


def tex_eclipse_disc():
    s = 256
    r, _ = radial(s)
    a = np.clip((0.72 - r) / 0.02, 0, 1)
    col = np.zeros((s, s, 3)) + 0.01
    col[..., 0] += 0.08 * np.exp(-((r - 0.7) / 0.03) ** 2)
    return rgba(col, a)


def tex_corona():
    s = 256
    r, th = radial(s)
    n = noise(s, 13, 61)
    flare = (0.5 + 0.5 * np.sin(th * 9 + n * 4)) * np.clip(1 - (r - 0.72) / 0.28, 0, 1)
    a = np.exp(-((r - 0.72) / 0.035) ** 2) + flare * 0.55 * (r > 0.7)
    col = np.dstack([np.ones_like(r), 0.15 + 0.6 * np.exp(-((r - 0.72) / 0.02) ** 2), 0.12 + 0.4 * np.exp(-((r - 0.72) / 0.02) ** 2)])
    return rgba(col, np.clip(a, 0, 1))


def tex_crescent():
    s = 128
    y, x = np.mgrid[0:s, 0:s] / s - 0.5
    outer = np.hypot(x, y) < 0.46
    inner = np.hypot(x - 0.16, y + 0.06) < 0.38
    m = (outer & ~inner).astype(float)
    img = Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
    a = np.asarray(img) / 255.0
    rim = np.clip(a - np.asarray(img.filter(ImageFilter.MinFilter(7)).filter(ImageFilter.GaussianBlur(1))) / 255.0, 0, 1)
    col = np.dstack([0.05 + 0.95 * rim * 1.6, 0.0 + 0.1 * rim, 0.02 + 0.1 * rim])
    return rgba(col, a)


def tex_crack():
    s = 128
    out = Image.new("RGBA", (s * 4, s))
    rng = np.random.default_rng(9)
    for i in range(4):
        im = Image.new("L", (s * 2, s * 2), 0)
        d = ImageDraw.Draw(im)
        c = s
        for b in range(5 + i):
            a = rng.uniform(0, 2 * math.pi)
            x, y = c, c
            w = 9
            for step in range(9):
                a += rng.uniform(-0.6, 0.6)
                L = rng.uniform(12, 26)
                nx, ny = x + L * math.cos(a), y + L * math.sin(a)
                d.line([(x, y), (nx, ny)], fill=255, width=max(2, int(w)))
                if rng.random() < 0.3:
                    a2 = a + rng.choice([-1, 1]) * rng.uniform(0.6, 1.2)
                    d.line([(nx, ny), (nx + 20 * math.cos(a2), ny + 20 * math.sin(a2))], fill=255, width=max(2, int(w * 0.6)))
                x, y = nx, ny
                w *= 0.82
        im = im.resize((s, s), Image.LANCZOS)
        L = np.asarray(im) / 255.0
        glow = np.asarray(im.filter(ImageFilter.GaussianBlur(4))) / 255.0
        core = np.asarray(im.filter(ImageFilter.MinFilter(3))) / 255.0
        col = np.dstack([0.05 + 0.95 * np.clip(core * 1.5 + glow * 0.5, 0, 1), 0.02 + 0.3 * core, 0.03 + 0.2 * core])
        a = np.clip(L + glow * 0.6, 0, 1)
        out.paste(rgba(col, a), (i * s, 0))
    return out


def tex_beam():
    w, h = 64, 8
    y, x = np.mgrid[0:h, 0:w] + 0.5
    a = np.clip(1 - np.abs(y - h / 2) / (h / 2), 0, 1) ** 1.2 * np.clip(x / w * 1.4, 0, 1) * np.clip((w - x) / (w * 0.15), 0, 1)
    return white(a)


def tex_chain():
    """Two horizontal chain links 32x32: [black/steel, crimson rune link]."""
    s = 32
    out = Image.new("RGBA", (s * 2, s))
    for i in range(2):
        im = Image.new("L", (s * 4, s * 4), 0)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([6, 34, s * 4 - 6, s * 4 - 34], radius=30, outline=255, width=16)
        L = np.asarray(im.resize((s, s), Image.LANCZOS)) / 255.0
        edge = np.asarray(im.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(5)).resize((s, s), Image.LANCZOS)) / 255.0
        if i == 0:
            col = np.dstack([0.08 + 0.45 * edge, 0.07 + 0.42 * edge, 0.09 + 0.45 * edge])
        else:
            col = np.dstack([0.75 + 0.25 * edge, 0.05 + 0.5 * edge, 0.06 + 0.4 * edge])
        out.paste(rgba(col, np.clip(L * 1.3, 0, 1)), (i * s, 0))
    return out


def textures():
    return {
        "glow": tex_glow(), "spark": tex_spark(), "smoke": tex_smoke(), "runes": tex_runes(),
        "circle": circle_texture(), "circle_ring_a": circle_texture(rings=True, star=False, glyph_ring=True, crescents=False),
        "circle_ring_b": circle_texture(rings=False, star=True, glyph_ring=False, crescents=True),
        "ring": tex_ring(), "wave": tex_wave(), "moon": tex_moon(), "eclipse_disc": tex_eclipse_disc(),
        "corona": tex_corona(), "crescent": tex_crescent(), "crack": tex_crack(), "beam": tex_beam(),
        "chain": tex_chain(),
    }


# ---------------------------------------------------------------- particle json helpers
def V(name, default):
    """Molang: script variable with a fallback when it is not set."""
    return f"(variable.{name} > 0 ? variable.{name} : {default})"


def fade(c0, c1=None, a_in=0.15, a_out=0.65):
    c1 = c1 or c0
    return {"color": {"interpolant": "v.particle_age / v.particle_lifetime", "gradient": {
        "0.0": "#00" + c0, str(a_in): "#FF" + c0, str(a_out): "#FF" + c1, "1.0": "#00" + c1}}}


def effect(pid, texture, material, comps, tw=None, th=None):
    return {
        "format_version": "1.10.0",
        "particle_effect": {
            "description": {"identifier": f"{NS}:{pid}",
                            "basic_render_parameters": {"material": material, "texture": TEX + texture}},
            "components": comps,
        },
    }


def billboard(size, mode, uv=None, extra=None):
    b = {"size": size, "facing_camera_mode": mode}
    if uv:
        b["uv"] = uv
    if extra:
        b.update(extra)
    return {"minecraft:particle_appearance_billboard": b}


def once(n, active=0.05):
    return {"minecraft:emitter_rate_instant": {"num_particles": n},
            "minecraft:emitter_lifetime_once": {"active_time": active}}


def life(expr):
    return {"minecraft:particle_lifetime_expression": {"max_lifetime": expr}}


def tint_vars(default_hex, a_in=0.12, a_out=0.6):
    """Colour from variable.cr/cg/cb (0-1) if given, else default; alpha fades."""
    t = "v.particle_age / v.particle_lifetime"
    d = [int(default_hex[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    alpha = f"math.clamp(math.min(({t}) / {a_in}, (1 - {t}) / {1 - a_out}), 0, 1)"
    return {"minecraft:particle_appearance_tinting": {"color": [
        f"(variable.cr + variable.cg + variable.cb > 0) ? variable.cr : {d[0]:.3f}",
        f"(variable.cr + variable.cg + variable.cb > 0) ? variable.cg : {d[1]:.3f}",
        f"(variable.cr + variable.cg + variable.cb > 0) ? variable.cb : {d[2]:.3f}",
        alpha]}}


def particles():
    P = {}
    T = "v.particle_age / v.particle_lifetime"

    # blade edge embers (attachable keyframes, no variables)
    P["reaper_edge_ember"] = effect("reaper_edge_ember", "glow", "particles_add", {
        **once(2), "minecraft:emitter_shape_sphere": {"radius": 0.05, "direction": "outwards"},
        **life("math.random(0.3, 0.55)"),
        "minecraft:particle_initial_speed": "math.random(0.2, 0.6)",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 0.6, 0], "linear_drag_coefficient": 1.5},
        **billboard([f"0.07 * (1 - {T})", f"0.07 * (1 - {T})"], "lookat_xyz"),
        "minecraft:particle_appearance_tinting": fade("FF2A2A", "5A0008", 0.1, 0.5),
    })
    # blade trail ribbon (dense points along the swing path)
    P["reaper_trail"] = effect("reaper_trail", "glow", "particles_add", {
        **once(1), "minecraft:emitter_shape_point": {},
        **life(V("life", 0.22)),
        "minecraft:particle_motion_dynamic": {},
        **billboard([f"{V('size', 0.16)} * (1 - 0.6 * {T})"] * 2, "lookat_xyz"),
        "minecraft:particle_appearance_tinting": {"color": {"interpolant": T, "gradient": {
            "0.0": "#FFFFD0D0", "0.12": "#FFFF2A2A", "0.5": "#C0B00010", "1.0": "#00300004"}}},
    })
    P["reaper_trail_dark"] = effect("reaper_trail_dark", "smoke", "particles_blend", {
        **once(1), "minecraft:emitter_shape_point": {},
        **life(V("life", 0.5)),
        "minecraft:particle_initial_speed": 0.15,
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 0.35, 0], "linear_drag_coefficient": 1},
        **billboard([f"{V('size', 0.22)} * (0.7 + 0.8 * {T})"] * 2, "rotate_xyz",
                    {"uv": {"texture_width": 256, "texture_height": 64,
                            "uv": ["math.floor(v.particle_random_1 * 4) * 64", 0], "uv_size": [64, 64]}}),
        "minecraft:particle_initial_spin": {"rotation": "math.random(0, 360)", "rotation_rate": "math.random(-40, 40)"},
        "minecraft:particle_appearance_tinting": fade("0A0507", "120408", 0.1, 0.45),
    })
    # spark burst
    P["reaper_sparks"] = effect("reaper_sparks", "spark", "particles_add", {
        **once(V("count", 14)), "minecraft:emitter_shape_sphere": {"radius": V("radius", 0.15), "direction": "outwards"},
        **life("math.random(0.25, 0.5)"),
        "minecraft:particle_initial_speed": f"math.random(3, 7) * {V('speed', 1)}",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, -6, 0], "linear_drag_coefficient": 2.6},
        **billboard([f"0.24 * (1 - {T})", 0.05], "lookat_direction"),
        "minecraft:particle_appearance_tinting": {"color": {"interpolant": T, "gradient": {
            "0.0": "#FFFFF0E0", "0.2": "#FFFF4040", "0.7": "#FFB00010", "1.0": "#00400004"}}},
    })
    # black smoke puffs
    P["reaper_smoke"] = effect("reaper_smoke", "smoke", "particles_blend", {
        **once(V("count", 6)), "minecraft:emitter_shape_sphere": {"radius": V("radius", 0.4), "direction": "outwards"},
        **life(f"math.random(0.5, 0.9) * {V('life', 1)}"),
        "minecraft:particle_initial_speed": "math.random(0.3, 1.0)",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 0.6, 0], "linear_drag_coefficient": 1.4},
        **billboard([f"{V('size', 0.6)} * (0.6 + 0.9 * {T})"] * 2, "rotate_xyz",
                    {"uv": {"texture_width": 256, "texture_height": 64,
                            "uv": ["math.floor(v.particle_random_1 * 4) * 64", 0], "uv_size": [64, 64]}}),
        "minecraft:particle_initial_spin": {"rotation": "math.random(0, 360)", "rotation_rate": "math.random(-30, 30)"},
        "minecraft:particle_appearance_tinting": fade("08040A", "1A0509", 0.12, 0.5),
    })
    # magic circles (flat on the ground) - three layers, counter-rotating
    for pid, tex in (("reaper_circle", "circle"), ("reaper_circle_ring_a", "circle_ring_a"), ("reaper_circle_ring_b", "circle_ring_b")):
        grow = f"math.clamp(v.particle_age / 0.3, 0, 1)"
        P[pid] = effect(pid, tex, "particles_blend", {
            **once(1), "minecraft:emitter_shape_point": {"offset": [0, 0.04, 0]},
            **life(V("life", 2.5)),
            "minecraft:particle_motion_dynamic": {},
            "minecraft:particle_initial_spin": {"rotation": "math.random(0, 360)", "rotation_rate": "variable.spin"},
            **billboard([f"{V('size', 3)} * (0.55 + 0.45 * (1 - math.pow(1 - {grow}, 3)))"] * 2, "emitter_transform_xz"),
            "minecraft:particle_appearance_tinting": {"color": ["1", "1", "1",
                                                                f"math.clamp(math.min(v.particle_age / 0.2, (v.particle_lifetime - v.particle_age) / 0.45), 0, 1)"]},
        })
    # the same circle standing up and facing the viewer (blade-centre circle, sky circle)
    P["reaper_circle_face"] = effect("reaper_circle_face", "circle", "particles_blend", {
        **once(1), "minecraft:emitter_shape_point": {},
        **life(V("life", 1.0)),
        "minecraft:particle_motion_dynamic": {},
        "minecraft:particle_initial_spin": {"rotation": 0, "rotation_rate": f"{V('spin', 90)}"},
        **billboard([f"{V('size', 1.2)} * math.clamp(v.particle_age / 0.15, 0.2, 1)"] * 2, "lookat_xyz"),
        "minecraft:particle_appearance_tinting": {"color": ["1", "1", "1",
                                                            f"math.clamp(math.min(v.particle_age / 0.1, (v.particle_lifetime - v.particle_age) / 0.3), 0, 1)"]},
    })
    # floating runes
    P["reaper_rune"] = effect("reaper_rune", "runes", "particles_add", {
        **once(V("count", 1)), "minecraft:emitter_shape_disc": {"radius": V("radius", 0.01), "plane_normal": "y"},
        **life("math.random(1.4, 2.4)"),
        "minecraft:particle_initial_speed": 0.0,
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, f"{V('rise', 0.45)}", 0], "linear_drag_coefficient": 0.8},
        **billboard([V("size", 0.28)] * 2, "lookat_xyz",
                    {"uv": {"texture_width": 256, "texture_height": 32,
                            "uv": ["math.floor(v.particle_random_2 * 8) * 32", 0], "uv_size": [32, 32]}}),
        "minecraft:particle_appearance_tinting": fade("FF2020", "8A0010", 0.2, 0.7),
    })
    # chain links, aligned with the chain direction
    P["reaper_chain_link"] = effect("reaper_chain_link", "chain", "particles_blend", {
        **once(1), "minecraft:emitter_shape_point": {"direction": ["variable.dx", "variable.dy", "variable.dz"]},
        **life(V("life", 0.12)),
        "minecraft:particle_initial_speed": 0.02,
        "minecraft:particle_motion_dynamic": {},
        **billboard([0.32, 0.2], "lookat_direction",
                    {"uv": {"texture_width": 64, "texture_height": 32, "uv": ["variable.red > 0 ? 32 : 0", 0], "uv_size": [32, 32]}}),
    })
    # coloured ring (target mark / impact ring), flat
    P["reaper_ring"] = effect("reaper_ring", "ring", "particles_add", {
        **once(1), "minecraft:emitter_shape_point": {"offset": [0, 0.06, 0]},
        **life(V("life", 0.6)),
        "minecraft:particle_motion_dynamic": {},
        **billboard([f"{V('size', 2)} * (0.35 + 0.65 * math.sqrt({T}))"] * 2, "emitter_transform_xz"),
        **tint_vars("FF1E1E", 0.08, 0.45),
    })
    # dark shadow / void shockwave ring, flat
    P["reaper_void_wave"] = effect("reaper_void_wave", "wave", "particles_blend", {
        **once(1), "minecraft:emitter_shape_point": {"offset": [0, 0.08, 0]},
        **life(V("life", 0.7)),
        "minecraft:particle_motion_dynamic": {},
        "minecraft:particle_initial_spin": {"rotation": "math.random(0, 360)", "rotation_rate": 60},
        **billboard([f"{V('size', 8)} * (0.1 + 0.9 * (1 - math.pow(1 - {T}, 2.5)))"] * 2, "emitter_transform_xz"),
        "minecraft:particle_appearance_tinting": {"color": ["1", "1", "1", f"math.clamp((1 - {T}) * 1.6, 0, 1)"]},
    })
    P["reaper_void_burst"] = effect("reaper_void_burst", "smoke", "particles_blend", {
        **once(V("count", 40)), "minecraft:emitter_shape_disc": {"radius": 0.6, "plane_normal": "y", "direction": "outwards"},
        **life("math.random(0.6, 1.1)"),
        "minecraft:particle_initial_speed": f"math.random(6, 12) * {V('speed', 1)}",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 1.2, 0], "linear_drag_coefficient": 2.4},
        **billboard([f"math.random(0.7, 1.3) * {V('size', 1)} * (0.6 + {T})"] * 2, "rotate_xyz",
                    {"uv": {"texture_width": 256, "texture_height": 64,
                            "uv": ["math.floor(v.particle_random_1 * 4) * 64", 0], "uv_size": [64, 64]}}),
        "minecraft:particle_initial_spin": {"rotation": "math.random(0, 360)", "rotation_rate": "math.random(-60, 60)"},
        "minecraft:particle_appearance_tinting": fade("050307", "200408", 0.06, 0.5),
    })
    # moon / eclipse
    P["reaper_moon"] = effect("reaper_moon", "moon", "particles_blend", {
        **once(1), "minecraft:emitter_shape_point": {},
        **life(V("life", 12)),
        "minecraft:particle_motion_dynamic": {},
        **billboard([f"{V('size', 7)} * (0.85 + 0.15 * math.clamp(v.particle_age / 1.2, 0, 1)) * (1 + 0.015 * math.sin(v.particle_age * 90))"] * 2, "lookat_xyz"),
        "minecraft:particle_appearance_tinting": {"color": ["1", "1", "1",
                                                            "math.clamp(math.min(v.particle_age / 1.2, (v.particle_lifetime - v.particle_age) / 1.0), 0, 1)"]},
    })
    P["reaper_eclipse_disc"] = effect("reaper_eclipse_disc", "eclipse_disc", "particles_blend", {
        **once(1), "minecraft:emitter_shape_point": {},
        **life(V("life", 6)),
        "minecraft:particle_motion_dynamic": {},
        **billboard([f"{V('size', 8)} * math.clamp(v.particle_age / 0.9, 0.05, 1)"] * 2, "lookat_xyz"),
        "minecraft:particle_appearance_tinting": {"color": ["1", "1", "1",
                                                            "math.clamp((v.particle_lifetime - v.particle_age) / 0.8, 0, 1)"]},
    })
    P["reaper_eclipse_corona"] = effect("reaper_eclipse_corona", "corona", "particles_add", {
        **once(1), "minecraft:emitter_shape_point": {},
        **life(V("life", 5)),
        "minecraft:particle_motion_dynamic": {},
        "minecraft:particle_initial_spin": {"rotation": 0, "rotation_rate": 12},
        **billboard([f"{V('size', 8)} * (1.0 + 0.04 * math.sin(v.particle_age * 140))"] * 2, "lookat_xyz"),
        "minecraft:particle_appearance_tinting": {"color": ["1", "1", "1",
                                                            "math.clamp(math.min(v.particle_age / 0.8, (v.particle_lifetime - v.particle_age) / 0.8), 0, 1)"]},
    })
    # area dressing
    P["reaper_mist"] = effect("reaper_mist", "smoke", "particles_blend", {
        **once(V("count", 6)), "minecraft:emitter_shape_disc": {"radius": V("radius", 4), "plane_normal": "y"},
        **life("math.random(2.5, 4.0)"),
        "minecraft:particle_initial_speed": 0.0,
        "minecraft:particle_motion_dynamic": {"linear_acceleration": ["math.random(-0.2, 0.2)", 0.12, "math.random(-0.2, 0.2)"], "linear_drag_coefficient": 0.6},
        **billboard([f"math.random(1.6, 3.0) * (0.7 + 0.5 * {T})"] * 2, "rotate_xyz",
                    {"uv": {"texture_width": 256, "texture_height": 64,
                            "uv": ["math.floor(v.particle_random_1 * 4) * 64", 0], "uv_size": [64, 64]}}),
        "minecraft:particle_initial_spin": {"rotation": "math.random(0, 360)", "rotation_rate": "math.random(-10, 10)"},
        "minecraft:particle_appearance_tinting": {"color": {"interpolant": T, "gradient": {
            "0.0": "#00080408", "0.25": "#7A0A0408", "0.75": "#6A140306", "1.0": "#00100306"}}},
    })
    P["reaper_mini_crescent"] = effect("reaper_mini_crescent", "crescent", "particles_blend", {
        **once(V("count", 3)), "minecraft:emitter_shape_disc": {"radius": V("radius", 0.6), "plane_normal": "y"},
        **life("math.random(1.0, 2.0)"),
        "minecraft:particle_initial_speed": "math.random(0.2, 0.8)",
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, 0.5, 0], "linear_drag_coefficient": 0.9},
        "minecraft:particle_initial_spin": {"rotation": "math.random(0, 360)", "rotation_rate": "math.random(-120, 120)"},
        **billboard([f"math.random(0.35, 0.7) * {V('size', 1)}"] * 2, "rotate_xyz"),
        "minecraft:particle_appearance_tinting": {"color": ["1", "1", "1",
                                                            f"math.clamp(math.min({T} / 0.15, (1 - {T}) / 0.4), 0, 1)"]},
    })
    P["reaper_crack"] = effect("reaper_crack", "crack", "particles_blend", {
        **once(1), "minecraft:emitter_shape_point": {"offset": [0, 0.05, 0]},
        **life(V("life", 3)),
        "minecraft:particle_motion_dynamic": {},
        "minecraft:particle_initial_spin": {"rotation": "math.random(0, 360)", "rotation_rate": 0},
        **billboard([f"{V('size', 2.5)} * math.clamp(v.particle_age / 0.25, 0.2, 1)"] * 2, "emitter_transform_xz",
                    {"uv": {"texture_width": 512, "texture_height": 128,
                            "uv": ["math.floor(v.particle_random_1 * 4) * 128", 0], "uv_size": [128, 128]}}),
        "minecraft:particle_appearance_tinting": {"color": ["1", "1", "1",
                                                            "math.clamp((v.particle_lifetime - v.particle_age) / 0.6, 0, 1)"]},
    })
    P["reaper_beam"] = effect("reaper_beam", "beam", "particles_add", {
        **once(V("count", 10)),
        "minecraft:emitter_shape_disc": {"offset": [0, 16, 0], "radius": V("radius", 6), "plane_normal": "y",
                                         "direction": ["math.random(-0.08, 0.08)", -1, "math.random(-0.08, 0.08)"]},
        **life("math.random(0.3, 0.45)"),
        "minecraft:particle_initial_speed": 50,
        "minecraft:particle_motion_dynamic": {},
        **billboard([3.2, 0.09], "lookat_direction"),
        "minecraft:particle_appearance_tinting": {"color": {"interpolant": T, "gradient": {
            "0.0": "#FFFFE0E0", "0.3": "#FFFF2020", "1.0": "#00800010"}}},
    })
    P["reaper_aura"] = effect("reaper_aura", "glow", "particles_add", {
        **once(V("count", 4)), "minecraft:emitter_shape_disc": {"radius": V("radius", 0.5), "plane_normal": "y"},
        **life("math.random(0.6, 1.0)"),
        "minecraft:particle_initial_speed": 0.0,
        "minecraft:particle_motion_dynamic": {"linear_acceleration": [0, f"math.random(1.2, 2.2) * {V('rise', 1)}", 0], "linear_drag_coefficient": 0.8},
        **billboard([f"math.random(0.08, 0.16) * (1 - {T})"] * 2, "lookat_xyz"),
        "minecraft:particle_appearance_tinting": fade("FF2424", "35000A", 0.1, 0.5),
    })
    P["reaper_energy_rise"] = effect("reaper_energy_rise", "spark", "particles_add", {
        **once(V("count", 8)), "minecraft:emitter_shape_disc": {"radius": V("radius", 6), "plane_normal": "y",
                                                               "direction": [0, 1, 0]},
        **life("math.random(0.7, 1.3)"),
        "minecraft:particle_initial_speed": "math.random(2, 5)",
        "minecraft:particle_motion_dynamic": {"linear_drag_coefficient": 0.6},
        **billboard(["0.3 + v.particle_random_3 * 0.3", 0.06], "lookat_direction"),
        "minecraft:particle_appearance_tinting": fade("FF3030", "50000C", 0.1, 0.55),
    })
    return P
