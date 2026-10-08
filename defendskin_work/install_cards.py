"""Decode the two new card portraits from the built pck and render a check sheet."""
import io
import os
import shutil
import struct
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
NEW = os.path.join(HERE, "DeepseekWhaleDefect.pck.new")
MODS = r"d:\steam\steamapps\common\Slay the Spire 2\mods\DeepseekWhaleDefect.pck"
BAK = os.path.join(HERE, "_prev_dualcast_DeepseekWhaleDefect.pck")


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
sheet = Image.new("RGBA", (1000, 760 * 2 + 20), (20, 20, 24, 255))
for i, (stem, art) in enumerate((("dualcast", r"d:\12415\Downloads\MEITU_20261008_193419724.jpg"),
                                 ("zap", r"d:\12415\Downloads\MEITU_20261008_093708976.jpg"))):
    # find the ctex referenced by this card's .import
    imp = new[f"DeepseekWhaleDefect/card_portraits/defect/{stem}.png.import"].decode()
    ctex_res = imp.split('path="')[1].split('"')[0].replace("res://", "")
    img = Image.open(io.BytesIO(new[ctex_res][new[ctex_res].find(b"RIFF"):])).convert("RGB")
    print(stem, "->", ctex_res, img.size)
    sheet.paste(img.resize((1000, 760)), (0, i * (760 + 20)))
sheet.save(os.path.join(HERE, "verify_cards_new.png"))
print("wrote verify_cards_new.png")

# backup then install
if os.path.exists(MODS) and not os.path.exists(BAK):
    shutil.copy2(MODS, BAK)
    print("backed up:", BAK)
shutil.copy2(NEW, MODS)
print("installed:", os.path.getsize(MODS), "bytes ->", MODS)