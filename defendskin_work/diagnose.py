"""Diagnose (a) head region content sizes and (b) which bones the restsite
animations keyframe."""
import io
import os
import struct
import sys

from PIL import Image

W = os.path.dirname(os.path.abspath(__file__))
SKEL = os.path.join(W, "restsite_defect.skel")
MODS = r"d:\steam\steamapps\common\Slay the Spire 2\mods\DeepseekWhaleDefect.pck"
WS = r"c:\Users\12415\Documents\trae_projects\slay\whale_workspace\content\DeepseekWhaleDefect.pck"
BATTLE = "res://.godot/imported/defect.png-d9a4219263a117f0ba83c83a65391b33.ctex"


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


def page(e, key):
    b = e[key]
    return Image.open(io.BytesIO(b[b.find(b"RIFF"):])).convert("RGBA")


def bbox(img):
    b = img.getbbox()
    if not b:
        return None, 0
    x0, y0, x1, y1 = b
    return (x0, y0, x1 - x0, y1 - y0), (x1 - x0) * (y1 - y0)


RECTS = {"head": (0, 0), "hit_head": (0, 280), "low_head": (0, 560),
         "attack_head": (0, 1396), "cast_head": (0, 1676)}
m = page(load_pck(MODS), BATTLE)
w = page(load_pck(WS), BATTLE)
print("=== head region content bbox (x,y,w,h) within 365x278 ===")
for name, (x, y) in RECTS.items():
    bo, ao = bbox(w.crop((x, y, x + 365, y + 278)))
    bc, ac = bbox(m.crop((x, y, x + 365, y + 278)))
    print(f"{name:12s} workshop={bo} area={ao:6d} | current={bc} area={ac:6d}")

# --- restsite animation timelines ---
sys.path.insert(0, os.path.dirname(W))
from parse_skel2 import R


def dump_anim():
    r = R(open(SKEL, "rb").read())
    r.p += 8
    r.string()
    for _ in range(4):
        r.f32()
    r.f32(); r.byte()
    sp_n = r.varint()
    setup = [r.string() for _ in range(sp_n)]
    bn = r.varint()
    bones = []
    for i in range(bn):
        nm = r.string()
        if i > 0:
            r.varint()
        for _ in range(8):
            r.f32()
        r.varint(); r.byte()
        bones.append(nm)
    sn = r.varint()
    slots = []
    for _ in range(sn):
        nm = r.string()
        r.varint()
        for _ in range(8):
            r.byte()
        r.varint(); r.varint()
        slots.append(nm)
    for _ in range(4):
        assert r.varint() == 0

    def skin():
        n = r.varint()
        for _ in range(n):
            r.varint(); a = r.varint()
            for _ in range(a):
                r.varint(); f = r.byte()
                if f & 0x04: r.f32()
                r.f32(); r.f32(); r.f32(); r.f32(); r.f32(); r.f32()
                if f & 0x01: r.string()
                if f & 0x08: [r.byte() for _ in range(4)]
                if f & 0x10: [r.f32(), r.f32(), r.varint(), r.varint()]
    skin()
    ns = r.varint()
    for _ in range(ns):
        r.string(); skin()
    ev = r.varint()
    for _ in range(ev):
        r.string(); r.zigzag(); r.f32(); r.string(); r.string()
    print("bones:", bones)
    print("slots:", slots)
    an = r.varint()
    print("=== animations ===")
    for _ in range(an):
        name = r.string()
        total = r.varint()
        sg = r.varint()
        stl = []
        for _ in range(sg):
            si = r.varint(); tn = r.varint()
            for _ in range(tn):
                t = r.byte()
                if t == 0:
                    fn = r.varint()
                    for _ in range(fn):
                        r.f32(); r.varint()
                elif t == 1:
                    fn = r.varint(); bn2 = r.varint()
                    for _ in range(fn):
                        r.f32()
                        for _ in range(4): r.byte()
                    for _ in range(bn2):
                        for _ in range(6): r.f32()
                stl.append((slots[si], t, fn if t in (0, 1) else None))
        bg = r.varint()
        btl = []
        for _ in range(bg):
            bi = r.varint(); tn = r.varint()
            for _ in range(tn):
                t = r.byte(); fn = r.varint(); bnz = r.varint()
                vals = {0: 1, 1: 2, 2: 2, 3: 2}[t]
                for fi in range(fn):
                    r.f32()
                    for _ in range(vals): r.f32()
                    if fi > 0: r.byte()
                for _ in range(bnz):
                    for _ in range(vals):
                        for _ in range(6): r.f32()
                btl.append((bones[bi], t, fn))
        for _ in range(6):
            assert r.varint() == 0, "unhandled timeline"
        evn = r.varint()
        for _ in range(evn):
            r.f32(); r.varint(); r.zigzag(); r.f32(); r.string()
        print(f"anim {name!r} total_tl={total} slot_tls={stl} bone_tls={btl}")
    print("trailing:", len(r.d) - r.p)


dump_anim()