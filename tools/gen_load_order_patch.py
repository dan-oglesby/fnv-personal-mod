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

Second job (2026-11-18): script variables for leveled spawns. A spawn point that re-rolls from one
creature to another keeps the old creature's script variables. When the two creatures' scripts
declare different variables, the new script reads or writes a variable its data doesn't have, and
the engine logs it, about once a frame per creature: "Variable ID 2 not found ... vGlowingOneSCRIPT"
and "Trying to set variableID 2 in script 'OblivionSpawnTestScript'" (8,400 errors in one minute
near IWS spawns, whose null creature runs OblivionSpawnTestScript with one variable while Glowing
Ones in the same lists run vGlowingOneSCRIPT with three). For every leveled list whose creatures
run scripts with different variable numbers, each of those scripts gets the variables it lacks:
added as unused floats ("float lvlPadN"), in the winning version of the script, with its compiled
code untouched (code refers to variables only by number, so an unused one changes nothing). The
source text gets the same declarations, so a recompile in the GECK numbers them the same way.

Third job (2026-11-18), only while Wasteland Bank is installed (WastelandBank.esp in the load order):
every mailbox is a bank counter. Opening one runs Wasteland Bank's OnActivate handler, which opens
the counter's menu, so the mailbox's own opening has to stay shut: each mailbox container
(MAILBOXES below, FalloutNV.esm) gets the empty OnActivate script vHDLegateCampExitDoorScript
(0x148137), the one WastelandBank.esp gives the Mojave Express dropbox. The bank's "look inside"
opens it with Activate and the script skipped. Only records the base game, a DLC or YUP win, and
that have no script of their own, are touched; anything else is left as the load order has it.
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


def subs_of(d):
    return list(audit.subrecords(d))


def script_var_fixes(order, plugins):
    """[(record bytes, tag, edid, source plugin)]: scripts given the variables their leveled-list
    neighbours use. Records come from the winning version; their form IDs stay in the source
    plugin's numbering and are remapped by the caller."""
    pos = {n: i for i, n in enumerate(order)}

    def key(p, n, fid):
        idx = fid >> 24
        return ((p["masters"][idx] if idx < len(p["masters"]) else n).lower(), fid & 0xFFFFFF)

    win = {}
    for n in order:
        p = plugins[n]
        for tag, fid, flags, off, size in p["recs"]:
            if tag in (b"CREA", b"NPC_", b"LVLC", b"LVLN", b"SCPT") and (fid >> 24) <= len(p["masters"]):
                win[key(p, n, fid)] = (n, tag, fid, flags, off, size)
    script_of, entries, varset = {}, {}, {}
    for k, (n, tag, fid, flags, off, size) in win.items():
        d = data_of(plugins[n], off, size, flags)
        if d is None:
            continue
        subs = subs_of(d)
        if tag in (b"CREA", b"NPC_"):
            s_ = next((struct.unpack("<I", v)[0] for t, v in subs if t == b"SCRI" and len(v) == 4), 0)
            if s_:
                script_of[k] = key(plugins[n], n, s_)
        elif tag == b"SCPT":
            varset[k] = {struct.unpack_from("<I", v)[0] for t, v in subs if t == b"SLSD" and len(v) >= 4}
        else:
            entries[k] = [key(plugins[n], n, struct.unpack_from("<I", v, 4)[0]) for t, v in subs if t == b"LVLO" and len(v) >= 8]

    def leaves(k, seen):
        if k in seen:
            return set()
        seen.add(k)
        if k in entries:
            out = set()
            for e in entries[k]:
                out |= leaves(e, seen)
            return out
        return {k}

    need = {}                                   # script -> variable numbers it should have
    for lst in entries:
        scripts = {script_of[c] for c in leaves(lst, set()) if c in script_of and script_of[c] in varset}
        if len(scripts) < 2:
            continue
        union = set().union(*(varset[s_] for s_ in scripts))
        for s_ in scripts:
            if union - varset[s_]:
                need.setdefault(s_, set()).update(union)
    out = []
    for s_, wanted in sorted(need.items()):
        n, tag, fid, flags, off, size = win[s_]
        p = plugins[n]
        d = data_of(p, off, size, flags)
        subs = subs_of(d)
        have = varset[s_]
        missing = sorted(wanted - have)
        nl = b"\r\n"
        rebuilt, inserted = b"", False
        last_var = max((i for i, (t, v) in enumerate(subs) if t in (b"SCVR", b"SLSD")), default=None)
        sctx_at = next((i for i, (t, v) in enumerate(subs) if t == b"SCTX"), None)
        after = last_var if last_var is not None else (sctx_at if sctx_at is not None else
                next(i for i, (t, v) in enumerate(subs) if t == b"SCDA"))
        for i, (t, v) in enumerate(subs):
            if t == b"SCHR":
                hdr = bytearray(v)
                struct.pack_into("<I", hdr, 12, max(struct.unpack_from("<I", hdr, 12)[0], max(missing)))
                v = bytes(hdr)
            elif t == b"SCTX":
                decl = nl.join(b"float lvlPad%d" % m for m in missing)
                text = v.rstrip(b"\0")
                lines = text.split(b"\n")
                # after the script's own declarations (before its first block), so a recompile
                # numbers the old variables as before and the new ones after them
                at = next((j + 1 for j, line in enumerate(lines) if line.strip().lower().startswith((b"scn", b"scriptname"))), 0)
                for j, line in enumerate(lines):
                    w = line.strip().lower().split(b";")[0].split()
                    if w and w[0] == b"begin":
                        break
                    if w and w[0] in (b"short", b"int", b"long", b"float", b"ref", b"reference", b"array_var", b"string_var"):
                        at = j + 1
                v = b"\n".join(lines[:at] + [b"; script variables for leveled spawns (LoadOrderPatch)\r", decl + b"\r"] + lines[at:]) + b"\0"
            rebuilt += sub(t, v)
            if i == after and not inserted:
                for m in missing:
                    rebuilt += sub(b"SLSD", struct.pack("<I", m) + bytes(20)) + sub(b"SCVR", b"lvlPad%d\0" % m)
                inserted = True
        ed = next((v.rstrip(b"\0").decode("latin1") for t, v in subs if t == b"EDID"), "")
        header = p["bytes"][off: off + 24]
        rec = b"SCPT" + struct.pack("<I", len(rebuilt)) + struct.pack("<I", struct.unpack_from("<I", header, 8)[0] & ~0x40000) + header[12:24] + rebuilt
        out.append((rec, b"SCPT", "%s: variables %s added" % (ed, ", ".join(map(str, missing))), n))
    return out


