"""Generate Ammo Boxing's plugin and its table from the load order (local only, never committed).

    python tools/gen_ammo_boxes.py      (build.py runs it)

Ammo Boxing (2026-11-19) hand-loads the ammo you carry into boxes, slowly, and opens them again as
your weapons need rounds. A box is an ordinary item, so it sells (whole, at full value) and is
saved. Ammo Boxes (Nexus 74951), which Dan uses so that merchants sell ammo by the box, makes its
boxes at every launch as temporary forms, which the game doesn't save, so they can't be carried.

What this writes:
  - src/Ammo Boxing/AmmoBoxing.esp: one MISC record per playable ammo type in the load order (Ammo
    Boxes' rules: only kinds with more than one round to a clip, unless its bIncludeSingleRounds is
    on). Named as Ammo Boxes names its boxes, "<ammo> Box [N]". N is Ammo Boxes' count for the
    ammo's category (pistol 50, rifle 20, assault 100, shell 12, anti-materiel 10, read from its
    config/Ammo Boxes/ammo_type_*.txt), else the ammo's clip size. Value: N rounds at the ammo's own
    value (what Ammo Boxes charges for its box). Weight: N rounds' weight plus 5 percent and 0.1 lb
    of cardboard. Model, icon and sounds: one of the base game's ammo boxes. Its only master is
    FalloutNV.esm.
  - src/Ammo Boxing/nvse/user_defined_functions/AmmoBoxing/Table.txt: a script that tells the mod,
    on every load, which box holds which ammo and how many rounds (Reg.txt).
  - local/ammo_box_ids.json: each ammo's box object ID, kept between builds. Boxes are saved in
    your inventory, so an ammo type's box must keep its ID when ammo mods come and go.
Both outputs are built from the user's own plugins (other mods' ammo names and form IDs), so they
are not committed (.gitignore). Without FalloutNV.esm nothing is written.
"""
import datetime as dt
import json
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_load_order as audit  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MOD = ROOT / "src" / "Ammo Boxing"
ESP = MOD / "AmmoBoxing.esp"
TABLE = MOD / "nvse" / "user_defined_functions" / "AmmoBoxing" / "Table.txt"
IDS = ROOT / "local" / "ammo_box_ids.json"
CONFIG = audit.DATA / "config" / "Ammo Boxes"
SKIP = {"ammoboxing.esp", "loadorderpatch.esp"}
CATEGORIES = {"pistol": 50, "rifle": 20, "assault": 100, "shell": 12, "anti-materiel": 10}
EXTRA = 0.05      # a box weighs its rounds plus 5 percent
CARDBOARD = 0.1   # plus this, in pounds
FIRST_ID = 0x800
# the base game's ammo boxes (FalloutNV.esm MISC), whose model, icon and sounds the boxes borrow
TEMPLATE = {"pistol": 0x16664F,      # BoxAmmo38Special
            "rifle": 0x16664E,       # BoxAmmo223
            "anti-materiel": 0x16664E,
            "assault": 0x166651,     # BoxAmmo556mmSurplus
            "shell": 0x16664F,
            "ecp": 0x166653,         # BoxAmmoElectronChargePackBulk
            "sec": 0x166654,         # BoxAmmoSmallEnergyCellBulk
            "mfc": 0x166655,         # BoxAmmoMicrofusionCellBulk
            None: 0x16664F}
KEEP = (b"OBND", b"MODL", b"MODT", b"ICON", b"MICO", b"YNAM", b"ZNAM")


def sub(tag, data):
    return tag + struct.pack("<H", len(data)) + data


def body_of(p, off, size, flags):
    d = p["bytes"][off + 24: off + 24 + size]
    if flags & 0x40000:
        d = zlib.decompress(d[4:])
    return d


def text(v):
    return v.rstrip(b"\0").decode("latin1")


def ini_flag(name, default):
    ini = audit.DATA / "config" / "Ammo Boxes.ini"
    if not ini.exists():
        return default
    for line in ini.read_text(encoding="latin1").splitlines():
        line = line.strip()
        if line.lower().startswith(name.lower() + "="):
            try:
                return int(line.split("=", 1)[1].strip())
            except ValueError:
                return default
    return default


