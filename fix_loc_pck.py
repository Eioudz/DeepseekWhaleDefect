"""Rebuild the mod pck adding a prefixed localization entry so GetModdedLocTables finds it.

GetModdedLocTables looks up res://{modId}/localization/{lang}/{file} (verified by
decompiling ModManager and by scanning ATA_IronClad.pck whose entries use
"ATA_IronClad/localization/zhs/characters.json"). Our pck only had
"res://localization/zhs/characters.json" which never matches that lookup, so the
merge was silently skipped.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import pcktool

WORK = os.path.dirname(__file__)
SRC_PCK = r"d:\12415\Desktop\DeepseekWhaleDefect.pck"
OUT_PCK = SRC_PCK

MOD_ID = "DeepseekWhaleDefect"
LOC_KEY = "res://localization/zhs/characters.json"
PREFIXED = f"{MOD_ID}/localization/zhs/characters.json"  # ATA-style, no res:// prefix


def main():
    meta = pcktool.parse_pck(SRC_PCK)
    entries = [(name, off, size) for name, off, size, _, _ in meta["entries"]]
    files = []
    loc_blob = None
    for name, off, size in entries:
        blob = meta["data"][meta["file_base"] + off:meta["file_base"] + off + size]
        files.append((name, blob))
        if name == LOC_KEY:
            loc_blob = blob
    assert loc_blob is not None, "localization entry missing from pck"
    # sanity: check the values we expect
    loc = json.loads(loc_blob.decode("utf-8"))
    assert loc["DEFECT.title"] == "\u84dd\u8272\u5927\u80a5\u9c7c", loc["DEFECT.title"]
    assert loc["DEFECT.description"] == "\u4e00\u53ea\u7231\u5403\u767d\u996d\u7684\u84dd\u8272\u5927\u80a5\u9c7c\u3002"

    have = [f[0] for f in files]
    if PREFIXED not in have:
        files.append((PREFIXED, loc_blob))
    print("entries:", len(files))

    pcktool.build_pck(OUT_PCK, files, ref_header_from=SRC_PCK)

    # verify by re-parsing
    m2 = pcktool.parse_pck(OUT_PCK)
    names = [e[0] for e in m2["entries"]]
    assert PREFIXED in names, "prefixed entry missing after rebuild"
    for (n1, _), (n2, o2, s2, _, _) in zip(files, m2["entries"]):
        assert n1 == n2
        b2 = m2["data"][m2["file_base"] + o2:m2["file_base"] + o2 + s2]
        assert b2 == dict(files)[n2], n2
    print("verified", len(m2["entries"]), "entries,", os.path.getsize(OUT_PCK), "bytes")
    print("new entry:", PREFIXED)


if __name__ == "__main__":
    main()
