"""Particle effect definitions for ECLIPSE TWIN SWORDS.

Bedrock needs one particle_effect per file, so each effect below becomes
resource_pack/particles/<name>.particle.json (prefixed solar_/void_/eclipse_).

Every effect reads optional Molang variables sent by the script through a
MolangVariableMap, with safe defaults, so size and count can be tuned without
touching JSON:

  variable.scale    size multiplier            (default 1)
  variable.density  particle-count multiplier  (default 1)
  variable.life     lifetime in seconds        (per effect default)
  variable.alpha    opacity multiplier         (default 1)
  variable.radius   area radius in blocks      (per effect default)
  variable.height   column height in blocks    (per effect default)
  variable.speed    travel speed, blocks/s     (default 0)
  variable.dir      unit direction vector      (default +Z)
  variable.vel      follow velocity, blocks/s  (default 0) - keeps short-lived
                    "attached" effects glued to a moving player
  variable.tilt     roll angle in degrees      (default 0)
  variable.phase    starting spin in degrees   (default 0)
"""
import os

from common import NS, PARTICLE_TEX_DIR, RP, write_json
from fxtex import ATLAS_CELLS, tex_size

T = "(v.particle_age / v.particle_lifetime)"
CELL = 64

# palette (r, g, b)
WHITE = (1.0, 0.98, 0.92)
GOLD = (1.0, 0.80, 0.36)
GOLD_HOT = (1.0, 0.90, 0.62)
ORANGE = (1.0, 0.52, 0.16)
PURPLE = (0.60, 0.28, 1.0)
VIOLET = (0.78, 0.50, 1.0)
DEEP = (0.20, 0.05, 0.40)
BLUE = (0.30, 0.46, 1.0)
STAR_BLUE = (0.70, 0.82, 1.0)
VOID_BLACK = (0.10, 0.02, 0.18)

EFFECTS = {}


def effect(name, texture, material, components, curves=None):
    tex_path = f"{PARTICLE_TEX_DIR}/{texture}"
    body = {
        "description": {
            "identifier": f"{NS}:{name}",
            "basic_render_parameters": {"material": material, "texture": tex_path},
        },
        "components": components,
    }
    if curves:
        body["curves"] = curves
    EFFECTS[name] = {"format_version": "1.10.0", "particle_effect": body}
    return name


# ------------------------------------------------------------ building blocks

def init(**defaults):
    """emitter_initialization that resolves script variables with defaults."""
    names = {"sc": "scale", "dn": "density", "lf": "life", "al": "alpha", "rd": "radius",
             "ht": "height", "spd": "speed", "tilt": "tilt", "ph": "phase"}
    parts = []
    for short, default in defaults.items():
        if short in ("dir", "vel"):
            x, y, z = default
            long = "dir" if short == "dir" else "vel"
            parts.append(f"variable.{long} ?? {{ variable.{long}.x = {x}; variable.{long}.y = {y}; variable.{long}.z = {z}; }};")
        else:
            parts.append(f"variable.{short} = variable.{names[short]} ?? {default};")
    return {"minecraft:emitter_initialization": {"creation_expression": " ".join(parts)}}


def instant(n):
    return {"minecraft:emitter_rate_instant": {"num_particles": n},
            "minecraft:emitter_lifetime_once": {"active_time": 0.05}}


def steady(rate, max_particles, active="v.lf"):
    return {"minecraft:emitter_rate_steady": {"spawn_rate": rate, "max_particles": max_particles},
            "minecraft:emitter_lifetime_once": {"active_time": active}}


def point(offset=(0, 0, 0), direction=None):
    c = {"offset": list(offset)}
    if direction is not None:
        c["direction"] = list(direction)
    return {"minecraft:emitter_shape_point": c}


def sphere(radius, offset=(0, 0, 0), surface=False, direction="outwards"):
    return {"minecraft:emitter_shape_sphere": {"offset": list(offset), "radius": radius,
                                               "surface_only": surface, "direction": direction}}


def disc(radius, offset=(0, 0, 0), surface=False, direction=None, normal=(0, 1, 0)):
    c = {"offset": list(offset), "radius": radius, "plane_normal": list(normal), "surface_only": surface}
    if direction is not None:
        c["direction"] = direction if isinstance(direction, str) else list(direction)
    return {"minecraft:emitter_shape_disc": c}


def life(expr):
    return {"minecraft:particle_lifetime_expression": {"max_lifetime": expr}}


def speed(expr):
    return {"minecraft:particle_initial_speed": expr}


def dynamic(acc=(0, 0, 0), drag=0.0):
    return {"minecraft:particle_motion_dynamic": {"linear_acceleration": list(acc), "linear_drag_coefficient": drag}}


def parametric(pos=(0, 0, 0), rot=None):
    c = {"relative_position": list(pos)}
    if rot is not None:
        c["rotation"] = rot
    return {"minecraft:particle_motion_parametric": c}


FOLLOW = ["v.vel.x * v.particle_age", "v.vel.y * v.particle_age", "v.vel.z * v.particle_age"]
TRAVEL = ["v.dir.x * v.spd * v.particle_age", "v.dir.y * v.spd * v.particle_age", "v.dir.z * v.spd * v.particle_age"]
CUSTOM_DIR = {"mode": "custom", "custom_direction": ["v.dir.x", "v.dir.y", "v.dir.z"]}
VEL_DIR = {"mode": "derive_from_velocity", "min_speed_threshold": 0.01}


def uv_full(tex):
    w, h = tex_size(tex)
    return {"texture_width": w, "texture_height": h, "uv": [0, 0], "uv_size": [w, h]}


def uv_cell(name):
    cx, cy = ATLAS_CELLS[name]
    return {"texture_width": 512, "texture_height": 512, "uv": [cx * CELL, cy * CELL], "uv_size": [CELL, CELL]}


def uv_pick(*names, rnd="v.particle_random_3"):
    """Random pick between atlas cells on the same row."""
    cells = [ATLAS_CELLS[n] for n in names]
    row = cells[0][1]
    assert all(c[1] == row for c in cells)
    n = len(cells)
    expr = f"{cells[-1][0] * CELL}"
    for i in range(n - 2, -1, -1):
        expr = f"({rnd} < {(i + 1) / n:.3f} ? {cells[i][0] * CELL} : {expr})"
    return {"texture_width": 512, "texture_height": 512, "uv": [expr, row * CELL], "uv_size": [CELL, CELL]}


