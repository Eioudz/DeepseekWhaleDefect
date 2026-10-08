"""Extract a preview image (PNG, <1MB) for the workshop page from a GST2 ctex in the mod pck."""
import io
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import pcktool
from PIL import Image

PCK = r"d:\12415\Desktop\DeepseekWhaleDefect.pck"
OUT = os.path.join(os.path.dirname(__file__), "whale_workspace", "image.png")

# Candidate entries, best preview first
WANT = [
    "res://.godot/imported/blue_fish_bg.png-f3ce5d6fb90e70fb64cb5e510eecc0a8.ctex",
    "res://.godot/imported/char_select_defect.png-ea5c993e940152de691cc0010360b.ctex",
]


def extract_webp(blob):
    i = blob.find(b"RIFF")
    if i < 0 or blob[i + 8:i + 12] != b"WEBP":
        return None
    size = struct.unpack_from("<I", blob, i + 4)[0]
    return blob[i:i + 8 + size]


def main():
    meta = pcktool.parse_pck(PCK)
    blobs = {e[0]: pcktool.extract(meta, e[0]) for e in meta["entries"]}
    img = None
    used = None
    for w in WANT:
        b = blobs.get(w)
        if b is None:
            continue
        webp = extract_webp(b)
        if webp:
            img = Image.open(io.BytesIO(webp))
            used = w
            break
    assert img is not None, "no preview source found"
    print("source:", used, "size:", img.size, "mode:", img.mode)

    # Workshop preview: keep reasonable dimensions, ensure < 1MB
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGBA")
    max_side = 1280
    if max(img.size) > max_side:
        ratio = max_side / max(img.size)
        img = img.resize((round(img.width * ratio), round(img.height * ratio)), Image.LANCZOS)

    # Try progressively; PNG of artwork can exceed 1MB, so quantize if needed
    quality_attempts = [
        dict(optimize=True),
    ]
    saved = False
    for kw in quality_attempts:
        img.save(OUT, "PNG", **kw)
        if os.path.getsize(OUT) < 1_000_000:
            saved = True
            break
    if not saved:
        # fall back to RGB (art preview doesn't need alpha) with quantization
        rgb = Image.new("RGB", img.size, (0, 0, 0))
        rgb.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        pal = rgb.convert("P", palette=Image.ADAPTIVE, colors=256)
        pal.save(OUT, "PNG", optimize=True)
    print("saved", OUT, os.path.getsize(OUT), "bytes, dimensions:", img.size)


if __name__ == "__main__":
    main()
