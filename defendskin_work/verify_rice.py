"""Compose setup-pose preview with rice bowl from the rebuilt pck."""
import io
import os
import struct
import sys

from PIL import Image

W = os.path.dirname(os.path.abspath(__file__))
OUT_PCK = os.path.join(W, "DeepseekWhaleDefect.pck.new")
REST_PNG = "res://.godot/imported/restsite_defect.png-b1461c3f515adbce2780a4a5d8a9c408.ctex"

d = open(OUT_PCK, "rb").read()
file_base = struct.unpack_from("<Q", d, 0x18)[0]
idx_off = struct.unpack_from("<Q", d, 0x20)[0]
n = struct.unpack_from("<I", d, idx_off)[0]
p = idx_off + 4
blob = None
for _ in range(n):
    plen = struct.unpack_from("<I", d, p)[0]
    p += 4
    name = d[p:p + plen].rstrip(b"\x00").decode()
    p += plen
    off, size = struct.unpack_from("<QQ", d, p)
    p += 16
    p += 16
    p += 4
    if name == REST_PNG:
        blob = d[file_base + off:file_base + off + size]
page = Image.open(io.BytesIO(blob[blob.find(b"RIFF"):])).convert("RGBA")

REGIONS = {
    "shadow": (0, 656, 414, 98), "tail": (65, 756, 74, 76),
    "hair_l": (0, 474, 172, 180), "hair_r": (238, 280, 157, 183),
    "leg_l": (187, 756, 44, 37), "leg_r": (141, 756, 44, 38),
    "bod": (0, 280, 236, 192), "arm_l": (416, 656, 63, 82),
    "arm_r": (0, 756, 63, 78), "head": (0, 0, 365, 278),
    "rice": (366, 0, 144, 105),
}
imgs = {k: page.crop((x, y, x + w, y + h)) for k, (x, y, w, h) in REGIONS.items()}

SLOTS = [
    ("shadow", (0, 0), (0, -75), (227.7, 53.9)),
    ("tail", (-40, -8), (0, 0), (40.7, 41.8)),
    ("hair_l", (-62, 56), (0, 0), (94.6, 99.0)),
    ("hair_r", (62, 56), (0, 0), (86.35, 100.65)),
    ("leg_l", (-25, -32), (0, 0), (24.2, 20.35)),
    ("leg_r", (25, -30), (0, 0), (24.2, 20.9)),
    ("bod", (0, 30), (0, 2), (129.8, 105.6)),
    ("arm_l", (-40, -46), (0, 0), (34.65, 45.1)),
    ("arm_r", (40, -46), (0, 0), (34.65, 42.9)),
    ("head", (0, 150), (0, 0), (200.75, 152.9)),
    ("rice", (0, 30), (0, 15), (79.2, 57.75)),
]
SC = 2.0
canvas = Image.new("RGBA", (560, 560), (40, 44, 60, 255))
for name, bone, off, size in SLOTS:
    img = imgs[name].resize((round(size[0] * SC), round(size[1] * SC)), Image.LANCZOS)
    cx = 280 + (bone[0] + off[0]) * SC
    cy = 400 - (bone[1] + off[1]) * SC
    canvas.alpha_composite(img, (round(cx - img.width / 2), round(cy - img.height / 2)))
canvas.save(os.path.join(W, "mock_restsite.png"))
print("mock saved")
