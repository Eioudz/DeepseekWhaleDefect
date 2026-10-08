"""Cut the whale-girl head out of the user's messy-background art for the
YUMMY_COOKIE (defect) relic icon.

Outputs (in this folder):
  _cookie_cut.png     256x256 RGBA icon
  _cookie_outline.png 256x256 RGBA white silhouette (relic outline slot)
  _cookie_cut_zoom.png / _cookie_cut_dark.png / _cookie_cut_magenta.png previews
"""
import numpy as np
from PIL import Image, ImageDraw

SRC = r"d:\12415\Desktop\MEITU_20261008_195314108 (3).png"
OUT = r"c:\Users\12415\Documents\trae_projects\slay\defendskin_work"
CANVAS = 256
CONTENT = 232          # icon longest side inside the 256 canvas (room for outline)
OUTLINE_GROW = 6       # px the white silhouette extends beyond the icon (in canvas space)
ALPHA_T = 128


def dilate(m, it=1):
    for _ in range(it):
        p = np.pad(m, 1)
        m = m | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return m


def erode(m, it=1):
    return ~dilate(~m, it)


def largest_component(mask):
    core = erode(mask, 4)
    idx = int(np.argmax(core))
    seed = np.zeros_like(mask)
    seed.flat[idx] = mask.flat[idx]
    assert seed.any(), "no solid seed found"
    cur = seed
    while True:
        nxt = dilate(cur) & mask
        if nxt.sum() == cur.sum():
            return cur
        cur = nxt


img = Image.open(SRC).convert("RGBA")
arr = np.asarray(img).astype(np.uint8)
H, W = arr.shape[:2]
al = arr[..., 3]
mask = al >= ALPHA_T
print("raw mask px", int(mask.sum()), f"({mask.mean()*100:.1f}%)")

head = largest_component(mask)
print("head px", int(head.sum()))

# fill interior holes (flare bits enclosed by hair/outline)
pad = Image.new("L", (W + 2, H + 2), 0)
pad.paste(Image.fromarray((head * 255).astype(np.uint8)), (1, 1))
ImageDraw.floodfill(pad, (0, 0), 128)
outside = np.asarray(pad)[1:-1, 1:-1] == 128
solid = head | ~outside
print("solid px", int(solid.sum()), "holes filled", int(solid.sum() - head.sum()))

# --- alpha: keep original antialiasing inside the silhouette, kill the rest ---
alpha = np.where(solid, al, 0).astype(np.uint8)
# the out-of-silhouette RGB is the dirty white haze; bleed subject colour outward
# so bilinear filtering never picks up white.
rgb = arr[..., :3].copy()
rgb[~solid] = 0
opaque = solid
for _ in range(24):
    acc = np.zeros_like(rgb, dtype=np.uint32)
    cnt = np.zeros((H, W), np.uint32)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        s = np.roll(opaque, (dy, dx), (0, 1))
        sr = np.roll(rgb, (dy, dx), (0, 1))
        acc += sr * s[..., None]
        cnt += s
    fill = (~opaque) & (cnt > 0)
    if not fill.any():
        break
    rgb[fill] = (acc[fill] / cnt[fill][:, None]).astype(np.uint8)
    opaque = opaque | fill
bleed_px = int(opaque.sum() - solid.sum())
print("alpha-bleed px", bleed_px)

cut = np.dstack([rgb, alpha])
# premultiplied resize (avoids any residual edge halo), then unpremultiply
ys, xs = np.where(solid)
x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
print("content bbox", (x0, y0, x1, y1), "size", (x1 - x0, y1 - y0))
crop = cut[y0:y1, x0:x1]

s = CONTENT / max(crop.shape[0], crop.shape[1])
nw, nh = max(1, round(crop.shape[1] * s)), max(1, round(crop.shape[0] * s))
pm = crop.astype(np.float32)
pm[..., :3] *= pm[..., 3:4] / 255.0
pm_img = Image.fromarray(np.clip(pm, 0, 255).astype(np.uint8)).resize((nw, nh), Image.LANCZOS)
pm = np.asarray(pm_img).astype(np.float32)
a2 = pm[..., 3:4]
pm[..., :3] = np.where(a2 > 0, pm[..., :3] * 255.0 / np.maximum(a2, 1e-6), pm[..., :3])
icon_small = np.dstack([np.clip(pm[..., :3], 0, 255), pm[..., 3]]).astype(np.uint8)
print(f"scaled {nw}x{nh} (scale {s:.4f})")

icon = np.zeros((CANVAS, CANVAS, 4), np.uint8)
ox, oy = (CANVAS - nw) // 2, (CANVAS - nh) // 2
icon[oy:oy + nh, ox:ox + nw] = icon_small
icon_mask = icon[..., 3] > 0

# --- outline: white silhouette grown a few px ---
out_mask = dilate(icon_mask, OUTLINE_GROW)
outline = np.zeros((CANVAS, CANVAS, 4), np.uint8)
outline[..., :3] = 255
outline[..., 3] = np.where(out_mask, 255, 0)
print("outline grow px", OUTLINE_GROW, "outline px", int(out_mask.sum()))

Image.fromarray(icon, "RGBA").save(OUT + r"\_cookie_cut.png")
Image.fromarray(outline, "RGBA").save(OUT + r"\_cookie_outline.png")


def compose(icon, outline, bg):
    canvas = Image.new("RGBA", (CANVAS, CANVAS), bg)
    canvas.alpha_composite(Image.fromarray(outline, "RGBA"))
    canvas.alpha_composite(Image.fromarray(icon, "RGBA"))
    return canvas.convert("RGB")


img_cut = Image.fromarray(icon, "RGBA")
img_out = Image.fromarray(outline, "RGBA")
compose(icon, outline, (34, 34, 40, 255)).resize((512, 512), Image.NEAREST).save(OUT + r"\_cookie_cut_dark.png")
compose(icon, outline, (255, 0, 255, 255)).resize((512, 512), Image.NEAREST).save(OUT + r"\_cookie_cut_magenta.png")
# as actually seen in game: 60x60 with the outline behind
compose(icon, outline, (34, 34, 40, 255)).resize((60, 60), Image.LANCZOS).resize((300, 300), Image.NEAREST).save(OUT + r"\_cookie_game_60.png")
img_cut.resize((512, 512), Image.NEAREST).save(OUT + r"\_cookie_cut_zoom.png")
print("saved previews")