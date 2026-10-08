"""Save head-region crops for visual comparison."""
import io
import os
import struct

from PIL import Image

W = os.path.dirname(os.path.abspath(__file__))
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


m = page(load_pck(MODS), BATTLE)
w = page(load_pck(WS), BATTLE)
R = {"orig_head": (w, 0, 0), "orig_hit": (w, 0, 280), "orig_low": (w, 0, 560),
     "orig_attack": (w, 0, 1396), "orig_cast": (w, 0, 1676),
     "cur_head": (m, 0, 0), "cur_cast": (m, 0, 1676)}
canvas = Image.new("RGBA", (365 * 4 + 30, 278 * 2 + 20), (30, 34, 44, 255))
order = ["orig_head", "cur_head", "orig_cast", "cur_cast", "orig_low", "orig_hit"]
for i, name in enumerate(order):
    src, x, y = R[name]
    crop = src.crop((x, y, x + 365, y + 278))
    crop.save(os.path.join(W, f"cmp_{name}.png"))
    canvas.alpha_composite(crop, ((i % 4) * (365 + 10), (i // 4) * (278 + 10)))
canvas.save(os.path.join(W, "cmp_heads.png"))
print("order:", order)
print("saved cmp_heads.png")

for name in ("orig_head", "cur_head", "orig_cast", "cur_cast"):
    src, x, y = R[name]
    crop = src.crop((x, y, x + 365, y + 278)).convert("RGBA")
    a = crop.getchannel("A")
    bbox = a.getbbox()
    px = a.load()
    tot = sx = sy = 0
    for yy in range(278):
        for xx in range(365):
            v = px[xx, yy]
            if v:
                tot += v
                sx += v * xx
                sy += v * yy
    print(f"{name:10s} bbox={bbox} centroid=({sx / tot:.1f},{sy / tot:.1f}) "
          f"box-centre=(182.5,139.0)")