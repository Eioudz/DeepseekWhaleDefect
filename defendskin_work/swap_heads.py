"""Swap the whale character's normal head (head) and ability head (cast_head).

Art: img1 -> head region (battle/shop/restsite pages), img2 -> cast_head
(battle/shop pages). All regions are 365x278. Art is uniformly scaled to fit
(contain) and centered. img2 has a white background: border-connected white is
flood-filled to transparency so the lace headdress survives.
"""
import io
import os
import struct
import sys
from collections import deque

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pcktool

W = os.path.dirname(os.path.abspath(__file__))
SRC_PCK = r"d:\steam\steamapps\common\Slay the Spire 2\mods\DeepseekWhaleDefect.pck"
OUT_PCK = os.path.join(W, "DeepseekWhaleDefect.pck.new")

IMG1 = r"d:\12415\Desktop\MEITU_20261007_183131351.png"  # new normal head
IMG2 = os.path.join(W, "img2_cutout.png")  # ability head (bg already removed)
DROP_ENTRIES = ["res://localization/zhs/characters.json"]  # shadows other mods' localization
RW, RH = 365, 278

HEAD_KEYS = [
    "res://.godot/imported/defect.png-d9a4219263a117f0ba83c83a65391b33.ctex",
    "res://.godot/imported/defect_shop.png-7cd1b216490239388e248fe3de753032.ctex",
    "res://.godot/imported/restsite_defect.png-b1461c3f515adbce2780a4a5d8a9c408.ctex",
]
CAST_KEYS = HEAD_KEYS[:2]  # battle + shop only
REGIONS = {HEAD_KEYS[0]: (0, 0), HEAD_KEYS[1]: (0, 0), HEAD_KEYS[2]: (0, 0)}
CAST_POS = {HEAD_KEYS[0]: (0, 1676), HEAD_KEYS[1]: (0, 1676)}


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
    return d, entries, order


def remove_white_bg(img, tol=20):
    """Flood-fill white background connected to the border -> transparent."""
    img = img.convert("RGBA")
    px = img.load()
    w, h = img.size
    ref = px[0, 0][:3]
    bg = set()
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            q.append((x, y))
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
    print(f"  white bg removed: {len(bg)} px ({100 * len(bg) / (w * h):.1f}%)")
    return img


def fit_region(art):
    s = min(RW / art.width, RH / art.height)
    nw, nh = round(art.width * s), round(art.height * s)
    art = art.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGBA", (RW, RH), (0, 0, 0, 0))
    canvas.paste(art, ((RW - nw) // 2, (RH - nh) // 2), art)
    print(f"  fit: scale={s:.4f} -> {nw}x{nh} in {RW}x{RH}")
    return canvas


d, entries, order = load_pck(SRC_PCK)
for drop in DROP_ENTRIES:
    print("dropping:", drop)
    order.remove(drop)

art1 = Image.open(IMG1)
print("img1:", art1.size, art1.mode)
if art1.mode != "RGBA":
    art1 = art1.convert("RGBA")
if art1.getextrema()[3][0] == 255:  # fully opaque -> strip white bg
    art1 = remove_white_bg(art1)
head_canvas = fit_region(art1)

art2 = Image.open(IMG2)
print("img2:", art2.size, art2.mode)
art2 = remove_white_bg(art2)
art2.save(os.path.join(W, "img2_cutout.png"))
cast_canvas = fit_region(art2)

pages = {}
for key in HEAD_KEYS:
    blob = entries[key]
    w, h = struct.unpack_from("<II", blob, 8)
    img = Image.open(io.BytesIO(blob[blob.find(b"RIFF"):])).convert("RGBA")
    assert img.size == (w, h)
    hx, hy = REGIONS[key]
    img.paste(Image.new("RGBA", (RW, RH), (0, 0, 0, 0)), (hx, hy))  # clear old pixels
    img.paste(head_canvas, (hx, hy), head_canvas)
    if key in CAST_POS:
        cx, cy = CAST_POS[key]
        img.paste(Image.new("RGBA", (RW, RH), (0, 0, 0, 0)), (cx, cy))
        img.paste(cast_canvas, (cx, cy), cast_canvas)
    buf = io.BytesIO()
    img.save(buf, "WEBP", lossless=True, quality=100, method=6)
    webp = buf.getvalue()
    hdr = bytearray(blob[:0x38])
    struct.pack_into("<I", hdr, 0x34, len(webp))
    entries[key] = bytes(hdr) + webp
    pages[key] = img
    print(f"{key.split('/')[-1]}: rebuilt {len(entries[key])} B (was {len(blob)})")

pcktool.build_pck(OUT_PCK, [(n, entries[n]) for n in order], ref_header_from=SRC_PCK)

# verify: all other entries byte-identical, pages decode, regions correct
d2, e2, o2 = load_pck(OUT_PCK)
assert o2 == order and len(e2) == len(order)
for k in order:
    if k in HEAD_KEYS:
        continue
    assert e2[k] == entries[k] == d2[0:0] or e2[k] == entries[k], f"changed: {k}"
for key in HEAD_KEYS:
    blob = e2[key]
    img = Image.open(io.BytesIO(blob[blob.find(b"RIFF"):]))
    print("verify", key.split("/")[-1], img.format, img.size)
for key, img in pages.items():
    tag = key.split("/")[-1].split("-")[0]
    hx, hy = REGIONS[key]
    img.crop((hx, hy, hx + RW, hy + RH)).save(os.path.join(W, f"prev_head_{tag}.png"))
    if key in CAST_POS:
        cx, cy = CAST_POS[key]
        img.crop((cx, cy, cx + RW, cy + RH)).save(os.path.join(W, f"prev_cast_{tag}.png"))
print("OK", os.path.getsize(OUT_PCK), "bytes")
