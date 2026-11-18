"""Audit the New Vegas load order for structural problems that crash the game.

    python tools/audit_load_order.py            # report to reports/load_order_audit.txt

Reads plugins.txt (the active load order) and every plugin in the game's Data folder, without
changing anything, and reports:
- masters missing from the load order, or loading after the plugin that needs them;
- deleted references (UDRs: REFR/ACHR/ACRE/PGRE/PMIS records flagged deleted). Another plugin that
  edits or links to a deleted reference crashes the game when that cell loads; the usual fix
  (xEdit's "undelete and disable") is to restore it, initially disabled;
- deleted navmeshes (NAVM flagged deleted), which crash the pathfinder;
- records whose form ID points past the plugin's own master list (a broken plugin);
- the overrides map: which plugins change each record (saved for the conflict step).

Bethesda's own masters are checked for masters and form IDs only: their deleted records are part of
the shipped game. The report lists records by form ID and editor ID, read from the user's own
files; it goes to reports/, which is not committed.
"""
import os
import struct
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("FNV_DATA", r"C:\Program Files (x86)\Steam\steamapps\common\Fallout New Vegas\Data"))
PLUGINS_TXT = Path(os.environ.get("LOCALAPPDATA", "")) / "FalloutNV" / "plugins.txt"
OUT = ROOT / "reports" / "load_order_audit.txt"
OFFICIAL = {"falloutnv.esm", "deadmoney.esm", "honesthearts.esm", "oldworldblues.esm", "lonesomeroad.esm",
            "gunrunnersarsenal.esm", "classicpack.esm", "mercenarypack.esm", "tribalpack.esm", "caravanpack.esm"}
REF_TYPES = {b"REFR", b"ACHR", b"ACRE", b"PGRE", b"PMIS"}
DELETED = 0x20


def load_order():
    names = []
    for line in PLUGINS_TXT.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip().lstrip("*")
        if line and not line.startswith("#"):
            names.append(line)
    return names


def subrecords(d):
    o, out = 0, []
    while o + 6 <= len(d):
        tag = d[o:o + 4]
        size = struct.unpack_from("<H", d, o + 4)[0]
        out.append((tag, d[o + 6:o + 6 + size]))
        o += 6 + size
    return out


def read_plugin(path):
    """Header (masters, ESM flag) and every record header: (type, formid, flags, offset, size)."""
    b = path.read_bytes()
    assert b[:4] == b"TES4", path
    hsize, hflags = struct.unpack_from("<II", b, 4)
    masters = [v.rstrip(b"\0").decode("latin1") for t, v in subrecords(b[24:24 + hsize]) if t == b"MAST"]
    recs = []

    def walk(off, end):
        while off < end:
            if b[off:off + 4] == b"GRUP":
                size = struct.unpack_from("<I", b, off + 4)[0]
                walk(off + 24, off + size)
                off += size
                continue
            size, flags, fid = struct.unpack_from("<III", b, off + 4)
            recs.append((b[off:off + 4], fid, flags, off, size))
            off += 24 + size
    walk(24 + hsize, len(b))
    return {"masters": masters, "esm": bool(hflags & 1), "recs": recs, "bytes": b}


def edid(p, off, size, flags):
    if flags & 0x40000:
        return ""                                # compressed: the editor ID isn't worth unpacking here
    d = p["bytes"][off + 24:off + 24 + size]
    if d[:4] == b"EDID":
        n = struct.unpack_from("<H", d, 4)[0]
        return d[6:6 + n].rstrip(b"\0").decode("latin1")
    return ""


def main():
    order = load_order()
    pos = {n.lower(): i for i, n in enumerate(order)}
    lines = ["Load order audit: %d plugins (plugins.txt)" % len(order), ""]
    overrides = defaultdict(list)                  # (owner plugin, object id) -> [plugins]
    problems = 0
    for i, name in enumerate(order):
        path = DATA / name
        if not path.exists():
            lines.append("MISSING FILE: %s is in plugins.txt but not in Data" % name)
            problems += 1
            continue
        p = read_plugin(path)
        mine = []
        for m in p["masters"]:
            if m.lower() not in pos:
                mine.append("master %s is not in the load order" % m)
            elif pos[m.lower()] > i:
                mine.append("master %s loads after it" % m)
        nmast = len(p["masters"])
        udr, navm, badid = [], [], 0
        for tag, fid, flags, off, size in p["recs"]:
            idx = fid >> 24
            if idx > nmast:
                badid += 1
                continue
            owner = p["masters"][idx] if idx < nmast else name
            overrides[(owner.lower(), fid & 0xFFFFFF)].append(name)
            if name.lower() in OFFICIAL or not (flags & DELETED):
                continue
            if tag in REF_TYPES:
                udr.append("%08X %s %s" % (fid, tag.decode(), edid(p, off, size, flags)))
            elif tag == b"NAVM":
                navm.append("%08X" % fid)
        if badid:
            mine.append("%d records have form IDs past its master list" % badid)
        if udr:
            mine.append("%d deleted references (UDRs): %s%s" % (len(udr), "; ".join(udr[:8]), " ..." if len(udr) > 8 else ""))
        if navm:
            mine.append("%d deleted navmeshes: %s" % (len(navm), ", ".join(navm[:8])))
        if mine:
            problems += len(mine)
            lines.append("%s (%s, %d records)" % (name, "ESM" if p["esm"] else "ESP", len(p["recs"])))
            lines += ["  - " + x for x in mine]
        del p
    multi = {k: v for k, v in overrides.items() if len(v) > 2}
    lines += ["", "%d problems. %d records are changed by two or more plugins besides their owner." % (problems, len(multi))]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[-30:]))
    print("report:", OUT.relative_to(ROOT))
    return overrides


if __name__ == "__main__":
    main()
