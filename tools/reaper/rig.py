"""Player rig + scythe: forward kinematics, arm IK and keyframe export.

Everything here works in Blockbench space (x = player's right, y up, -z = facing).
Bedrock animation values relate to it like Blockbench's importer does:
  rotation [rx, ry, rz]  ->  R = Rz(rz) . Ry(-ry) . Rx(-rx)
  position [px, py, pz]  ->  t = (-px, py, pz)
Bone pivots are the vanilla `geometry.humanoid.custom` ones with x mirrored.

A pose is authored as intent, not angles:
  hand     right-hand position (root frame, px)
  shaft    direction pommel -> head (root frame)
  blade    direction the blade sticks out from the head
  left     True -> left hand solved onto the shaft; or explicit left arm angles
plus optional root / waist / leg / head angles. `solve()` turns that into bone
rotations (bedrock values) via IK.
"""
import math

import numpy as np
from scipy.optimize import minimize

# name: (parent, pivot in Blockbench space)
BONES = {
    "root": (None, (0, 0, 0)),
    "waist": ("root", (0, 12, 0)),
    "body": ("waist", (0, 24, 0)),
    "head": ("body", (0, 24, 0)),
    "rightArm": ("body", (5, 22, 0)),
    "rightItem": ("rightArm", (6, 15, 1)),
    "leftArm": ("body", (-5, 22, 0)),
    "leftItem": ("leftArm", (-6, 15, 1)),
    "rightLeg": ("root", (1.9, 12, 0)),
    "leftLeg": ("root", (-1.9, 12, 0)),
}
ORDER = list(BONES)
PLAYER_SCALE = 0.9375          # player.entity.json "scale"
HAND = {"rightArm": np.array([6.0, 15, 1]), "leftArm": np.array([-6.0, 15, 1])}

# Scythe neutral mount on rightItem: model +y (shaft) -> forward (-z), model -x (blade side) -> up.
# columns = images of the model x, y, z axes
N_MOUNT = np.c_[[0, -1, 0], [0, 0, -1], [1, 0, 0]]


def Rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def Rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def rot_bedrock(r):
    rx, ry, rz = (math.radians(v) for v in r)
    return Rz(rz) @ Ry(-ry) @ Rx(-rx)


def euler_bedrock(R, near=None):
    """Inverse of rot_bedrock; unwrapped towards `near` (bedrock values)."""
    b = math.asin(max(-1.0, min(1.0, -R[2, 0])))
    a = math.atan2(R[2, 1], R[2, 2])
    c = math.atan2(R[1, 0], R[0, 0])
    out = np.array([-math.degrees(a), -math.degrees(b), math.degrees(c)])
    if near is not None:
        out = near + (out - near + 180) % 360 - 180
    return out


def mat4(R=np.eye(3), t=(0, 0, 0)):
    M = np.eye(4)
    M[:3, :3] = R
    M[:3, 3] = t
    return M


def fk(rot, pos=None):
    """rot/pos: {bone: bedrock values}. Returns {bone: 4x4 world matrix} (model space)."""
    pos = pos or {}
    W = {}
    for name in ORDER:
        parent, piv = BONES[name]
        piv = np.array(piv, float)
        R = rot_bedrock(rot.get(name, (0, 0, 0)))
        p = pos.get(name, (0, 0, 0))
        t = np.array([-p[0], p[1], p[2]], float)
        local = mat4(np.eye(3), t + piv) @ mat4(R) @ mat4(np.eye(3), -piv)
        W[name] = (W[parent] @ local) if parent else local
    return W


def apply(M, p):
    p = np.atleast_2d(p)
    return p @ M[:3, :3].T + M[:3, 3]


# ---------------------------------------------------------------- scythe
class Scythe:
    """Scythe geometry facts the poses need (model frame of mesh.py)."""

    def __init__(self, sil, grip_y=13.0, tip=None):
        self.grip_y = grip_y
        ys = np.arange(4.0, 34.0, 0.5)
        xs = []
        for y in ys:
            px, py = sil.to_img(np.linspace(-4, 4, 161), np.full(161, y))
            inside = sil.sample(sil.mask, np.linspace(-4, 4, 161), np.full(161, y)) > 0.5
            xs.append(np.linspace(-4, 4, 161)[inside].mean() if inside.any() else np.nan)
        xs = np.array(xs)
        ok = ~np.isnan(xs)
        self.poly = np.polyfit(ys[ok], xs[ok], 3)
        self.grip = self.shaft_point(grip_y)
        self.tip = np.array(tip if tip is not None else (-14.6, 22.6, 0.0))

    def shaft_point(self, y):
        return np.array([np.polyval(self.poly, y), y, 0.0])

    def local(self, p):
        """Model-frame point -> rightItem-local offset from the grip (neutral mount)."""
        return (np.atleast_2d(p) - self.grip) @ N_MOUNT.T