def billboard(size, facing, uv, direction=None):
    c = {"size": list(size), "facing_camera_mode": facing, "uv": uv}
    if direction is not None:
        c["direction"] = direction
    return {"minecraft:particle_appearance_billboard": c}


def color(rgb, alpha_expr):
    r, g, b = rgb
    return {"minecraft:particle_appearance_tinting": {"color": [r, g, b, alpha_expr]}}


def gradient(stops, interp=T):
    """stops: [(t, (r,g,b,a))] -> tinting gradient (alpha may be an expression string)."""
    grad = {f"{t:.2f}": list(c) for t, c in stops}
    return {"minecraft:particle_appearance_tinting": {"color": {"gradient": grad, "interpolant": interp}}}


def color_pick(rgb_a, rgb_b, alpha_expr, rnd="v.particle_random_4", split=0.5):
    expr = [f"({rnd} < {split} ? {a} : {b})" for a, b in zip(rgb_a, rgb_b)]
    return {"minecraft:particle_appearance_tinting": {"color": expr + [alpha_expr]}}


def spin(rotation="math.random(0, 360)", rate="math.random(-90, 90)"):
    return {"minecraft:particle_initial_spin": {"rotation": rotation, "rotation_rate": rate}}


def merge(*parts):
    out = {}
    for p in parts:
        out.update(p)
    return out


# alpha profiles
TRI = f"(1 - math.abs(2 * {T} - 1))"                      # tent: overlapping respawns sum flat
TRAP = f"math.clamp(math.min({T} / 0.4, (1 - {T}) / 0.4), 0, 1)"  # for 3-tick refresh, 5-tick life
POP = f"math.clamp(math.min(v.particle_age * 12, (1 - {T}) * 3), 0, 1)"
FADE_OUT = f"math.pow(1 - {T}, 1.4)"
EASE_OUT = f"(1 - math.pow(1 - {T}, 3))"
APPEAR = "(1 - 0.35 * math.pow(math.max(0, 1 - v.particle_age * 6), 2))"
HOLD_FADE = "math.clamp(math.min(v.particle_age * 8, (v.lf - v.particle_age) * 3), 0, 1)"


# =================================================================== SOLAR

