"""Swap the low-health (`low_head`) face in the battle and shop atlas pages.

The low_health_loop head swap itself works fine (the skeleton points the head
slot at `low_head` and the game enters that animation at HP <= 25%), but the
face that was shipped there is a very subtle "aggrieved" drawing -- in game it
reads as if the head never changed at all. This restores the original wide-open
crying face.

Pipeline:
 1. Decode the battle/shop pages (lossless WebP inside a GST2 ctex).
 2. Clear the 365x278 `low_head` rectangle and paste the crying art over it (the
    art is authored at exactly that size). Clearing first keeps nothing of the
    old face where the new art is transparent.
 3. Colour-bleed the region so the atlas' linear filter cannot sample a rim.
 4. Re-encode lossless WebP, wrap GST2 (same 56-byte header, patched length).
 5. Every other entry is copied through byte for byte.
"""
import io
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcktool
from PIL import Image, ImageChops

W = os.path.dirname(os.path.abspath(__file__))
PCK = os.path.join(W, "whale_workspace", "content", "DeepseekWhaleDefect.pck")
OUT = os.path.join(W, "defendskin_work", "DeepseekWhaleDefect.pck.new")
LOW_ART = os.path.join(W, "investigate", "regions", "low_head.png")

BATTLE_CTEX_KEY = "res://.godot/imported/defect.png-d9a4219263a117f0ba83c83a65391b33.ctex"
SHOP_CTEX_KEY = "res://.godot/imported/defect_shop.png-7cd1b216490239388e248fe3de753032.ctex"
REGION = (0, 560, 365, 278)  # x, y, w, h of low_head in the 512x1954 pages


def decode_page(ctex_blob):
    off = ctex_blob.find(b"RIFF")
    size = struct.unpack_from("<I", ctex_blob, off + 4)[0]
    return Image.open(io.BytesIO(ctex_blob[off:off + 8 + size])).convert("RGBA")


def encode_ctex(page_img, header_template):
    buf = io.BytesIO()
    page_img.save(buf, "WEBP", lossless=True, quality=100, method=6)
    webp = buf.getvalue()
    assert webp[:4] == b"RIFF"
    hdr = bytearray(header_template[:0x38])
    struct.pack_into("<I", hdr, 0x34, len(webp))
    return bytes(hdr) + webp


def alpha_bleed(img, iterations=8):
    """Smear the silhouette colours over the transparent texels.

    The atlas is sampled with linear filtering, so a transparent texel still
    contributes its RGB to the samples just outside the sprite. Edge colours are
    extended into the empty space; fully transparent pixels keep alpha 0 and
    visible pixels are never touched.
    """
    img = img.convert("RGBA")
    rgb = img.convert("RGB")
    alpha = img.getchannel("A")
    known = alpha.point(lambda v: 255 if v > 0 else 0)
    for _ in range(iterations):
        grown = known
        rgb_new = rgb.copy()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            cand = ImageChops.multiply(ImageChops.invert(known),
                                       ImageChops.offset(known, dx, dy))
            if cand.getbbox() is None:
                continue
            rgb_new.paste(ImageChops.offset(rgb, dx, dy), (0, 0), cand)
            grown = ImageChops.lighter(grown, cand)
        rgb = rgb_new
        known = grown
    return Image.merge("RGBA", (*rgb.split(), alpha))


def same_geometry(a, b):
    """True when alpha is identical and RGB matches wherever alpha > 0."""
    na = np.asarray(a.convert("RGBA"), dtype=np.uint8)
    nb = np.asarray(b.convert("RGBA"), dtype=np.uint8)
    if not np.array_equal(na[..., 3], nb[..., 3]):
        return False
    vis = na[..., 3] > 0
    return np.array_equal(na[..., :3][vis], nb[..., :3][vis])


def main():
    low = Image.open(LOW_ART).convert("RGBA")
    rw, rh = REGION[2], REGION[3]
    assert low.size == (rw, rh), f"low_head art must be {rw}x{rh}, got {low.size}"

    meta = pcktool.parse_pck(PCK)
    out_entries = []
    for name, blob in ((e[0], pcktool.extract(meta, e[0])) for e in meta["entries"]):
        if name in (BATTLE_CTEX_KEY, SHOP_CTEX_KEY):
            page = decode_page(blob)
            x, y = REGION[0], REGION[1]
            box = (x, y, x + rw, y + rh)
            page.paste(Image.new("RGBA", (rw, rh), (0, 0, 0, 0)), (x, y))
            # No mask here: the rect is already fully transparent, and pasting
            # with `low` as its own mask would apply the mask to the alpha
            # channel too (alpha -> alpha^2/255), rounding 254 down to 253.
            page.paste(low, (x, y))
            page.paste(alpha_bleed(page.crop(box)), box)
            blob = encode_ctex(page, blob[:0x38])
        out_entries.append((name, blob))

    pcktool.build_pck(OUT, out_entries, ref_header_from=PCK)
    print("rebuilt pck:", os.path.getsize(OUT), "bytes")

    # Verify: low_head now matches the crying art in both pages, and every other
    # region of both pages is byte-for-byte unchanged.
    m2 = pcktool.parse_pck(OUT)
    x, y = REGION[0], REGION[1]
    box = (x, y, x + rw, y + rh)
    for key in (BATTLE_CTEX_KEY, SHOP_CTEX_KEY):
        before = decode_page(pcktool.extract(meta, key))
        after = decode_page(pcktool.extract(m2, key))
        assert same_geometry(after.crop(box), low), f"{key}: low_head not applied"
        a, b = before.copy(), after.copy()
        a.paste(Image.new("RGBA", (rw, rh), (0, 0, 0, 0)), (x, y))
        b.paste(Image.new("RGBA", (rw, rh), (0, 0, 0, 0)), (x, y))
        assert same_geometry(a, b), f"{key}: other regions changed"
        print("ok:", key.split("/")[-1])
    print("verified: crying low_head in battle+shop; rest of both pages untouched")


if __name__ == "__main__":
    main()