"""Add an attack-specific head: new atlas region + AttachmentTimeline on attack.

Pipeline (purely additive, all existing numeric data preserved):
 1. Parse the live spskel from the mod pck into capture objects.
 2. Add "attack_head" setup-pose name and a region attachment on the head
    slot in the default skin (geometry copied from the normal head).
 3. Add a head AttachmentTimeline to attack: attack_head at t=0, head at end.
 4. Expand the atlas page 512x1394 -> 512x1674 and place attack_head at
    (0,1396,365,278); patch GST2 header height fields; update both spatlas.
 5. Rebuild the pck (battle + shop share bytes for ctex/spskel).
"""
import io
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(__file__))
import pcktool
from PIL import Image

W = os.path.dirname(__file__)
PCK = os.path.join(W, "whale_workspace", "content", "DeepseekWhaleDefect.pck")
NEW_ART = r"d:\12415\Desktop\MEITU_20260930_175059895.png"

BATTLE_CTEX = "res://.godot/imported/defect.png-d9a4219263a117f0ba83c83a65391b33.ctex"
SHOP_CTEX = "res://.godot/imported/defect_shop.png-7cd1b216490239388e248fe3de753032.ctex"
BATTLE_SPATLAS = "res://.godot/imported/defect.atlas-d4a29937acf4aaaf137b95ee851d8a50.spatlas"
SHOP_SPATLAS = "res://.godot/imported/defect_shop.atlas-3f96406f9a6da27430b19860989128f7.spatlas"
SPSKEL = "res://.godot/imported/defect.skel-5dba1374f717ab634fbb5c1941158597.spskel"

OLD_H = 1394
NEW_H = 1674
ATTACK_HEAD_REGION = (0, 1396, 365, 278)


