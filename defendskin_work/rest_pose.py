"""Dump restsite skeleton bone setup + animation timeline values."""
import os
import struct
import sys

W = os.path.dirname(os.path.abspath(__file__))
SKEL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(W, "restsite_defect.skel")


class R:
    def __init__(self, data):
        self.d = data
        self.p = 0

    def byte(self):
        v = self.d[self.p]; self.p += 1; return v

    def f32(self):
        v = struct.unpack_from(">f", self.d, self.p)[0]; self.p += 4; return v

    def varint(self):
        b = self.byte(); r = b & 0x7F; s = 7
        while b & 0x80:
            b = self.byte(); r |= (b & 0x7F) << s; s += 7
        return r

    def zigzag(self):
        v = self.varint(); return (v >> 1) ^ -(v & 1)

    def string(self):
        n = self.varint()
        if n == 0:
            return None
        raw = self.d[self.p:self.p + n - 1]; self.p += n - 1
        return raw.decode("utf-8", errors="replace")


def parse(path):
    r = R(open(path, "rb").read())
    r.p += 8
    r.string()
    for _ in range(4):
        r.f32()
    r.f32(); r.byte()
    sp_n = r.varint()
    setup = [r.string() for _ in range(sp_n)]

    bone_n = r.varint()
    bones = []
    for i in range(bone_n):
        name = r.string()
        parent = r.varint() if i > 0 else None
        rot = r.f32(); x = r.f32(); y = r.f32()
        r.f32(); r.f32(); r.f32(); r.f32()
        r.f32(); r.varint(); r.byte()
        bones.append(dict(name=name, parent=parent, rot=rot, x=x, y=y))

    slot_n = r.varint()
    slots = []
    for _ in range(slot_n):
        name = r.string()
        bi = r.varint()
        for _ in range(8):
            r.byte()
        r.varint(); r.varint()
        slots.append(dict(name=name, bone=bi))

    for _ in range(4):
        assert r.varint() == 0, "constraint"

    skins = []
    skin_start = skin_end = None
    for s_i in range(1 + 0):  # default skin only (named skins are 0 here)
        n = r.varint()
        assert n >= 1, f"expected at least 1 skin slot, got {n}"
        skin_start = r.p
        recs = []
        for _ in range(n):
            slot_i = r.varint()
            a = r.varint()
            atts = []
            for _ in range(a):
                name_ref = r.varint()
                flags = r.byte()
                rot = r.f32() if flags & 0x04 else 0.0
                ax, ay = r.f32(), r.f32()
                scx, scy = r.f32(), r.f32()
                w, h = r.f32(), r.f32()
                if flags & 0x01:
                    r.string()
                if flags & 0x08:
                    for _ in range(4):
                        r.byte()
                if flags & 0x10:
                    r.f32(); r.f32(); r.varint(); r.varint()
                atts.append(dict(name=setup[name_ref - 1] if name_ref else None,
                                 off=(ax, ay), size=(w, h)))
            recs.append((slot_i, atts))
        skins.append(recs)
        skin_end = r.p
    named = r.varint()
    for _ in range(named):
        r.string()
        raise SystemExit("named skins unexpected")
    ev = r.varint()
    for _ in range(ev):
        r.string(); r.zigzag(); r.f32(); r.string(); r.string()

    anim_start = r.p
    anim_n = r.varint()
    anims = []
    for _ in range(anim_n):
        name = r.string()
        total = r.varint()
        sg = r.varint()
        stl = []
        for _ in range(sg):
            si = r.varint(); tn = r.varint()
            for _ in range(tn):
                t = r.byte()
                if t == 0:
                    fn = r.varint()
                    fr = [(r.f32(), r.varint()) for _ in range(fn)]
                    stl.append((slots[si]["name"], "attach", fr))
                elif t == 1:
                    fn = r.varint(); bnz = r.varint()
                    fr = []
                    for _ in range(fn):
                        tt = r.f32()
                        c = [r.byte() for _ in range(4)]
                        fr.append((tt, tuple(c)))
                    for _ in range(bnz):
                        for _ in range(6):
                            r.f32()
                    stl.append((slots[si]["name"], "rgba", fr))
                else:
                    raise SystemExit("slot tl " + str(t))
        bg = r.varint()
        btl = []
        for _ in range(bg):
            bi = r.varint(); tn = r.varint()
            for _ in range(tn):
                t = r.byte(); fn = r.varint(); bnz = r.varint()
                nv = {0: 1, 1: 2, 2: 2, 3: 2}[t]
                fr = []
                for fi in range(fn):
                    tt = r.f32()
                    offs = []
                    vals = []
                    for _ in range(nv):
                        offs.append(r.p)
                        vals.append(r.f32())
                    if fi > 0:
                        r.byte()
                    fr.append((tt, vals, offs))
                for _ in range(bnz):
                    for _ in range(nv):
                        for _ in range(6):
                            r.f32()
                btl.append((bones[bi]["name"], t, fr, bnz))
        for _ in range(6):
            assert r.varint() == 0, "unhandled tl"
        evn = r.varint()
        for _ in range(evn):
            r.f32(); r.varint(); r.zigzag(); r.f32(); r.string()
        anims.append(dict(name=name, slot_tl=stl, bone_tl=btl))
    assert r.p == len(r.d), f"trailing {len(r.d) - r.p}"
    return dict(setup=setup, bones=bones, slots=slots, skin=skins[0], anims=anims,
                anim_start=anim_start, skin_start=skin_start, skin_end=skin_end)


if __name__ == "__main__":
    d = parse(SKEL)
    print("bones:")
    for b in d["bones"]:
        print(f"  {b['name']:12s} parent={b['parent']} rot={b['rot']:8.2f} pos=({b['x']:7.1f},{b['y']:7.1f})")
    print("slots -> bone:", [(s["name"], d["bones"][s["bone"]]["name"]) for s in d["slots"]])
    print("skin:")
    for slot_i, atts in d["skin"]:
        for a in atts:
            print(f"  slot[{slot_i}] {d['slots'][slot_i]['name']:8s} att={a['name']:10s} off={a['off']} size=({a['size'][0]:.1f},{a['size'][1]:.1f})")
    print("animations @", d["anim_start"])
    for a in d["anims"]:
        print(f"anim {a['name']!r}")
        for n, t, fr, bnz in a["bone_tl"]:
            print(f"   bone {n:12s} type={t} bezier={bnz}")
            for tt, v, _o in fr:
                print(f"      t={tt:<6.2f} v={[round(x, 2) for x in v]}")