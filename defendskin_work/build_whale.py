"""Build DeepseekWhaleDefect.pck from the pristine workshop base.

1. localization: drop the un-prefixed global `characters.json` (it replaces the
   whole table and shadows every other mod) and trim the mod's own
   `DeepseekWhaleDefect/localization/zhs/characters.json` down to the keys this
   mod actually changes -- shipping the full vanilla table re-applied the
   vanilla character names and stomped other skin mods.
2. normal head: replace the `head` region in the battle/shop/restsite pages,
   cropped to its content and scaled to fill the 365x278 box exactly like the
   other (untouched) poses do.
3. ability face: replace `cast_head` (battle + shop) with the 32088 art.
3b. low-health face: restore the original wide-open crying `low_head` art -- the
   later "aggrieved" replacement was so subtle that the low_health_loop head swap
   was no longer readable in game.
4. cutouts: the head art is cropped off its white backdrop with a border flood
   fill (premultiplied alpha scaling keeps the resize clean), and every head
   region on every page then gets a colour bleed -- the silhouette colours are
   smeared into the empty texels so the atlas' linear filter can no longer pick
   up a white rim just outside the sprite. The ability art's watermark is
   dropped with the stray blobs.
5. rice bowl: new `rice` region in the restsite page + atlas entry inserted
   before the last region, with a sacrificial dummy appended (the game's atlas
   parser drops the final entry).
6. restsite skeleton: append a `rice` slot and tune the rest pose (hair inward,
   arms inward + tilted so the hands cradle the bowl).
7. battle skeleton: scale the positive (backward) head rotate keys in the
   standing-idle loops so the head no longer reads as leaning back.
"""
import io
import json
import os
import struct
import sys
from collections import deque

from PIL import Image, ImageChops

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pcktool

W = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, W)
from rest_pose import parse as parse_skel  # noqa: E402

BASE_PCK = r"c:\Users\12415\Documents\trae_projects\slay\whale_workspace\content\DeepseekWhaleDefect.pck"
OUT_PCK = os.path.join(W, "DeepseekWhaleDefect.pck.new")
HEAD_ART = r"d:\12415\Desktop\MEITU_20261007_183131351.png"
CAST_ART = r"d:\12415\Desktop\32088.png"
RICE_ART = r"d:\12415\Desktop\fan22.png"
FALLBACK_HEAD_PCK = r"d:\steam\steamapps\common\Slay the Spire 2\mods\DeepseekWhaleDefect.pck"

BATTLE = "res://.godot/imported/defect.png-d9a4219263a117f0ba83c83a65391b33.ctex"
SHOP = "res://.godot/imported/defect_shop.png-7cd1b216490239388e248fe3de753032.ctex"
REST_PNG = "res://.godot/imported/restsite_defect.png-b1461c3f515adbce2780a4a5d8a9c408.ctex"
REST_ATLAS = "res://.godot/imported/restsite_defect.atlas-d47514764581271cf35b4bbe66e2441c.spatlas"
REST_SKEL = "res://.godot/imported/restsite_defect.skel-ff0d5434498d809964bf95b0eb025379.spskel"
BATTLE_SKEL = "res://.godot/imported/defect.skel-5dba1374f717ab634fbb5c1941158597.spskel"
DROP = ["res://localization/zhs/characters.json"]
LOC_ZHS = "DeepseekWhaleDefect/localization/zhs/characters.json"
# The game merges a mod's `localization/{lang}/characters.json` key by key into
# the global table. The pristine base pck shipped a full copy of the vanilla
# table here, so every vanilla name got re-applied -- which reset other skin
# mods' renames (e.g. an Ironclad skin reverting to 铁甲战士). Only the keys this
# mod deliberately changes are kept.
LOC_KEYS = ("DEFECT.title", "DEFECT.titleObject", "DEFECT.description")

