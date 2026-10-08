"""Replace the *defect* version of the YUMMY_COOKIE (美味饼干) relic icon in
DeepseekWhaleDefect.pck with the user's whale-girl art.

Chain replaced (base game keys, remapped into the mod):
  images/relics/yummy_cookie_defect.png.import            -> our own ctex
  images/atlases/relic_atlas.sprites/<stem>.tres          -> our standalone AtlasTexture
  images/atlases/relic_outline_atlas.sprites/<stem>.tres  -> our outline AtlasTexture

The original relic ctex is BPTC (format 0 / ifmt 22); we instead ship a lossless
WebP ctex (format 2 / ifmt 5 = RGBA8) whose 0x38-byte GST2 header is copied from
a base-game WebP texture, so alpha survives. Idempotent.
"""
import hashlib
import io
import os
import re
import struct
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import pcktool

BASE_PCK = r"D:\steam\steamapps\common\Slay the Spire 2\SlayTheSpire2.pck"
WHALE_PCK = r"d:\steam\steamapps\common\Slay the Spire 2\mods\DeepseekWhaleDefect.pck"
WHALE_OUT = os.path.join(HERE, "DeepseekWhaleDefect.pck.new")
PREFIX = "DeepseekWhaleDefect"
STEM = "yummy_cookie_defect"
UID_ALPHABET = "0123456789abcdefghijklmnopqrstuv"

ICON_PNG = os.path.join(HERE, "_cookie_cut.png")
OUTLINE_PNG = os.path.join(HERE, "_cookie_outline.png")
CANVAS = 256


def parse_v3(path):
    d = open(path, "rb").read()
    assert d[:4] == b"GDPC"
    file_base = struct.unpack_from("<Q", d, 0x18)[0]
    idx_off = struct.unpack_from("<Q", d, 0x20)[0]
    n = struct.unpack_from("<I", d, idx_off)[0]
    p = idx_off + 4
    entries = []
    for _ in range(n):
        plen = struct.unpack_from("<I", d, p)[0]
        p += 4
        name = d[p:p + plen].rstrip(b"\x00").decode("utf-8")
        p += plen
        off, size = struct.unpack_from("<QQ", d, p)
        p += 16 + 16 + 4
        entries.append((name, off, size))
    return d, file_base, entries


def make_uid(seed):
    v = int.from_bytes(hashlib.md5(seed.encode()).digest()[:8], "little")
    s = ""
    while v:
        s += UID_ALPHABET[v & 31]
        v >>= 5
    return s


def webp_ctex(header_src, png_path):
    """Build a GST2 / WebP(RGBA8) ctex from a 256x256 RGBA png."""
    img = Image.open(png_path).convert("RGBA")
    assert img.size == (CANVAS, CANVAS), img.size
    buf = io.BytesIO()
    img.save(buf, "WEBP", lossless=True, quality=100, method=6, exact=True)
    webp = buf.getvalue()
    assert webp[:4] == b"RIFF" and webp[8:12] == b"WEBP", "not webp"
    hdr = bytearray(header_src[:0x38])
    struct.pack_into("<II", hdr, 0x08, CANVAS, CANVAS)
    struct.pack_into("<I", hdr, 0x24, 2)                       # data format = WEBP
    struct.pack_into("<I", hdr, 0x28, (CANVAS << 16) | CANVAS)  # u16 w, u16 h
    struct.pack_into("<I", hdr, 0x30, 5)                       # Image::Format = RGBA8
    struct.pack_into("<I", hdr, 0x34, len(webp))
    return bytes(hdr) + webp


bd, b_fb, b_entries = parse_v3(BASE_PCK)
base_blob = {name: bd[b_fb + o:b_fb + o + s] for name, o, s in b_entries}

# header template: a base-game WEBP+RGBA8 ctex (health_bar.png)
tmp_txt = base_blob[[k for k in base_blob
                     if k.endswith("health_bar.png.import")][0]].decode()
tmpl_key = re.search(r'path(?:\.\w+)?="([^"]+)"', tmp_txt).group(1).replace("res://", "")
tmpl_ctex = base_blob[tmpl_key]
assert struct.unpack_from("<I", tmpl_ctex, 0x24)[0] == 2
assert struct.unpack_from("<I", tmpl_ctex, 0x30)[0] == 5
print("ctex header template:", tmpl_key.split("/")[-1], "wh",
      struct.unpack_from("<II", tmpl_ctex, 8))