# The mailbox containers (FalloutNV.esm object IDs): MailDropbox01New, MailboxClean, MailboxDestroyed,
# MailboxDestroyedUnarmed, MailboxDestroyedGuns, VLootMailDropboxGen01-10, VLootMailboxDestroyedGen01-05,
# VLootMailboxCleanGen01-05. Wasteland Bank's MailBases.txt lists the same ones.
MAILBOXES = ([0x019F3C, 0x017F2D, 0x017F2E, 0x070BA6, 0x070BA7] + list(range(0x1677E9, 0x1677F3))
             + list(range(0x167A96, 0x167AA0)))
EMPTY_ACTIVATE = 0x148137   # vHDLegateCampExitDoorScript: an OnActivate block that does nothing


def bank_mailboxes(order, plugins):
    """[(record bytes, b"CONT", edid, source)] for the mailboxes, each with the empty script."""
    if "WastelandBank.esp" not in order:
        return []
    numbered = {"falloutnv.esm", YUP.lower()} | {m.lower() for m in plugins[YUP]["masters"]}
    win = {}
    for n in order:
        p = plugins[n]
        for tag, fid, flags, off, size in p["recs"]:
            if tag != b"CONT":
                continue
            idx = fid >> 24
            owner = p["masters"][idx] if idx < len(p["masters"]) else n
            if owner.lower() == "falloutnv.esm" and (fid & 0xFFFFFF) in MAILBOXES:
                win[fid & 0xFFFFFF] = (n, fid, flags, off, size)
    out = []
    for oid in MAILBOXES:
        if oid not in win:
            continue
        n, fid, flags, off, size = win[oid]
        if n.lower() not in numbered:          # its numbering may not match ours: leave it be
            print("  mailbox %06X: won by %s, left as it is" % (oid, n))
            continue
        d = data_of(plugins[n], off, size, flags)
        if d is None:
            continue
        subs = subs_of(d)
        if any(t == b"SCRI" for t, _ in subs):  # a mod gave it a script: leave it be
            print("  mailbox %06X: has a script already (%s), left as it is" % (oid, n))
            continue
        body, done = b"", False
        for t, v in subs:
            if not done and t in (b"CNTO", b"COED", b"DATA"):
                body += sub(b"SCRI", struct.pack("<I", EMPTY_ACTIVATE))
                done = True
            body += sub(t, v)
        ed = next((v for t, v in subs if t == b"EDID"), b"").rstrip(b"\0").decode("latin1")
        # uncompressed now, so the compressed flag is cleared
        rec = b"CONT" + struct.pack("<III", len(body), flags & ~0x40000, fid) + p_hdr_tail(plugins[n], off) + body
        out.append((rec, b"CONT", ed, n))
    return out


