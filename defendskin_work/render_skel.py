"""Generic renderer for the character skeletons -> preview PNG.

Usage: python render_skel.py CONFIG SKELFILE ANIM TIME
CONFIG = battle | rest
"""
import io
import json
import math
import os
import struct
import sys

from PIL import Image

W = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, W)
from rest_pose import parse  # noqa: E402

MODS = r"d:\steam\steamapps\common\Slay the Spire 2\mods\DeepseekWhaleDefect.pck"

CONFIGS = {
    "battle": dict(
        png="res://.godot/imported/defect.png-d9a4219263a117f0ba83c83a65391b33.ctex",
        atlas="res://.godot/imported/defect.atlas-d4a29937acf4aaaf137b95ee851d8a50.spatlas",
        S=0.20, canvas=(560, 660), origin=(280, 600),
    ),
    "rest": dict(
        png="res://.godot/imported/restsite_defect.png-b1461c3f515adbce2780a4a5d8a9c408.ctex",
        atlas="res://.godot/imported/restsite_defect.atlas-d47514764581271cf35b4bbe66e2441c.spatlas",
        S=2.0, canvas=(620, 620), origin=(320, 560),
    ),
}


def load_pck(path):
    d = open(path, "rb").read()
    fb = struct.unpack_from("<Q", d, 0x18)[0]
    idx = struct.unpack_from("<Q", d, 0x20)[0]
    n = struct.unpack_from("<I", d, idx)[0]
    p = idx + 4
    e = {}
    for _ in range(n):
        pl = struct.unpack_from("<I", d, p)[0]; p += 4
        nm = d[p:p + pl].rstrip(b"\x00").decode(); p += pl
        off, sz = struct.unpack_from("<QQ", d, p); p += 16 + 16 + 4
        e[nm] = d[fb + off:fb + off + sz]
    return e


cfg = CONFIGS[sys.argv[1]]
skel = sys.argv[2]
anim_name = sys.argv[3]
t = float(sys.argv[4])

e = load_pck(MODS)
b = e[cfg["png"]]
page = Image.open(io.BytesIO(b[b.find(b"RIFF"):])).convert("RGBA")
atlas = json.loads(e[cfg["atlas"]].decode("utf-8"))["atlas_data"]
regions, cur = {}, None
for line in atlas.splitlines():
    if line.startswith("bounds:"):
        regions[cur] = tuple(int(v) for v in line[7:].split(","))
    elif ":" not in line and line.strip():
        cur = line.strip().split()[0]
page_imgs = {k: page.crop((x, y, x + w, y + h)) for k, (x, y, w, h) in regions.items()}

d = parse(skel)
bones = d["bones"]
anims = {a["name"]: a for a in d["anims"]}
anim_rot, anim_tr = {}, {}
for bn, typ, fr, _ in anims[anim_name]["bone_tl"]:
    if typ == 0:
        v = fr[0][1][0]
        for i in range(len(fr) - 1):
            if fr[i][0] <= t <= fr[i + 1][0]:
                t0, v0 = fr[i][0], fr[i][1][0]
                t1, v1 = fr[i + 1][0], fr[i + 1][1][0]
                v = v0 + (v1 - v0) * ((t - t0) / (t1 - t0))
                break
        anim_rot[bn] = v
    elif typ == 1:
        anim_tr[bn] = tuple(fr[0][1])

cache = {}


def world(i):
    if i in cache:
        return cache[i]
    bo = bones[i]
    px = py = pr = 0.0
    if bo["parent"] is not None:
        px, py, pr = world(bo["parent"])
    lx, ly = bo["x"], bo["y"]
    if bo["name"] in anim_tr:
        lx += anim_tr[bo["name"]][0]
        ly += anim_tr[bo["name"]][1]
    rad = math.radians(pr)
    wx = px + lx * math.cos(rad) - ly * math.sin(rad)
    wy = py + lx * math.sin(rad) + ly * math.cos(rad)
    cache[i] = (wx, wy, pr + anim_rot.get(bo["name"], bo["rot"]))
    return cache[i]


S = cfg["S"]
CW, CH = cfg["canvas"]
OX, OY = cfg["origin"]
canvas = Image.new("RGBA", (CW, CH), (34, 40, 56, 255))
skin_by_slot = {si: atts for si, atts in d["skin"]}
for si, s in enumerate(d["slots"]):
    atts = skin_by_slot.get(si)
    if not atts:
        continue
    a = atts[0]
    if a["name"] not in page_imgs:
        continue
    img = page_imgs[a["name"]].resize(
        (max(1, round(a["size"][0] * S)), max(1, round(a["size"][1] * S))), Image.LANCZOS)
    wx, wy, wr = world(s["bone"])
    offx, offy = a["off"]
    r = math.radians(wr)
    cx = wx + offx * math.cos(r) - offy * math.sin(r)
    cy = wy + offx * math.sin(r) + offy * math.cos(r)
    rot_img = img.rotate(wr, resample=Image.BICUBIC, expand=True)
    canvas.alpha_composite(rot_img, (round(OX + cx * S - rot_img.width / 2),
                                     round(OY - cy * S - rot_img.height / 2)))
out = os.path.join(W, f"mock_{sys.argv[1]}_{anim_name}_{t:g}.png")
canvas.save(out)
print("saved", out, "anim", anim_name, "t", t)
print("head bone world:", world([i for i, b in enumerate(bones) if b["name"] == "head"][0]))
print("head rot:", round(anim_rot.get("head", 0.0), 2))