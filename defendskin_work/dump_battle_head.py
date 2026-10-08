"""Dump the battle skeleton's head bone: setup, attachment offset, and every
animation's head rotation keyframes."""
import os
import struct
import sys

W = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, W)
from rest_pose import parse  # noqa: E402

MODS = r"d:\steam\steamapps\common\Slay the Spire 2\mods\DeepseekWhaleDefect.pck"
BATTLE_SKEL = "res://.godot/imported/defect.skel-5dba1374f717ab634fbb5c1941158597.spskel"


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


sk = load_pck(MODS)[BATTLE_SKEL]
tmp = os.path.join(W, "_battle.skel")
open(tmp, "wb").write(sk)
d = parse(tmp)

print("bones:")
for i, b in enumerate(d["bones"]):
    print(f"  [{i}] {b['name']:14s} parent={b['parent']} rot={b['rot']:7.2f} pos=({b['x']:7.1f},{b['y']:7.1f})")
print("slots:", [(i, s["name"], d["bones"][s["bone"]]["name"]) for i, s in enumerate(d["slots"])])
print("skin head/attachment records:")
for si, atts in d["skin"]:
    if d["slots"][si]["name"] in ("head", "bod", "hair_l", "hair_r"):
        for a in atts:
            print(f"  slot[{si}] {d['slots'][si]['name']:8s} att={a['name']:12s} off={a['off']} size={a['size']}")

print("\nhead rotation keyframes per animation:")
for a in d["anims"]:
    for bn, t, fr, bnz in a["bone_tl"]:
        if bn in ("head", "hair_l", "hair_r"):
            vals = [(round(v[0], 2), round(v[1][0], 2)) if t == 0 else (round(v[0], 2), [round(x, 2) for x in v[1]]) for v in fr]
            print(f"  {a['name']:22s} {bn:12s} type={t} {vals}")

print("\nanimation names:", [a["name"] for a in d["anims"]])
for a in d["anims"]:
    print(f"  {a['name']:22s} bones={[bt[0] for bt in a['bone_tl']]}")

for a in d["anims"]:
    if a["name"] not in ("idle_loop", "relaxed_loop"):
        continue
    print(f"\n== {a['name']} full timelines ==")
    for bn, t, fr, bnz in a["bone_tl"]:
        vals = [(round(v[0], 2), [round(x, 2) for x in v[1]]) for v in fr]
        print(f"  {bn:14s} type={t} {vals}")