"""Add the Defend card portrait replacement into DeepseekWhaleDefect.pck.

Mirrors OrangePion's DefectSkin mod structure, but re-homed under the whale
mod's own prefix so the two mods never collide:
  1. DeepseekWhaleDefect/imported/e6c2885b8ae868655ef66e9e694ebbb0.ctex
  2. DeepseekWhaleDefect/card_portraits/defect/defend_defect.png.import
  3. images/packed/card_portraits/defect/defend_defect.png.remap
  4. DeepseekWhaleDefect/sprites/defend_defect.tres
  5. images/atlases/card_atlas.sprites/defect/defend_defect.tres.remap
The ctex is rebuilt from the user's defend_defect.jpg (cover-crop 1000x760,
lossless WebP, original 56-byte GST2 header).
"""
import io
import os
import struct
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pcktool  # workspace pck builder that produced the whale pck

W = os.path.dirname(os.path.abspath(__file__))
DEFECTSKIN_BAK = r"d:\12415\Desktop\DefectSkin.pck.bak"  # pristine OrangePion mod
WHALE_PCK = r"d:\steam\steamapps\common\Slay the Spire 2\mods\DeepseekWhaleDefect.pck"
WHALE_OUT = os.path.join(W, "DeepseekWhaleDefect.pck.new")
NEW_ART = r"d:\12415\Desktop\defend_defect.jpg"

CTEX_KEY = "DefectSkin/imported/e6c2885b8ae868655ef66e9e694ebbb0.ctex"
W, H = 1000, 760


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


# --- 1. pull the 4 metadata files + ctex header template from pristine DefectSkin ---
ds, ds_fb, ds_entries = parse_v3(DEFECTSKIN_BAK)
meta = {}
ctex_old = None
for name, off, size in ds_entries:
    blob = ds[ds_fb + off:ds_fb + off + size]
    if "defend_defect" in name:
        meta[name] = blob
    elif name == CTEX_KEY:
        ctex_old = blob
assert ctex_old is not None and len(meta) == 4, (ctex_old is not None, list(meta))
assert ctex_old[:4] == b"GST2" and struct.unpack_from("<II", ctex_old, 8) == (W, H)

# --- 2. rebuild the ctex from the new art ---
art = Image.open(NEW_ART).convert("RGBA")
scale = max(W / art.width, H / art.height)
nw, nh = round(art.width * scale), round(art.height * scale)
art = art.resize((nw, nh), Image.LANCZOS)
x, y = (nw - W) // 2, (nh - H) // 2
canvas = art.crop((x, y, x + W, y + H))
buf = io.BytesIO()
canvas.save(buf, "WEBP", lossless=True, quality=100, method=6)
webp = buf.getvalue()
hdr = bytearray(ctex_old[:0x38])
struct.pack_into("<I", hdr, 0x34, len(webp))
new_ctex = bytes(hdr) + webp

# --- 3. re-home paths: DefectSkin/ -> DeepseekWhaleDefect/ ---
def rehome(blob):
    return blob.replace(b"res://DefectSkin/", b"res://DeepseekWhaleDefect/")

def rehome_name(name):
    return name.replace("DefectSkin/", "DeepseekWhaleDefect/")

new_entries = [(rehome_name(n), rehome(b)) for n, b in meta.items()]
new_entries.append((rehome_name(CTEX_KEY), new_ctex))
for n, b in new_entries:
    print("add:", n, len(b), "bytes")

# --- 4. append to the whale pck and rebuild with its own builder ---
wd, w_fb, w_entries = parse_v3(WHALE_PCK)
existing = {n for n, _, _ in w_entries}
whale_files = []
for name, off, size in w_entries:
    whale_files.append((name, wd[w_fb + off:w_fb + off + size]))
for name, blob in new_entries:
    assert name not in existing, f"collision: {name}"
    whale_files.append((name, blob))

pcktool.build_pck(WHALE_OUT, whale_files, ref_header_from=WHALE_PCK)
print(f"rebuilt: {WHALE_OUT} ({os.path.getsize(WHALE_OUT)} bytes, was {os.path.getsize(WHALE_PCK)})")

# --- 5. verify ---
d2, fb2, e2 = parse_v3(WHALE_OUT)
assert len(e2) == 30, len(e2)
old_map = {n: wd[w_fb + o:w_fb + o + s] for n, o, s in w_entries}
new_map = {n: d2[fb2 + o:fb2 + o + s] for n, o, s in e2}
assert set(new_map) == set(old_map) | {rehome_name(CTEX_KEY)} | set(rehome_name(n) for n in meta)
for n, b in old_map.items():
    assert new_map[n] == b, f"corrupted: {n}"
ct = new_map[rehome_name(CTEX_KEY)]
assert ct[:4] == b"GST2" and struct.unpack_from("<II", ct, 8) == (W, H)
img = Image.open(io.BytesIO(ct[ct.find(b"RIFF"):]))
print("verify ctex:", img.format, img.size)
for n, b in new_map.items():
    if n.endswith(".remap") or n.endswith(".import") or n.endswith(".tres"):
        if "defend" in n:
            print("---", n)
            print(b.decode("utf-8"))
print("all 25 original entries intact")