def build_solar():
    # passive motes around the body while holding Solaris
    effect("solar_passive", "fx_atlas", "particles_add", merge(
        init(sc=1.0, dn=1.0),
        instant("math.max(1, math.floor(3 * v.dn))"),
        sphere("0.8 * v.sc", offset=(0, 0, 0), surface=True, direction=["math.random(-0.3, 0.3)", 1, "math.random(-0.3, 0.3)"]),
        life("math.random(0.8, 1.3)"),
        speed("math.random(0.2, 0.6)"),
        dynamic((0, 0.15, 0), 0.6),
        billboard([f"(0.05 + 0.06 * v.particle_random_2) * v.sc * math.sin({T} * 180)"] * 2, "lookat_xyz",
                  uv_pick("glow", "spark4", "spark8")),
        spin("math.random(0, 360)", "math.random(-60, 60)"),
        gradient([(0.0, (1, 0.97, 0.85, 0)), (0.2, (1, 0.86, 0.48, 1)), (0.7, (1, 0.66, 0.26, 0.8)), (1.0, (1, 0.5, 0.15, 0))]),
    ))

    # crescent body (respawned every tick by the script, tent alpha)
    for name, tex, rgb, sx, sy in [("solar_slash_glow", "slash_arc", (1.0, 0.76, 0.30), 1.9, 0.95),
                                   ("solar_slash_core", "slash_edge", (1.0, 0.97, 0.86), 1.85, 0.92)]:
        effect(name, tex, "particles_add", merge(
            init(sc=1.0, lf=0.2, al=0.55, spd=32.0, tilt=0.0, dir=(0, 0, 1)),
            instant(1), point(),
            life("v.lf"),
            parametric(TRAVEL, "v.tilt"),
            billboard([f"{sx} * v.sc * (0.92 + 0.16 * {T})", f"{sy} * v.sc"], "direction_z", uv_full(tex), CUSTOM_DIR),
            color(rgb, f"{TRI} * v.al"),
        ))

    # spinning rune ring around the projectile
    effect("solar_slash_ring", "rune_ring", "particles_add", merge(
        init(sc=1.0, lf=0.2, al=0.5, spd=32.0, ph=0.0, dir=(0, 0, 1)),
        instant(1), point(),
        life("v.lf"),
        parametric(TRAVEL, "v.ph + v.particle_age * 540"),
        billboard(["0.62 * v.sc", "0.62 * v.sc"], "direction_z", uv_full("rune_ring"), CUSTOM_DIR),
        color(GOLD_HOT, f"{TRI} * v.al"),
    ))

    # speed streaks left behind the slash
    effect("solar_streaks", "fx_atlas", "particles_add", merge(
        init(sc=1.0, dn=1.0, dir=(0, 0, 1)),
        instant("math.floor(4 * v.dn)"),
        sphere("0.55 * v.sc", direction=["-v.dir.x * 2 + math.random(-0.6, 0.6)", "-v.dir.y * 2 + math.random(-0.6, 0.6)",
                                         "-v.dir.z * 2 + math.random(-0.6, 0.6)"]),
        life("math.random(0.18, 0.32)"),
        speed("math.random(2, 5)"),
        dynamic((0, 0, 0), 3.0),
        billboard([f"(0.25 + 0.3 * v.particle_random_1) * v.sc * (1 - {T})", f"0.035 * v.sc * (1 - {T})"],
                  "lookat_direction", uv_cell("glow"), VEL_DIR),
        gradient([(0.0, (1, 0.95, 0.8, 1)), (0.5, (1, 0.75, 0.3, 0.9)), (1.0, (1, 0.5, 0.15, 0))]),
    ))

    # generic star sparkle burst (trails, hits, explosions)
    effect("solar_stars", "fx_atlas", "particles_add", merge(
        init(sc=1.0, dn=1.0, rd=0.3, spd=1.0),
        instant("math.max(1, math.floor(10 * v.dn))"),
        sphere("v.rd", direction="outwards"),
        life("math.random(0.35, 0.8)"),
        speed("math.random(2, 7) * v.spd"),
        dynamic((0, -1.5, 0), 3.5),
        billboard([f"(0.06 + 0.11 * v.particle_random_2) * v.sc * (1 - {T} * {T})"] * 2, "lookat_xyz",
                  uv_pick("spark4", "spark8", "dot")),
        spin("math.random(0, 360)", "math.random(-180, 180)"),
        gradient([(0.0, (1, 1, 0.95, 1)), (0.35, (1, 0.84, 0.45, 1)), (1.0, (1, 0.5, 0.15, 0))]),
    ))

    # impact flash (camera facing)
    effect("solar_flash", "flash", "particles_add", merge(
        init(sc=1.0, lf=0.18, al=1.0),
        instant(1), point(),
        life("v.lf"),
        dynamic(),
        billboard([f"1.6 * v.sc * (1 - 0.45 * {T})"] * 2, "lookat_xyz", uv_full("flash")),
        spin("math.random(0, 360)", 0),
        gradient([(0.0, (1, 1, 1, "v.al")), (0.35, (1, 0.9, 0.6, "0.9 * v.al")), (1.0, (1, 0.62, 0.2, 0))]),
    ))

    # impact ring facing the travel direction
    effect("solar_hit_ring", "shock_ring", "particles_add", merge(
        init(sc=1.0, lf=0.32, dir=(0, 0, 1)),
        instant(1), point(),
        life("v.lf"),
        dynamic(),
        billboard([f"v.sc * (0.3 + 2.2 * {EASE_OUT})"] * 2, "direction_z", uv_full("shock_ring"), CUSTOM_DIR),
        color(GOLD, FADE_OUT),
    ))

    # ---- Radiant Spear
    effect("solar_circle", "magic_circle_solar", "particles_add", merge(
        init(sc=1.0, lf=1.2, rd=4.0, al=1.0),
        instant(1), point(),
        life("v.lf"),
        parametric([0, 0, 0], "v.particle_age * 45"),
        billboard([f"v.rd * 1.05 * {APPEAR}"] * 2, "emitter_transform_xz", uv_full("magic_circle_solar")),
        color(GOLD, f"{HOLD_FADE} * v.al"),
    ))
    effect("solar_rune_ring", "rune_ring", "particles_add", merge(
        init(sc=1.0, lf=1.2, rd=4.0),
        instant(1), point(),
        life("v.lf"),
        parametric([0, "0.12 + 0.15 * math.sin(v.particle_age * 360)", 0], "-v.particle_age * 90"),
        billboard([f"v.rd * 0.62 * {APPEAR}"] * 2, "emitter_transform_xz", uv_full("rune_ring")),
        color(GOLD_HOT, HOLD_FADE),
    ))
    effect("solar_sky_beam", "beam", "particles_add", merge(
        init(sc=1.0, lf=0.8, ht=18.0, al=1.0),
        instant(1), point(),
        life("v.lf"),
        parametric([0, "v.ht * 0.5", 0]),
        billboard(["0.32 * v.sc * (1 + 0.25 * math.sin(v.particle_age * 1800))", "v.ht * 0.5"], "lookat_y", uv_full("beam")),
        color(GOLD_HOT, f"{HOLD_FADE} * v.al"),
    ))
    # spear falls from v.ht above the emitter and lands exactly at its life end
    effect("solar_spear_fall", "spear", "particles_add", merge(
        init(sc=1.0, lf=0.3, ht=16.0),
        instant(1), point(),
        life("v.lf"),
        parametric([0, f"3.2 * v.sc + v.ht * (1 - {T} * {T})", 0]),
        billboard(["0.8 * v.sc", "3.2 * v.sc"], "lookat_y", uv_full("spear")),
        color((1, 1, 1), f"math.min(1, {T} * 5)"),
    ))
    effect("solar_spear_stuck", "spear", "particles_add", merge(
        init(sc=1.0, lf=0.9),
        instant(1), point(),
        life("v.lf"),
        parametric([0, "3.2 * v.sc * 0.62", 0]),
        billboard([f"0.8 * v.sc * (1 + 0.06 * math.sin(v.particle_age * 2000))", "3.2 * v.sc"], "lookat_y", uv_full("spear")),
        color((1, 1, 1), f"math.pow(1 - {T}, 1.6)"),
    ))
    effect("solar_shockwave", "shock_ring", "particles_add", merge(
        init(sc=1.0, lf=0.5, rd=5.0),
        instant(1), point(),
        life("v.lf"),
        dynamic(),
        billboard([f"v.rd * (0.15 + 1.0 * {EASE_OUT})"] * 2, "emitter_transform_xz", uv_full("shock_ring")),
        gradient([(0.0, (1, 0.95, 0.75, 1)), (0.4, (1, 0.78, 0.32, 0.85)), (1.0, (1, 0.5, 0.15, 0))]),
    ))
    effect("solar_ground_crack", "crack_star", "particles_add", merge(
        init(sc=1.0, lf=1.3, rd=4.0),
        instant(1), point(),
        life("v.lf"),
        parametric([0, 0, 0], "v.particle_random_1 * 360"),
        billboard(["v.rd * 0.85", "v.rd * 0.85"], "emitter_transform_xz", uv_full("crack_star")),
        gradient([(0.0, (1, 1, 0.9, 1)), (0.15, (1, 0.8, 0.35, 1)), (0.6, (1, 0.55, 0.15, 0.7)), (1.0, (0.9, 0.3, 0.05, 0))]),
    ))
    effect("solar_debris", "fx_atlas", "particles_add", merge(
        init(sc=1.0, dn=1.0),
        instant("math.floor(14 * v.dn)"),
        point(direction=["math.random(-1, 1)", "math.random(0.7, 1.8)", "math.random(-1, 1)"]),
        life("math.random(0.6, 1.0)"),
        speed("math.random(5, 11) * v.sc"),
        dynamic((0, -16, 0), 0.6),
        billboard([f"0.22 * v.sc * (1 - {T} * 0.5)", f"0.08 * v.sc"], "lookat_direction", uv_cell("shard"), VEL_DIR),
        gradient([(0.0, (1, 1, 0.95, 1)), (0.4, (1, 0.82, 0.4, 1)), (1.0, (1, 0.45, 0.1, 0))]),
    ))
    effect("solar_pillar", "fx_atlas", "particles_add", merge(
        init(sc=1.0, dn=1.0, rd=3.0),
        instant("math.floor(18 * v.dn)"),
        disc("v.rd * 0.7", direction=[0, 1, 0]),
        life("math.random(0.3, 0.55)"),
        speed("math.random(9, 18)"),
        dynamic((0, 0, 0), 2.2),
        billboard([f"(0.7 + 0.6 * v.particle_random_1) * v.sc * (1 - {T})", f"0.05 * v.sc"], "lookat_direction", uv_cell("glow"), VEL_DIR),
        gradient([(0.0, (1, 1, 0.95, 1)), (0.5, (1, 0.8, 0.35, 0.8)), (1.0, (1, 0.5, 0.15, 0))]),
    ))

    # ---- Solar Crown (respawned every 3 ticks, 5-tick life, trapezoid alpha)
    effect("solar_crown_halo", "sun_halo", "particles_add", merge(
        init(sc=1.0, lf=0.25, al=1.0, ph=0.0, dir=(0, 0, 1), vel=(0, 0, 0)),
        instant(1), point(),
        life("v.lf"),
        parametric(FOLLOW, "v.ph + v.particle_age * 40"),
        billboard(["1.15 * v.sc", "1.15 * v.sc"], "direction_z", uv_full("sun_halo"), CUSTOM_DIR),
        color(GOLD, f"{TRAP} * v.al"),
    ))
    effect("solar_crown_orbit", "crown_orbit", "particles_add", merge(
        init(sc=1.0, lf=0.25, al=1.0, ph=0.0, vel=(0, 0, 0)),
        instant(1), point(),
        life("v.lf"),
        parametric(FOLLOW, "v.ph + v.particle_age * 220"),
        billboard(["1.3 * v.sc", "1.3 * v.sc"], "emitter_transform_xz", uv_full("crown_orbit")),
        color(GOLD_HOT, f"{TRAP} * v.al"),
    ))
    effect("solar_crown_burst", "sun_halo", "particles_add", merge(
        init(sc=1.0, lf=0.6, dir=(0, 0, 1)),
        instant(1), point(),
        life("v.lf"),
        parametric([0, 0, 0], "v.particle_age * 120"),
        billboard([f"v.sc * (0.4 + 2.4 * {EASE_OUT})"] * 2, "direction_z", uv_full("sun_halo"), CUSTOM_DIR),
        gradient([(0.0, (1, 1, 0.9, 1)), (0.3, (1, 0.82, 0.4, 0.9)), (1.0, (1, 0.5, 0.15, 0))]),
    ))


