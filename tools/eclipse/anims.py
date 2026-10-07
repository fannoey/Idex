"""Animations for ECLIPSE TWIN SWORDS.

Player animations (played from the script with Entity.playAnimation on the
"eclipse.stance" / "eclipse.cast" controllers):
    idle_solaris, idle_noctis, eclipse_idle         (looping stances)
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


def kf(points, smooth=True):
    """points: {time: [x,y,z]} -> keyframe dict (catmull-rom for motion)."""
    out = {}
    for t, v in sorted(points.items()):
        key = f"{t:.4g}"
        out[key] = {"post": list(v), "lerp_mode": "catmullrom"} if smooth else list(v)
    return out


def anim(length, bones, loop=False):
    a = {"animation_length": length, "blend_weight": FP_OFF, "bones": {}}
    if loop:
        a["loop"] = True
    for bone, channels in bones.items():
        a["bones"][bone] = {ch: (kf(val) if isinstance(val, dict) else val) for ch, val in channels.items()}
    return a


Z = [0, 0, 0]


def player_animations():
    A = {}
    breathe = "math.sin(q.anim_time * 180)"
    # ---------------------------------------------------------------- stances
    A["idle_solaris"] = anim(2.0, {
        "rightArm": {"rotation": [f"-14 + 2.5 * {breathe}", 10, 9]},
        "leftArm": {"rotation": [f"-9 + 2 * math.sin(q.anim_time * 180 + 90)", -12, -11]},
        "body": {"rotation": [0, f"-4 + 1.5 * {breathe}", 0]},
    }, loop=True)
    A["idle_noctis"] = anim(2.0, {
        "rightArm": {"rotation": [f"-11 + 2.5 * {breathe}", 14, 13]},
        "leftArm": {"rotation": [f"-15 + 2 * math.sin(q.anim_time * 180 + 90)", -8, -8]},
        "body": {"rotation": [0, f"4 - 1.5 * {breathe}", 0]},
    }, loop=True)
    A["eclipse_idle"] = anim(2.4, {
        "rightArm": {"rotation": [f"-22 + 3 * math.sin(q.anim_time * 150)", 16, 24]},
        "leftArm": {"rotation": [f"-22 + 3 * math.sin(q.anim_time * 150 + 120)", -16, -24]},
        "body": {"rotation": [f"-3 + 1.2 * math.sin(q.anim_time * 150)", 0, 0]},
        "head": {"rotation": [-4, 0, 0]},
    }, loop=True)

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


PLAYER_ANIMS = ["idle_solaris", "idle_noctis", "eclipse_idle", "solar_cast", "radiant_spear", "solar_crown",
                "void_crescent", "abyss_field", "moonfall", "eclipse_activate", "eclipse_ultimate"]
