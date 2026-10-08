"""Extract all localization/zhs/*.json entries from the game pck (v3, index at tail)."""
import struct, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))

GAME = r"D:\Steam\steamapps\common\Slay the Spire 2\SlayTheSpire2.pck"
OUT = os.path.join(os.path.dirname(__file__), "base_zhs")


def find_entries(f, needle):
    f.seek(0, 2)
    total = f.tell()
    hits = []
    f.seek(total - (1 << 26))  # last 64MB
    base = f.tell()
    prev = b""
    while True:
        d = f.read(1 << 26)
        if not d:
            break
        buf = prev + d
        start = 0
        while True:
            i = buf.find(needle, start)
            if i < 0:
                break
            hits.append(base - len(prev) + i)
            start = i + 1
        if len(d) < (1 << 26):
            break
        prev = buf[-32:]
        base += len(d)
    return hits


def main():
    os.makedirs(OUT, exist_ok=True)
    with open(GAME, "rb") as f:
        hits = find_entries(f, b"localization/zhs/")
        entries = {}
        for h in hits:
            f.seek(h - 4)
            (plen,) = struct.unpack("<I", f.read(4))
            if not (0 < plen < 512):
                continue
            raw = f.read(plen)
            path = raw.rstrip(b"\x00").decode("utf-8", "replace")
            if not path.startswith("localization/zhs/") or not path.endswith(".json"):
                continue
            off, size = struct.unpack("<QQ", f.read(16))
            if size > 5_000_000:
                continue
            entries[path] = (off, size)
        file_base = 0x70
        for path, (off, size) in sorted(entries.items()):
            f.seek(file_base + off)
            blob = f.read(size)
            try:
                obj = json.loads(blob.decode("utf-8"))
            except Exception as e:
                print("BAD JSON", path, e)
                continue
            rel = path.split("localization/zhs/")[1]
            dst = os.path.join(OUT, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, "wb").write(blob)
            print(f"{rel}: {len(obj)} keys, {size}B")


if __name__ == "__main__":
    main()