# ----------------------------------------------------------- spskel parser
class R:
    def __init__(self, data):
        self.d = data
        self.p = 0

    def byte(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def f32(self):
        v = struct.unpack_from(">f", self.d, self.p)[0]
        self.p += 4
        return v

    def varint(self):
        b = self.byte()
        result = b & 0x7F
        shift = 7
        while b & 0x80:
            b = self.byte()
            result |= (b & 0x7F) << shift
            shift += 7
        return result

    def zigzag(self):
        v = self.varint()
        return (v >> 1) ^ -(v & 1)

    def string(self):
        n = self.varint()
        if n == 0:
            return None
        raw = self.d[self.p:self.p + n - 1]
        self.p += n - 1
        return raw.decode("utf-8", errors="replace")


def parse_skin_attachment(r):
    """Capture one skin attachment generically (region/mesh/path/sequence)."""
    name_ref = r.varint()
    flags = r.byte()
    att = {"name_ref": name_ref, "flags": flags}
    if flags & 0x04:
        att["rotation"] = r.f32()
    att["x"] = r.f32()
    att["y"] = r.f32()
    att["sx"] = r.f32()
    att["sy"] = r.f32()
    att["w"] = r.f32()
    att["h"] = r.f32()
    if flags & 0x01:
        att["path"] = r.string()
    if flags & 0x08:
        att["color"] = [r.byte() for _ in range(4)]
    if flags & 0x10:
        att["seq_f"] = [r.f32(), r.f32()]
        att["seq_v"] = [r.varint(), r.varint()]
    return att


BONE_TL_VALUES = {0: 1, 1: 2, 2: 2, 3: 2}


def parse_bone_timeline(r):
    tt = r.byte()
    frame_n = r.varint()
    bezier_n = r.varint()
    nval = BONE_TL_VALUES[tt]
    frames = []
    for fi in range(frame_n):
        t = r.f32()
        vals = [r.f32() for _ in range(nval)]
        curve = r.byte() if fi > 0 else None
        frames.append({"t": t, "vals": vals, "curve": curve})
    beziers = []
    for _ in range(bezier_n):
        beziers.append([r.f32() for _ in range(nval * 6)])
    return {"type": tt, "frames": frames, "beziers": beziers}


def parse_anim(r):
    name = r.string()
    total = r.varint()

    slot_groups = []
    sg_n = r.varint()
    for _ in range(sg_n):
        slot_i = r.varint()
        tl_n = r.varint()
        tls = []
        for _ in range(tl_n):
            tl_type = r.byte()
            if tl_type == 0:
                frame_n = r.varint()
                frames = [(r.f32(), r.varint()) for _ in range(frame_n)]
                tls.append({"type": 0, "frames": frames})
            else:
                raise SystemExit(f"unhandled slot timeline type {tl_type} in {name}")
        slot_groups.append({"slot": slot_i, "tls": tls})

    bone_groups = []
    bg_n = r.varint()
    for _ in range(bg_n):
        bone_i = r.varint()
        tl_n = r.varint()
        tls = [parse_bone_timeline(r) for _ in range(tl_n)]
        bone_groups.append({"bone": bone_i, "tls": tls})

    extra_counts = [r.varint() for _ in range(6)]
    if any(extra_counts):
        raise SystemExit(f"unhandled non-slot/bone timelines in {name}: {extra_counts}")

    event_tls = []
    ev_n = r.varint()
    for _ in range(ev_n):
        t = r.f32()
        ev_i = r.varint()
        iv = r.zigzag()
        fv = r.f32()
        sv = r.string()
        event_tls.append({"t": t, "ev": ev_i, "iv": iv, "fv": fv, "sv": sv})

    return {
        "name": name,
        "total": total,
        "slots": slot_groups,
        "bones": bone_groups,
        "events": event_tls,
    }


def parse_spskel(data):
    r = R(data)
    hash_raw = data[:8]
    r.p = 8
    version = r.string()
    floats = [r.f32() for _ in range(5)]
    nonessential = r.byte()

    setup_n = r.varint()
    setup = [r.string() for _ in range(setup_n)]

    bone_n = r.varint()
    bones = []
    for i in range(bone_n):
        bname = r.string()
        parent = r.varint() if i > 0 else None
        rot, bx, by = r.f32(), r.f32(), r.f32()
        sx, sy = r.f32(), r.f32()
        shx, shy = r.f32(), r.f32()
        length = r.f32()
        inherit = r.varint()
        skin_required = r.byte()
        bones.append({
            "name": bname, "parent": parent, "rot": rot, "x": bx, "y": by,
            "sx": sx, "sy": sy, "shx": shx, "shy": shy, "length": length,
            "inherit": inherit, "skin_required": skin_required,
        })

    slot_n = r.varint()
    slots = []
    for _ in range(slot_n):
        sname = r.string()
        bone_i = r.varint()
        color = [r.byte() for _ in range(4)]
        dark = [r.byte() for _ in range(4)]
        att_ref = r.varint()
        blend = r.varint()
        slots.append({
            "name": sname, "bone": bone_i, "color": color, "dark": dark,
            "att_ref": att_ref, "blend": blend,
        })

    constraint_counts = [r.varint() for _ in range(4)]
    assert not any(constraint_counts), constraint_counts

    def read_skin():
        skin_slots_n = r.varint()
        groups = []
        for _ in range(skin_slots_n):
            slot_i = r.varint()
            att_n = r.varint()
            atts = [parse_skin_attachment(r) for _ in range(att_n)]
            groups.append({"slot": slot_i, "atts": atts})
        return groups

    default_skin = read_skin()
    named_n = r.varint()
    named_skins = []
    for _ in range(named_n):
        sname = r.string()
        named_skins.append({"name": sname, "groups": read_skin()})

    event_n = r.varint()
    events = []
    for _ in range(event_n):
        ename = r.string()
        iv = r.zigzag()
        fv = r.f32()
        sv = r.string()
        audio = r.string()
        events.append({"name": ename, "iv": iv, "fv": fv, "sv": sv, "audio": audio})

    anim_n = r.varint()
    anims = [parse_anim(r) for _ in range(anim_n)]

    assert r.p == len(data), f"trailing bytes: {len(data) - r.p}"
    return {
        "hash": hash_raw, "version": version, "floats": floats,
        "nonessential": nonessential, "setup": setup, "bones": bones,
        "slots": slots, "default_skin": default_skin,
        "named_skins": named_skins, "events": events, "anims": anims,
    }


# ----------------------------------------------------------- spskel writer
class WW:
    def __init__(self):
        self.b = bytearray()

    def byte(self, v):
        self.b.append(v & 0xFF)

    def f32(self, v):
        self.b += struct.pack(">f", v)

    def varint(self, v):
        while v > 127:
            self.byte((v & 0x7F) | 0x80)
            v >>= 7
        self.byte(v)

    def zigzag(self, v):
        if v >= 0:
            self.varint((v << 1))
        else:
            self.varint(((-v) << 1) - 1)

    def string(self, s):
        if s is None:
            self.byte(0)
            return
        e = s.encode("utf-8")
        self.varint(len(e) + 1)
        self.b += e


def write_skin_attachment(w, att, name_ref):
    w.varint(name_ref)
    w.byte(att["flags"])
    if att["flags"] & 0x04:
        w.f32(att["rotation"])
    w.f32(att["x"])
    w.f32(att["y"])
    w.f32(att["sx"])
    w.f32(att["sy"])
    w.f32(att["w"])
    w.f32(att["h"])
    if att["flags"] & 0x01:
        w.string(att["path"])
    if att["flags"] & 0x08:
        for c in att["color"]:
            w.byte(c)
    if att["flags"] & 0x10:
        w.f32(att["seq_f"][0])
        w.f32(att["seq_f"][1])
        w.varint(att["seq_v"][0])
        w.varint(att["seq_v"][1])


def write_anim(w, anim, setup):
    w.string(anim["name"])
    w.varint(anim["total"])

    w.varint(len(anim["slots"]))
    for group in anim["slots"]:
        w.varint(group["slot"])
        w.varint(len(group["tls"]))
        for tl in group["tls"]:
            w.byte(0)
            w.varint(len(tl["frames"]))
            for t, ref in tl["frames"]:
                w.f32(t)
                w.varint(ref)

    w.varint(len(anim["bones"]))
    for group in anim["bones"]:
        w.varint(group["bone"])
        w.varint(len(group["tls"]))
        for tl in group["tls"]:
            nval = BONE_TL_VALUES[tl["type"]]
            w.byte(tl["type"])
            w.varint(len(tl["frames"]))
            w.varint(len(tl["beziers"]))
            for fi, frame in enumerate(tl["frames"]):
                w.f32(frame["t"])
                for v in frame["vals"]:
                    w.f32(v)
                if fi > 0:
                    w.byte(frame["curve"])
            for bez in tl["beziers"]:
                for v in bez:
                    w.f32(v)

    for _ in range(6):
        w.varint(0)

    w.varint(len(anim["events"]))
    for ev in anim["events"]:
        w.f32(ev["t"])
        w.varint(ev["ev"])
        w.zigzag(ev["iv"])
        w.f32(ev["fv"])
        w.string(ev["sv"])


def write_spskel(sk):
    w = WW()
    w.b += sk["hash"]
    w.string(sk["version"])
    for f in sk["floats"]:
        w.f32(f)
    w.byte(1 if sk["nonessential"] else 0)

    w.varint(len(sk["setup"]))
    for s in sk["setup"]:
        w.string(s)

    w.varint(len(sk["bones"]))
    for i, b in enumerate(sk["bones"]):
        w.string(b["name"])
        if i > 0:
            w.varint(b["parent"])
        w.f32(b["rot"])
        w.f32(b["x"])
        w.f32(b["y"])
        w.f32(b["sx"])
        w.f32(b["sy"])
        w.f32(b["shx"])
        w.f32(b["shy"])
        w.f32(b["length"])
        w.varint(b["inherit"])
        w.byte(1 if b["skin_required"] else 0)

    w.varint(len(sk["slots"]))
    for s in sk["slots"]:
        w.string(s["name"])
        w.varint(s["bone"])
        for c in s["color"]:
            w.byte(c)
        for c in s["dark"]:
            w.byte(c)
        w.varint(s["att_ref"])
        w.varint(s["blend"])

    for _ in range(4):
        w.varint(0)

    w.varint(len(sk["default_skin"]))
    for group in sk["default_skin"]:
        w.varint(group["slot"])
        w.varint(len(group["atts"]))
        for att in group["atts"]:
            write_skin_attachment(w, att, att["name_ref"])

    w.varint(len(sk["named_skins"]))
    for skin in sk["named_skins"]:
        w.string(skin["name"])
        w.varint(len(skin["groups"]))
        for group in skin["groups"]:
            w.varint(group["slot"])
            w.varint(len(group["atts"]))
            for att in group["atts"]:
                write_skin_attachment(w, att, att["name_ref"])

    w.varint(len(sk["events"]))
    for e in sk["events"]:
        w.string(e["name"])
        w.zigzag(e["iv"])
        w.f32(e["fv"])
        w.string(e["sv"])
        w.string(e["audio"])

    w.varint(len(sk["anims"]))
    for anim in sk["anims"]:
        write_anim(w, anim, sk["setup"])

    return bytes(w.b)


# ----------------------------------------------------------- image pipeline
def decode_page(blob):
    off = blob.find(b"RIFF")
    size = struct.unpack_from("<I", blob, off + 4)[0]
    return Image.open(io.BytesIO(blob[off:off + 8 + size])).convert("RGBA")


def encode_ctex(page_img, header):
    buf = io.BytesIO()
    page_img.save(buf, "WEBP", lossless=True, quality=100, method=6)
    webp = buf.getvalue()
    hdr = bytearray(header[:0x38])
    struct.pack_into("<I", hdr, 0x0C, page_img.height)
    struct.pack_into("<H", hdr, 0x2A, page_img.height)
    struct.pack_into("<I", hdr, 0x34, len(webp))
    return bytes(hdr) + webp


def composite_attack_head(new_art, old_head):
    art = Image.open(new_art).convert("RGBA")
    art = art.crop(art.getbbox())
    bw, bh = art.size
    w, h = 365, 278
    scale = min(w / bw, h / bh)
    scaled = art.resize((round(bw * scale), round(bh * scale)), Image.LANCZOS)

    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(scaled, ((w - scaled.width) // 2, (h - scaled.height) // 2), scaled)

    # Keep the tiny red neck tip from the normal head wherever art is transparent.
    ca, oh = canvas.load(), old_head.load()
    for yy in range(h - 14, h):
        for xx in range(w):
            if ca[xx, yy][3] == 0 and oh[xx, yy][3] != 0:
                ca[xx, yy] = oh[xx, yy]
    return canvas


def patch_spatlas(blob):
    doc = json.loads(blob.decode("utf-8"))
    data = doc["atlas_data"]
    assert "size:512,1394" in data
    data = data.replace("size:512,1394", f"size:512,{NEW_H}")
    marker = "zz_tail_insurance"
    assert marker in data
    data = data.replace(
        marker, "attack_head\nbounds:0,1396,365,278\n" + marker, 1)
    doc["atlas_data"] = data
    return json.dumps(doc).encode("utf-8")


# ----------------------------------------------------------- main
def main():
    meta = pcktool.parse_pck(PCK)
    old_ctex = pcktool.extract(meta, BATTLE_CTEX)
    header = old_ctex[:0x38]
    page = decode_page(old_ctex)
    assert page.size == (512, OLD_H), page.size

    attack_head = composite_attack_head(NEW_ART, page.crop((0, 0, 365, 278)))
    attack_head.save(os.path.join(W, "investigate", "regions", "attack_head.png"))

    new_page = Image.new("RGBA", (512, NEW_H), (0, 0, 0, 0))
    new_page.paste(page, (0, 0))
    ax, ay, aw, ah = ATTACK_HEAD_REGION
    new_page.paste(attack_head, (ax, ay))
    new_ctex = encode_ctex(new_page, header)
    print("new ctex:", len(new_ctex), "bytes")

    new_battle_spatlas = patch_spatlas(pcktool.extract(meta, BATTLE_SPATLAS))
    new_shop_spatlas = patch_spatlas(pcktool.extract(meta, SHOP_SPATLAS))

    # Modify skeleton.
    sk = parse_spskel(pcktool.extract(meta, SPSKEL))
    assert "attack_head" not in sk["setup"]
    sk["setup"].append("attack_head")
    ah_ref = len(sk["setup"])  # 1-based ref = index+1

    head_slot_i = next(i for i, s in enumerate(sk["slots"]) if s["name"] == "head")
    head_group = next(g for g in sk["default_skin"] if g["slot"] == head_slot_i)
    new_att = dict(head_group["atts"][0])
    new_att["name_ref"] = ah_ref
    head_group["atts"].append(new_att)

    attack = next(a for a in sk["anims"] if a["name"] == "attack")
    assert not attack["slots"]
    head_ref = sk["setup"].index("head") + 1
    attack["slots"].append({
        "slot": head_slot_i,
        "tls": [{
            "type": 0,
            "frames": [(0.0, ah_ref), (0.7, head_ref)],
        }],
    })
    attack["total"] += 1

    new_skel = write_spskel(sk)
    # Round-trip the new skeleton through the parser once more for evidence.
    reparsed = parse_spskel(new_skel)
    re_attack = next(a for a in reparsed["anims"] if a["name"] == "attack")
    assert len(re_attack["slots"]) == 1
    frames = re_attack["slots"][0]["tls"][0]["frames"]
    names = [(t, reparsed["setup"][ref - 1]) for t, ref in frames]
    print("attack head timeline:", names)
    assert names[0] == (0.0, "attack_head")
    assert abs(names[1][0] - 0.7) < 1e-6 and names[1][1] == "head"

    replacements = {
        BATTLE_CTEX: new_ctex,
        SHOP_CTEX: new_ctex,
        BATTLE_SPATLAS: new_battle_spatlas,
        SHOP_SPATLAS: new_shop_spatlas,
        SPSKEL: new_skel,
    }
    entries = []
    for e in meta["entries"]:
        entries.append((e[0], replacements.get(e[0], pcktool.extract(meta, e[0]))))
    pcktool.build_pck(PCK, entries, ref_header_from=PCK)
    print("rebuilt pck:", os.path.getsize(PCK), "entries:", len(entries))

    # Pixel-level verification: old content unchanged, new region matches.
    m2 = pcktool.parse_pck(PCK)
    check_page = decode_page(pcktool.extract(m2, BATTLE_CTEX))
    assert check_page.size == (512, NEW_H)
    old_px, new_px = page.load(), check_page.load()
    for yy in range(OLD_H):
        for xx in range(512):
            po, pn = old_px[xx, yy], new_px[xx, yy]
            # Lossless WebP normalizes RGB of fully transparent pixels.
            assert po[3] == pn[3], ("alpha", xx, yy)
            if po[3] > 0:
                assert po[:3] == pn[:3], ("rgb", xx, yy)
    reg = check_page.crop((ax, ay, ax + aw, ay + ah))
    ra, ca = reg.load(), attack_head.load()
    for yy in range(ah):
        for xx in range(aw):
            pa, pb = ra[xx, yy], ca[xx, yy]
            assert pa[3] == pb[3], ("reg alpha", xx, yy)
            if pa[3] > 0:
                assert pa[:3] == pb[:3], ("reg rgb", xx, yy)
    print("verified: old page unchanged; attack_head region exact")


if __name__ == "__main__":
    main()
