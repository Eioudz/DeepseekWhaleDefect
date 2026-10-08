"""Experimental parser for the custom packed spskel format used by STS2.

Goal: locate sections and, in particular, attachment timelines inside each
animation, so we can surgically remove head-slot keys from attack/cast/process.
"""
import struct
import sys


class R:
    def __init__(self, d):
        self.d = d
        self.p = 0

    def u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]
        self.p += 4
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]
        self.p += 4
        return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.p)[0]
        self.p += 2
        return v

    def f32(self):
        v = struct.unpack_from("<f", self.d, self.p)[0]
        self.p += 4
        return v

    def s(self):
        n = self.u8()
        if n == 0:
            return ""
        v = self.d[self.p:self.p + n - 1].decode("utf-8")
        self.p += n
        assert self.d[self.p - 1] == 0
        return v


def main(path):
    d = open(path, "rb").read()
    r = R(d)
    hash8 = d[r.p:r.p + 8]
    r.p += 8
    ver = r.s()
    print("hash", hash8.hex(), "version", ver)
    x, y = r.f32(), r.f32()
    w, h = r.f32(), r.f32()
    f5 = r.f32()
    print("x y w h:", x, y, w, h, "f5:", f5)
    flag = r.u8()
    print("flag:", flag)
    if flag:
        print(" extra float:", r.f32())
    s1 = r.s()
    print("str1:", repr(s1))
    # string table
    n = r.u8()
    print("string table count:", n, "at", r.p - 1)
    table = []
    for i in range(n):
        t = r.s()
        table.append(t)
    for i, t in enumerate(table):
        print("  [%d] %s" % (i + 1, t))
    # bones
    nb = r.u8()
    print("bones:", nb, "at", r.p - 1)
    bone_start = r.p
    for i in range(nb):
        start = r.p
        name = r.s()
        after_name = r.p
        # parse tentative fields, figure size by next name marker later
        print("  bone %2d %-18s body@%d" % (i, name, after_name))
        # dump rest until next u8 string marker heuristic
    # I will measure using re-walk below instead
    r.p = bone_start
    # measure bones by trying layout: parent u8 + 7 floats + u8 inherit? verify floats look sane
    offsets = []
    for i in range(nb):
        name = r.s()
        body = r.p
        offsets.append((i, name, body))
        # guess: parent(u8), rotation,x,y (3f), scaleX,scaleY,shearX,shearY (4f), inherit(u8)
        parent = r.u8()
        vals = [r.f32() for _ in range(7)]
        inherit = r.u8()
        print("   b%2d %-18s parent=%2d vals=%s inherit=%d end=%d" % (i, name, parent, [round(v, 2) for v in vals], inherit, r.p))
    print("after bones at", r.p, "next byte:", hex(d[r.p]))
    ns = r.u8()
    print("slots:", ns, "at", r.p - 1)
    for i in range(ns):
        start = r.p
        name = r.s()
        bone = r.u8()
        color = d[r.p:r.p + 8]
        r.p += 8
        u = r.u16()
        print("  slot %2d %-8s bone=%2d color=%s u16=%d end=%d" % (i, name, bone, color.hex(), u, r.p))
    print("after slots at", r.p, "next:", hex(d[r.p]))


if __name__ == "__main__":
    main(sys.argv[1])
