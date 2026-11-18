"""Generate LoadOrderPatch.esp: forward fixes that a later plugin undoes by carrying a vanilla copy.

    python tools/gen_load_order_patch.py      (build.py runs it)

YUP (the unofficial patch) fixes thousands of records in the official masters. A plugin loading
after it that carries an unchanged vanilla copy of one of those records puts the original bug
back. This finds every record where:
  - YUP's version differs from the official master's, and
  - the winning version (a plugin after YUP) is byte-identical to the official master's,
and writes those records, exactly as YUP has them, into src/Load Order Patch/LoadOrderPatch.esp.
Its masters are YUP's masters, YUP itself and the plugins it corrects, so it always loads after
them. Only exact vanilla copies are forwarded: a plugin's own deliberate changes are never touched.

The output is built from the user's own files and contains YUP's record data, so it is not
committed (the repo's rule for third-party content): it lives only in the local build and staging.
Nothing is written when there is nothing to forward (and a stale patch is removed).
"""
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_load_order as audit  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "Load Order Patch" / "LoadOrderPatch.esp"
YUP = "YUP - Base Game + All DLC.esm"
SKIP = {b"CELL", b"WRLD", b"NAVM", b"NAVI", b"LAND", b"REFR", b"ACHR", b"ACRE", b"PGRE", b"PMIS",
        b"INFO", b"GRUP"}   # placed and world records need their parent groups: never forwarded here


def sub(tag, data):
    return tag + struct.pack("<H", len(data)) + data


def data_of(p, off, size, flags):
    d = p["bytes"][off + 24: off + 24 + size]
    if flags & 0x40000:
        try:
            d = zlib.decompress(d[4:])
        except zlib.error:
            return None
    return d


def find(order, plugins):
    """[(record bytes from YUP, tag, edid, plugin that undid it)]"""
    pos = {n: i for i, n in enumerate(order)}
    yup = plugins[YUP]
    ymasters = [m.lower() for m in yup["masters"]]
    owners = {m for m in ymasters if m in audit.OFFICIAL}

    def key(p, n, fid):
        nm = len(p["masters"])
        idx = fid >> 24
        return ((p["masters"][idx] if idx < nm else n).lower(), fid & 0xFFFFFF)

    index = {}                                     # key -> {plugin: (offset, size, flags, tag)}
    for n in order:
        p = plugins[n]
        for tag, fid, flags, off, size in p["recs"]:
            if tag in SKIP or (fid >> 24) > len(p["masters"]):
                continue
            k = key(p, n, fid)
            if k[0] in owners:
                index.setdefault(k, {})[n] = (off, size, flags, tag)
    out = []
    for k, by in index.items():
        owner = next((n for n in by if n.lower() == k[0]), None)
        if YUP not in by or owner is None:
            continue
        later = [n for n in by if pos[n] > pos[YUP]]
        if not later:
            continue
        winner = max(later, key=lambda n: pos[n])
        oy, sy, fy, tag = by[YUP]
        dy = data_of(yup, oy, sy, fy)
        dv = data_of(plugins[owner], *by[owner][:3])
        dw = data_of(plugins[winner], *by[winner][:3])
        if None in (dy, dv, dw) or dy == dv or dw != dv:
            continue
        ed = [v for t, v in audit.subrecords(dy) if t == b"EDID"]
        out.append((yup["bytes"][oy: oy + 24 + sy], tag, ed[0].rstrip(b"\0").decode("latin1") if ed else "", winner))
    return out


def main():
    if not audit.PLUGINS_TXT.exists() or not (audit.DATA / YUP).exists():
        print("gen_load_order_patch: no plugins.txt or no YUP; nothing to do")
        return
    order = [n for n in audit.load_order() if (audit.DATA / n).exists()]
    if YUP not in order:
        return
    plugins = {n: audit.read_plugin(audit.DATA / n) for n in order}
    found = find(order, plugins)
    if not found:
        if OUT.exists():
            OUT.unlink()
            print("gen_load_order_patch: nothing to forward; removed", OUT.relative_to(ROOT))
        return
    masters = list(plugins[YUP]["masters"]) + [YUP]
    for _, _, _, winner in found:
        if winner not in masters:
            masters.append(winner)
    groups = {}
    for raw, tag, _, _ in found:
        groups.setdefault(tag, b"")
        groups[tag] += raw
    body = b"".join(b"GRUP" + struct.pack("<I", 24 + len(g)) + tag + struct.pack("<iHHHH", 0, 0, 0, 0, 0) + g
                    for tag, g in groups.items())
    hdr = sub(b"HEDR", struct.pack("<fiI", 1.34, len(found), 0x800)) + sub(b"CNAM", b"fnv-personal-mod\0")
    hdr += sub(b"SNAM", b"Forwards fixes undone by vanilla copies (generated locally)\0")
    for m in masters:
        hdr += sub(b"MAST", m.encode("latin1") + b"\0") + sub(b"DATA", bytes(8))
    data = b"TES4" + struct.pack("<IIIIHH", len(hdr), 0, 0, 0, 15, 0) + hdr + body   # form version 15, as make_plugins
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if not OUT.exists() or OUT.read_bytes() != data:
        OUT.write_bytes(data)
    print("gen_load_order_patch: %d record(s) forwarded into %s" % (len(found), OUT.relative_to(ROOT)))
    for _, tag, ed, winner in found:
        print("  %s %s (undone by %s)" % (tag.decode(), ed, winner))


if __name__ == "__main__":
    main()
