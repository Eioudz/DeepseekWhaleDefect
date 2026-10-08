"""Replace the Defend card portrait inside DefectSkin.pck with new art.

Pipeline:
 1. Parse the mod pck (v3, flags=REL_FILEBASE, file_base=0x70, index at EOF).
 2. Decode target ctex (GST2, 1000x760, lossless WebP payload).
 3. Uniform-scale the new art to cover 1000x760 (no stretching), center-crop.
 4. Re-encode lossless WebP, wrap in the same 56-byte header (patched length).
 5. Rebuild the pck preserving the original layout conventions.
"""
import io
import os
import struct

from PIL import Image

SRC_PCK = r"d:\12415\Desktop\DefectSkin.pck"
NEW_ART = r"d:\12415\Desktop\defend_defect.jpg"
OUT_PCK = r"d:\12415\Desktop\DefectSkin.pck.new"
CTEX_KEY = "DefectSkin/imported/e6c2885b8ae868655ef66e9e694ebbb0.ctex"
W, H = 1000, 760


def parse(path):
    d = open(path, "rb").read()
    assert d[:4] == b"GDPC"
    flags = struct.unpack_from("<I", d, 0x14)[0]
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
    return d, flags, file_base, entries


d, flags, file_base, entries = parse(SRC_PCK)
print(f"entries: {len(entries)}, flags: {flags}, file_base: {file_base:#x}")

target = next(e for e in entries if e[0] == CTEX_KEY)
old_ctex = d[file_base + target[1]:file_base + target[1] + target[2]]
assert old_ctex[:4] == b"GST2"
ow, oh = struct.unpack_from("<II", old_ctex, 8)
assert (ow, oh) == (W, H), f"unexpected dims {ow}x{oh}"
print(f"target ctex: {target[2]} bytes, {ow}x{oh}")

# --- build new art: uniform scale to cover, center-crop ---
art = Image.open(NEW_ART).convert("RGBA")
scale = max(W / art.width, H / art.height)
nw, nh = round(art.width * scale), round(art.height * scale)
art = art.resize((nw, nh), Image.LANCZOS)
x, y = (nw - W) // 2, (nh - H) // 2
canvas = art.crop((x, y, x + W, y + H))
print(f"art {art.width // 1}x{nh} scaled={scale:.4f} crop=({x},{y})")

buf = io.BytesIO()
canvas.save(buf, "WEBP", lossless=True, quality=100, method=6)
webp = buf.getvalue()
assert webp[:4] == b"RIFF"

hdr = bytearray(old_ctex[:0x38])
struct.pack_into("<I", hdr, 0x34, len(webp))
new_ctex = bytes(hdr) + webp
print(f"new ctex: {len(new_ctex)} bytes (was {target[2]})")

# --- rebuild pck in the original layout ---
parts = []
for name, off, size in entries:
    blob = new_ctex if name == CTEX_KEY else d[file_base + off:file_base + off + size]
    parts.append((name, blob))

idx = bytearray()
idx += struct.pack("<I", len(parts))
cursor = 0
for name, blob in parts:
    rb = name.encode("utf-8") + b"\x00"
    idx += struct.pack("<I", len(rb)) + rb
    idx += struct.pack("<QQ", cursor, len(blob))
    idx += b"\x00" * 16  # md5
    idx += struct.pack("<I", 0)  # entry flags
    cursor += len(blob)
    cursor = (cursor + 15) & ~15  # 16-byte align like the original

out = bytearray(d[:0x28])  # header, index offset patched below
struct.pack_into("<Q", out, 0x20, file_base + cursor)  # index offset (absolute)
out += b"\x00" * (file_base - len(out))
for name, blob in parts:
    out += blob
    pad = (-len(blob)) % 16
    out += b"\x00" * pad
out += idx
open(OUT_PCK, "wb").write(out)
print(f"rebuilt: {OUT_PCK} ({len(out)} bytes, was {os.path.getsize(SRC_PCK)})")

# --- verify: re-parse and decode the replaced ctex ---
d2, flags2, fb2, entries2 = parse(OUT_PCK)
assert [e[0] for e in entries2] == [e[0] for e in entries], "entry list mismatch"
t2 = next(e for e in entries2 if e[0] == CTEX_KEY)
blob2 = d2[fb2 + t2[1]:fb2 + t2[1] + t2[2]]
assert blob2[:4] == b"GST2"
img = Image.open(io.BytesIO(blob2[blob2.find(b"RIFF"):]))
print("verify:", img.format, img.size, img.mode)
# spot-check a few other entries survived intact
for probe in ("DefectSkin/card_portraits/defect/defend_defect.png.import",
              "DefectSkin/sprites/defend_defect.tres"):
    e_old = next(e for e in entries if e[0] == probe)
    e_new = next(e for e in entries2 if e[0] == probe)
    a = d[file_base + e_old[1]:file_base + e_old[1] + e_old[2]]
    b = d2[fb2 + e_new[1]:fb2 + e_new[1] + e_new[2]]
    assert a == b, f"entry corrupted: {probe}"
print("other entries intact")