HEAD_RECT = (0, 0, 365, 278)
RICE_RECT = (366, 0, 144, 105)
RW, RH = 365, 278
# cast_head lives at the same spot in the battle and shop pages
CAST_POS = {BATTLE: (0, 1676), SHOP: (0, 1676)}
# The original v0.1.0 low-health face (crying, drawn at the exact 365x278 region
# size). It was swapped for a much subtler art, which reads in game as if the
# low_health_loop head never switched at all, so it is restored here.
LOW_ART = r"c:\Users\12415\Documents\trae_projects\slay\investigate\regions\low_head.png"
LOW_POS = {BATTLE: (0, 560), SHOP: (0, 560)}
# top-left y of every 365x278 head region per page; all get the colour bleed
HEAD_YLIST = {
    BATTLE: (0, 280, 560, 1396, 1676),
    SHOP: (0, 280, 560, 1396, 1676),
    REST_PNG: (0,),
}

HAIR_DX = 16.0
HAIR_DY = 4.0
LEG_DY = 4.0
ARM_DX = 37.0
ARM_DY = 24.0
ARM_ROT_DELTA = {"arm_l": 32.0, "arm_r": -32.0}

# The character faces right, so a positive head rotation tilts the head back
# (screen-left). The artwork makes that backward swing read larger than the
# forward one, so the backward keyframes in the standing-idle loops are scaled
# down to even the two out. Forward (negative) keys are left untouched.
HEAD_BACK_SCALE = 0.5
HEAD_BACK_ANIMS = {"idle_loop", "relaxed_loop"}


def load_pck(path):
    d = open(path, "rb").read()
    fb = struct.unpack_from("<Q", d, 0x18)[0]
    idx = struct.unpack_from("<Q", d, 0x20)[0]
    n = struct.unpack_from("<I", d, idx)[0]
    p = idx + 4
    e, order = {}, []
    for _ in range(n):
        pl = struct.unpack_from("<I", d, p)[0]; p += 4
        nm = d[p:p + pl].rstrip(b"\x00").decode(); p += pl
        off, sz = struct.unpack_from("<QQ", d, p); p += 16 + 16 + 4
        e[nm] = d[fb + off:fb + off + sz]
        order.append(nm)
    return e, order


def decode_ctex(blob):
    img = Image.open(io.BytesIO(blob[blob.find(b"RIFF"):])).convert("RGBA")
    assert img.size == struct.unpack_from("<II", blob, 8)
    return img


def encode_ctex(old_blob, img):
    buf = io.BytesIO()
    img.save(buf, "WEBP", lossless=True, quality=100, method=6)
    webp = buf.getvalue()
    hdr = bytearray(old_blob[:0x38])
    struct.pack_into("<I", hdr, 0x34, len(webp))
    return bytes(hdr) + webp


def _largest_blob(mask, w, h):
    """Biggest 4-connected blob of a boolean mask (used to drop stray marks)."""
    seen = set()
    best = set()
    for sy in range(h):
        for sx in range(w):
            if not mask[sy][sx] or (sx, sy) in seen:
                continue
            comp = set()
            q = deque([(sx, sy)])
            seen.add((sx, sy))
            while q:
                x, y = q.popleft()
                comp.add((x, y))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] \
                            and (nx, ny) not in seen:
                        seen.add((nx, ny))
                        q.append((nx, ny))
            if len(comp) > len(best):
                best = comp
    return best


def remove_white_bg(img, tol=28, drop_strays=False):
    """Cut a white backdrop off.

    Border-connected pixels that are already transparent OR close to white are
    filled, which also eats the anti-aliased white ring instead of leaving it
    behind. `drop_strays` keeps only the largest blob, so tiny detached marks
    (watermarks, specks) disappear along with their white-grey pixels.
    """
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
        if a == 0 or max(abs(r - ref[0]), abs(g - ref[1]), abs(b - ref[2])) <= tol:
            bg.add((x, y))
            q.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    if drop_strays:
        mask = [[(x, y) not in bg for x in range(w)] for y in range(h)]
        keep = _largest_blob(mask, w, h)
    else:
        keep = None
    n = 0
    for y in range(h):
        for x in range(w):
            if (x, y) not in bg and (keep is None or (x, y) in keep):
                continue
            if px[x, y][3] or px[x, y][:3] != (0, 0, 0):
                px[x, y] = (0, 0, 0, 0)
                n += 1
    print(f"  bg removed: {n} px ({100 * n / (w * h):.1f}%)")
    return img


