"""Write a new Spine 4.2 binary skeleton for the whale girl.

Self-contained writer (inverse of parse_skel_full.py, both validated against
spine-cpp SkeletonBinary.cpp). Produces defect.skel replacement with:
 - humanoid bone tree (head/body/limbs split parts, per user request)
 - original key bone names kept for game-code compatibility
 - 10 region attachments on a new atlas (scale 0.2)
 - 8 animations matching original names
"""
import struct
from collections import OrderedDict

ORIG = r"extracted\godot\imported\defect.skel-5dba1374f717ab634fbb5c1941158597.spskel"
OUT = "defect.skel-5dba1374f717ab634fbb5c1941158597.spskel"

class W:
    def __init__(self):
        self.b = bytearray()

    def byte(self, v):
        self.b.append(v & 0xFF)

    def boolean(self, v):
        self.b.append(1 if v else 0)

    def f32(self, v):
        self.b += struct.pack(">f", v)

    def i32be(self, v):
        self.b += struct.pack(">i", v)

    def varint(self, v, maxbytes=2):
        assert 0 <= v < (1 << (7 * maxbytes)), f"varint too big: {v}"
        while v > 127:
            self.byte((v & 0x7F) | 0x80)
            v >>= 7
        self.byte(v)

    def zigzag(self, v):
        self.varint((v << 1) ^ (v >> 31) if v >= 0 else ((-v) << 1) - 1)

    def string(self, s):
        if s is None:
            self.byte(0)
            return
        e = s.encode("utf-8")
        self.varint(len(e) + 1)
        self.b += e

    def color(self, r, g, b, a):
        self.b += bytes((r, g, b, a))


# ---------------------------------------------------------------- bone tree
# (name, parent, abs_x, abs_y)  -- local coords relative to root (character axis)
BONES = [
    ("root",               None,    0,    0),
    ("shadow",             "root", 15,  -40),
    ("COG_bonus_control",  "root",   0,  334),
    ("COG",                "COG_bonus_control", 0, 772),
    ("hips",               "COG",    0,  772),
    ("pelvis",             "COG",    0,  772),
    ("leg_upper_r",        "hips", 160,  497),
    ("leg_lower_r",        "leg_upper_r", 160, 497),
    ("foot_r",             "leg_lower_r", 160, 187),
    ("leg_upper_l",        "hips",  -160,  497),
    ("leg_lower_l",        "leg_upper_l", -160, 497),
    ("foot_l",             "leg_lower_l", -160, 187),
    ("torso",              "COG",    0,  772),
    ("torso_upper",        "torso",  0,  890),
    ("shoulder_r",         "torso_upper", 300, 900),
    ("shoulder_l",         "torso_upper",  -300, 900),
    ("arm_upper_r",        "shoulder_r", 315, 872),
    ("arm_lower_r",        "arm_upper_r", 450, 1127),
    ("hand_r",             "arm_lower_r", 385, 430),
    ("arm_upper_l",        "shoulder_l", -220, 857),
    ("arm_lower_l",        "arm_upper_l",  -460, 1120),
    ("hand_l",             "arm_lower_l",  -450, 430),
    ("neck",               "torso_upper", 0, 927),
    ("head",               "neck",   0,  967),
    ("head_adjust",        "head",   0,  967),
    ("eye_orb",            "head",  60, 1202),
    ("head_pipe_attach",   "head",   0, 2127),
    ("hair_r",             "head", 540, 1270),
    ("hair_l",             "head",  -540, 1270),
    ("orb",                "torso", -550, 1000),
    ("tail",               "COG",   -235,  802),
]

# ---------------------------------------------------------------- slots
# (slot_name, bone, attachment, att_x, att_y, att_w, att_h)
# Draw order = list order (bottom first): arms sit UNDER the hair streams,
# head on top. tail/shadow keep hand-tuned values (verified in game); every
# other part is computed from parts_meta.json so it sits exactly at its
# source position: lx = (px-158)*5, u = (417-py)*5 + 192 (feet u=187).
import json as _json
_META = _json.load(open("parts_meta.json"))


