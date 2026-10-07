"""Animations for ECLIPSE TWIN SWORDS.

Player animations (played from the script with Entity.playAnimation):
    idle_solaris, idle_noctis, eclipse_idle         holding stance (standing)
    walk, run, attack                               locomotion / basic swing layers
    attack_left, attack_cross                       2nd / 3rd melee hit (blades alternate)
    skill_select                                    flourish when Sneak changes skill
    solar_cast, radiant_spear, solar_crown,
    void_crescent, abyss_field, moonfall,
    eclipse_activate, eclipse_ultimate              (one-shot casts)

Bedrock bone conventions (from vanilla poses): rightArm X<0 raises the arm
forward/up, rightArm Z>0 lifts it out to the right; leftArm Z<0 lifts it out
to the left. All casts are additive (they never fight the walk cycle) and
fade out in first person so the camera view stays clean.
"""
from common import NS

FP_OFF = "variable.is_first_person ? 0.0 : 1.0"
# movement blend (0 standing -> 1 walking), sprint and "can locomote" gates
MOVE = "math.clamp(q.modified_move_speed * 1.6, 0.0, 1.0)"
GROUND = "(1.0 - q.is_riding) * (1.0 - q.is_swimming) * (1.0 - q.is_gliding)"
STEP = "q.modified_distance_moved * 38.17"     # same phase as the vanilla leg swing
ATK = "math.sin(variable.attack_time * 180.0)"  # vanilla swing progress 0..1 -> 0..1..0


def kf(points, smooth=True):
    """points: {time: [x,y,z]} -> keyframe dict (catmull-rom for motion)."""
    out = {}
    for t, v in sorted(points.items()):
        key = f"{t:.4g}"
        out[key] = {"post": list(v), "lerp_mode": "catmullrom"} if smooth else list(v)
    return out


def anim(length, bones, loop=False, weight=None):
    a = {"animation_length": length, "blend_weight": f"({FP_OFF}) * ({weight})" if weight else FP_OFF, "bones": {}}
    if loop:
        a["loop"] = True
    for bone, channels in bones.items():
        a["bones"][bone] = {ch: (kf(val) if isinstance(val, dict) else val) for ch, val in channels.items()}
    return a


Z = [0, 0, 0]