def alpha_bleed(img, iterations=8):
    """Smear the silhouette colours outward over the transparent pixels.

    The atlas is sampled with linear filtering, so a transparent texel still
    contributes its RGB to the samples taken just outside the sprite. Leaving
    those texels white is what paints a white rim around the head, so the edge
    colours are extended into the empty space (visible pixels are untouched).
    """
    img = img.convert("RGBA")
    rgb = img.convert("RGB")
    alpha = img.getchannel("A")
    known = alpha.point(lambda v: 255 if v > 0 else 0)
    for _ in range(iterations):
        grown = known
        rgb_new = rgb.copy()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            cand = ImageChops.multiply(ImageChops.invert(known),
                                       ImageChops.offset(known, dx, dy))
            if cand.getbbox() is None:
                continue
            rgb_new.paste(ImageChops.offset(rgb, dx, dy), (0, 0), cand)
            grown = ImageChops.lighter(grown, cand)
        rgb = rgb_new
        known = grown
    return Image.merge("RGBA", (*rgb.split(), alpha))


def _resize_premul(img, size):
    """LANCZOS resize with premultiplied alpha.

    Plain RGBA resizing averages the raw RGB of transparent pixels with the
    visible ones, which paints the colour of the (white) backdrop into the
    silhouette edge. Premultiplying first makes the invisible pixels weigh 0.
    """
    return img.convert("RGBa").resize(size, Image.LANCZOS).convert("RGBA")


