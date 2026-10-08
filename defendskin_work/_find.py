import struct, sys

path = sys.argv[1]
d = open(path, "rb").read()
fb = struct.unpack_from("<Q", d, 0x18)[0]
io_ = struct.unpack_from("<Q", d, 0x20)[0]
n = struct.unpack_from("<I", d, io_)[0]
p = io_ + 4
pats = sys.argv[2:]
for i in range(n):
    pl = struct.unpack_from("<I", d, p)[0]; p += 4
    nm = d[p:p + pl].rstrip(b"\x00").decode("utf-8", "replace"); p += pl
    off, sz = struct.unpack_from("<QQ", d, p); p += 16; p += 16; p += 4
    low = nm.lower()
    if any(pt.lower() in low for pt in pats):
        print(sz, nm)