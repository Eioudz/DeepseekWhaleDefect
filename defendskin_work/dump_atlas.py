"""Dump atlas texts + decode battle/shop atlas pages from desktop whale pck."""
import io
import os
import struct

from PIL import Image

W = os.path.dirname(os.path.abspath(__file__))
PCK = r"d:\12415\Desktop\DeepseekWhaleDefect.pck"

d = open(PCK, "rb").read()
file_base = struct.unpack_from("<Q", d, 0x18)[0]
idx_off = struct.unpack_from("<Q", d, 0x20)[0]
n = struct.unpack_from("<I", d, idx_off)[0]
p = idx_off + 4
entries = {}
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

for key in entries:
    if key.endswith(".spatlas"):
        txt = entries[key].decode("utf-8", "replace")
        print("=" * 20, key)
        print(txt)
        open(os.path.join(W, key.split("/")[-1] + ".txt"), "w", encoding="utf-8").write(txt)

for key in [k for k in entries if k.endswith(".ctex") and ("defect.png-" in k or "defect_shop" in k)]:
    blob = entries[key]
    w, h = struct.unpack_from("<II", blob, 8)
    img = Image.open(io.BytesIO(blob[blob.find(b"RIFF"):]))
    print(key.split("/")[-1], "header", w, "x", h, "| decoded", img.format, img.size, img.mode)
    img.save(os.path.join(W, key.split("/")[-1].split("-")[0] + "_page.png"))
