"""Write tools/fnv_commands.txt: every console and script command name the game itself defines
(long names and short aliases), read from FalloutNV.exe's two command tables.

    python tools/gen_fnv_commands.py

check_scripts.py uses the list to catch script variables named like a command. A variable named
after any command, or its alias, makes xNVSE refuse to compile the whole file. The shorter
built-in list missed rw (RevertWorld) and SSP (SetSkyParam), and on 2026-11-17 six files failed
to compile in game because of them.

How: find a known name's string in the exe, then the pointer to it in a command table. Walk the
table's 0x28-byte entries (long name, short name, opcode, ...) both ways from there.
"""
import os
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "fnv_commands.txt"
EXE = Path(os.environ.get("FNV_EXE", r"C:\Program Files (x86)\Steam\steamapps\common\Fallout New Vegas\FalloutNV.exe"))
ENTRY = 0x28


def main():
    if not EXE.exists():
        print("FalloutNV.exe not found at %s; keeping the existing list" % EXE)
        return
    b = EXE.read_bytes()
    pe = struct.unpack_from("<I", b, 0x3C)[0]
    nsec = struct.unpack_from("<H", b, pe + 6)[0]
    optsz = struct.unpack_from("<H", b, pe + 20)[0]
    base = struct.unpack_from("<I", b, pe + 24 + 28)[0]
    secs, o = [], pe + 24 + optsz
    for _ in range(nsec):
        vsz, va, rsz, raw = struct.unpack_from("<IIII", b, o + 8)
        secs.append((va, vsz, raw, rsz))
        o += 40

    def off2va(off):
        for va, vsz, raw, rsz in secs:
            if raw <= off < raw + rsz:
                return base + va + (off - raw)

    def va2off(v):
        v -= base
        for va, vsz, raw, rsz in secs:
            if va <= v < va + max(vsz, rsz):
                return raw + (v - va)

    def cstr(v):
        if not v:
            return None
        off = va2off(v)
        if off is None:
            return None
        end = b.find(b"\0", off)
        return b[off:end].decode("latin1") if 0 < end - off < 80 else None

    def ok(s):
        return bool(s) and s.replace("_", "").isalnum()

    def table(known):
        ref = b.find(struct.pack("<I", off2va(b.find(known.encode() + b"\0"))))
        start = ref
        while ok(cstr(struct.unpack_from("<I", b, start - ENTRY)[0])):
            start -= ENTRY
        out, o = [], start
        while ok(cstr(struct.unpack_from("<I", b, o)[0])):
            ln, sn = struct.unpack_from("<II", b, o)
            out.append(cstr(ln))
            if ok(cstr(sn)):
                out.append(cstr(sn))
            o += ENTRY
        return out

    names = sorted(set(table("ToggleGodMode") + table("ReleaseWeatherOverride")), key=str.lower)
    OUT.write_text("\n".join(names) + "\n", encoding="ascii")
    print("wrote %s: %d names" % (OUT.relative_to(ROOT), len(names)))


if __name__ == "__main__":
    main()