def frame(shaft, blade):
    """Rotation mapping scythe model axes to world: y -> shaft, -x -> blade."""
    d = np.asarray(shaft, float)
    d /= np.linalg.norm(d)
    b = np.asarray(blade, float)
    b = b - d * (b @ d)
    b /= np.linalg.norm(b)
    ex = -b
    ez = np.cross(ex, d)
    return np.c_[ex, d, ez]


def aim(W_parent, bone, target, seed=(0.0, 0.0, 0.0), twist=0.0):
    """Bedrock rotation of an arm so its hand point points at target (world)."""
    piv = np.array(BONES[bone][1], float)
    h0 = HAND[bone] - piv
    Rp = W_parent[:3, :3]
    sh = apply(W_parent, piv)[0]
    want = Rp.T @ (np.asarray(target) - sh)
    want /= np.linalg.norm(want)

    def cost(v):
        d = rot_bedrock((v[0], twist, v[1])) @ h0
        # among equally good aims prefer the one closest to the previous key (continuity)
        return -(d @ want) / np.linalg.norm(d) + 4e-6 * (abs(v[0] - seed[0]) + abs(v[1] - seed[2]))

    best = None
    for s0 in [(seed[0], seed[2]), (seed[0] + 25, seed[2]), (seed[0] - 25, seed[2]), (seed[0], seed[2] + 25), (seed[0], seed[2] - 25), (-90, 0), (-45, 30), (-45, -30), (0, 60), (0, -60)]:
        r = minimize(cost, s0, method="Nelder-Mead", options={"xatol": 1e-4, "fatol": 1e-9, "maxiter": 600})
        if best is None or r.fun < best.fun - 1e-9:
            best = r
    return np.array([best.x[0], twist, best.x[1]])


REACH = float(np.linalg.norm(HAND["rightArm"] - np.array(BONES["rightArm"][1])))


def two_hand_target(W, scythe, want, shaft, left_y):
    """Right-hand position closest to `want` such that the left hand, `left_y - grip`
    further along the shaft, is also within reach. Grip spacing may slide if needed."""
    sR = apply(W["body"], np.array(BONES["rightArm"][1], float))[0]
    sL = apply(W["body"], np.array(BONES["leftArm"][1], float))[0]
    d = np.asarray(shaft, float) / np.linalg.norm(shaft)
    want_d = left_y - scythe.grip_y
    cands = [x for x in np.r_[np.arange(-11, -2.4, 0.5), np.arange(2.5, 20.5, 0.5)]]
    cands.sort(key=lambda x: abs(x - want_d))
    rho = REACH
    for dl in cands:
        c = sL - d * dl
        dist = np.linalg.norm(c - sR)
        if dist > 2 * rho - 0.1 or dist < 1e-6:
            continue
        a = (c - sR) / dist
        m = (sR + c) / 2
        rc = math.sqrt(max(rho * rho - (dist / 2) ** 2, 0))
        v = want - m
        v = v - a * (v @ a)
        if np.linalg.norm(v) < 1e-6:
            v = np.cross(a, [0, 1, 0])
        return m + rc * v / np.linalg.norm(v)
    return want


