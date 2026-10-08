"""Revert cast_head to the original serious face + add a rice-hugging pose.

1. cast_head regions (battle+shop pages) restored from the pristine .bak pck.
2. fan22.png (rice bowl) -> new `rice` region in the restsite atlas page at
   (366,0,144,105); atlas text gains the region BEFORE the last entry plus a
   sacrificial dummy at the end (game atlas parser drops the last entry).
3. restsite_defect.skel: appends string "rice" (index 11, no existing ref
   shifts), slot "rice" on torso (index 10, no slot-index shifts), and one
   default-skin record; animation bytes copied verbatim.
"""
import io
import json
import os
import struct
import sys
from collections import deque

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pcktool

W = os.path.dirname(os.path.abspath(__file__))
SRC_PCK = r"d:\steam\steamapps\common\Slay the Spire 2\mods\DeepseekWhaleDefect.pck"
BAK_PCK = r"c:\Users\12415\Documents\trae_projects\slay\whale_workspace\content\DeepseekWhaleDefect.pck"  # workshop build: has the original pipeline cast_head
OUT_PCK = os.path.join(W, "DeepseekWhaleDefect.pck.new")
RICE_ART = r"d:\12415\Desktop\fan22.png"

BATTLE = "res://.godot/imported/defect.png-d9a4219263a117f0ba83c83a65391b33.ctex"
SHOP = "res://.godot/imported/defect_shop.png-7cd1b216490239388e248fe3de753032.ctex"
REST_PNG = "res://.godot/imported/restsite_defect.png-b1461c3f515adbce2780a4a5d8a9c408.ctex"
REST_ATLAS = "res://.godot/imported/restsite_defect.atlas-d47514764581271cf35b4bbe66e2441c.spatlas"
REST_SKEL = "res://.godot/imported/restsite_defect.skel-ff0d5434498d809964bf95b0eb025379.spskel"

CAST_RECT = (0, 1676, 365, 278)   # in battle/shop pages
RICE_RECT = (366, 0, 144, 105)    # in restsite page
RW, RH = 365, 278

# rest-pose tuning: pull hair inward, bring arms inward + tilt so hands cradle
# the bowl. Hair/arm bones have no translate timelines, so setup-relative
# offsets take effect; arm rotation is animated, so the animated values are
# shifted by ROT_DELTA instead.
HAIR_DX = 16.0
ARM_DX = 25.0
ARM_DY = 9.0
ARM_ROT_DELTA = {"arm_l": 20.0, "arm_r": -20.0}


def load_pck(path):
    d = open(path, "rb").read()
    file_base = struct.unpack_from("<Q", d, 0x18)[0]
    idx_off = struct.unpack_from("<Q", d, 0x20)[0]
    n = struct.unpack_from("<I", d, idx_off)[0]
    p = idx_off + 4
    entries = {}
    order = []
    for _ in range(n):
        plen = struct.unpack_from("<I", d, p)[0]
        p += 4
        name = d[p:p + plen].rstrip(b"\x00").decode("utf-8")
        p += plen
        off, size = struct.unpack_from("<QQ", d, p)
        p += 16
        p += 16
        p += 4
        entries[name] = d[file_base + off:file_base + off + size]
        order.append(name)
    return entries, order


def decode_ctex(blob):
    img = Image.open(io.BytesIO(blob[blob.find(b"RIFF"):])).convert("RGBA")
    w, h = struct.unpack_from("<II", blob, 8)
    assert img.size == (w, h)
    return img


def encode_ctex(old_blob, img):
    buf = io.BytesIO()
    img.save(buf, "WEBP", lossless=True, quality=100, method=6)
    webp = buf.getvalue()
    hdr = bytearray(old_blob[:0x38])
    struct.pack_into("<I", hdr, 0x34, len(webp))
    return bytes(hdr) + webp


def remove_white_bg(img, tol=20):
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    ref = px[0, 0][:3]
    bg = set()
    q = deque()
    for x in range(w):
        q.extend(((x, 0), (x, h - 1)))
    for y in range(h):
        q.extend(((0, y), (w - 1, y)))
    while q:
        x, y = q.popleft()
        if (x, y) in bg or not (0 <= x < w and 0 <= y < h):
            continue
        r, g, b, a = px[x, y]
        if max(abs(r - ref[0]), abs(g - ref[1]), abs(b - ref[2])) > tol:
            continue
        bg.add((x, y))
        q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    for x, y in bg:
        r, g, b, a = px[x, y]
        px[x, y] = (r, g, b, 0)
    print(f"  rice bg removed: {len(bg)} px ({100 * len(bg) / (w * h):.1f}%)")
    return img