def _att(name, bone):
    bx, by = {n: (x, y) for n, _, x, y in BONES}[bone]
    p = _META["parts"][name]
    x0, y0, x1, y1 = p["bbox"]
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    return (name, bone, name,
            (cx - 158) * 5 - bx, (417 - cy) * 5 + 192 - by,
            p["w"] * 5, p["h"] * 5)


# head shifted slightly LEFT of the neck axis (pivot stays on the neck bone,
# so head-tilt animations still rotate naturally)
_head_att = _att("head", "head")
_head_att = (_head_att[0], _head_att[1], _head_att[2],
             _head_att[3] - 40, _head_att[4], _head_att[5], _head_att[6])

# left arm pivot re-seated at the sleeve cap (bone was relocated), so the
# attachment center offset differs from the meta-computed one; image unchanged
_la_att = _att("arm_l", "arm_upper_l")
_la_att = (_la_att[0], _la_att[1], _la_att[2], -95.0, -180.0,
           _la_att[5], _la_att[6])

SLOTS = [
    ("shadow", "shadow", "shadow", 0, 0, 2070, 490),
    ("tail",   "tail",   "tail",  -330, -192.5, 472, 480),
    _att("hair_r", "hair_r"),
    _att("hair_l", "hair_l"),
    _att("leg_r", "leg_upper_r"),
    _att("leg_l", "leg_upper_l"),
    _att("bod",   "torso"),
    _att("arm_r", "arm_upper_r"),
    _la_att,
    _head_att,
]

EVENTS = [
    ("fire_sparks_left", 0, 0.0, ""),
    ("fire_sparks_right", 0, 0.0, ""),
]

# ---------------------------------------------------------------- writer
bone_index = {n: i for i, (n, *_ ) in enumerate(BONES)}
bone_abs = {n: (x, y) for n, _, x, y in BONES}
bone_parent = {n: p for n, p, *_ in BONES}

w = W()

# header: copy 8-byte hash from original, write same version string
orig = open(ORIG, "rb").read()
w.b += orig[:8]
w.string("4.2.43")

w.f32(-1055.0)      # skeleton x
w.f32(-287.0)       # skeleton y
w.f32(2080.0)       # width
w.f32(2339.0)       # height
w.f32(100.0)        # referenceScale
w.boolean(False)    # nonessential

# strings table: setup attachment names (shared by slots & skin) plus the two
# expression-head attachments swapped in by hurt / low_health animations
EXTRA_ATTS = ["hit_head", "low_head"]
strings = [s[2] for s in SLOTS if s[2] is not None] + EXTRA_ATTS
w.varint(len(strings))
for s in strings:
    w.string(s)

# bones
w.varint(len(BONES))
for i, (name, parent, ax, ay) in enumerate(BONES):
    w.string(name)
    if i > 0:
        w.varint(bone_index[parent])
    px, py = bone_abs[parent] if parent else (0, 0)
    w.f32(0.0)                       # rotation
    w.f32(ax - px)                   # x (relative to parent)
    w.f32(ay - py)                   # y
    w.f32(1.0); w.f32(1.0)           # scale
    w.f32(0.0); w.f32(0.0)           # shear
    w.f32(0.0)                       # length
    w.varint(0)                      # inherit = Normal
    w.boolean(False)                 # skinRequired

# slots
w.varint(len(SLOTS))
for slot_name, bone, att, *_ in SLOTS:
    w.string(slot_name)
    w.varint(bone_index[bone])
    w.color(255, 255, 255, 255)
    w.color(255, 255, 255, 255)      # dark (unused)
    w.varint(0 if att is None
             else strings.index(att) + 1)  # setup attachment name ref
    w.varint(0)                       # blend normal

# no IK / transform / path / physics constraints
w.varint(0); w.varint(0); w.varint(0); w.varint(0)

# default skin
# The two expression heads are pre-composited onto the exact same canvas as
# the default head part (upper silhouette from the expression art, lower
# neck/hair/collar-adjacent pixels from the original head, cross-blended),
# so all three attachments share one geometry and swapping is a pure visual
# change.
HEAD_SLOT_I = next(i for i, s in enumerate(SLOTS) if s[0] == "head")

