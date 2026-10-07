"""Every player animation of the Cursed Reaper Scythe, authored as intent poses.

Root frame (Blockbench space): player faces -z, +x is the player's right, y up.
hand  = right-hand (grip) position, shaft = pommel->head direction,
blade = direction the blade sticks out of the head.
Movement language of the weapon: drag low -> spin -> wide swing -> flick up.
"""
import math

import numpy as np

from rig import Clip

C, L = "catmullrom", "linear"
FP_SAFE = {"blend_weight": "1.0 - q.is_first_person"}


def n(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


UP = np.array([0.0, 1, 0])


def lead_left(shaft):      # blade leading a right -> left sweep (counter-clockwise from above)
    return np.cross(UP, n(shaft))


def lead_right(shaft):     # blade leading a left -> right sweep / rightward body spin
    return np.cross(n(shaft), UP)


def P(hand, shaft, blade, left=True, **kw):
    pose = {"hand": hand, "shaft": shaft, "blade": blade, "left": left}
    rot, pos = {}, {}
    for k, v in kw.items():
        if k in ("left_y", "twist"):
            pose[k] = v
        elif k.endswith("_p"):
            pos[k[:-2]] = v
        else:
            rot[k] = v
    if left is not True and left is not False:
        rot["leftArm"] = left
        pose["left"] = False
    pose["rot"], pose["pos"] = rot, pos
    return pose


# ---------------------------------------------------------------- key poses
def hold(**kw):
    return P((5.5, 15.5, -3.0), (-0.6, 1, -0.12), (-0.15, -0.25, -1), left_y=22, **kw)


ZERO_BODY = dict(root=(0, 0, 0), waist=(0, 0, 0), rightLeg=(0, 0, 0), leftLeg=(0, 0, 0), root_p=(0, 0, 0))


def full(pose):
    """Make sure every body bone is keyed (so overriding clips start/end clean)."""
    for k, v in ZERO_BODY.items():
        if k.endswith("_p"):
            pose["pos"].setdefault(k[:-2], v)
        else:
            pose["rot"].setdefault(k, v)
    return pose


def H():
    return full(hold())


def lunge(depth=1.4, spread=24):
    return dict(rightLeg=(spread, 0, 3), leftLeg=(-spread, 0, -3), root_p=(0, -depth, 0))


def clips(scythe):
    S = scythe
    out = []

    # -- hold (loops while the scythe is in hand; arms + item only, legs stay vanilla)
    out.append(Clip("animation.idex.reaper.hold", 1.0, True,
                    [(0.0, hold(), L), (1.0, hold(), L)], S, extra=dict(FP_SAFE)))

    # -- normal attack 1: wide horizontal reap, right -> left
    sh0 = n((0.8, 0.15, 0.6))
    sh1 = n((0.05, 0.1, -1))
    sh2 = n((-0.85, 0.1, 0.35))
    out.append(Clip("animation.idex.reaper.attack1", 0.6, "hold_on_last_frame", [
        (0.0, H(), C),
        (0.12, full(P((6.5, 17, 1.5), sh0, lead_left(sh0), left_y=5, waist=(5, 40, 0), rightLeg=(12, 0, 2), leftLeg=(-10, 0, -2), root_p=(0, -0.5, 0))), C),
        (0.22, full(P((3.0, 17, -6.5), sh1, lead_left(sh1), left_y=5, waist=(8, 0, 0), rightLeg=(-6, 0, 2), leftLeg=(14, 0, -2), root_p=(0, -0.8, 0))), C),
        (0.32, full(P((0.5, 17, -4.5), sh2, lead_left(sh2), left_y=5, waist=(6, -45, 0), rightLeg=(-14, 0, 3), leftLeg=(16, 0, -3), root_p=(0, -0.6, 0))), C),
        (0.6, H(), C),
    ], S, extra=dict(FP_SAFE)))

    # -- normal attack 2: rising flick, low left -> high right
    a0 = n((-0.45, -0.3, -0.85))
    a1 = n((0.25, 0.55, -0.8))
    a2 = n((0.45, 0.85, 0.25))
    out.append(Clip("animation.idex.reaper.attack2", 0.6, "hold_on_last_frame", [
        (0.0, H(), C),
        (0.1, full(P((1.0, 15.5, -5), a0, (0.35, -0.4, 0.85), waist=(18, -30, 0), **lunge(1.4, 18))), C),
        (0.2, full(P((5.0, 19, -5.5), a1, (0.2, 0.8, 0.55), waist=(0, 10, 0), **lunge(0.6, 10))), C),
        (0.32, full(P((5.5, 23, -2), a2, (0.0, 0.25, 1), waist=(-8, 30, 0), rightLeg=(-6, 0, 2), leftLeg=(6, 0, -2))), C),
        (0.6, H(), C),
    ], S, extra=dict(FP_SAFE)))

    # -- normal attack 3: spin + overhead chop
    out.append(Clip("animation.idex.reaper.attack3", 0.8, "hold_on_last_frame", [
        (0.0, H(), C),
        (0.12, full(P((4.5, 26, -2), n((0.1, 0.8, 0.6)), (0, 0.6, -0.8), root=(0, -120, 0), waist=(-10, 0, 0))), C),
        (0.3, full(P((4.0, 27, -2.5), n((0.0, 0.85, 0.5)), (0, 0.5, -0.85), root=(0, -300, 0), waist=(-14, 0, 0), root_p=(0, 1.0, 0))), C),
        (0.42, full(P((3.5, 16.5, -6.5), n((0, -0.28, -0.96)), (0, -0.96, 0.28), root=(0, -360, 0), waist=(14, 0, 0), **lunge(1.2, 22))), C),
        (0.6, full(P((3.5, 16.5, -6.5), n((0, -0.3, -0.95)), (0, -0.95, 0.3), root=(0, -360, 0), waist=(12, 0, 0), **lunge(1.1, 20))), L),
        (0.8, full(hold(root=(0, -360, 0))), C),
    ], S, extra=dict(FP_SAFE)))

    # -- skill 1: Crimson Crescent (release at 0.42)
    c0 = n((0.75, 0.05, 0.65))
    c1 = n((0.0, 0.12, -1))
    c2 = n((-0.75, 0.1, -0.6))
    out.append(Clip("animation.idex.reaper.crimson_crescent", 1.2, "hold_on_last_frame", [
        (0.0, H(), C),
        (0.25, full(P((6.5, 16, 1.5), c0, lead_left(c0), root=(0, 70, 0), waist=(12, 25, 0), **lunge(1.6, 26))), C),
        (0.34, full(P((6.0, 16.5, -2.5), n((0.6, 0.1, -0.8)), lead_left((0.6, 0.1, -0.8)), root=(0, 35, 0), waist=(12, 10, 0), **lunge(1.8, 26))), C),
        (0.42, full(P((3.0, 17, -6.5), c1, lead_left(c1), root=(0, 0, 0), waist=(10, 0, 0), **lunge(1.8, 26))), C),
        (0.55, full(P((0.0, 17, -6.0), c2, lead_left(c2), root=(0, -90, 0), waist=(8, -20, 0), **lunge(1.2, 20))), C),
        (0.8, full(P((0.0, 17, -6.0), c2, lead_left(c2), root=(0, -95, 0), waist=(4, -20, 0), **lunge(0.6, 12))), C),
        (1.2, H(), C),
    ], S, extra=dict(FP_SAFE)))

    # -- skill 2: Reaper's Chain (flick at 0.38 -> circle + chain, yank at 0.75)
    free_l = (-35, 0, -12)
    out.append(Clip("animation.idex.reaper.reapers_chain", 1.4, "hold_on_last_frame", [
        (0.0, H(), C),
        (0.18, full(P((6.0, 26, 2.5), n((0.1, 0.55, 0.85)), (0, -0.85, 0.5), left=(-20, 0, -8), waist=(-8, 20, 0))), C),
        (0.3, full(P((6.0, 26, 2.5), n((0.15, 0.75, 0.65)), (0, -0.65, 0.75), left=(-20, 0, -8), waist=(-10, 25, 0))), C),
        (0.38, full(P((5.0, 21, -7.5), n((0, 0.05, -1)), (0, -1, 0), left=free_l, waist=(12, -10, 0), **lunge(1.0, 18))), C),
        (0.62, full(P((5.0, 21, -7.5), n((0, 0.05, -1)), (0, -1, 0), left=free_l, waist=(12, -10, 0), **lunge(1.0, 18))), L),
        (0.75, full(P((6.5, 20, 1.5), n((0.05, 0.5, -0.85)), (0, -0.85, -0.5), left=(-50, 0, -15), waist=(-14, 25, 0), rightLeg=(18, 0, 2), leftLeg=(-4, 0, -2))), C),
        (1.0, full(P((6.0, 19, 0.5), n((0.05, 0.55, -0.83)), (0, -0.83, -0.55), left=(-40, 0, -12), waist=(-8, 18, 0), rightLeg=(10, 0, 2))), C),
        (1.4, H(), C),
    ], S, extra=dict(FP_SAFE)))

    # -- skill 2b: chain finisher spin (shadow ring)
    s1 = n((0.0, 0.05, -1))
    out.append(Clip("animation.idex.reaper.chain_spin", 0.8, "hold_on_last_frame", [
        (0.0, H(), C),
        (0.12, full(P((4.0, 18, -6.5), s1, lead_right(s1), root=(0, 30, 0), waist=(10, 0, 0), **lunge(1.2, 16))), C),
        (0.3, full(P((4.0, 18, -6.5), s1, lead_right(s1), root=(0, 200, 0), waist=(10, 0, 0), **lunge(1.4, 16))), L),
        (0.45, full(P((4.0, 18, -6.5), s1, lead_right(s1), root=(0, 360, 0), waist=(10, 0, 0), **lunge(1.2, 16))), C),
        (0.8, full(hold(root=(0, 360, 0))), C),
    ], S, extra=dict(FP_SAFE)))

    # -- skill 3: Phantom Scythe (plant at 0.45, phantom rises 0.6 -> 1.6)
    up_shaft = n((0, 1, -0.06))
    out.append(Clip("animation.idex.reaper.phantom_scythe", 1.8, "hold_on_last_frame", [
        (0.0, H(), C),
        (0.25, full(P((2.5, 25.5, -6.0), up_shaft, (0, 0, -1), left_y=6, waist=(-6, 0, 0), root_p=(0, 0.5, 0))), C),
        (0.45, full(P((2.5, 14.0, -6.0), up_shaft, (0, 0, -1), left_y=19, waist=(22, 0, 0), **lunge(1.8, 20))), C),
        (0.75, full(P((2.5, 14.0, -6.0), up_shaft, (0, 0, -1), left_y=19, waist=(20, 0, 0), **lunge(1.6, 20))), L),
        (1.15, full(P((2.5, 14.5, -6.0), up_shaft, (0, 0, -1), left=(-110, 0, 35), waist=(6, 0, 0), **lunge(0.6, 10))), C),
        (1.45, full(P((2.5, 14.5, -6.0), up_shaft, (0, 0, -1), left=(-140, 0, 55), waist=(0, 0, 0))), C),
        (1.8, H(), C),
    ], S, extra=dict(FP_SAFE)))

    # -- skill 4: Blood Moon (raise, trace a circle with the tip 0.5 -> 1.5)
    keys = [(0.0, H(), C),
            (0.35, full(P((2.5, 29, -3), n((0, 1, -0.15)), (0, 0.15, -1), left_y=6, waist=(-12, 0, 0))), C)]
    for i, t in enumerate(np.linspace(0.5, 1.5, 7)):
        th = 2 * math.pi * i / 6
        sh = n((0.42 * math.sin(th), 1, -0.42 * math.cos(th) - 0.1))
        tang = np.array([math.cos(th), 0, math.sin(th)])
        keys.append((float(t), full(P((2.5, 29, -3), sh, tang, left_y=6, waist=(-12, 0, 0))), C))
    keys += [(1.8, full(P((2.5, 29.5, -3), n((0, 1, -0.1)), (0, 0.1, -1), left_y=6, waist=(-14, 0, 0))), C),
             (2.2, H(), C)]
    out.append(Clip("animation.idex.reaper.blood_moon", 2.2, "hold_on_last_frame", keys, S, extra=dict(FP_SAFE)))

    # -- skill 5: Abyssal Reap (one-hand slow spin, slam 1.75, auto lift, giant blade 3.4)
    ab = n((0.55, 0.02, -0.85))
    one = (-25, 0, -10)
    keys = [(0.0, H(), C),
            (0.2, full(P((8.0, 19, -3), ab, lead_right(ab), left=one)), C)]
    keys += [(float(t), full(P((8.0, 19, -3), ab, lead_right(ab), left=one, root=(0, 360 * (k + 1) / 5, 0))), L)
             for k, t in enumerate(np.linspace(0.35, 1.25, 5))]
    keys += [
        (1.5, full(P((3.0, 26, -5), up_shaft, (0, 0, -1), left_y=6, root=(0, 360, 0), waist=(-8, 0, 0), root_p=(0, 0.6, 0))), C),
        (1.75, full(P((3.0, 14.5, -5.5), up_shaft, (0, 0, -1), left_y=19, root=(0, 360, 0), waist=(22, 0, 0), **lunge(1.8, 22))), C),
        (2.2, full(P((3.0, 14.5, -5.5), up_shaft, (0, 0, -1), left_y=19, root=(0, 360, 0), waist=(20, 0, 0), **lunge(1.6, 22))), L),
        (2.8, full(P((3.0, 28.5, -2.5), n((0, 1, 0.25)), (0, -0.25, -1), left_y=6, root=(0, 360, 0), waist=(-14, 0, 0))), C),
        (3.25, full(P((3.0, 28.5, -2.5), n((0, 1, 0.3)), (0, -0.3, -1), left_y=6, root=(0, 360, 0), waist=(-16, 0, 0))), L),
        (3.45, full(P((3.5, 16.5, -6.5), n((0, -0.28, -0.96)), (0, -0.96, 0.28), root=(0, 360, 0), waist=(14, 0, 0), **lunge(1.2, 22))), C),
        (3.8, full(P((3.5, 16.5, -6.5), n((0, -0.3, -0.95)), (0, -0.95, 0.3), root=(0, 360, 0), waist=(12, 0, 0), **lunge(1.1, 20))), L),
        (4.2, full(hold(root=(0, 360, 0))), C),
    ]
    out.append(Clip("animation.idex.reaper.abyssal_reap", 4.2, "hold_on_last_frame", keys, S, extra=dict(FP_SAFE)))

    # -- skill 6: Eclipse Requiem (ultimate, 5 phases)
    hang = n((0.3, -0.12, 0.95))
    drag = n((0.35, -0.1, 0.93))
    flick = n((0.1, 0.85, -0.5))
    sp = n((0, 0.08, -1))
    keys = [
        (0.0, H(), C),
        # P1 awakening: stand still, scythe hanging at the side
        (0.4, full(P((6.8, 14.5, -0.5), hang, (0.3, 0.9, 0.2), left=(0, 0, -4))), C),
        (1.6, full(P((6.8, 14.3, -0.5), hang, (0.3, 0.9, 0.2), left=(0, 0, -4))), L),
        # P2 eclipse: swing up in front, then overhead
        (1.9, full(P((5.0, 21, -5.5), n((0.15, 0.55, -0.82)), (0, 0.82, 0.55), left_y=6)), C),
        (2.2, full(P((2.5, 29, -3), n((0, 1, -0.05)), (0, 0.05, -1), left_y=6, waist=(-14, 0, 0))), C),
        # P3 domain: hold high
        (3.0, full(P((2.5, 29.5, -3), n((0, 1, -0.05)), (0, 0.05, -1), left_y=6, waist=(-16, 0, 0))), C),
        (4.3, full(P((2.5, 29, -3), n((0, 1, -0.05)), (0, 0.05, -1), left_y=6, waist=(-12, 0, 0))), C),
        # P4 requiem: two-hand full spin, stop -> every phantom falls
        (4.55, full(P((4.0, 18, -6.5), sp, lead_right(sp), root=(0, 20, 0), waist=(10, 0, 0), **lunge(1.0, 14))), C),
        (4.85, full(P((4.0, 18, -6.5), sp, lead_right(sp), root=(0, 190, 0), waist=(10, 0, 0), **lunge(1.2, 16))), L),
        (5.15, full(P((4.0, 18, -6.5), sp, lead_right(sp), root=(0, 360, 0), waist=(12, 0, 0), **lunge(1.4, 18))), C),
        (5.5, full(P((4.0, 18, -6.5), sp, lead_right(sp), root=(0, 360, 0), waist=(10, 0, 0), **lunge(1.2, 16))), L),
        # P5 final crescent: crouch, drag along the ground, flick up
        (5.85, full(P((6.5, 15.0, 1.5), drag, (0.4, 0.85, 0.2), root=(0, 360, 0), waist=(26, 15, 0), **lunge(2.2, 30))), C),
        (6.4, full(P((5.5, 15.0, -2.0), n((0.3, -0.1, -0.95)), (0.2, 0.95, -0.1), root=(0, 360, 0), waist=(28, 5, 0), **lunge(2.2, 30))), C),
        (6.6, full(P((4.0, 27, -4.5), flick, (0, 0.5, 0.85), root=(0, 360, 0), waist=(-14, -10, 0), rightLeg=(-10, 0, 3), leftLeg=(10, 0, -3), root_p=(0, 0.6, 0))), C),
        (7.0, full(P((4.0, 27.5, -4.0), flick, (0, 0.5, 0.85), root=(0, 360, 0), waist=(-12, -10, 0))), L),
        (7.6, full(hold(root=(0, 360, 0))), C),
    ]
    out.append(Clip("animation.idex.reaper.eclipse_requiem", 7.6, "hold_on_last_frame", keys, S, extra=dict(FP_SAFE)))
    return out


# Moments the script syncs to (seconds into each clip) and where to sample blade trails.
EVENTS = {
    "attack1": {"hit": 0.2, "trail": (0.1, 0.36)},
    "attack2": {"hit": 0.2, "trail": (0.08, 0.34)},
    "attack3": {"hit": 0.42, "trail": (0.3, 0.46)},
    "crimson_crescent": {"release": 0.42, "trail": (0.25, 0.6)},
    "reapers_chain": {"circle": 0.36, "yank": 0.72, "trail": (0.3, 0.42)},
    "chain_spin": {"ring": 0.3, "trail": (0.1, 0.48)},
    "phantom_scythe": {"plant": 0.45, "trail": None},
    "blood_moon": {"circle": 0.5, "moon": 1.6, "trail": (0.5, 1.5)},
    "abyssal_reap": {"slam": 1.75, "lift": 2.8, "blade": 3.45, "trail": (0.2, 1.3)},
    "eclipse_requiem": {"spin": (4.55, 5.15), "fall": 5.25, "drag": (5.85, 6.4), "flick": 6.55,
                        "trail": [(4.55, 5.2), (5.85, 6.7)]},
}