def main():
    if not (audit.DATA / "FalloutNV.esm").exists():
        print("gen_ammo_boxes: no FalloutNV.esm; nothing written")
        return
    order = [n for n in audit.load_order() if (audit.DATA / n).exists() and n.lower() not in SKIP]
    plugins = {n: audit.read_plugin(audit.DATA / n) for n in order}
    pos = {n.lower(): i for i, n in enumerate(order)}

    def owner_of(p, n, fid):
        idx = fid >> 24
        return (p["masters"][idx] if idx < len(p["masters"]) else n).lower()

    win = {}                                   # (owner, object id) -> (tag, plugin, subrecords)
    for n in order:
        p = plugins[n]
        for tag, fid, flags, off, size in p["recs"]:
            if tag in (b"AMMO", b"FLST", b"MISC"):
                win[(owner_of(p, n, fid), fid & 0xFFFFFF)] = (tag, n, off, size, flags)

    def subs(key):
        tag, n, off, size, flags = win[key]
        return tag, n, list(audit.subrecords(body_of(plugins[n], off, size, flags)))

    # Ammo Boxes' categories: each file lists ammo or form lists of ammo, as @Plugin:XXXXXX
    category = {}
    if ini_flag("bRealisticRoundsPerBox", 1):
        for cat in CATEGORIES:
            f = CONFIG / ("ammo_type_%s.txt" % cat)
            if not f.exists():
                continue
            for entry in f.read_text(encoding="latin1").replace("\n", "\t").split("\t"):
                entry = entry.strip()
                if not entry.startswith("@") or ":" not in entry:
                    continue
                plug, hexid = entry[1:].rsplit(":", 1)
                try:
                    key = (plug.lower(), int(hexid, 16))
                except ValueError:
                    continue
                if key not in win:
                    continue
                tag, n, ss = subs(key)
                if tag == b"AMMO":
                    category[key] = cat
                elif tag == b"FLST":
                    p = plugins[n]
                    for t, v in ss:
                        if t == b"LNAM" and len(v) == 4:
                            fid = struct.unpack("<I", v)[0]
                            category[(owner_of(p, n, fid), fid & 0xFFFFFF)] = cat
    singles = ini_flag("bIncludeSingleRounds", 0)

    templates = {}
    for k, oid in TEMPLATE.items():
        key = ("falloutnv.esm", oid)
        if key in win:
            templates[k] = [(t, v) for t, v in subs(key)[2] if t in KEEP]
    if None not in templates:
        print("gen_ammo_boxes: the base game's ammo box (BoxAmmo38Special) wasn't found; nothing written")
        return

    ids = json.loads(IDS.read_text()) if IDS.exists() else {}
    next_id = max([FIRST_ID - 1] + list(ids.values())) + 1
    boxes = []
    used_edids = set()
    for key in sorted((k for k, v in win.items() if v[0] == b"AMMO"), key=lambda k: (pos.get(k[0], 999), k[1])):
        tag, n, ss = subs(key)
        data = next((v for t, v in ss if t == b"DATA"), b"")
        dat2 = next((v for t, v in ss if t == b"DAT2"), b"")
        name = text(next((v for t, v in ss if t == b"FULL"), b""))
        edid = text(next((v for t, v in ss if t == b"EDID"), b""))
        if len(data) < 13 or not name:
            continue
        flags, value, clip = data[4], struct.unpack_from("<i", data, 8)[0], data[12]
        if flags & 0x02:                       # not playable
            continue
        if clip < 2 and not singles:           # missiles, mini nukes: Ammo Boxes sells them singly
            continue
        weight = struct.unpack_from("<f", dat2, 8)[0] if len(dat2) >= 12 else 0.0
        cat = category.get(key)
        count = CATEGORIES[cat] if cat else max(clip, 1)
        low = (edid + " " + name).lower()
        look = cat
        if "electron" in low:
            look = "ecp"
        elif "microfusion" in low or "micro fusion" in low:
            look = "mfc"
        elif "energycell" in low or "energy cell" in low:
            look = "sec"
        tmpl = templates.get(look) or templates[None]
        ident = "%s:%06X" % (key[0], key[1])
        if ident not in ids:
            ids[ident] = next_id
            next_id += 1
        box_edid = ("ABox" + "".join(c for c in edid if c.isalnum()))[:60] or "ABox%06X" % ids[ident]
        if box_edid.lower() in used_edids:
            box_edid = (box_edid[:52] + "%06X" % ids[ident])
        used_edids.add(box_edid.lower())
        box_value = count * value if value > 0 else count
        box_weight = round(count * weight * (1 + EXTRA) + CARDBOARD, 2)
        boxes.append({"oid": ids[ident], "edid": box_edid, "name": "%s Box [%d]" % (name, count)[:120],
                      "value": box_value, "weight": box_weight, "tmpl": tmpl, "ammo_plugin": key[0],
                      "ammo_oid": key[1], "ammo_name": name, "count": count})

    # the plugin
    recs = b""
    for b in sorted(boxes, key=lambda b: b["oid"]):
        body = sub(b"EDID", b["edid"].encode("latin1") + b"\0")
        tm = dict(b["tmpl"])
        if b"OBND" in tm:
            body += sub(b"OBND", tm[b"OBND"])
        body += sub(b"FULL", b["name"].encode("latin1", "replace") + b"\0")
        for t in (b"MODL", b"MODT", b"ICON", b"MICO", b"YNAM", b"ZNAM"):
            if t in tm:
                body += sub(t, tm[t])
        body += sub(b"DATA", struct.pack("<if", b["value"], b["weight"]))
        recs += b"MISC" + struct.pack("<III", len(body), 0, 0x01000000 | b["oid"]) + struct.pack("<IHH", 0, 15, 0) + body
    group = b"GRUP" + struct.pack("<I", 24 + len(recs)) + b"MISC" + struct.pack("<iHHHH", 0, 0, 0, 0, 0) + recs
    hdr = sub(b"HEDR", struct.pack("<fiI", 1.34, len(boxes), next_id)) + sub(b"CNAM", b"fnv-personal-mod\0")
    hdr += sub(b"SNAM", b"Ammo Boxing: a box for every ammo type (generated locally from the load order)\0")
    hdr += sub(b"MAST", b"FalloutNV.esm\0") + sub(b"DATA", bytes(8))
    plugin = b"TES4" + struct.pack("<IIIIHH", len(hdr), 0, 0, 0, 15, 0) + hdr + group
    ESP.parent.mkdir(parents=True, exist_ok=True)
    if not ESP.exists() or ESP.read_bytes() != plugin:
        ESP.write_bytes(plugin)

    # the table
    names = {n.lower(): n for n in order}
    lines = ["; Ammo Boxing: GENERATED by tools/gen_ammo_boxes.py from this game's load order (%s)." % dt.date.today(),
             "; Do not edit, and do not commit: it names other mods' ammo. Each box in AmmoBoxing.esp, the ammo",
             "; it holds and how many rounds: Reg.txt puts them on the forms (\"*_abBox\", \"*_abAmmo\", \"*_abN\").",
             "int iMe", "int iP", "ref rBx", "ref rAm", "ref rReg", "", "begin Function {}",
             '\tlet iMe := GetModIndex "AmmoBoxing.esp"', '\tlet rReg := CompileScript "AmmoBoxing/Reg.txt"',
             "\tif eval (IsFormValid rReg) == 0", "\t\treturn", "\tendif"]
    last = None
    for b in sorted(boxes, key=lambda b: (pos.get(b["ammo_plugin"], 999), b["ammo_oid"])):
        if b["ammo_plugin"] != last:
            last = b["ammo_plugin"]
            lines.append('\tlet iP := GetModIndex "%s"' % names.get(last, last).replace('"', ""))
        lines.append("\tlet rBx := BuildRef iMe %d\t; %s" % (b["oid"], b["name"]))
        lines.append("\tlet rAm := BuildRef iP %d" % b["ammo_oid"])
        lines.append("\tcall rReg rBx rAm %d" % b["count"])
    lines += ["\tSetFunctionValue %d" % len(boxes), "end", ""]
    TABLE.parent.mkdir(parents=True, exist_ok=True)
    TABLE.write_text("\n".join(lines), encoding="latin1")
    IDS.parent.mkdir(parents=True, exist_ok=True)
    IDS.write_text(json.dumps(ids, indent=1, sort_keys=True))
    print("gen_ammo_boxes: %d box type(s) into %s and %s" % (len(boxes), ESP.relative_to(ROOT), TABLE.relative_to(ROOT)))


if __name__ == "__main__":
    main()
