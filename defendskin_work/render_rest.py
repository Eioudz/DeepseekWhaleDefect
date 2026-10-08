"""Mini Spine renderer for the restsite skeleton -> preview PNG.

Usage: python render_rest.py SKEL [ANIM] [TIME]
"""
import io
import json
import os
import struct
import sys

from PIL import Image

W = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, W)
from rest_pose import parse

MODS = r"d:\steam\steamapps\common\Slay the Spire 2\mods\DeepseekWhaleDefect.pck"
REST_PNG = "res://.godot/imported/restsite_defect.png-b1461c3f515adbce2780a4a5d8a9c408.ctex"
REST_ATLAS = "res://.godot/imported/restsite_defect.atlas-d47514764581271cf35b4bbe66e2441c.spatlas"


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


e = load_pck(MODS)
b = e[REST_PNG]
page = Image.open(io.BytesIO(b[b.find(b"RIFF"):])).convert("RGBA")
atlas = json.loads(e[REST_ATLAS].decode("utf-8"))["atlas_data"]
regions = {}
cur = None
for line in atlas.splitlines():
    if line.startswith("bounds:"):
        regions[cur] = tuple(int(v) for v in line[7:].split(","))
    elif ":" not in line and line.strip():
        cur = line.strip().split()[0]
page_imgs = {k: page.crop((x, y, x + w, y + h)) for k, (x, y, w, h) in regions.items()}

skel = sys.argv[1] if len(sys.argv) > 1 else os.path.join(W, "restsite_defect_rice.skel")
d = parse(skel)
bones = d["bones"]
anims = {a["name"]: a for a in d["anims"]}
anim_name = sys.argv[2] if len(sys.argv) > 2 else "glory_loop"
t = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0

# animated values at time t
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


def world(i, cache={}):
    if i in cache:
        return cache[i]
    bo = bones[i]
    if bo["parent"] is None:
        px = py = pr = 0.0
    else:
        px, py, pr = world(bo["parent"])
    lx, ly = bo["x"], bo["y"]
    if bo["name"] in anim_tr:
        lx += anim_tr[bo["name"]][0]
        ly += anim_tr[bo["name"]][1]
    rad = pr * 3.141592653589793 / 180.0
    wx = px + lx * __import__("math").cos(rad) - ly * __import__("math").sin(rad)
    wy = py + lx * __import__("math").sin(rad) + ly * __import__("math").cos(rad)
    wr = pr + (anim_rot.get(bo["name"], bo["rot"]))
    cache[i] = (wx, wy, wr)
    return cache[i]


S = 2.0
CW, CH = 620, 620
OX, OY = 320.0, 560.0
# passing a canvas height / origin lets the feet below the default frame show
if len(sys.argv) > 5:
    CH = int(sys.argv[5])
if len(sys.argv) > 4:
    OY = float(sys.argv[4])
canvas = Image.new("RGBA", (CW, CH), (34, 40, 56, 255))
import math

skin_by_slot = {si: atts for si, atts in d["skin"]}
for si, s in enumerate(d["slots"]):
    atts = skin_by_slot.get(si)
    if not atts:
        continue
    a = atts[0]
    if a["name"] not in page_imgs:
        continue
    img = page_imgs[a["name"]]
    tw, th = a["size"][0] * S, a["size"][1] * S
    img = img.resize((max(1, round(tw)), max(1, round(th))), Image.LANCZOS)
    wx, wy, wr = world(s["bone"])
    rad = wrap = None
    offx, offy = a["off"]
    r = math.radians(wr)
    cx = wx + offx * math.cos(r) - offy * math.sin(r)
    cy = wy + offx * math.sin(r) + offy * math.cos(r)
    rot_img = img.rotate(wr, resample=Image.BICUBIC, expand=True)
    px = OX + cx * S - rot_img.width / 2
    py = OY - cy * S - rot_img.height / 2
    canvas.alpha_composite(rot_img, (round(px), round(py)))
canvas.save(os.path.join(W, "mock_restsite.png"))
print("saved mock_restsite.png", "anim", anim_name, "t", t)