# --- 1. original cast pixels from pristine mod ---
bak, _ = load_pck(BAK_PCK)
cx0, cy0, cw, ch = CAST_RECT
cast_orig = decode_ctex(bak[BATTLE]).crop((cx0, cy0, cx0 + cw, cy0 + ch))

entries, order = load_pck(SRC_PCK)

# --- 2. battle + shop: restore original cast_head ---
for key in (BATTLE, SHOP):
    page = decode_ctex(entries[key])
    x0, y0, rw, rh = CAST_RECT
    page.paste(Image.new("RGBA", (rw, rh), (0, 0, 0, 0)), (x0, y0))
    page.paste(cast_orig, (x0, y0))
    entries[key] = encode_ctex(entries[key], page)
    print(f"cast reverted: {key.split('/')[-1]}")
cast_orig.save(os.path.join(W, "prev_cast_restored.png"))

# --- 3. rice region pixels ---
art = remove_white_bg(Image.open(RICE_ART))
rx, ry, rw2, rh2 = RICE_RECT
s = min(rw2 / art.width, rh2 / art.height)
nw, nh = round(art.width * s), round(art.height * s)
art = art.resize((nw, nh), Image.LANCZOS)
rice_canvas = Image.new("RGBA", (rw2, rh2), (0, 0, 0, 0))
rice_canvas.paste(art, ((rw2 - nw) // 2, (rh2 - nh) // 2), art)
print(f"rice fit: {art.width}x{art.height} in {rw2}x{rh2}")

rest_page = decode_ctex(entries[REST_PNG])
rest_page.paste(rice_canvas, (rx, ry), rice_canvas)
entries[REST_PNG] = encode_ctex(entries[REST_PNG], rest_page)
rice_canvas.save(os.path.join(W, "prev_rice_region.png"))

# --- 4. restsite atlas text: rice before last entry + sacrificial dummy ---
obj = json.loads(entries[REST_ATLAS].decode("utf-8"))
txt = obj["atlas_data"]
lines = txt.rstrip("\n").split("\n")
assert lines[-1].startswith("shadow") or "shadow" in lines, lines[-6:]
# find the bounds line belonging to the last region; insert rice before it
i_last = len(lines) - 2  # region name line; bounds follows
assert lines[i_last + 1].startswith("bounds:"), lines[i_last:i_last + 2]
rice_lines = ["rice", f"bounds:{rx},{ry},{rw2},{rh2}"]
dummy_lines = ["zz_insurance", "bounds:506,828,4,4"]
new_txt = "\n".join(lines[:i_last] + rice_lines + lines[i_last:]) + "\n" + "\n".join(dummy_lines) + "\n"
obj["atlas_data"] = new_txt
entries[REST_ATLAS] = json.dumps(obj, ensure_ascii=False).encode("utf-8")
print("atlas text updated:", len(new_txt), "chars")
print(new_txt)

# --- 5. restsite skeleton: append rice slot (no index shifts anywhere) ---
sk = open(os.path.join(W, "restsite_defect.skel"), "rb").read()  # dumped earlier
assert sk == entries[REST_SKEL], "restsite skel changed since dump"


class BW:
    def __init__(self):
        self.b = bytearray()

    def byte(self, v):
        self.b.append(v & 0xFF)

    def f32(self, v):
        self.b += struct.pack(">f", v)

    def varint(self, v):
        while v > 127:
            self.byte((v & 0x7F) | 0x80)
            v >>= 7
        self.byte(v)

    def string(self, s):
        e = s.encode("utf-8")
        self.varint(len(e) + 1)
        self.b += e


# header fields from dump: hash=ba42c4daa2d16763 version=4.2.43
# bounds=(-270,-366,684,728) refScale=100 nonessential=0
w = BW()
w.b += sk[:8]
w.string("4.2.43")
for v in (-270.0, -366.0, 684.0, 728.0):
    w.f32(v)
w.f32(100.0)
w.byte(0)

# strings: 10 original + "rice"
STRINGS = ["shadow", "tail", "hair_l", "hair_r", "leg_l", "leg_r",
           "bod", "arm_l", "arm_r", "head", "rice"]
w.varint(len(STRINGS))
for s in STRINGS:
    w.string(s)

# bones: 15, verbatim field values from dump (local offsets)
BONES = [
    ("root", None, 0.0, 0.0, 0.0), ("root_adjust", 0, 0.0, 0.0, 0.0),
    ("hips", 1, 0.0, 0.0, -30.0), ("torso", 2, 0.0, 0.0, 60.0),
    ("neck", 3, 0.0, 0.0, 80.0), ("head", 4, 0.0, 0.0, 40.0),
    ("shoulder_l", 3, 0.0, -70.0, 0.0), ("arm_l", 6, 0.0, ARM_DX, -6.0 + ARM_DY),
    ("shoulder_r", 3, 0.0, 70.0, 0.0), ("arm_r", 8, 0.0, -ARM_DX, -6.0 + ARM_DY),
    ("hair_l", 1, 0.0, -62.0 + HAIR_DX, 56.0), ("hair_r", 1, 0.0, 62.0 - HAIR_DX, 56.0),
    ("leg_l", 2, 0.0, -25.0, -2.0), ("leg_r", 2, 0.0, 25.0, -2.0),
    ("tail", 1, 0.0, -40.0, -8.0),
]
w.varint(len(BONES))
for i, (name, parent, rot, x, y) in enumerate(BONES):
    w.string(name)
    if i > 0:
        w.varint(parent)
    w.f32(rot)
    w.f32(x)
    w.f32(y)
    w.f32(1.0); w.f32(1.0)   # scale
    w.f32(0.0); w.f32(0.0)   # shear
    w.f32(0.0)               # length
    w.varint(0)              # inherit
    w.byte(0)                # skinRequired

# slots: 10 original + rice (index 10, bone 3 = torso)
SLOTS = [
    ("shadow", 0, 1), ("tail", 14, 2), ("hair_l", 10, 3), ("hair_r", 11, 4),
    ("leg_l", 12, 5), ("leg_r", 13, 6), ("bod", 3, 7), ("arm_l", 7, 8),
    ("arm_r", 9, 9), ("head", 5, 10), ("rice", 3, 11),
]
w.varint(len(SLOTS))
for name, bone_i, att_ref in SLOTS:
    w.string(name)
    w.varint(bone_i)
    w.b += b"\xff\xff\xff\xff"
    w.b += b"\xff\xff\xff\xff"
    w.varint(att_ref)
    w.varint(0)

w.varint(0); w.varint(0); w.varint(0); w.varint(0)  # constraints

# default skin: 11 slots; original 10 records copied verbatim (sk[899:1179]),
# then the rice record (region px -> spine units: x0.55)
w.varint(len(SLOTS))
w.b += sk[899:1179]
w.varint(10)          # slot index 10
w.varint(1)           # one attachment
w.varint(11)          # name ref -> "rice" (strings index 10 + 1)
w.byte(0x00)          # flags: no path/color/sequence
w.f32(0.0); w.f32(15.0)   # center offset on torso bone
w.f32(1.0); w.f32(1.0)
w.f32(rw2 * 0.55); w.f32(rh2 * 0.55)

w.varint(0)           # named skins
w.varint(0)           # events

# animations: copied verbatim, then arm rotate frame values shifted in place.
sys.path.insert(0, W)
from rest_pose import parse as parse_skel  # noqa: E402

INFO = parse_skel(os.path.join(W, "restsite_defect.skel"))
ANIM_START = INFO["anim_start"]
anim_bytes = bytearray(sk[ANIM_START:])
n_patched = 0
for anim in INFO["anims"]:
    for bname, ttype, frames, _ in anim["bone_tl"]:
        if ttype != 0 or bname not in ARM_ROT_DELTA:
            continue
        for _t, vals, offs in frames:
            struct.pack_into(">f", anim_bytes, offs[0] - ANIM_START,
                             vals[0] + ARM_ROT_DELTA[bname])
            n_patched += 1
print(f"arm rotate keys patched: {n_patched}")
w.b += anim_bytes

assert sk[898] == 10, "skin slot count varint expected at 898"
assert sk[1180] == 0, "events count varint expected at 1180"
new_sk = bytes(w.b)
print(f"restsite skel: {len(sk)} -> {len(new_sk)} bytes")
open(os.path.join(W, "restsite_defect_rice.skel"), "wb").write(new_sk)
entries[REST_SKEL] = new_sk

# --- 6. rebuild + verify ---
pcktool.build_pck(OUT_PCK, [(n, entries[n]) for n in order], ref_header_from=SRC_PCK)
e2, o2 = load_pck(OUT_PCK)
assert o2 == order
changed = []
for k in order:
    if e2[k] != entries[k]:
        changed.append(k)
    # source of truth: rebuild must reproduce exactly what we staged
for k in (BATTLE, SHOP, REST_PNG, REST_ATLAS, REST_SKEL):
    assert e2[k] == entries[k], f"mismatch: {k}"
print("changed entries:", [k.split('/')[-1] for k in changed])
print("OK", os.path.getsize(OUT_PCK), "bytes")
