"""Verify the built pck (head sizes, skeleton parse) and install it."""
import io
import os
import shutil
import struct
import subprocess
import sys

from PIL import Image

W = os.path.dirname(os.path.abspath(__file__))
NEW = os.path.join(W, "DeepseekWhaleDefect.pck.new")
MODS = r"d:\steam\steamapps\common\Slay the Spire 2\mods\DeepseekWhaleDefect.pck"
DESK = r"d:\12415\Desktop\DeepseekWhaleDefect.pck"
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


new = load_pck(NEW)
b = new[BATTLE]
page = Image.open(io.BytesIO(b[b.find(b"RIFF"):])).convert("RGBA")
print("battle page:", page.size)
RECTS = {"head": (0, 0), "hit_head": (0, 280), "low_head": (0, 560),
         "attack_head": (0, 1396), "cast_head": (0, 1676)}
tiles = []
for name, (x, y) in RECTS.items():
    crop = page.crop((x, y, x + 365, y + 278))
    print(f"{name:12s} bbox={crop.getbbox()}")
    tiles.append((name, crop))
sheet = Image.new("RGBA", (365 * 3 + 20, 278 * 2 + 10), (30, 34, 44, 255))
for i, (name, crop) in enumerate(tiles):
    sheet.alpha_composite(crop, ((i % 3) * (365 + 10), (i // 3) * (278 + 10)))
sheet.save(os.path.join(W, "verify_heads_new.png"))
print("order:", [n for n, _ in tiles])

r = subprocess.run([sys.executable, os.path.join(os.path.dirname(W), "parse_skel2.py"),
                    os.path.join(W, "restsite_defect_rice.skel")],
                   capture_output=True, text=True)
print("skel parse rc:", r.returncode)
print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-400:])

shutil.copy2(NEW, MODS)
shutil.copy2(NEW, DESK)
print("installed:", os.path.getsize(MODS), "bytes ->", MODS)