w.varint(len(SLOTS))                  # slot count in default skin
for si, (slot_name, bone, att, ax, ay, aw, ah) in enumerate(SLOTS):
    w.varint(si)                      # slot index
    n_att = 1 + len(EXTRA_ATTS) if si == HEAD_SLOT_I else 1
    w.varint(n_att)                   # attachment count
    w.varint(strings.index(att) + 1)  # attachment name ref
    # region attachment, flags = 0 (no path ref, no color, no sequence)
    w.byte(0x00)
    w.f32(ax); w.f32(ay)              # position (center offset from bone)
    w.f32(1.0); w.f32(1.0)            # scale
    w.f32(aw); w.f32(ah)              # size in spine units
    if si == HEAD_SLOT_I:
        for n in EXTRA_ATTS:
            w.varint(strings.index(n) + 1)
            w.byte(0x00)
            w.f32(ax); w.f32(ay)
            w.f32(1.0); w.f32(1.0)
            w.f32(aw); w.f32(ah)
w.varint(0)                           # no other skins

# events
w.varint(len(EVENTS))
for (name, iv, fv, sv) in EVENTS:
    w.string(name)
    w.zigzag(iv)
    w.f32(fv)
    w.string(sv)
    w.string(None)                    # no audio path


# ---------------------------------------------------------------- animations
def frames_rot(frames):
    """frames: [(t, deg)] all-linear."""
    w.varint(0)                       # bezier count
    for i, (t, v) in enumerate(frames):
        w.f32(t); w.f32(v)
        if i > 0:
            w.byte(0)                 # linear curve


def frames_tr(frames):
    """frames: [(t, dx, dy)] all-linear."""
    w.varint(0)
    for i, (t, x, y) in enumerate(frames):
        w.f32(t); w.f32(x); w.f32(y)
        if i > 0:
            w.byte(0)


B_ROT, B_TRA = 0, 1

ANIMS = []

def add_anim(name, bone_tls, events=None, slot_tls=None):
    """bone_tls: list of (bone_name, type, frames); events: [(t, ev_name, iv, fv, sv)];
    slot_tls: {slot_name: [(t, attachment_name or None)]} (attachment timelines)."""
    ANIMS.append({"name": name, "bones": bone_tls,
                  "events": events or [], "slots": slot_tls or {}})

B = lambda n: bone_index[n]

# ---- idle_loop: gentle breathing (2.4s cycle)
add_anim("idle_loop", [
    ("COG", B_TRA, [(0, 0, 0), (1.2, 0, 12), (2.4, 0, 0)]),
    ("head", B_ROT, [(0, 0), (0.6, 1.6), (1.2, 0), (1.8, -1.6), (2.4, 0)]),
    ("hair_l", B_ROT, [(0, 0), (0.6, 2.5), (1.2, 0), (1.8, -2.5), (2.4, 0)]),
    ("hair_r", B_ROT, [(0, 0), (0.6, -2.5), (1.2, 0), (1.8, 2.5), (2.4, 0)]),
    ("tail", B_ROT, [(0, 0), (0.9, 2.5), (1.8, -2.5), (2.4, 0)]),
    ("arm_upper_l", B_ROT, [(0, 0), (1.2, -1.2), (2.4, 0)]),
    ("arm_upper_r", B_ROT, [(0, 0), (1.2, 1.2), (2.4, 0)]),
])

# ---- relaxed_loop: bigger relaxed sway (3s)
add_anim("relaxed_loop", [
    ("COG", B_TRA, [(0, 0, 0), (1.5, 0, 22), (3, 0, 0)]),
    ("COG", B_ROT, [(0, 0), (1.5, 1.2), (3, 0)]),
    ("torso_upper", B_ROT, [(0, 0), (0.75, 1.8), (1.5, 0), (2.25, -1.8), (3, 0)]),
    ("head", B_ROT, [(0, 0), (0.75, 3), (1.5, 0), (2.25, -3), (3, 0)]),
    ("hair_l", B_ROT, [(0, 0), (0.75, 4.5), (1.5, 0), (2.25, -4.5), (3, 0)]),
    ("hair_r", B_ROT, [(0, 0), (0.75, -4.5), (1.5, 0), (2.25, 4.5), (3, 0)]),
    ("tail", B_ROT, [(0, 0), (0.75, 8), (1.5, 0), (2.25, -8), (3, 0)]),
    ("arm_upper_l", B_ROT, [(0, 0), (1.5, -2), (3, 0)]),
    ("arm_upper_r", B_ROT, [(0, 0), (1.5, 2), (3, 0)]),
])