def player_animations():
    A = {}
    IDLE = f"1.0 - {MOVE} * {GROUND}"
    breathe = "math.sin(q.anim_time * 180)"
    # ---------------------------------------------------------------- stances
    A["idle_solaris"] = anim(2.0, {
        "rightArm": {"rotation": [f"-14 + 2.5 * {breathe}", 10, 9]},
        "leftArm": {"rotation": [f"-9 + 2 * math.sin(q.anim_time * 180 + 90)", -12, -11]},
        "body": {"rotation": [0, f"-4 + 1.5 * {breathe}", 0]},
    }, loop=True, weight=IDLE)
    A["idle_noctis"] = anim(2.0, {
        "rightArm": {"rotation": [f"-11 + 2.5 * {breathe}", 14, 13]},
        "leftArm": {"rotation": [f"-15 + 2 * math.sin(q.anim_time * 180 + 90)", -8, -8]},
        "body": {"rotation": [0, f"4 - 1.5 * {breathe}", 0]},
    }, loop=True, weight=IDLE)
    A["eclipse_idle"] = anim(2.4, {
        "rightArm": {"rotation": [f"-22 + 3 * math.sin(q.anim_time * 150)", 16, 24]},
        "leftArm": {"rotation": [f"-22 + 3 * math.sin(q.anim_time * 150 + 120)", -16, -24]},
        "body": {"rotation": [f"-3 + 1.2 * math.sin(q.anim_time * 150)", 0, 0]},
        "head": {"rotation": [-4, 0, 0]},
    }, loop=True, weight=IDLE)

    # ------------------------------------------------- locomotion / attack
    # Played on their own controllers next to the stance; each one fades in
    # through its blend_weight, so standing / walking / sprinting / swinging
    # blend smoothly without a player.entity.json override.
    A["walk"] = anim(1.0, {
        # cancel most of the vanilla arm swing (variable.tcos0) and carry both blades low and ready
        "rightArm": {"rotation": [f"variable.tcos0 * 0.85 - 16 + 7 * math.cos({STEP})", 8, 12]},
        "leftArm": {"rotation": [f"-variable.tcos0 * 0.85 - 13 - 7 * math.cos({STEP})", -8, -12]},
        "body": {"rotation": [4, f"5 * math.sin({STEP} * 0.5)", 0]},
        "head": {"rotation": [-3, 0, 0]},
    }, loop=True, weight=f"{MOVE} * (1.0 - q.is_sprinting) * {GROUND}")
    A["run"] = anim(1.0, {
        # sprint: lean in, both blades swept back and trailing (anime dash run)
        "rightArm": {"rotation": [f"variable.tcos0 + 52 + 5 * math.cos({STEP})", 12, 24]},
        "leftArm": {"rotation": [f"-variable.tcos0 + 52 - 5 * math.cos({STEP})", -12, -24]},
        "body": {"rotation": [16, f"4 * math.sin({STEP} * 0.5)", 0]},
        "head": {"rotation": [-15, 0, 0]},
        "root": {"position": [0, f"-0.4 + 0.4 * math.abs(math.sin({STEP} * 0.5))", 0]},
    }, loop=True, weight=f"{MOVE} * q.is_sprinting * {GROUND}")
    A["attack"] = anim(1.0, {
        # reshapes the vanilla swing into a wide diagonal blade slash
        "rightArm": {"rotation": [f"-70 * {ATK}", f"40 * {ATK} - 55 * math.sin(variable.attack_time * 90.0)", f"22 * {ATK}"]},
        "leftArm": {"rotation": [f"-18 * {ATK}", 0, f"-20 * {ATK}"]},
        "body": {"rotation": [f"6 * {ATK}", f"-24 * {ATK}", 0]},
    }, loop=True)
    A["attack_left"] = anim(0.45, {
        "leftArm": {"rotation": {0.0: Z, 0.07: [-118, -40, -34], 0.16: [-82, 56, -10], 0.28: [-72, 50, -6], 0.45: Z}},
        "rightArm": {"rotation": {0.0: Z, 0.12: [-16, 0, 24], 0.45: Z}},
        "body": {"rotation": {0.0: Z, 0.07: [0, -16, 0], 0.16: [3, 22, 0], 0.28: [2, 18, 0], 0.45: Z}},
    })
    A["attack_cross"] = anim(0.5, {
        "rightArm": {"rotation": {0.0: Z, 0.08: [-150, -10, 30], 0.18: [-70, -40, -14], 0.32: [-64, -36, -12], 0.5: Z}},
        "leftArm": {"rotation": {0.0: Z, 0.08: [-150, 10, -30], 0.18: [-70, 40, 14], 0.32: [-64, 36, 12], 0.5: Z}},
        "body": {"rotation": {0.0: Z, 0.08: [-8, 0, 0], 0.18: [14, 0, 0], 0.32: [12, 0, 0], 0.5: Z}},
        "root": {"position": {0.0: Z, 0.18: [0, -0.8, 0], 0.5: Z}},
    })
    A["skill_select"] = anim(0.35, {
        # quick wrist flourish of both blades when the skill changes
        "rightArm": {"rotation": {0.0: Z, 0.1: [-34, 0, 20], 0.2: [-30, 0, 16], 0.35: Z}},
        "leftArm": {"rotation": {0.0: Z, 0.1: [-34, 0, -20], 0.2: [-30, 0, -16], 0.35: Z}},
    })

    # ---------------------------------------------------------- SOLARIS casts
    A["solar_cast"] = anim(0.55, {
        "rightArm": {"rotation": {0.0: Z, 0.08: [-115, 42, 34], 0.17: [-86, -58, 12], 0.3: [-72, -52, 6], 0.55: Z}},
        "leftArm": {"rotation": {0.0: Z, 0.12: [-14, 0, -26], 0.3: [-10, 0, -20], 0.55: Z}},
        "body": {"rotation": {0.0: Z, 0.08: [0, 16, 0], 0.17: [3, -22, 0], 0.3: [2, -18, 0], 0.55: Z}},
        "rightLeg": {"rotation": {0.0: Z, 0.17: [-8, 0, 0], 0.55: Z}},
        "leftLeg": {"rotation": {0.0: Z, 0.17: [10, 0, 0], 0.55: Z}},
    })
    A["radiant_spear"] = anim(0.9, {
        "rightArm": {"rotation": {0.0: Z, 0.15: [-166, 0, 14], 0.36: [-171, 0, 12], 0.46: [-62, 0, 6], 0.66: [-56, 0, 6], 0.9: Z}},
        "leftArm": {"rotation": {0.0: Z, 0.15: [-34, 0, -42], 0.46: [8, 0, -18], 0.9: Z}},
        "body": {"rotation": {0.0: Z, 0.15: [-6, 0, 0], 0.46: [13, 0, 0], 0.66: [11, 0, 0], 0.9: Z}},
        "head": {"rotation": {0.0: Z, 0.15: [-18, 0, 0], 0.46: [6, 0, 0], 0.9: Z}},
    })
    A["solar_crown"] = anim(1.1, {
        "rightArm": {"rotation": {0.0: Z, 0.22: [-176, 0, 6], 0.72: [-179, 0, 6], 1.1: Z}},
        "leftArm": {"rotation": {0.0: Z, 0.22: [-34, 0, -56], 0.72: [-36, 0, -58], 1.1: Z}},
        "body": {"rotation": {0.0: Z, 0.22: [-9, 0, 0], 0.72: [-9, 0, 0], 1.1: Z}},
        "head": {"rotation": {0.0: Z, 0.22: [-22, 0, 0], 0.72: [-22, 0, 0], 1.1: Z}},
    })

    # ----------------------------------------------------------- NOCTIS casts
    A["void_crescent"] = anim(0.55, {
        "rightArm": {"rotation": {0.0: Z, 0.08: [-58, -52, -18], 0.17: [-124, 52, 42], 0.3: [-116, 46, 38], 0.55: Z}},
        "leftArm": {"rotation": {0.0: Z, 0.12: [-18, 0, -22], 0.3: [-12, 0, -18], 0.55: Z}},
        "body": {"rotation": {0.0: Z, 0.08: [2, -18, 0], 0.17: [-2, 20, 0], 0.3: [-1, 16, 0], 0.55: Z}},
        "rightLeg": {"rotation": {0.0: Z, 0.17: [10, 0, 0], 0.55: Z}},
        "leftLeg": {"rotation": {0.0: Z, 0.17: [-8, 0, 0], 0.55: Z}},
    })
    A["abyss_field"] = anim(0.8, {
        "rightArm": {"rotation": {0.0: Z, 0.14: [-152, 0, 10], 0.28: [-28, 0, 2], 0.55: [-26, 0, 2], 0.8: Z}},
        "leftArm": {"rotation": {0.0: Z, 0.14: [-40, 0, -30], 0.28: [-6, 0, -26], 0.8: Z}},
        "body": {"rotation": {0.0: Z, 0.14: [-6, 0, 0], 0.28: [24, 0, 0], 0.55: [22, 0, 0], 0.8: Z}},
        "root": {"position": {0.0: Z, 0.28: [0, -1.2, 0], 0.55: [0, -1.1, 0], 0.8: Z}},
        "rightLeg": {"rotation": {0.0: Z, 0.28: [-22, 0, 0], 0.55: [-20, 0, 0], 0.8: Z}},
        "leftLeg": {"rotation": {0.0: Z, 0.28: [16, 0, 0], 0.55: [14, 0, 0], 0.8: Z}},
    })
    A["moonfall"] = anim(1.2, {
        "rightArm": {"rotation": {0.0: Z, 0.2: [-174, 0, 28], 0.6: [-178, 26, 38], 0.85: [-74, 0, 10], 1.0: [-70, 0, 8], 1.2: Z}},
        "leftArm": {"rotation": {0.0: Z, 0.2: [-158, 0, -30], 0.6: [-162, -20, -36], 0.85: [-30, 0, -20], 1.2: Z}},
        "body": {"rotation": {0.0: Z, 0.2: [-8, 0, 0], 0.6: [-10, 0, 0], 0.85: [15, 0, 0], 1.0: [13, 0, 0], 1.2: Z}},
        "head": {"rotation": {0.0: Z, 0.2: [-20, 0, 0], 0.6: [-24, 0, 0], 0.85: [4, 0, 0], 1.2: Z}},
    })

    # ---------------------------------------------------------------- ECLIPSE
    A["eclipse_activate"] = anim(1.1, {
        "rightArm": {"rotation": {0.0: Z, 0.15: [-90, -36, -10], 0.45: [-92, -36, -10], 0.6: [-40, 30, 76], 0.9: [-42, 30, 74], 1.1: Z}},
        "leftArm": {"rotation": {0.0: Z, 0.15: [-90, 36, 10], 0.45: [-92, 36, 10], 0.6: [-40, -30, -76], 0.9: [-42, -30, -74], 1.1: Z}},
        "body": {"rotation": {0.0: Z, 0.15: [10, 0, 0], 0.45: [10, 0, 0], 0.6: [-10, 0, 0], 0.9: [-9, 0, 0], 1.1: Z}},
        "head": {"rotation": {0.0: Z, 0.6: [-12, 0, 0], 1.1: Z}},
    })
    tremble = "math.sin(q.anim_time * 2200) * 1.2"
    A["eclipse_ultimate"] = anim(3.5, {
        # 0.0-0.4 raise both blades to the sky | 0.4-1.9 hold (sun & moon gather)
        # 1.9-2.2 black eclipse (frozen pose)  | 2.2 slam + spread | 3.5 recover
        "rightArm": {"rotation": {0.0: Z, 0.4: [-170, 0, -16], 1.9: [-172, 0, -14], 2.2: [-172, 0, -14],
                                  2.32: [-30, 22, 82], 3.0: [-32, 22, 80], 3.5: Z}},
        "leftArm": {"rotation": {0.0: Z, 0.4: [-170, 0, 16], 1.9: [-172, 0, 14], 2.2: [-172, 0, 14],
                                 2.32: [-30, -22, -82], 3.0: [-32, -22, -80], 3.5: Z}},
        "body": {"rotation": {0.0: Z, 0.4: [-10, 0, 0], 1.9: [-12, 0, 0], 2.2: [-12, 0, 0], 2.32: [16, 0, 0], 3.0: [14, 0, 0], 3.5: Z}},
        "head": {"rotation": {0.0: Z, 0.4: [-28, 0, 0], 2.2: [-30, 0, 0], 2.32: [8, 0, 0], 3.5: Z}},
        "root": {"position": {0.0: Z, 2.2: Z, 2.32: [0, -1.6, 0], 3.0: [0, -1.4, 0], 3.5: Z}},
        "rightLeg": {"rotation": {0.0: Z, 2.2: Z, 2.32: [-24, 0, 6], 3.0: [-22, 0, 6], 3.5: Z}},
        "leftLeg": {"rotation": {0.0: Z, 2.2: Z, 2.32: [20, 0, -6], 3.0: [18, 0, -6], 3.5: Z}},
        "waist": {"rotation": [f"(q.anim_time > 0.4 && q.anim_time < 1.9) ? {tremble} : 0", 0, 0]},
    })
    return {"format_version": "1.10.0",
            "animations": {f"animation.{NS}.{k}": v for k, v in A.items()}}