def solve(scythe, pose, prev=None):
    """Turn an intent pose into bedrock rotations/positions for every keyed bone."""
    rot = {k: np.array(v, float) for k, v in pose.get("rot", {}).items()}
    pos = {k: np.array(v, float) for k, v in pose.get("pos", {}).items()}
    prev = prev or {}
    # body first (root spin is applied on top: hand/shaft are given in the root frame)
    root_rot = rot.get("root", np.zeros(3))
    base = dict(rot)
    base["root"] = np.zeros(3)
    W = fk(base, {k: v for k, v in pos.items() if k != "root"})
    # two-handed: move the grip pair to the nearest spot both arms can reach
    hand = np.array(pose["hand"], float) if "hand" in pose else None
    if hand is not None and pose.get("left") is True:
        hand = two_hand_target(W, scythe, hand, pose["shaft"], pose.get("left_y", scythe.grip_y + 9))
    # right arm -> hand target
    if hand is not None:
        rot["rightArm"] = aim(W["body"], "rightArm", hand,
                              seed=prev.get("rightArm", (-40, 0, 0)), twist=pose.get("twist", 0.0))
        base["rightArm"] = rot["rightArm"]
        W = fk(base, {k: v for k, v in pos.items() if k != "root"})
    # rightItem -> scythe orientation
    if "shaft" in pose:
        D = frame(pose["shaft"], pose["blade"])
        Rarm = W["rightArm"][:3, :3]
        local = Rarm.T @ D @ N_MOUNT.T
        rot["rightItem"] = euler_bedrock(local, prev.get("rightItem"))
        base["rightItem"] = rot["rightItem"]
        W = fk(base, {k: v for k, v in pos.items() if k != "root"})
    gap = 0.0
    if pose.get("left") is True:
        Mi = W["rightItem"]
        ys = np.r_[np.linspace(1.5, scythe.grip_y - 2.5, 30), np.linspace(scythe.grip_y + 2.5, scythe.grip_y + 22, 80)]
        pts = apply(Mi, np.array([HAND["rightArm"]]) + scythe.local([scythe.shaft_point(y) for y in ys]))
        sh = apply(W["body"], np.array(BONES["leftArm"][1], float))[0]
        dist = np.linalg.norm(pts - sh, axis=1)
        want_y = pose.get("left_y", scythe.grip_y + 9)
        cand = np.where(np.abs(dist - REACH) < 0.35)[0]
        if len(cand):
            i = cand[np.argmin(np.abs(ys[cand] - want_y))]
        else:
            i = int(np.argmin(np.abs(dist - REACH)))
        gap = abs(dist[i] - REACH)
        rot["leftArm"] = aim(W["body"], "leftArm", pts[i], seed=prev.get("leftArm", (-40, 0, 0)))
    if "root" in pose.get("rot", {}):
        rot["root"] = root_rot
    for k in ("rightArm", "leftArm", "rightItem"):
        if k in rot and k in prev:
            rot[k] = prev[k] + (rot[k] - prev[k] + 180) % 360 - 180
    return {"rot": rot, "pos": pos, "gap": gap}


# ---------------------------------------------------------------- animation clips
class Clip:
    """Keyframed animation built from intent poses.

    keys: list of (time, pose, interp) with interp 'catmullrom' or 'linear'.
    Bones keyed in any pose are keyed in all poses (zeros where unspecified),
    so overriding animations never leave a bone half-defined.
    """

    def __init__(self, name, length, loop, keys, scythe, override=True, extra=None, subdiv=2):
        self.name, self.length, self.loop = name, length, loop
        self.override = override
        self.extra = extra or {}
        keys = expand(keys, subdiv)
        self.keys = []
        prev = {}
        self.gaps = []
        for t, pose, interp in keys:
            s = solve(scythe, pose, prev)
            prev = {k: v for k, v in s["rot"].items()}
            self.keys.append((t, s, interp))
            self.gaps.append((t, s["gap"]))
        self.rot_bones = sorted({b for _, s, _ in self.keys for b in s["rot"]}, key=ORDER.index)
        self.pos_bones = sorted({b for _, s, _ in self.keys for b in s["pos"]}, key=ORDER.index)

    def channel(self, kind, bone):
        out = []
        for t, s, interp in self.keys:
            v = s[kind].get(bone, np.zeros(3))
            out.append((t, np.array(v, float), interp))
        return out

    def sample(self, t):
        rot = {b: interp(self.channel("rot", b), t) for b in self.rot_bones}
        pos = {b: interp(self.channel("pos", b), t) for b in self.pos_bones}
        return rot, pos

    def bedrock(self):
        bones = {}
        for b in self.rot_bones + [p for p in self.pos_bones if p not in self.rot_bones]:
            entry = {}
            for kind, key in (("rot", "rotation"), ("pos", "position")):
                if (kind == "rot" and b in self.rot_bones) or (kind == "pos" and b in self.pos_bones):
                    ch = {}
                    for t, v, it in self.channel(kind, b):
                        val = [round(float(x), 3) for x in v]
                        ch[fmt_t(t)] = {"post": val, "lerp_mode": it} if it == "catmullrom" else val
                    entry[key] = ch
            bones[b] = entry
        out = {}
        out["loop"] = self.loop
        out["animation_length"] = self.length
        if self.override:
            out["override_previous_animation"] = True
        out.update(self.extra)
        out["bones"] = bones
        return out