# ---- attack: lunge toward enemy (right) + right arm swing (0.7s)
add_anim("attack", [
    ("COG", B_ROT, [(0, 0), (0.15, -3), (0.35, -7), (0.55, -2), (0.7, 0)]),
    ("COG", B_TRA, [(0, 0, 0), (0.2, 45, 0), (0.4, 65, -10), (0.7, 0, 0)]),
    ("arm_upper_r", B_ROT, [(0, 0), (0.1, -15), (0.3, 75), (0.55, 35), (0.7, 0)]),
    ("arm_upper_l", B_ROT, [(0, 0), (0.15, -12), (0.4, -6), (0.7, 0)]),
    ("head", B_ROT, [(0, 0), (0.3, -3), (0.7, 0)]),
    ("hair_l", B_ROT, [(0, 0), (0.2, 6), (0.5, -8), (0.7, 0)]),
    ("hair_r", B_ROT, [(0, 0), (0.2, -6), (0.5, 8), (0.7, 0)]),
    ("tail", B_ROT, [(0, 0), (0.2, -12), (0.4, 8), (0.7, 0)]),
], events=[(0.32, "fire_sparks_left", 0, 0.0, ""), (0.32, "fire_sparks_right", 0, 0.0, "")])

# ---- cast: BOTH arms swing to the right (enemy side), slight lift (0.8s)
add_anim("cast", [
    ("arm_upper_l", B_ROT, [(0, 0), (0.2, 95), (0.55, 117), (0.8, 0)]),
    ("arm_upper_r", B_ROT, [(0, 0), (0.2, 45), (0.55, 55), (0.8, 0)]),
    ("COG", B_TRA, [(0, 0, 0), (0.3, 0, 28), (0.6, 0, 28), (0.8, 0, 0)]),
    ("head", B_ROT, [(0, 0), (0.3, 3), (0.8, 0)]),
    ("hair_l", B_ROT, [(0, 0), (0.4, -6), (0.8, 0)]),
    ("hair_r", B_ROT, [(0, 0), (0.4, 6), (0.8, 0)]),
    ("tail", B_ROT, [(0, 0), (0.4, 12), (0.8, 0)]),
])

# ---- hurt: recoil shake (0.4s)
add_anim("hurt", [
    ("COG", B_TRA, [(0, 0, 0), (0.08, -55, 0), (0.22, -28, 0), (0.4, 0, 0)]),
    ("COG", B_ROT, [(0, 0), (0.1, 5), (0.4, 0)]),
    ("head", B_ROT, [(0, 0), (0.1, -9), (0.25, -4), (0.4, 0)]),
    ("hair_l", B_ROT, [(0, 0), (0.12, 8), (0.4, 0)]),
    ("hair_r", B_ROT, [(0, 0), (0.12, -8), (0.4, 0)]),
    ("tail", B_ROT, [(0, 0), (0.12, -14), (0.4, 0)]),
], slot_tls={"head": [(0, "hit_head"), (0.4, "head")]})

# ---- die: fall to the LEFT (backward), settle (1.2s)
add_anim("die", [
    ("COG", B_ROT, [(0, 0), (0.5, 55), (0.9, 82), (1.2, 88)]),
    ("COG", B_TRA, [(0, 0, 0), (0.5, 0, -140), (1.2, 0, -250)]),
    ("head", B_ROT, [(0, 0), (0.6, -25), (1.2, -38)]),
    ("arm_upper_l", B_ROT, [(0, 0), (0.5, -18), (1.2, -28)]),
    ("arm_upper_r", B_ROT, [(0, 0), (0.5, 24), (1.2, 32)]),
    ("hair_l", B_ROT, [(0, 0), (0.7, 14), (1.2, 18)]),
    ("hair_r", B_ROT, [(0, 0), (0.7, 10), (1.2, 15)]),
    ("tail", B_ROT, [(0, 0), (0.7, -10), (1.2, -4)]),
])

