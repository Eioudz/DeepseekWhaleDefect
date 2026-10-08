import struct, sys
BASE = r"D:\steam\steamapps\common\Slay the Spire 2\SlayTheSpire2.pck"
d = open(BASE, "rb").read()
fb = struct.unpack_from("<Q", d, 0x18)[0]
io_ = struct.unpack_from("<Q", d, 0x20)[0]
n = struct.unpack_from("<I", d, io_)[0]
p = io_ + 4
E = {}
for _ in range(n):
    pl = struct.unpack_from("<I", d, p)[0]; p += 4
    nm = d[p:p + pl].rstrip(b"\x00").decode("utf-8", "replace"); p += pl
    off, sz = struct.unpack_from("<QQ", d, p); p += 16 + 16 + 4
    E[nm] = (fb + off, sz)
for nm in sys.argv[1:]:
    o, s = E[nm]
    print(f"===== {nm} =====")
    print(d[o:o + s].decode("utf-8", "replace"))