import struct

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

samples = {
    "card_strike(ours)": open(r"c:\Users\12415\Documents\trae_projects\slay\defendskin_work\strike_ctex.bin", "rb").read(),
    "card_zap(base)": d[E[".godot/imported/zap.png-bd0bd069b08ff9bdf4f983f7b3d2e0b0.ctex"][0]:][:0x40],
    "relic_bptc": d[E[".godot/imported/yummy_cookie_defect.png-8a68b24403a84b3852d2b357fa31151f.bptc.ctex"][0]:][:0x40],
}
for label, blob in samples.items():
    print(f"### {label}  (full size {len(blob) if label!='relic_bptc' else E[chr(46)+'godot/imported/yummy_cookie_defect.png-8a68b24403a84b3852d2b357fa31151f.bptc.ctex'][1]})")
    for off in range(0, 0x40, 4):
        b = blob[off:off + 4]
        print(f"  {off:#04x}: {b.hex()}  u32le={struct.unpack('<I', b)[0]:<12} "
              f"u16le=({struct.unpack_from('<H', b, 0)[0]},{struct.unpack_from('<H', b, 2)[0]})")
    print()