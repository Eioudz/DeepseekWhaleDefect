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

for nm in ("images/relics/yummy_cookie_defect.png.import",
           "images/atlases/relic_atlas.sprites/yummy_cookie_defect.tres",
           "images/atlases/relic_outline_atlas.sprites/yummy_cookie_defect.tres",
           "src/Core/Models/Relics/YummyCookie.cs"):
    o, s = E[nm]
    print(f"=== {nm} ({s}B) ===")
    print(d[o:o + s].decode("utf-8", "replace"))

ct = ".godot/imported/yummy_cookie_defect.png-8a68b24403a84b3852d2b357fa31151f.bptc.ctex"
o, s = E[ct]
blob = d[o:o + s]
print("=== ctex ===", "size", s)
print("magic", blob[:4])
print("header hex", blob[:0x40].hex())
print("w,h@8", struct.unpack_from("<II", blob, 8))
print("u32@0x10", hex(struct.unpack_from("<I", blob, 0x10)[0]))
print("u32@0x2c", hex(struct.unpack_from("<I", blob, 0x2c)[0]), "u32@0x30", hex(struct.unpack_from("<I", blob, 0x30)[0]))
print("RIFF at", blob.find(b"RIFF"), "has WebP", b"WEBP" in blob[:100])