uid_icon = make_uid(f"{STEM}/icon")
uid_outline = make_uid(f"{STEM}/outline")
uid_icon_tres = make_uid(f"{STEM}/icon/tres")
uid_outline_tres = make_uid(f"{STEM}/outline/tres")
ctex_icon = f"{PREFIX}/imported/{hashlib.md5(b'yummy_cookie_defect/icon/ctex').hexdigest()}.ctex"
ctex_outline = f"{PREFIX}/imported/{hashlib.md5(b'yummy_cookie_defect/outline/ctex').hexdigest()}.ctex"
icon_png_res = f"{PREFIX}/relics/{STEM}.png"
outline_png_res = f"{PREFIX}/relics/{STEM}_outline.png"


def import_txt(uid, ctex):
    return (f'[remap]\n\nimporter="texture"\ntype="CompressedTexture2D"\n'
            f'uid="uid://{uid}"\npath="res://{ctex}"\n'
            f'metadata={{\n"vram_texture": false\n}}\n').encode("utf-8")


def sprite_tres(uid, png_res):
    return (f'[gd_resource type="AtlasTexture" load_steps=2 format=3 uid="uid://{uid}"]\n\n'
            f'[ext_resource type="Texture2D" path="res://{png_res}" id="1"]\n\n'
            f'[resource]\natlas = ExtResource("1")\nregion = Rect2(0, 0, {CANVAS}, {CANVAS})\n'
            ).encode("utf-8")


files = [
    (f"{icon_png_res}.import", import_txt(uid_icon, ctex_icon)),
    (ctex_icon, webp_ctex(tmpl_ctex, ICON_PNG)),
    (f"{outline_png_res}.import", import_txt(uid_outline, ctex_outline)),
    (ctex_outline, webp_ctex(tmpl_ctex, OUTLINE_PNG)),
    (f"{PREFIX}/sprites/{STEM}_relic.tres", sprite_tres(uid_icon_tres, icon_png_res)),
    (f"{PREFIX}/sprites/{STEM}_outline_relic.tres", sprite_tres(uid_outline_tres, outline_png_res)),
    (f"images/relics/{STEM}.png.remap",
     f'[remap]\n\npath="res://{icon_png_res}"\n'.encode("utf-8")),
    (f"images/atlases/relic_atlas.sprites/{STEM}.tres.remap",
     f'[remap]\n\npath="res://{PREFIX}/sprites/{STEM}_relic.tres"\n'.encode("utf-8")),
    (f"images/atlases/relic_outline_atlas.sprites/{STEM}.tres.remap",
     f'[remap]\n\npath="res://{PREFIX}/sprites/{STEM}_outline_relic.tres"\n'.encode("utf-8")),
]
for n, b in files:
    print(f"  + {n} ({len(b)} B)")

wd, w_fb, w_entries = parse_v3(WHALE_PCK)
new_names = {n for n, _ in files}
whale_files = [(n, wd[w_fb + o:w_fb + o + s]) for n, o, s in w_entries if n not in new_names]
skipped = len(w_entries) - len(whale_files)
whale_files += files
print(f"existing entries: {len(w_entries)} (replaced {skipped}), total now {len(whale_files)}")

pcktool.build_pck(WHALE_OUT, whale_files, ref_header_from=WHALE_PCK)
print(f"rebuilt: {WHALE_OUT} ({os.path.getsize(WHALE_OUT)} bytes)")

# --- verify ---
d2, fb2, e2 = parse_v3(WHALE_OUT)
new_map = {n: d2[fb2 + o:fb2 + o + s] for n, o, s in e2}
old_map = {n: wd[w_fb + o:w_fb + o + s] for n, o, s in w_entries}
for n, b in old_map.items():
    if n not in new_names:
        assert new_map[n] == b, f"corrupted: {n}"
for n, b in files:
    assert new_map[n] == b, f"mismatch: {n}"
for n in (ctex_icon, ctex_outline):
    ct = new_map[n]
    img = Image.open(io.BytesIO(ct[ct.find(b"RIFF"):]))
    print("verify", n.split("/")[-1], img.format, img.mode, img.size,
          "ifmt", struct.unpack_from("<I", ct, 0x30)[0],
          "wh@8", struct.unpack_from("<II", ct, 8))
print("entries:", len(e2))