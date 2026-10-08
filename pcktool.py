"""Minimal Godot 4 PCK parser/builder (format used by Slay the Spire 2 mod pcks)."""
import struct
import os

MAGIC = 0x43504447  # "GDPC"


def parse_pck(path):
    with open(path, "rb") as f:
        d = f.read()
    assert struct.unpack_from("<I", d, 0)[0] == MAGIC, "bad magic"
    ver = struct.unpack_from("<I", d, 4)[0]
    major, minor, patch = struct.unpack_from("<III", d, 8)
    flags = struct.unpack_from("<I", d, 0x14)[0]
    file_base = struct.unpack_from("<Q", d, 0x18)[0]
    # index offset is right after the fixed 0x60 header; some tools use 0x68
    n60 = struct.unpack_from("<I", d, 0x60)[0]
    n68 = struct.unpack_from("<I", d, 0x68)[0]
    entries = []
    idx = None
    for cand, n in ((0x60, n60), (0x68, n68)):
        if 0 < n < 100000:
            p = cand + 4
            ok = True
            tmp = []
            try:
                for _ in range(n):
                    (plen,) = struct.unpack_from("<I", d, p)
                    p += 4
                    if plen == 0 or plen > 4096:
                        ok = False
                        break
                    raw = d[p:p + plen]
                    p += plen
                    name = raw.rstrip(b"\x00").decode("utf-8")
                    off, size = struct.unpack_from("<QQ", d, p)
                    p += 16
                    md5 = d[p:p + 16]
                    p += 16
                    (eflags,) = struct.unpack_from("<I", d, p)
                    p += 4
                    tmp.append((name, off, size, md5, eflags))
                if ok:
                    entries = tmp
                    idx = cand
                    break
            except struct.error:
                continue
    assert entries, "could not locate index"
    return {
        "ver": ver, "major": major, "minor": minor, "patch": patch,
        "flags": flags, "file_base": file_base, "idx": idx,
        "entries": entries, "data": d,
    }


def extract(meta, name):
    for ename, off, size, md5, eflags in meta["entries"]:
        if ename == name:
            b = meta["file_base"]
            return meta["data"][b + off:b + off + size]
    raise KeyError(name)


def list_entries(meta):
    return [e[0] for e in meta["entries"]]


def build_pck(out_path, files, ref_header_from=None):
    """files: list of (res_path, bytes). Index at 0x68, matching existing mod pck."""
    n = len(files)
    # header: keep same shape as the mod pck
    if ref_header_from and os.path.exists(ref_header_from):
        ref = parse_pck(ref_header_from)
        ver, major, minor, patch, flags = ref["ver"], ref["major"], ref["minor"], ref["patch"], ref["flags"]
        idx = ref["idx"]
    else:
        ver, major, minor, patch, flags, idx = 2, 4, 5, 0, 1, 0x68
    hdr = bytearray(idx)
    struct.pack_into("<I", hdr, 0, MAGIC)
    struct.pack_into("<I", hdr, 4, ver)
    struct.pack_into("<III", hdr, 8, major, minor, patch)
    struct.pack_into("<I", hdr, 0x14, flags)
    # file_base patched later at 0x18
    index = bytearray()
    index += struct.pack("<I", n)
    # placeholder: serialize entries with unknown offsets first to size the index
    parts = []
    for path, blob in files:
        rb = path.encode("utf-8") + b"\x00"
        parts.append((rb, blob))
    # first pass: compute index size
    def serialize_index(file_base):
        buf = bytearray()
        buf += struct.pack("<I", n)
        cursor = file_base
        for rb, blob in parts:
            buf += struct.pack("<I", len(rb))
            buf += rb
            buf += struct.pack("<QQ", cursor - file_base, len(blob))
            buf += b"\x00" * 16  # md5
            buf += struct.pack("<I", 0)  # entry flags
            cursor += len(blob)
        return buf, cursor

    file_base = len(hdr)  # tentative; compute after index
    index, end = serialize_index(file_base)
    # v3 layout: 0x18 = file_base (16-aligned, matching original tooling),
    # 0x20 = index offset (u64). Writing 0 there makes Godot parse the index
    # from file start and hang.
    file_base = (len(hdr) + len(index) + 15) & ~15
    index, end = serialize_index(file_base)
    struct.pack_into("<Q", hdr, 0x18, file_base)
    struct.pack_into("<Q", hdr, 0x20, idx)  # index begins right after header
    with open(out_path, "wb") as f:
        f.write(hdr)
        f.write(index)
        f.write(b"\x00" * (file_base - len(hdr) - len(index)))  # alignment pad
        for rb, blob in parts:
            f.write(blob)
    return out_path
