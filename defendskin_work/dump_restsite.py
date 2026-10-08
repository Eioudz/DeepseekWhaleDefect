"""Dump restsite skel bones + slot->bone mapping (fields captured for rewrite)."""
import struct
import sys


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

    def string(self):
        n = self.varint()
        if n == 0:
            return None
        raw = self.d[self.p:self.p + n - 1]
        self.p += n - 1
        return raw.decode("utf-8", errors="replace")


d = open(r"defendskin_work\restsite_defect.skel", "rb").read()
r = R(d)
r.p += 8
version = r.string()
bounds = [r.f32() for _ in range(4)]
ref_scale = r.f32()
nonessential = r.byte()

setup_n = r.varint()
setup = [r.string() for _ in range(setup_n)]
print("strings:", setup)

bone_n = r.varint()
bones = []
for i in range(bone_n):
    name = r.string()
    parent = r.varint() if i > 0 else None
    rot, bx, by = r.f32(), r.f32(), r.f32()
    scx, scy = r.f32(), r.f32()
    shx, shy = r.f32(), r.f32()
    length = r.f32()
    inherit = r.varint()
    skreq = r.byte()
    bones.append((name, parent, rot, bx, by, scx, scy, shx, shy, length, inherit, skreq))
for b in bones:
    print("bone:", b)

slot_n = r.varint()
slots = []
for _ in range(slot_n):
    name = r.string()
    bone_i = r.varint()
    color = bytes(r.byte() for _ in range(4))
    dark = bytes(r.byte() for _ in range(4))
    att = r.varint()
    blend = r.varint()
    slots.append((name, bone_i, color, dark, att, blend))
for s in slots:
    print("slot:", s)

for label in ("ik", "transform", "path", "physics"):
    print(label, r.varint())

skin_start = r.p
skin_slots_n = r.varint()
records = []
for _ in range(skin_slots_n):
    slot_i = r.varint()
    att_n = r.varint()
    for _ in range(att_n):
        name_ref = r.varint()
        flags = r.byte()
        vals = {}
        if flags & 0x04:
            vals["rot"] = r.f32()
        vals["ax"], vals["ay"] = r.f32(), r.f32()
        vals["scx"], vals["scy"] = r.f32(), r.f32()
        vals["w"], vals["h"] = r.f32(), r.f32()
        if flags & 0x01:
            vals["path"] = r.string()
        if flags & 0x08:
            vals["color"] = bytes(r.byte() for _ in range(4))
        if flags & 0x10:
            vals["seq"] = (r.f32(), r.f32(), r.varint(), r.varint())
        records.append((slot_i, name_ref, flags, vals))
print("skin raw bytes:", skin_start, "->", r.p)
named_skins = r.varint()
print("named skins:", named_skins)
events_n = r.varint()
print("events:", events_n)
print("animations start at", r.p, "of", len(d))