def fit_fill(art, rw, rh):
    """Crop to content, then scale uniformly to fill rw x rh (like other poses)."""
    art = art.crop(art.getbbox())
    s = min(rw / art.width, rh / art.height)
    nw, nh = round(art.width * s), round(art.height * s)
    art = _resize_premul(art, (nw, nh))
    canvas = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
    canvas.paste(art, ((rw - nw) // 2, (rh - nh) // 2), art)
    print(f"  content {art.width}x{art.height} -> {nw}x{nh} in {rw}x{rh} (scale {s:.4f})")
    return canvas


# ---------------------------------------------------------------- head art
if os.path.exists(HEAD_ART):
    art1 = Image.open(HEAD_ART)
    if art1.mode != "RGBA":
        art1 = art1.convert("RGBA")
    if art1.getextrema()[3][0] == 255:
        art1 = remove_white_bg(art1)
    print("head art from desktop:", art1.size)
else:
    fb_e, _ = load_pck(FALLBACK_HEAD_PCK)
    x, y, w, h = HEAD_RECT
    art1 = decode_ctex(fb_e[BATTLE]).crop((x, y, x + w, y + h))
    print("head art recovered from installed pck:", art1.size)
head_canvas = fit_fill(art1, RW, RH)

# ------------------------------------------------------------- ability face
cast_art = remove_white_bg(Image.open(CAST_ART).convert("RGBA"), drop_strays=True)
cast_canvas = fit_fill(cast_art, RW, RH)

# Already authored at exactly the head-region size, so paste it verbatim.
low_canvas = Image.open(LOW_ART).convert("RGBA")
assert low_canvas.size == (RW, RH), f"low_head art must be {RW}x{RH}, got {low_canvas.size}"
print("low-health face:", low_canvas.size, "from", os.path.basename(LOW_ART))

entries, order = load_pck(BASE_PCK)
for k in DROP:
    print("dropping:", k)
    order.remove(k)

loc = json.loads(entries[LOC_ZHS].decode("utf-8"))
entries[LOC_ZHS] = json.dumps({k: loc[k] for k in LOC_KEYS},
                              ensure_ascii=False).encode("utf-8")
print("localization kept:", list(LOC_KEYS), "of", len(loc), "keys")

# head + ability face + colour bleed of every head region
for key in (BATTLE, SHOP, REST_PNG):
    page = decode_ctex(entries[key])
    x, y, w, h = HEAD_RECT
    page.paste(Image.new("RGBA", (w, h), (0, 0, 0, 0)), (x, y))
    page.paste(head_canvas, (x, y), head_canvas)
    if key in CAST_POS:
        page.paste(Image.new("RGBA", (RW, RH), (0, 0, 0, 0)), CAST_POS[key])
        page.paste(cast_canvas, CAST_POS[key], cast_canvas)
    if key in LOW_POS:
        page.paste(Image.new("RGBA", (RW, RH), (0, 0, 0, 0)), LOW_POS[key])
        page.paste(low_canvas, LOW_POS[key], low_canvas)
    for y2 in HEAD_YLIST[key]:
        box = (0, y2, RW, y2 + RH)
        page.paste(alpha_bleed(page.crop(box)), box)
    entries[key] = encode_ctex(entries[key], page)
    print(f"page updated: {key.split('/')[-1]}")

# ---------------------------------------------------------------- rice art
rx, ry, rw2, rh2 = RICE_RECT
rice = fit_fill(remove_white_bg(Image.open(RICE_ART)), rw2, rh2)
rest_page = decode_ctex(entries[REST_PNG])
rest_page.paste(rice, (rx, ry), rice)
entries[REST_PNG] = encode_ctex(entries[REST_PNG], rest_page)
rice.save(os.path.join(W, "prev_rice_region.png"))

obj = json.loads(entries[REST_ATLAS].decode("utf-8"))
lines = obj["atlas_data"].rstrip("\n").split("\n")
i_last = len(lines) - 2
assert lines[i_last + 1].startswith("bounds:"), lines[i_last:i_last + 2]
new_txt = "\n".join(lines[:i_last] + ["rice", f"bounds:{rx},{ry},{rw2},{rh2}"]
                    + lines[i_last:]) + "\nzz_insurance\nbounds:506,828,4,4\n"
obj["atlas_data"] = new_txt
entries[REST_ATLAS] = json.dumps(obj, ensure_ascii=False).encode("utf-8")
print("restsite atlas regions now:",
      [l for l in new_txt.split("\n") if l and ":" not in l])

# ---------------------------------------------------------------- restsite skel
sk = entries[REST_SKEL]
INFO = parse_skel_orig = None
tmp = os.path.join(W, "_base_restsite.skel")
open(tmp, "wb").write(sk)
INFO = parse_skel(tmp)
os.remove(tmp)


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


w = BW()
w.b += sk[:8]
w.string("4.2.43")
for v in (-270.0, -366.0, 684.0, 728.0):
    w.f32(v)
w.f32(100.0)
w.byte(0)

STRINGS = ["shadow", "tail", "hair_l", "hair_r", "leg_l", "leg_r",
           "bod", "arm_l", "arm_r", "head", "rice"]
w.varint(len(STRINGS))
for s in STRINGS:
    w.string(s)

BONES = [
    ("root", None, 0.0, 0.0, 0.0), ("root_adjust", 0, 0.0, 0.0, 0.0),
    ("hips", 1, 0.0, 0.0, -30.0), ("torso", 2, 0.0, 0.0, 60.0),
    ("neck", 3, 0.0, 0.0, 80.0), ("head", 4, 0.0, 0.0, 40.0),
    ("shoulder_l", 3, 0.0, -70.0, 0.0), ("arm_l", 6, 0.0, ARM_DX, -6.0 + ARM_DY),
    ("shoulder_r", 3, 0.0, 70.0, 0.0), ("arm_r", 8, 0.0, -ARM_DX, -6.0 + ARM_DY),
    ("hair_l", 1, 0.0, -62.0 + HAIR_DX, 56.0 + HAIR_DY), ("hair_r", 1, 0.0, 62.0 - HAIR_DX, 56.0 + HAIR_DY),
    ("leg_l", 2, 0.0, -25.0, -2.0 + LEG_DY), ("leg_r", 2, 0.0, 25.0, -2.0 + LEG_DY),
    ("tail", 1, 0.0, -40.0, -8.0),
]
w.varint(len(BONES))
for i, (name, parent, rot, x, y) in enumerate(BONES):
    w.string(name)
    if i > 0:
        w.varint(parent)
    w.f32(rot); w.f32(x); w.f32(y)
    w.f32(1.0); w.f32(1.0)
    w.f32(0.0); w.f32(0.0)
    w.f32(0.0)
    w.varint(0)
    w.byte(0)

SLOTS = [
    ("shadow", 0, 1), ("tail", 14, 2), ("hair_l", 10, 3), ("hair_r", 11, 4),
    ("leg_l", 12, 5), ("leg_r", 13, 6), ("bod", 3, 7), ("arm_l", 7, 8),
    ("arm_r", 9, 9), ("head", 5, 10), ("rice", 3, 11),
]
w.varint(len(SLOTS))
for name, bone_i, att_ref in SLOTS:
    w.string(name)
    w.varint(bone_i)
    w.b += b"\xff\xff\xff\xff" * 2
    w.varint(att_ref)
    w.varint(0)

w.varint(0); w.varint(0); w.varint(0); w.varint(0)

# skin: locate the original default-skin record block by re-parsing offsets
SKIN_START = INFO["skin_start"]
SKIN_END = INFO["skin_end"]
w.varint(len(SLOTS))
w.b += sk[SKIN_START:SKIN_END]
w.varint(10)                 # slot index 10 -> rice
w.varint(1)
w.varint(11)                 # strings index 10 + 1
w.byte(0x00)
w.f32(0.0); w.f32(20.0)      # bowl centre on the torso bone
w.f32(1.0); w.f32(1.0)
w.f32(rw2 * 0.55); w.f32(rh2 * 0.55)

w.varint(0)                  # named skins
w.varint(0)                  # events

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
new_sk = bytes(w.b)
print(f"restsite skel: {len(sk)} -> {len(new_sk)} bytes")
open(os.path.join(W, "restsite_defect_rice.skel"), "wb").write(new_sk)
entries[REST_SKEL] = new_sk

# ------------------------------------------------------- battle skel head sway
bsk = entries[BATTLE_SKEL]
tmp = os.path.join(W, "_base_battle.skel")
open(tmp, "wb").write(bsk)
BINFO = parse_skel(tmp)
os.remove(tmp)
b_bytes = bytearray(bsk)
n_head = 0
for anim in BINFO["anims"]:
    if anim["name"] not in HEAD_BACK_ANIMS:
        continue
    for bname, ttype, frames, _ in anim["bone_tl"]:
        if ttype != 0 or bname != "head":
            continue
        for _t, vals, offs in frames:
            if vals[0] > 0.0:
                struct.pack_into(">f", b_bytes, offs[0], vals[0] * HEAD_BACK_SCALE)
                n_head += 1
        print(f"  {anim['name']}: head rotate keys ->",
              [round(v[1][0] * HEAD_BACK_SCALE if v[1][0] > 0 else v[1][0], 2)
               for v in frames])
print(f"battle head back keys scaled: {n_head}")
entries[BATTLE_SKEL] = bytes(b_bytes)

# ---------------------------------------------------------------- rebuild
pcktool.build_pck(OUT_PCK, [(n, entries[n]) for n in order], ref_header_from=BASE_PCK)
e2, o2 = load_pck(OUT_PCK)
assert o2 == order, "entry order changed"
for k in order:
    assert e2[k] == entries[k], f"content mismatch: {k}"
print("changed:", [k.split("/")[-1] for k in (BATTLE, SHOP, REST_PNG, REST_ATLAS, REST_SKEL, BATTLE_SKEL)])
print("entries:", len(order), "size:", os.path.getsize(OUT_PCK))