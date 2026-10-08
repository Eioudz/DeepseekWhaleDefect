"""Add/refresh card portrait replacements inside DeepseekWhaleDefect.pck.

The pristine OrangePion DefectSkin template (d:\\12415\\Desktop\\DefectSkin.pck.bak)
is gone, so this sources each card's GST2 header straight from the *base game*
ctex of the same card and synthesizes the 4 metadata files (import / packed
remap / atlas remap / sprites tres) with fresh UIDs, re-homing the chain under
DeepseekWhaleDefect/. Idempotent: existing entries for these cards are replaced.
"""
import hashlib
import io
import os
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
UID_ALPHABET = "0123456789abcdefghijklmnopqrstuv"

CARDS = [
    # (card file stem, new art)
    ("dualcast", r"d:\12415\Downloads\qq_pic_merged_1791464093585.jpg"),  # 双重释放
    ("zap", r"d:\12415\Downloads\MEITU_20261008_093708976.jpg"),          # 电击 = 图二
]


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
        p += 16
        p += 16  # md5
        p += 4  # entry flags
        entries.append((name, off, size))
    return d, file_base, entries


def make_uid(seed):
    v = int.from_bytes(hashlib.md5(seed.encode()).digest()[:8], "little")
    s = ""
    while v:
        s += UID_ALPHABET[v & 31]
        v >>= 5
    return s


# --- base game: ctex header template + canvas size for each card ---
bd, b_fb, b_entries = parse_v3(BASE_PCK)
base_blob = {name: bd[b_fb + o:b_fb + o + s] for name, o, s in b_entries}

added = []
for stem, art_path in CARDS:
    imp_res = f"images/packed/card_portraits/defect/{stem}.png.import"
    imp_text = base_blob[imp_res].decode()
    ctex_res = imp_text.split('path="')[1].split('"')[0].replace("res://", "")
    ctex_old = base_blob[ctex_res]
    assert ctex_old[:4] == b"GST2" and ctex_old.find(b"RIFF") == 0x38
    cw, ch = struct.unpack_from("<II", ctex_old, 8)

    art = Image.open(art_path).convert("RGBA")
    scale = max(cw / art.width, ch / art.height)
    nw, nh = round(art.width * scale), round(art.height * scale)
    art = art.resize((nw, nh), Image.LANCZOS)
    x, y = (nw - cw) // 2, (nh - ch) // 2
    canvas = art.crop((x, y, x + cw, y + ch))
    buf = io.BytesIO()
    canvas.save(buf, "WEBP", lossless=True, quality=100, method=6)
    webp = buf.getvalue()
    hdr = bytearray(ctex_old[:0x38])
    struct.pack_into("<I", hdr, 0x34, len(webp))
    new_ctex = bytes(hdr) + webp
    print(f"{stem}: art {art.width}x{art.height} scale={scale:.4f} "
          f"crop=({x},{y}) ctex {len(new_ctex)} B (canvas {cw}x{ch})")

    uid_imp = make_uid(f"{stem}/import")
    uid_tres = make_uid(f"{stem}/tres")
    ctex_name = f"{PREFIX}/imported/{hashlib.md5((stem + '/ctex').encode()).hexdigest()}.ctex"

    files = [
        (f"{PREFIX}/card_portraits/defect/{stem}.png.import",
         (f'[remap]\n\nimporter="texture"\ntype="CompressedTexture2D"\n'
          f'uid="uid://{uid_imp}"\npath="res://{ctex_name}"\n'
          f'metadata={{\n"vram_texture": false\n}}\n').encode("utf-8")),
        (ctex_name, new_ctex),
        (f"images/packed/card_portraits/defect/{stem}.png.remap",
         f'[remap]\n\npath="res://{PREFIX}/card_portraits/defect/{stem}.png"\n'.encode("utf-8")),
        (f"{PREFIX}/sprites/{stem}.tres",
         (f'[gd_resource type="AtlasTexture" load_steps=2 format=3 uid="uid://{uid_tres}"]\n\n'
          f'[ext_resource type="Texture2D" path="res://{PREFIX}/card_portraits/defect/{stem}.png" id="1"]\n\n'
          f'[resource]\natlas = ExtResource("1")\nregion = Rect2(0, 0, {cw}, {ch})\n').encode("utf-8")),
        (f"images/atlases/card_atlas.sprites/defect/{stem}.tres.remap",
         f'[remap]\n\npath="res://{PREFIX}/sprites/{stem}.tres"\n'.encode("utf-8")),
    ]
    added += files

# --- rebuild whale pck: drop old copies of these card entries, add fresh ---
wd, w_fb, w_entries = parse_v3(WHALE_PCK)
new_names = {n for n, _ in added}
whale_files = [(n, wd[w_fb + o:w_fb + o + s]) for n, o, s in w_entries
               if n not in new_names]
skipped = len(w_entries) - len(whale_files)
whale_files += added
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
for n, b in added:
    assert new_map[n] == b, f"mismatch: {n}"
    if n.endswith(".ctex"):
        ct = new_map[n]
        img = Image.open(io.BytesIO(ct[ct.find(b"RIFF"):]))
        print("verify", n.split("/")[-1], img.format, img.size)
print("entries:", len(e2))