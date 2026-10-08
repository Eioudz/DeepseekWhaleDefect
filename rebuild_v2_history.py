
import json, os
from PIL import Image

SRC = r"D:\12415\Desktop\新建文件夹"
DST = r"C:\Users\12415\Documents\trae_projects\slay\parts"

scale = 0.55

layout = {
    "head":   {"cx": 147, "cy": 120, "src": "head.png"},
    "bod":    {"cx": 158, "cy": 350, "src": "body.png"},
    "hair_l": {"cx": 75,  "cy": 290, "src": "hair_l.png"},
    "hair_r": {"cx": 241, "cy": 290, "src": "hair_r.png"},
    "arm_l":  {"cx": 85,  "cy": 250, "src": "arm_l.png"},
    "arm_r":  {"cx": 231, "cy": 250, "src": "arm_r.png"},
    "leg_l":  {"cx": 135, "cy": 450, "src": "leg_l.png"},
    "leg_r":  {"cx": 181, "cy": 450, "src": "leg_r.png"},
    "tail":   {"cx": 350, "cy": 450, "src": "tail.png"},
}

meta = {
    "scale": 0.2,
    "img_w": 336,
    "img_h": 442,
    "origin": {"x": 158, "y": 417},
    "parts": {}
}

for name, info in layout.items():
    im = Image.open(os.path.join(SRC, info["src"])).convert("RGBA")
    bbox = im.getbbox()
    cropped = im.crop(bbox)
    cw, ch = cropped.size
    nw = max(1, round(cw * scale))
    nh = max(1, round(ch * scale))
    resized = cropped.resize((nw, nh), Image.LANCZOS)
    resized.save(os.path.join(DST, f"{name}.png"))
    
    cx, cy = info["cx"], info["cy"]
    meta["parts"][name] = {
        "bbox": [round(cx - nw/2), round(cy - nh/2), round(cx + nw/2), round(cy + nh/2)],
        "w": nw,
        "h": nh
    }
    print(f"{name}: {cw}x{ch} -> {nw}x{nh}  center=({cx},{cy})")

# Shadow
meta["parts"]["shadow"] = {"bbox": None, "w": 414, "h": 98}

json.dump(meta, open("parts_meta.json", "w"), indent=1)
print("meta saved")