def attachable_animations():
    twin_visible = "query.is_item_name_any('slot.weapon.offhand', 0, '') ? 1.0 : 0.0"
    return {
        "format_version": "1.10.0",
        "animations": {
            f"animation.{NS}.blade.third_person": {
                "loop": True,
                "bones": {
                    "blade_fp": {"scale": 0.0},
                    "twin_l": {"scale": twin_visible},
                },
            },
            f"animation.{NS}.blade.first_person": {
                "loop": True,
                "bones": {
                    "blade_r": {"scale": 0.0},
                    "twin_l": {"scale": 0.0},
                    "blade_l": {"scale": 0.0},
                    # vanilla trident first-person hold (same bone frame as geometry.trident)
                    "blade_fp": {"position": [-7.0, -3.0, -2.0], "rotation": [152.0, -9.0, 25.0]},
                },
            },
        },
    }


def attachable_controller():
    return {
        "format_version": "1.10.0",
        "animation_controllers": {
            f"controller.animation.{NS}.blade": {
                "initial_state": "third_person",
                "states": {
                    "third_person": {
                        "animations": ["third_person"],
                        "transitions": [{"first_person": "c.is_first_person"}],
                    },
                    "first_person": {
                        "animations": ["first_person"],
                        "transitions": [{"third_person": "!c.is_first_person"}],
                    },
                },
            }
        },
    }


PLAYER_ANIMS = ["idle_solaris", "idle_noctis", "eclipse_idle", "walk", "run", "attack", "attack_left", "attack_cross",
                "skill_select", "solar_cast", "radiant_spear", "solar_crown",
                "void_crescent", "abyss_field", "moonfall", "eclipse_activate", "eclipse_ultimate"]