# =================================================================== VOID

def build_void():
    effect("void_passive_wisp", "fx_atlas", "particles_blend", merge(
        init(sc=1.0, dn=1.0),
        instant("math.max(1, math.floor(2 * v.dn))"),
        sphere("0.75 * v.sc", surface=True, direction=["math.random(-0.4, 0.4)", 0.6, "math.random(-0.4, 0.4)"]),
        life("math.random(0.9, 1.4)"),
        speed("math.random(0.1, 0.35)"),
        dynamic((0, 0.1, 0), 0.8),
        billboard([f"(0.18 + 0.14 * v.particle_random_2) * v.sc * math.sin({T} * 180)"] * 2, "lookat_xyz",
                  uv_pick("wisp0", "wisp1", "wisp2", "wisp3")),
        spin("math.random(0, 360)", "math.random(-40, 40)"),
        gradient([(0.0, (0.25, 0.08, 0.45, 0)), (0.3, (0.18, 0.05, 0.34, 0.75)), (1.0, (0.06, 0.0, 0.12, 0))]),
    ))
    effect("void_stars", "fx_atlas", "particles_add", merge(
        init(sc=1.0, dn=1.0, rd=0.4, spd=1.0),
        instant("math.max(1, math.floor(8 * v.dn))"),
        sphere("v.rd", direction="outwards"),
        life("math.random(0.6, 1.2)"),
        speed("math.random(0.6, 3.5) * v.spd"),
        dynamic((0, 0.25, 0), 2.5),
        billboard([f"(0.05 + 0.09 * v.particle_random_2) * v.sc * math.sin({T} * 180)"] * 2, "lookat_xyz",
                  uv_pick("spark4", "dot", "crescent")),
        spin("math.random(0, 360)", "math.random(-90, 90)"),
        color_pick(STAR_BLUE, VIOLET, "math.sin(" + T + " * 180)", split=0.6),
    ))
    # dark crescent body (alpha blended) + glowing rim + deep-blue aura
    effect("void_crescent_body", "slash_arc", "particles_blend", merge(
        init(sc=1.0, lf=0.2, al=0.7, spd=30.0, tilt=0.0, dir=(0, 0, 1)),
        instant(1), point(),
        life("v.lf"),
        parametric(TRAVEL, "v.tilt"),
        billboard([f"1.95 * v.sc * (0.92 + 0.16 * {T})", "1.0 * v.sc"], "direction_z", uv_full("slash_arc"), CUSTOM_DIR),
        color(VOID_BLACK, f"{TRI} * v.al"),
    ))
    effect("void_crescent_rim", "slash_edge", "particles_add", merge(
        init(sc=1.0, lf=0.2, al=0.6, spd=30.0, tilt=0.0, dir=(0, 0, 1)),
        instant(1), point(),
        life("v.lf"),
        parametric(TRAVEL, "v.tilt"),
        billboard([f"1.9 * v.sc * (0.92 + 0.16 * {T})", "0.95 * v.sc"], "direction_z", uv_full("slash_edge"), CUSTOM_DIR),
        color(VIOLET, f"{TRI} * v.al"),
    ))
    effect("void_crescent_aura", "slash_arc", "particles_add", merge(
        init(sc=1.0, lf=0.2, al=0.35, spd=30.0, tilt=0.0, dir=(0, 0, 1)),
        instant(1), point(),
        life("v.lf"),
        parametric(TRAVEL, "v.tilt"),
        billboard([f"2.3 * v.sc", "1.25 * v.sc"], "direction_z", uv_full("slash_arc"), CUSTOM_DIR),
        color(BLUE, f"{TRI} * v.al"),
    ))
    effect("void_trail", "fx_atlas", "particles_blend", merge(
        init(sc=1.0, dn=1.0, dir=(0, 0, 1)),
        instant("math.max(1, math.floor(3 * v.dn))"),
        sphere("0.5 * v.sc", direction=["-v.dir.x + math.random(-0.5, 0.5)", "-v.dir.y + math.random(-0.5, 0.5)",
                                        "-v.dir.z + math.random(-0.5, 0.5)"]),
        life("math.random(0.45, 0.8)"),
        speed("math.random(0.5, 1.5)"),
        dynamic((0, 0.2, 0), 2.0),
        billboard([f"(0.28 + 0.2 * v.particle_random_2) * v.sc * (0.6 + 0.4 * {T})"] * 2, "lookat_xyz",
                  uv_pick("wisp0", "wisp1", "wisp2", "wisp3")),
        spin("math.random(0, 360)", "math.random(-60, 60)"),
        gradient([(0.0, (0.3, 0.1, 0.55, 0.0)), (0.15, (0.2, 0.05, 0.38, 0.8)), (1.0, (0.05, 0.0, 0.1, 0))]),
    ))
    effect("void_lines", "fx_atlas", "particles_add", merge(
        init(sc=1.0, dn=1.0, dir=(0, 0, 1)),
        instant("math.floor(3 * v.dn)"),
        sphere("0.45 * v.sc", direction=["-v.dir.x * 2 + math.random(-0.4, 0.4)", "-v.dir.y * 2 + math.random(-0.4, 0.4)",
                                         "-v.dir.z * 2 + math.random(-0.4, 0.4)"]),
        life("math.random(0.2, 0.35)"),
        speed("math.random(2, 4)"),
        dynamic((0, 0, 0), 3.0),
        billboard([f"(0.35 + 0.3 * v.particle_random_1) * v.sc * (1 - {T})", f"0.03 * v.sc"], "lookat_direction", uv_cell("glow"), VEL_DIR),
        color_pick(PURPLE, BLUE, f"1 - {T}"),
    ))
    effect("void_hit_ring", "shock_ring", "particles_add", merge(
        init(sc=1.0, lf=0.35, dir=(0, 0, 1)),
        instant(1), point(),
        life("v.lf"),
        dynamic(),
        billboard([f"v.sc * (0.3 + 2.3 * {EASE_OUT})"] * 2, "direction_z", uv_full("shock_ring"), CUSTOM_DIR),
        gradient([(0.0, (0.85, 0.65, 1.0, 1)), (0.4, (0.6, 0.28, 1.0, 0.9)), (1.0, (0.3, 0.1, 0.7, 0))]),
    ))
    effect("void_hit_core", "void_core", "particles_blend", merge(
        init(sc=1.0, lf=0.3),
        instant(1), point(),
        life("v.lf"),
        dynamic(),
        billboard([f"v.sc * 0.9 * (1 - 0.8 * {T})"] * 2, "lookat_xyz", uv_full("void_core")),
        spin("math.random(0, 360)", -720),
        color((1, 1, 1), f"math.min(1, (1 - {T}) * 3)"),
    ))
    effect("void_implode", "fx_atlas", "particles_add", merge(
        init(sc=1.0, dn=1.0, rd=1.5),
        instant("math.floor(14 * v.dn)"),
        sphere("v.rd", surface=True, direction="inwards"),
        life("math.random(0.18, 0.3)"),
        speed("v.rd * 4"),
        dynamic(),
        billboard([f"(0.4 + 0.3 * v.particle_random_1) * v.sc * (1 - {T} * 0.7)", "0.04 * v.sc"], "lookat_direction", uv_cell("glow"), VEL_DIR),
        color_pick(VIOLET, STAR_BLUE, f"math.min(1, {T} * 4)"),
    ))

    # ---- Abyss Field (spawned once, lives for the whole field duration)
    effect("void_field_pool", "eclipse_disc", "particles_blend", merge(
        init(sc=1.0, lf=6.0, rd=5.0, al=0.9),
        instant(1), point(),
        life("v.lf"),
        parametric([0, 0, 0], "v.particle_age * -12"),
        billboard([f"v.rd * 1.6 * {APPEAR}"] * 2, "emitter_transform_xz", uv_full("eclipse_disc")),
        color((1, 1, 1), f"math.clamp(math.min(v.particle_age * 4, (v.lf - v.particle_age) * 1.6), 0, 1) * v.al"),
    ))
    effect("void_field_swirl", "void_swirl", "particles_add", merge(
        init(sc=1.0, lf=6.0, rd=5.0),
        instant(1), point(),
        life("v.lf"),
        parametric([0, 0.04, 0], "v.particle_age * -70"),
        billboard([f"v.rd * {APPEAR}"] * 2, "emitter_transform_xz", uv_full("void_swirl")),
        color(PURPLE, f"math.clamp(math.min(v.particle_age * 4, (v.lf - v.particle_age) * 1.6), 0, 1) * (0.8 + 0.2 * math.sin(v.particle_age * 400))"),
    ))
    effect("void_field_circle", "magic_circle_void", "particles_add", merge(
        init(sc=1.0, lf=6.0, rd=5.0, al=0.75),
        instant(1), point(),
        life("v.lf"),
        parametric([0, 0.06, 0], "v.particle_age * 25"),
        billboard([f"v.rd * 1.04 * {APPEAR}"] * 2, "emitter_transform_xz", uv_full("magic_circle_void")),
        color(VIOLET, f"math.clamp(math.min(v.particle_age * 5, (v.lf - v.particle_age) * 1.6), 0, 1) * v.al"),
    ))
    effect("void_field_lines", "crown_orbit", "particles_add", merge(
        init(sc=1.0, lf=6.0, rd=5.0),
        instant(1), point(),
        life("v.lf"),
        parametric([0, 0.1, 0], "v.particle_age * 160"),
        billboard(["v.rd * 1.12", "v.rd * 1.12"], "emitter_transform_xz", uv_full("crown_orbit")),
        color(VIOLET, f"math.clamp(math.min(v.particle_age * 3, (v.lf - v.particle_age) * 1.6), 0, 1)"),
    ))
    effect("void_field_inflow", "fx_atlas", "particles_add", merge(
        init(sc=1.0, dn=1.0, lf=6.0, rd=5.0),
        steady("16 * v.dn", 40),
        point(),
        life("math.random(1.0, 1.4)"),
        parametric([f"v.rd * (1 - {T}) * math.cos(v.particle_random_1 * 360 + v.particle_age * 160)",
                    f"0.15 + 0.5 * math.sin({T} * 180) * v.particle_random_2",
                    f"v.rd * (1 - {T}) * math.sin(v.particle_random_1 * 360 + v.particle_age * 160)"]),
        billboard([f"(0.06 + 0.06 * v.particle_random_2) * v.sc * (0.4 + {T})"] * 2, "lookat_xyz", uv_pick("glow", "dot", "spark4")),
        color_pick(VIOLET, STAR_BLUE, f"math.sin({T} * 180)", split=0.7),
    ))
    effect("void_field_stars", "fx_atlas", "particles_add", merge(
        init(sc=1.0, dn=1.0, lf=6.0, rd=5.0),
        steady("7 * v.dn", 20),
        disc("v.rd * 0.85", direction=[0, 1, 0]),
        life("math.random(1.2, 1.8)"),
        speed("math.random(0.5, 1.2)"),
        dynamic((0, 0.2, 0), 0.4),
        billboard([f"(0.05 + 0.08 * v.particle_random_2) * v.sc * math.sin({T} * 180)"] * 2, "lookat_xyz", uv_pick("spark4", "crescent", "dot")),
        spin("math.random(0, 360)", "math.random(-60, 60)"),
        color_pick(STAR_BLUE, VIOLET, f"math.sin({T} * 180)", split=0.55),
    ))
    effect("void_field_core", "void_core", "particles_blend", merge(
        init(sc=1.0, lf=6.0),
        instant(1), point(),
        life("v.lf"),
        parametric([0, 0.9, 0], "v.particle_age * -200"),
        billboard([f"v.sc * 0.9 * (1 + 0.12 * math.sin(v.particle_age * 540)) * {APPEAR}"] * 2, "lookat_xyz", uv_full("void_core")),
        color((1, 1, 1), "math.clamp(math.min(v.particle_age * 4, (v.lf - v.particle_age) * 2), 0, 1)"),
    ))
    effect("void_pulse", "shock_ring", "particles_add", merge(
        init(sc=1.0, lf=0.45, rd=5.0),
        instant(1), point(),
        life("v.lf"),
        dynamic(),
        billboard([f"v.rd * (1.05 - 0.85 * {EASE_OUT})"] * 2, "emitter_transform_xz", uv_full("shock_ring")),
        color(PURPLE, f"math.sin({T} * 180) * 0.8"),
    ))

    # ---- Moonfall
    effect("void_circle", "magic_circle_void", "particles_add", merge(
        init(sc=1.0, lf=1.6, rd=5.5, al=1.0),
        instant(1), point(),
        life("v.lf"),
        parametric([0, 0.05, 0], "v.particle_age * -50"),
        billboard([f"v.rd * 1.05 * {APPEAR}"] * 2, "emitter_transform_xz", uv_full("magic_circle_void")),
        color(VIOLET, f"{HOLD_FADE} * v.al"),
    ))
    effect("void_moon", "black_moon", "particles_blend", merge(
        init(sc=1.0, lf=1.4, vel=(0, 0, 0)),
        instant(1), point(),
        life("v.lf"),
        parametric(["v.vel.x * v.particle_age", "v.vel.y * v.particle_age + 0.15 * math.sin(v.particle_age * 240)", "v.vel.z * v.particle_age"]),
        billboard([f"2.4 * v.sc * (1 - math.pow(math.max(0, 1 - v.particle_age * 3), 3))"] * 2, "lookat_xyz", uv_full("black_moon")),
        color((1, 1, 1), "math.clamp((v.lf - v.particle_age) * 6, 0, 1)"),
    ))
    effect("void_moon_corona", "corona", "particles_add", merge(
        init(sc=1.0, lf=1.4, vel=(0, 0, 0)),
        instant(1), point(),
        life("v.lf"),
        parametric(["v.vel.x * v.particle_age", "v.vel.y * v.particle_age + 0.15 * math.sin(v.particle_age * 240)", "v.vel.z * v.particle_age"],
                   "v.particle_age * 30"),
        billboard([f"5.9 * v.sc * (1 - math.pow(math.max(0, 1 - v.particle_age * 3), 3)) * (1 + 0.04 * math.sin(v.particle_age * 900))"] * 2,
                  "lookat_xyz", uv_full("corona")),
        color((0.62, 0.42, 1.0), f"math.clamp((v.lf - v.particle_age) * 6, 0, 1) * math.min(1, v.particle_age * 3)"),
    ))
    effect("void_beam", "beam", "particles_add", merge(
        init(sc=1.0, lf=0.5, ht=14.0, al=1.0),
        instant(1), point(),
        life("v.lf"),
        parametric([0, "v.ht * 0.5", 0]),
        billboard([f"0.9 * v.sc * (1 - 0.6 * {T}) * (1 + 0.2 * math.sin(v.particle_age * 2400))", "v.ht * 0.5"], "lookat_y", uv_full("beam")),
        gradient([(0.0, (0.9, 0.8, 1.0, "v.al")), (0.3, (0.62, 0.32, 1.0, "v.al")), (1.0, (0.3, 0.1, 0.8, 0))]),
    ))
    effect("void_rain", "fx_atlas", "particles_add", merge(
        init(sc=1.0, dn=1.0, rd=3.0, ht=10.0),
        instant("math.floor(16 * v.dn)"),
        disc("v.rd", offset=(0, "v.ht", 0), direction=[0, -1, 0]),
        life("math.random(0.25, 0.4)"),
        speed("math.random(28, 40)"),
        dynamic(),
        billboard([f"(0.9 + 0.6 * v.particle_random_1) * v.sc", "0.05 * v.sc"], "lookat_direction", uv_cell("glow"), VEL_DIR),
        color_pick(VIOLET, STAR_BLUE, "1", split=0.6),
    ))
    effect("void_shockwave", "shock_ring", "particles_add", merge(
        init(sc=1.0, lf=0.6, rd=6.0),
        instant(1), point(),
        life("v.lf"),
        dynamic(),
        billboard([f"v.rd * (0.15 + 1.05 * {EASE_OUT})"] * 2, "emitter_transform_xz", uv_full("shock_ring")),
        gradient([(0.0, (0.9, 0.8, 1.0, 1)), (0.35, (0.6, 0.28, 1.0, 0.9)), (1.0, (0.25, 0.06, 0.6, 0))]),
    ))
    effect("void_ground_crack", "crack_star", "particles_add", merge(
        init(sc=1.0, lf=1.5, rd=5.0),
        instant(1), point(),
        life("v.lf"),
        parametric([0, 0, 0], "v.particle_random_1 * 360"),
        billboard(["v.rd * 0.9", "v.rd * 0.9"], "emitter_transform_xz", uv_full("crack_star")),
        gradient([(0.0, (0.9, 0.85, 1, 1)), (0.15, (0.62, 0.3, 1, 1)), (0.6, (0.4, 0.15, 0.9, 0.7)), (1.0, (0.2, 0.05, 0.5, 0))]),
    ))
    effect("void_smoke", "fx_atlas", "particles_blend", merge(
        init(sc=1.0, dn=1.0, rd=4.0),
        instant("math.floor(12 * v.dn)"),
        disc("v.rd * 0.5", direction="outwards"),
        life("math.random(0.8, 1.4)"),
        speed("math.random(2, 6)"),
        dynamic((0, 0.6, 0), 2.2),
        billboard([f"(0.6 + 0.5 * v.particle_random_2) * v.sc * (0.5 + {T})"] * 2, "lookat_xyz", uv_pick("wisp0", "wisp1", "wisp2", "wisp3")),
        spin("math.random(0, 360)", "math.random(-50, 50)"),
        gradient([(0.0, (0.25, 0.08, 0.45, 0.0)), (0.1, (0.16, 0.04, 0.3, 0.85)), (1.0, (0.04, 0.0, 0.08, 0))]),
    ))


