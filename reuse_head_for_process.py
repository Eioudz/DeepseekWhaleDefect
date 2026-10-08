"""Reuse the existing cast_head attachment on the process (PowerUp) animation.

No new atlas region: add a head AttachmentTimeline to process pointing at the
already-present cast_head at t=0 and back to head at the animation end.
Rebuild + reinstall the pck.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import pcktool
import add_expression_head as base

W = os.path.dirname(__file__)
PCK = os.path.join(W, "whale_workspace", "content", "DeepseekWhaleDefect.pck")
SPSKEL = base.SPSKEL
TARGET_ANIM = "process"
ANIM_DURATION = 1.5
EXPR_NAME = "cast_head"


def main():
    meta = pcktool.parse_pck(PCK)
    sk = base.parse_spskel(pcktool.extract(meta, SPSKEL))

    assert EXPR_NAME in sk["setup"]
    expr_ref = sk["setup"].index(EXPR_NAME) + 1
    head_ref = sk["setup"].index("head") + 1

    head_slot_i = next(i for i, s in enumerate(sk["slots"]) if s["name"] == "head")
    target = next(a for a in sk["anims"] if a["name"] == TARGET_ANIM)
    assert not target["slots"]
    target["slots"].append({
        "slot": head_slot_i,
        "tls": [{
            "type": 0,
            "frames": [(0.0, expr_ref), (ANIM_DURATION, head_ref)],
        }],
    })
    target["total"] += 1

    new_skel = base.write_spskel(sk)
    reparsed = base.parse_spskel(new_skel)
    re_target = next(a for a in reparsed["anims"] if a["name"] == TARGET_ANIM)
    assert len(re_target["slots"]) == 1
    frames = re_target["slots"][0]["tls"][0]["frames"]
    names = [(t, reparsed["setup"][ref - 1]) for t, ref in frames]
    print(TARGET_ANIM, "head timeline:", names)
    assert names[0] == (0.0, EXPR_NAME)
    assert abs(names[1][0] - ANIM_DURATION) < 1e-6 and names[1][1] == "head"

    entries = []
    for e in meta["entries"]:
        blob = new_skel if e[0] == SPSKEL else pcktool.extract(meta, e[0])
        entries.append((e[0], blob))
    pcktool.build_pck(PCK, entries, ref_header_from=PCK)
    print("rebuilt pck:", os.path.getsize(PCK), "entries:", len(entries))


if __name__ == "__main__":
    main()
