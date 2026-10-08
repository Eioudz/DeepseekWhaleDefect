"""Extract the strike_defect card chain from pristine DefectSkin.pck.bak."""
import os
import struct

W = os.path.dirname(os.path.abspath(__file__))
d = open(r"d:\12415\Desktop\DefectSkin.pck.bak", "rb").read()
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
    p += 16
    p += 4
    entries.append((name, off, size))

ctex_path = None
for name, off, size in entries:
    if "strike_defect" in name:
        blob = d[file_base + off:file_base + off + size]
        open(os.path.join(W, name.replace("/", "__")), "wb").write(blob)
        print(name, size)
        if name.endswith(".png.import"):
            text = blob.decode()
            print(text)
            ctex_path = text.split('path="')[1].split('"')[0].replace("res://", "")
    if name == ctex_path:
        blob = d[file_base + off:file_base + off + size]
        open(os.path.join(W, "strike_ctex.bin"), "wb").write(blob)
        w, h = struct.unpack_from("<II", blob, 8)
        print("ctex:", name, size, f"{w}x{h}",
              "flags", hex(struct.unpack_from("<I", blob, 0x10)[0]))
