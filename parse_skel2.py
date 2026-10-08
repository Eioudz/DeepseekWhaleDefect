"""Minimal but format-accurate Spine 4.2 binary skeleton parser.

Aligned with make_skel.py (its inverse writer) and spine-cpp SkeletonBinary.
Dumps per-animation attachment timelines. Usage: python parse_skel2.py FILE
"""
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


def parse(path):
    r = R(open(path, "rb").read())
    # 8 raw hash bytes precede the varint-prefixed strings.
    hash_raw = r.d[r.p:r.p + 8]
    r.p += 8
    hash_ = hash_raw.hex()
    version = r.string()
    sx, sy, sw, sh = r.f32(), r.f32(), r.f32(), r.f32()
    reference_scale = r.f32()
    nonessential = r.byte()
    print(f"hash={hash_!r} version={version!r} bounds=({sx},{sy},{sw},{sh}) refScale={reference_scale}")

    setup_pose_n = r.varint()
    setup_pose = [r.string() for _ in range(setup_pose_n)]
    print("setup pose attachments:", setup_pose)

    # bones
    bone_n = r.varint()
    bones = []
    for i in range(bone_n):
        name = r.string()
        parent = r.varint() if i > 0 else None
        rot, bx, by = r.f32(), r.f32(), r.f32()
        bscx, bscy = r.f32(), r.f32()
        shx, shy = r.f32(), r.f32()
        length = r.f32()
        inherit = r.varint()
        skin_required = r.byte()
        bones.append(name)
    print(f"{bone_n} bones")

    # slots
    slot_n = r.varint()
    slots = []
    for _ in range(slot_n):
        name = r.string()
        bone_i = r.varint()
        color = [r.byte() for _ in range(4)]
        dark = [r.byte() for _ in range(4)]
        att_ref = r.varint()
        blend = r.varint()
        slots.append(name)
    print("slots:", slots)

    for label in ("ik", "transform", "path", "physics"):
        n = r.varint()
        print(f"{label} constraints: {n}")
        if n:
            raise SystemExit("constraint parsing not implemented")

    # default skin: directly a slot count, then named skin count afterwards
    def read_skin_contents():
        skin_slots_n = r.varint()
        for _ in range(skin_slots_n):
            slot_i = r.varint()
            att_n = r.varint()
            for _ in range(att_n):
                name_ref = r.varint()
                flags = r.byte()
                if flags & 0x04:
                    r.f32()  # rotation
                ax, ay = r.f32(), r.f32()
                ascx, ascy = r.f32(), r.f32()
                aw, ah = r.f32(), r.f32()
                if flags & 0x01:
                    r.string()  # path
                if flags & 0x08:
                    for _ in range(4):
                        r.byte()  # color
                if flags & 0x10:
                    for _ in range(2):
                        r.f32()
                    for _ in range(2):
                        r.varint()
                an = setup_pose[name_ref - 1] if name_ref else None
                print(f"   slot[{slot_i}] {slots[slot_i]!r} att={an!r} flags={flags} off=({ax},{ay}) size=({aw},{ah})")

    print("default skin:")
    read_skin_contents()
    skin_n = r.varint()
    print("named skins:", skin_n)
    for _ in range(skin_n):
        skin_name = r.string()
        print(f" named skin {skin_name!r}:")
        read_skin_contents()

    # events
    event_n = r.varint()
    events = []
    for _ in range(event_n):
        name = r.string()
        iv = r.zigzag()
        fv = r.f32()
        sv = r.string()
        audio = r.string()
        events.append(name)
    print("events:", events)

    # animations
    anim_n = r.varint()
    print(f"{anim_n} animations")
    head_slot = slots.index("head")
    for _ in range(anim_n):
        name = r.string()
        total_tl = r.varint()
        slot_groups = r.varint()
        head_tl = None
        for _ in range(slot_groups):
            slot_i = r.varint()
            tl_n = r.varint()
            for _ in range(tl_n):
                tl_type = r.byte()
                if tl_type == 0:  # attachment
                    frame_n = r.varint()
                    frames = []
                    for _ in range(frame_n):
                        t = r.f32()
                        ref = r.varint()
                        frames.append((t, setup_pose[ref - 1] if ref else None))
                    if slot_i == head_slot:
                        head_tl = frames
                elif tl_type == 1:  # rgba
                    frame_n = r.varint()
                    bezier_n = r.varint()
                    for _ in range(frame_n):
                        r.f32()
                        for _ in range(4):
                            r.byte()
                        # curves handled by bezier_n count; skip conservatively
                    # bezier curves: each 6 floats
                    for _ in range(bezier_n):
                        for _ in range(6):
                            r.f32()
                else:
                    raise SystemExit(f"unknown slot timeline type {tl_type} in {name}")

        # bone timelines
        bone_groups = r.varint()
        for _ in range(bone_groups):
            bone_i = r.varint()
            tl_n = r.varint()
            for _ in range(tl_n):
                tl_type = r.byte()
                frame_n = r.varint()
                bezier_n = r.varint()
                values = {0: 1, 1: 2, 2: 2, 3: 2}[tl_type]
                for fi in range(frame_n):
                    r.f32()
                    for _ in range(values):
                        r.f32()
                    if fi > 0:
                        r.byte()  # curve type linear
                for _ in range(bezier_n):
                    for _ in range(values):
                        for _ in range(6):
                            r.f32()

        for label in ("ik", "transform", "path", "physics", "deform", "draworder"):
            n = r.varint()
            if n:
                raise SystemExit(f"unhandled {label} timelines in {name}")

        ev_tl_n = r.varint()
        for _ in range(ev_tl_n):
            r.f32()
            r.varint()
            r.zigzag()
            r.f32()
            r.string()

        print(f" anim {name!r}: head attachment timeline = {head_tl}")
    print("parsed OK, trailing bytes:", len(r.d) - r.p)


if __name__ == "__main__":
    parse(sys.argv[1])