# ================================================================= ECLIPSE

def build_eclipse():
    effect("eclipse_halo", "eclipse_halo", "particles_add", merge(
        init(sc=1.0, lf=0.25, al=1.0, ph=0.0, dir=(0, 0, 1), vel=(0, 0, 0)),
        instant(1), point(),
        life("v.lf"),
        parametric(FOLLOW, "v.ph + v.particle_age * 30"),
        billboard(["1.5 * v.sc", "1.5 * v.sc"], "direction_z", uv_full("eclipse_halo"), CUSTOM_DIR),
        color((1, 1, 1), f"{TRAP} * v.al"),
    ))
    effect("eclipse_orbit", "eclipse_orbit", "particles_add", merge(
        init(sc=1.0, lf=0.25, al=1.0, ph=0.0, vel=(0, 0, 0)),
        instant(1), point(),
        life("v.lf"),
        parametric(FOLLOW, "v.ph + v.particle_age * 200"),
        billboard(["1.4 * v.sc", "1.4 * v.sc"], "emitter_transform_xz", uv_full("eclipse_orbit")),
        color((1, 1, 1), f"{TRAP} * v.al"),
    ))
    effect("eclipse_stardust", "fx_atlas", "particles_add", merge(
        init(sc=1.0, dn=1.0, rd=1.2),
        instant("math.max(1, math.floor(3 * v.dn))"),
        sphere("v.rd", surface=True, direction=["math.random(-0.4, 0.4)", "math.random(0.2, 1)", "math.random(-0.4, 0.4)"]),
        life("math.random(0.9, 1.5)"),
        speed("math.random(0.15, 0.5)"),
        dynamic((0, 0, 0), 0.5),
        billboard([f"(0.05 + 0.08 * v.particle_random_2) * v.sc * math.sin({T} * 180)"] * 2, "lookat_xyz", uv_pick("spark4", "spark8", "dot", "crescent")),
        spin("math.random(0, 360)", "math.random(-90, 90)"),
        color_pick(GOLD_HOT, VIOLET, f"math.sin({T} * 180)"),
    ))
    effect("eclipse_split_ring", "split_ring", "particles_add", merge(
        init(sc=1.0, lf=1.0, al=1.0, ph=0.0, dir=(0, 0, 1)),
        instant(1), point(),
        life("v.lf"),
        parametric([0, 0, 0], "v.ph + v.particle_age * 35"),
        billboard([f"2.6 * v.sc * {APPEAR}"] * 2, "direction_z", uv_full("split_ring"), CUSTOM_DIR),
        color((1, 1, 1), f"{HOLD_FADE} * v.al"),
    ))
    effect("eclipse_sun", "sun_disc", "particles_add", merge(
        init(sc=1.0, lf=1.6, vel=(0, 0, 0)),
        instant(1), point(),
        life("v.lf"),
        parametric(FOLLOW, "v.particle_age * 40"),
        billboard([f"1.5 * v.sc * (1 - math.pow(math.max(0, 1 - v.particle_age * 3), 3)) * (1 + 0.05 * math.sin(v.particle_age * 1100))"] * 2,
                  "lookat_xyz", uv_full("sun_disc")),
        color((1, 1, 1), "math.clamp((v.lf - v.particle_age) * 8, 0, 1)"),
    ))
    effect("eclipse_vortex", "fx_atlas", "particles_add", merge(
        init(sc=1.0, dn=1.0, lf=1.5, rd=3.0),
        steady("40 * v.dn", 90),
        point(),
        life("math.random(0.6, 1.0)"),
        parametric([f"v.rd * (0.75 + 0.4 * v.particle_random_2) * (1 - 0.35 * {T}) * math.cos(v.particle_random_1 * 360 + v.particle_age * 300)",
                    f"(v.particle_random_3 - 0.5) * 1.6 + 0.8 * {T}",
                    f"v.rd * (0.75 + 0.4 * v.particle_random_2) * (1 - 0.35 * {T}) * math.sin(v.particle_random_1 * 360 + v.particle_age * 300)"]),
        billboard([f"(0.07 + 0.08 * v.particle_random_2) * v.sc * math.sin({T} * 180)"] * 2, "lookat_xyz", uv_pick("glow", "spark4", "dot")),
        color_pick(GOLD_HOT, VIOLET, f"math.sin({T} * 180)"),
    ))
    effect("eclipse_disc", "eclipse_disc", "particles_blend", merge(
        init(sc=1.0, lf=1.2),
        instant(1), point(),
        life("v.lf"),
        dynamic(),
        billboard([f"2.2 * v.sc * (1 - math.pow(math.max(0, 1 - v.particle_age * 5), 2))"] * 2, "lookat_xyz", uv_full("eclipse_disc")),
        color((1, 1, 1), "math.clamp((v.lf - v.particle_age) * 5, 0, 1)"),
    ))
    effect("eclipse_corona", "corona", "particles_add", merge(
        init(sc=1.0, lf=1.2),
        instant(1), point(),
        life("v.lf"),
        parametric([0, 0, 0], "v.particle_age * 25"),
        billboard([f"4.4 * v.sc * (1 - math.pow(math.max(0, 1 - v.particle_age * 5), 2)) * (1 + 0.05 * math.sin(v.particle_age * 1300))"] * 2,
                  "lookat_xyz", uv_full("corona")),
        color((1, 1, 1), "math.clamp((v.lf - v.particle_age) * 5, 0, 1)"),
    ))
    effect("eclipse_shockwave", "shock_ring", "particles_add", merge(
        init(sc=1.0, lf=0.8, rd=11.0),
        instant(1), point(),
        life("v.lf"),
        dynamic(),
        billboard([f"v.rd * (0.1 + 1.1 * {EASE_OUT})"] * 2, "emitter_transform_xz", uv_full("shock_ring")),
        gradient([(0.0, (1, 1, 0.95, 1)), (0.25, (1, 0.8, 0.36, 1)), (0.6, (0.62, 0.3, 1.0, 0.8)), (1.0, (0.3, 0.08, 0.7, 0))]),
    ))
    effect("eclipse_shock_wall", "split_ring", "particles_add", merge(
        init(sc=1.0, lf=0.7, rd=11.0),
        instant(1), point(),
        life("v.lf"),
        parametric([0, 0.2, 0], "v.particle_age * 90"),
        billboard([f"v.rd * (0.1 + 0.95 * {EASE_OUT})"] * 2, "emitter_transform_xz", uv_full("split_ring")),
        color((1, 1, 1), FADE_OUT),
    ))
    effect("eclipse_burst", "fx_atlas", "particles_add", merge(
        init(sc=1.0, dn=1.0, rd=0.8, spd=1.0),
        instant("math.floor(48 * v.dn)"),
        sphere("v.rd", direction="outwards"),
        life("math.random(0.5, 1.1)"),
        speed("math.random(8, 22) * v.spd"),
        dynamic((0, -2, 0), 2.6),
        billboard([f"(0.5 + 0.6 * v.particle_random_1) * v.sc * (1 - {T})", f"0.06 * v.sc * (1 - {T} * 0.5)"],
                  "lookat_direction", uv_cell("glow"), VEL_DIR),
        color_pick(GOLD_HOT, VIOLET, f"1 - {T} * {T}"),
    ))
    effect("eclipse_pillar", "beam", "particles_add", merge(
        init(sc=1.0, lf=0.55, ht=16.0),
        instant(1), point(),
        life("v.lf"),
        parametric([0, "v.ht * 0.5", 0]),
        billboard([f"2.0 * v.sc * (1 - {T}) * (1 + 0.15 * math.sin(v.particle_age * 2600))", "v.ht * 0.5"], "lookat_y", uv_full("beam")),
        gradient([(0.0, (1, 1, 1, 1)), (0.3, (1, 0.85, 0.5, 1)), (0.7, (0.62, 0.3, 1.0, 0.7)), (1.0, (0.3, 0.1, 0.7, 0))]),
    ))
    effect("eclipse_final_ring", "split_ring", "particles_add", merge(
        init(sc=1.0, lf=1.8, rd=12.0),
        instant(1), point(),
        life("v.lf"),
        parametric([0, 0.3, 0], "v.particle_age * 30"),
        billboard([f"v.rd * (0.5 + 1.5 * {EASE_OUT})"] * 2, "emitter_transform_xz", uv_full("split_ring")),
        color((1, 1, 1), f"math.min(1, v.particle_age * 5) * math.pow(1 - {T}, 1.2)"),
    ))
    effect("eclipse_star_rain", "fx_atlas", "particles_add", merge(
        init(sc=1.0, dn=1.0, lf=1.4, rd=10.0, ht=9.0),
        steady("30 * v.dn", 60),
        disc("v.rd", offset=(0, "v.ht", 0), direction=[0, -1, 0]),
        life("math.random(1.0, 1.6)"),
        speed("math.random(3, 6)"),
        dynamic((0, -2, 0), 0.3),
        billboard([f"(0.07 + 0.09 * v.particle_random_2) * v.sc * math.sin({T} * 180)"] * 2, "lookat_xyz", uv_pick("spark4", "spark8", "dot", "crescent")),
        spin("math.random(0, 360)", "math.random(-120, 120)"),
        color_pick(GOLD_HOT, VIOLET, f"math.sin({T} * 180)"),
    ))
    effect("eclipse_ready", "fx_atlas", "particles_add", merge(
        init(sc=1.0, dn=1.0),
        instant("math.floor(20 * v.dn)"),
        sphere("0.4 * v.sc", direction="outwards"),
        life("math.random(0.5, 0.9)"),
        speed("math.random(2, 5)"),
        dynamic((0, 1.5, 0), 3),
        billboard([f"(0.07 + 0.1 * v.particle_random_2) * v.sc * (1 - {T})"] * 2, "lookat_xyz", uv_pick("spark4", "spark8", "dot")),
        spin("math.random(0, 360)", "math.random(-180, 180)"),
        color_pick(GOLD_HOT, VIOLET, f"1 - {T}"),
    ))
    effect("eclipse_flash", "flash", "particles_add", merge(
        init(sc=1.0, lf=0.25, al=1.0),
        instant(1), point(),
        life("v.lf"),
        dynamic(),
        billboard([f"2.2 * v.sc * (1 - 0.4 * {T})"] * 2, "lookat_xyz", uv_full("flash")),
        spin("math.random(0, 360)", 0),
        gradient([(0.0, (1, 1, 1, "v.al")), (0.3, (1, 0.8, 0.45, "v.al")), (0.7, (0.65, 0.32, 1.0, "0.7 * v.al")), (1.0, (0.3, 0.1, 0.7, 0))]),
    ))


def build_all():
    EFFECTS.clear()
    build_solar()
    build_void()
    build_eclipse()
    out_dir = os.path.join(RP, "particles")
    if os.path.isdir(out_dir):
        for f in os.listdir(out_dir):
            if f.endswith(".json"):
                os.remove(os.path.join(out_dir, f))
    for name, data in EFFECTS.items():
        write_json(os.path.join(out_dir, f"{name}.particle.json"), data)
    return sorted(EFFECTS)


if __name__ == "__main__":
    names = build_all()
    print(len(names), "particle effects")
