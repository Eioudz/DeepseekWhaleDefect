"""Verify the cookie relic icons in the built pck, render mock previews, install."""
import io
import os
import shutil
import struct
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
NEW = os.path.join(HERE, "DeepseekWhaleDefect.pck.new")
MODS = r"d:\steam\steamapps\common\Slay the Spire 2\mods\DeepseekWhaleDefect.pck"
BAK = os.path.join(HERE, "_prev_cookie_DeepseekWhaleDefect.pck")


def load(path):
    d = open(path, "rb").read()
    fb = struct.unpack_from("<Q", d, 0x18)[0]
    io_ = struct.unpack_from("<Q", d, 0x20)[0]
    n = struct.unpack_from("<I", d, io_)[0]
    p = io_ + 4
    e = {}
    for _ in range(n):
        pl = struct.unpack_from("<I", d, p)[0]; p += 4
        nm = d[p:p + pl].rstrip(b"\x00").decode(); p += pl
        off, sz = struct.unpack_from("<QQ", d, p); p += 16 + 16 + 4
        e[nm] = d[fb + off:fb + off + sz]
    return e


new = load(NEW)
print("entries:", len(new))
print(new["images/relics/yummy_cookie_defect.png.remap"].decode().strip())
print(new["images/atlases/relic_atlas.sprites/yummy_cookie_defect.tres.remap"].decode().strip())
print(new["images/atlases/relic_outline_atlas.sprites/yummy_cookie_defect.tres.remap"].decode().strip())
for stem in ("yummy_cookie_defect", "yummy_cookie_defect_outline"):
    ct = new[[k for k in new if k.startswith("DeepseekWhaleDefect/imported/")
              and new[f"DeepseekWhaleDefect/relics/{stem}.png.import"].decode()
              .find(k.replace("DeepseekWhaleDefect/", "res://DeepseekWhaleDefect/")) >= 0
              ][0]]
    print(stem, "ctex", len(ct), "ifmt", struct.unpack_from("<I", ct, 0x30)[0])

imp = new["DeepseekWhaleDefect/relics/yummy_cookie_defect.png.import"].decode()
icon_res = imp.split('path="')[1].split('"')[0].replace("res://", "")
imp_o = new["DeepseekWhaleDefect/relics/yummy_cookie_defect_outline.png.import"].decode()
out_res = imp_o.split('path="')[1].split('"')[0].replace("res://", "")
icon = Image.open(io.BytesIO(new[icon_res][new[icon_res].find(b"RIFF"):])).convert("RGBA")
outline = Image.open(io.BytesIO(new[out_res][new[out_res].find(b"RIFF"):])).convert("RGBA")
print("icon", icon.size, icon.mode, "outline", outline.size, outline.mode)


def fit(img, box):
    s = min(box / img.width, box / img.height)
    return img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)


def slot(bg, box=60):
    """Simulate TextureRect 60x60, expand_mode=IGNORE_SIZE, KEEP_ASPECT_CENTERED:
    outline drawn behind the icon, both fitted to the box."""
    c = Image.new("RGBA", (box, box), bg)
    o = fit(outline, box)
    c.alpha_composite(o, ((box - o.width) // 2, (box - o.height) // 2))
    i = fit(icon, box)
    c.alpha_composite(i, ((box - i.width) // 2, (box - i.height) // 2))
    return c.convert("RGB")


# a) in-game size on the relic bar (dark) and on a light panel
row = Image.new("RGB", (60 * 3 + 40, 60), (200, 200, 205))
row.paste(slot((34, 34, 40, 255)), (10, 0))
row.paste(slot((24, 24, 28, 255)), (80, 0))
row.paste(slot((238, 238, 240, 255)), (150, 0))
row.resize((row.width * 4, row.height * 4), Image.NEAREST).save(HERE + r"\_cookie_ingame_60.png")

# b) big (BigIcon) view on dark
big = Image.new("RGB", (512, 512), (26, 26, 30))
o = fit(outline, 480).convert("RGBA")
big.paste(o, (256 - o.width // 2, 256 - o.height // 2), o)
i = fit(icon, 480).convert("RGBA")
big.paste(i, (256 - i.width // 2, 256 - i.height // 2), i)
big.save(HERE + r"\_cookie_big_preview.png")
print("wrote _cookie_ingame_60.png / _cookie_big_preview.png")

if os.path.exists(MODS) and not os.path.exists(BAK):
    shutil.copy2(MODS, BAK)
    print("backed up:", BAK, os.path.getsize(BAK), "bytes")
shutil.copy2(NEW, MODS)
print("installed:", os.path.getsize(MODS), "bytes ->", MODS)