# ---- low_health_loop: weak drooping breath (2s)
add_anim("low_health_loop", [
    ("COG", B_TRA, [(0, 0, -12), (1.0, 0, -24), (2.0, 0, -12)]),
    ("head", B_ROT, [(0, -12), (1.0, -18), (2.0, -12)]),
    ("torso_upper", B_ROT, [(0, 3), (1.0, 5), (2.0, 3)]),
    ("arm_upper_l", B_ROT, [(0, -6), (1.0, -9), (2.0, -6)]),
    ("arm_upper_r", B_ROT, [(0, 6), (1.0, 9), (2.0, 6)]),
    ("hair_l", B_ROT, [(0, 3), (1.0, 5), (2.0, 3)]),
    ("hair_r", B_ROT, [(0, -3), (1.0, -5), (2.0, -3)]),
    ("tail", B_ROT, [(0, -6), (1.0, -3), (2.0, -6)]),
], slot_tls={"head": [(0, "low_head")]})

# ---- process: charge-up trembling with arms cupped (1.5s)
add_anim("process", [
    ("COG", B_TRA, [(0, 0, 0), (0.15, -7, 2), (0.3, 0, 0), (0.45, 7, -2),
                    (0.6, 0, 0), (0.75, -7, 2), (0.9, 0, 0), (1.05, 7, -2),
                    (1.2, 0, 0), (1.35, -5, 0), (1.5, 0, 0)]),
    ("arm_upper_l", B_ROT, [(0, 0), (0.3, 22), (0.75, 32), (1.2, 22), (1.5, 0)]),
    ("arm_upper_r", B_ROT, [(0, 0), (0.3, -28), (0.75, -38), (1.2, -28), (1.5, 0)]),
    ("head", B_ROT, [(0, 0), (0.2, 2), (0.4, -2), (0.6, 2), (0.8, -2), (1.0, 2), (1.5, 0)]),
    ("tail", B_ROT, [(0, 0), (0.25, 4), (0.5, -4), (0.75, 4), (1.0, -4), (1.25, 3), (1.5, 0)]),
    ("COG", B_ROT, [(0, 0), (0.3, -1.5), (0.75, -3), (1.2, -1.5), (1.5, 0)]),
])

w.varint(len(ANIMS))
slot_index_map = {s[0]: i for i, s in enumerate(SLOTS)}
for anim in ANIMS:
    w.string(anim["name"])
    # total timeline count = slot + bone timelines + events timeline (if any)
    n_bone_tls = len(anim["bones"])
    n_event_tl = 1 if anim["events"] else 0
    w.varint(n_bone_tls + len(anim["slots"]) + n_event_tl)

    # slot timeline groups
    w.varint(len(anim["slots"]))
    for slot_name, frames in anim["slots"].items():
        w.varint(slot_index_map[slot_name])
        w.varint(1)                       # one timeline per slot
        w.byte(0)                         # SLOT_ATTACHMENT
        w.varint(len(frames))
        for t, att_name in frames:
            w.f32(t)
            w.varint(0 if att_name is None
                     else strings.index(att_name) + 1)
    # bone timeline groups
    groups = OrderedDict()
    for bone_name, tt, frames in anim["bones"]:
        groups.setdefault(bone_name, []).append((tt, frames))
    w.varint(len(groups))
    for bone_name, tls in groups.items():
        w.varint(B(bone_name))
        w.varint(len(tls))
        for tt, frames in tls:
            w.byte(tt)
            w.varint(len(frames))
            if tt == B_ROT:
                frames_rot(frames)
            else:
                frames_tr(frames)
    # ik / transform / path / physics / attachment-skins / draw order: all empty
    w.varint(0); w.varint(0); w.varint(0); w.varint(0); w.varint(0); w.varint(0)
    # events
    w.varint(len(anim["events"]))
    for (t, ev_name, iv, fv, sv) in anim["events"]:
        w.f32(t)
        w.varint([e[0] for e in EVENTS].index(ev_name))
        w.zigzag(iv)
        w.f32(fv)
        w.string(sv)

with open(OUT, "wb") as f:
    f.write(w.b)
print(f"wrote {OUT}: {len(w.b)} bytes, {len(BONES)} bones, {len(SLOTS)} slots, {len(ANIMS)} anims")
