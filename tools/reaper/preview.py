"""Pose previews: player boxes + the scythe mesh, posed with rig.fk."""
import numpy as np

import render
import rig

# Blockbench-space boxes of the vanilla player (from, to), per bone
BOXES = {
    "body": ((-4, 12, -2), (4, 24, 2), (60, 70, 120)),
    "head": ((-4, 24, -4), (4, 32, 4), (205, 170, 135)),
    "rightArm": ((4, 12, -2), (8, 24, 2), (150, 70, 70)),
    "leftArm": ((-8, 12, -2), (-4, 24, 2), (75, 85, 140)),
    "rightLeg": ((-0.1, 0, -2), (3.9, 12, 2), (45, 45, 60)),
    "leftLeg": ((-3.9, 0, -2), (0.1, 12, 2), (45, 45, 60)),
}
FACE = [((0, 2, 3, 1), (-1, 0, 0)), ((4, 5, 7, 6), (1, 0, 0)), ((0, 1, 5, 4), (0, -1, 0)),
        ((2, 6, 7, 3), (0, 1, 0)), ((0, 4, 6, 2), (0, 0, -1)), ((1, 3, 7, 5), (0, 0, 1))]


def box_item(a, b, color, M):
    a, b = np.array(a, float), np.array(b, float)
    c = np.array([[a[0] if i & 4 == 0 else b[0], a[1] if i & 2 == 0 else b[1], a[2] if i & 1 == 0 else b[2]]
                  for i in range(8)])
    pos, nrm, polys = [], [], []
    for idx, n in FACE:
        base = len(pos)
        for i in idx:
            pos.append(c[i])
            nrm.append(n)
        polys.append([base, base + 1, base + 2, base + 3])
    pos = rig.apply(M, np.array(pos))
    nrm = np.array(nrm, float) @ M[:3, :3].T
    return {"pos": pos, "nrm": nrm, "polys": polys, "color": color}


def posed_items(parts, tex, scythe, rot, pos, ground=True):
    W = rig.fk(rot, pos)
    items = [box_item(a, b, col, W[bone]) for bone, (a, b, col) in BOXES.items()]
    for ex in (-2.5, 1.5):     # eyes on the face (-z) so the facing is readable
        items.append(box_item((ex, 28, -4.3), (ex + 1, 29, -4.0), (20, 20, 20), W["head"]))
    Mi = W["rightItem"]
    for p in parts.values():
        P = rig.apply(Mi, np.array([rig.HAND["rightArm"]]) + scythe.local(p["pos"]))
        Nn = (p["nrm"] @ rig.N_MOUNT.T) @ Mi[:3, :3].T
        items.append({"pos": P, "nrm": Nn, "uv": p["uv"], "polys": p["polys"], "tex": tex})
    if ground:
        g = 26
        items.append({"pos": np.array([[-g, 0, -g], [g, 0, -g], [g, 0, g], [-g, 0, g]], float),
                      "nrm": np.tile([0, 1.0, 0], (4, 1)), "polys": [[0, 1, 2, 3]], "color": (200, 196, 188)})
    return items


def clip_strip(clip, parts, tex, scythe, times, yaw=200, pitch=12, size=(300, 380), scale=5.2):
    imgs = []
    for t in times:
        rot, pos = clip.sample(t)
        items = posed_items(parts, tex, scythe, rot, pos)
        imgs.append(render.render(items, yaw, pitch, size, scale=scale, centre=(0, 20, 0), ss=1))
    return render.sheet(imgs)