def p_hdr_tail(p, off):
    """A record header's last 8 bytes (version control info and form version), as the source has them."""
    return p["bytes"][off + 16: off + 24]


def remap(rec, src, masters, plugins):
    """The record's form IDs (header and SCRO) moved from the source plugin's numbering to ours."""
    names = list(plugins[src]["masters"]) + [src]
    def fix(fid):
        idx = fid >> 24
        name = names[idx] if idx < len(names) else src
        return (masters.index(name) << 24) | (fid & 0xFFFFFF)
    rec = bytearray(rec)
    struct.pack_into("<I", rec, 12, fix(struct.unpack_from("<I", rec, 12)[0]))
    body = bytes(rec[24:])
    out, i = b"", 0
    while i + 6 <= len(body):
        t, ln = body[i:i + 4], struct.unpack_from("<H", body, i + 4)[0]
        v = body[i + 6: i + 6 + ln]
        if t == b"SCRO" and ln == 4:
            v = struct.pack("<I", fix(struct.unpack("<I", v)[0]))
        out += sub(t, v)
        i += 6 + ln
    return bytes(rec[:24]) + out


def main():
    if not audit.PLUGINS_TXT.exists() or not (audit.DATA / YUP).exists():
        print("gen_load_order_patch: no plugins.txt or no YUP; nothing to do")
        return
    # the patch itself is never part of the analysis: once enabled, its own records would count as
    # the winners, so the fixes it forwards would look undone by nobody and drop out, and it would
    # flip between full and empty on alternate builds (2026-11-18)
    order = [n for n in audit.load_order() if (audit.DATA / n).exists() and n.lower() != OUT.name.lower()]
    if YUP not in order:
        return
    plugins = {n: audit.read_plugin(audit.DATA / n) for n in order}
    found = find(order, plugins)
    scripts = script_var_fixes(order, plugins)
    scripts += bank_mailboxes(order, plugins)
    if not found and not scripts:
        if OUT.exists():
            OUT.unlink()
            print("gen_load_order_patch: nothing to forward; removed", OUT.relative_to(ROOT))
        return
    masters = list(plugins[YUP]["masters"]) + [YUP]
    pos = {n: i for i, n in enumerate(order)}
    extra = {w for _, _, _, w in found} | {src for _, _, _, src in scripts}
    for m in list(extra):                       # a source plugin's own masters come along
        extra |= set(plugins[m]["masters"]) if m in plugins else set()
    # masters stay in load order (the first ones are YUP's masters and YUP, as the forwarded
    # records are numbered against them)
    masters += sorted((m for m in extra if m not in masters and m in pos), key=lambda m: pos[m])
    groups = {}
    for raw, tag, _, _ in found:
        groups.setdefault(tag, b"")
        groups[tag] += raw
    for raw, tag, _, src in scripts:
        groups.setdefault(tag, b"")
        groups[tag] += remap(raw, src, masters, plugins)
    found = found + [(None, tag, ed, src) for _, tag, ed, src in scripts]
    body = b"".join(b"GRUP" + struct.pack("<I", 24 + len(g)) + tag + struct.pack("<iHHHH", 0, 0, 0, 0, 0) + g
                    for tag, g in groups.items())
    hdr = sub(b"HEDR", struct.pack("<fiI", 1.34, len(found), 0x800)) + sub(b"CNAM", b"fnv-personal-mod\0")
    hdr += sub(b"SNAM", b"Forwards fixes undone by vanilla copies; script variables for leveled spawns; mailboxes as bank counters (generated locally)\0")
    for m in masters:
        hdr += sub(b"MAST", m.encode("latin1") + b"\0") + sub(b"DATA", bytes(8))
    data = b"TES4" + struct.pack("<IIIIHH", len(hdr), 0, 0, 0, 15, 0) + hdr + body   # form version 15, as make_plugins
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if not OUT.exists() or OUT.read_bytes() != data:
        OUT.write_bytes(data)
    print("gen_load_order_patch: %d record(s) into %s" % (len(found), OUT.relative_to(ROOT)))
    for raw, tag, ed, winner in found:
        if raw is None:
            print("  %s %s (from %s)" % (tag.decode(), ed, winner))
        else:
            print("  %s %s (undone by %s)" % (tag.decode(), ed, winner))


if __name__ == "__main__":
    main()