def _slerp(a, b, u):
    a = np.asarray(a, float) / np.linalg.norm(a)
    b = np.asarray(b, float) / np.linalg.norm(b)
    om = math.acos(max(-1.0, min(1.0, float(a @ b))))
    if om < 1e-4:
        return a
    if om > math.pi - 1e-3:            # opposite: go round via an orthogonal axis
        o = np.cross(a, [0, 1, 0])
        if np.linalg.norm(o) < 1e-6:
            o = np.cross(a, [1, 0, 0])
        o /= np.linalg.norm(o)
        return a * math.cos(math.pi * u) + o * math.sin(math.pi * u)
    return (math.sin((1 - u) * om) * a + math.sin(u * om) * b) / math.sin(om)


def _mix(pa, pb, u):
    """Intent pose between pa and pb (directions slerped, positions/angles lerped)."""
    out = {"rot": {}, "pos": {}}
    for k in ("hand",):
        if k in pa and k in pb:
            out[k] = tuple(np.asarray(pa[k], float) * (1 - u) + np.asarray(pb[k], float) * u)
    if "shaft" in pa and "shaft" in pb:
        out["shaft"] = _slerp(pa["shaft"], pb["shaft"], u)
        out["blade"] = _slerp(pa["blade"], pb["blade"], u)
    for k in ("left_y", "twist"):
        if k in pa or k in pb:
            va, vb = pa.get(k, pb.get(k)), pb.get(k, pa.get(k))
            out[k] = va * (1 - u) + vb * u
    la, lb = pa.get("left"), pb.get("left")
    out["left"] = True if (la is True and lb is True) else False
    for kind in ("rot", "pos"):
        for b in set(pa[kind]) | set(pb[kind]):
            va = np.asarray(pa[kind].get(b, (0, 0, 0)), float)
            vb = np.asarray(pb[kind].get(b, (0, 0, 0)), float)
            out[kind][b] = tuple(va * (1 - u) + vb * u)
    if out["left"] is False and "leftArm" not in out["rot"]:
        # one side IK, other explicit: blend towards the explicit arm
        src = pa if la is not True else pb
        out["rot"]["leftArm"] = tuple(src["rot"].get("leftArm", (0, 0, 0)))
        out["left"] = True if u < 0.5 and la is True or u >= 0.5 and lb is True else False
        if out["left"]:
            del out["rot"]["leftArm"]
    return out


def expand(keys, n):
    """Insert n solved-from-intent in-betweens between keys, so per-axis Euler
    interpolation follows the intended arc instead of cutting corners."""
    if n <= 0:
        return keys
    out = []
    for i, (t, pose, it) in enumerate(keys):
        out.append((t, pose, it))
        if i + 1 < len(keys):
            t2, pose2, it2 = keys[i + 1]
            if it == "linear" and it2 == "linear":
                continue
            if t2 - t < 0.06 * (n + 1):
                continue
            for k in range(1, n + 1):
                u = k / (n + 1)
                out.append((t + (t2 - t) * u, _mix(pose, pose2, u), "catmullrom"))
    return out


def fmt_t(t):
    s = f"{t:.4f}".rstrip("0").rstrip(".")
    return s if "." in s else s + ".0"


def interp(ch, t):
    """Bedrock-style per-channel interpolation (linear / catmull-rom)."""
    times = [c[0] for c in ch]
    if t <= times[0]:
        return ch[0][1]
    if t >= times[-1]:
        return ch[-1][1]
    i = max(j for j in range(len(times)) if times[j] <= t)
    t0, v0, m0 = ch[i]
    t1, v1, m1 = ch[i + 1]
    u = (t - t0) / (t1 - t0)
    if m0 == "catmullrom" or m1 == "catmullrom":
        vp = ch[i - 1][1] if i > 0 else v0
        vn = ch[i + 2][1] if i + 2 < len(ch) else v1
        u2, u3 = u * u, u * u * u
        return 0.5 * ((2 * v0) + (-vp + v1) * u + (2 * vp - 5 * v0 + 4 * v1 - vn) * u2 + (-vp + 3 * v0 - 3 * v1 + vn) * u3)
    return v0 + (v1 - v0) * u


def world_of(clip, t, scythe, pts):
    """Model-space positions of scythe model points at time t (root spin included)."""
    rot, pos = clip.sample(t)
    W = fk(rot, pos)
    return apply(W["rightItem"], np.array([HAND["rightArm"]]) + scythe.local(pts))


def to_world_offset(p_model):
    """Model px (Blockbench space, facing -z) -> blocks relative to the player feet,
    in the player's local frame: x = right, y = up, z = forward."""
    p = np.atleast_2d(p_model) / 16.0 * PLAYER_SCALE
    return np.c_[p[:, 0], p[:, 1], -p[:, 2]]
