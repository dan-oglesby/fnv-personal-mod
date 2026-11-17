"""Write the small item plugins (.esp) that some mods use as their menu item.

    python make_plugins.py      # also run by build.py

Each plugin holds one apparel item with no body slot, no script and no weight, modelled on the
Bank Card item in BankCard.esp (Nexus 39741): you equip it from the Pip-Boy's Apparel tab and the
mod's menu opens when you close the Pip-Boy. The plugins carry no script bytecode (that needs the
GECK); the mod's xNVSE scripts watch for the item being equipped (OnActorEquip) and find it by
the plugin's load-order index and the object ID below (BuildRef <index> 2048).

The only master is FalloutNV.esm, so a plugin never pulls in another mod.

A plugin can also carry empty form lists (LISTS below) that its scripts fill at run time, at
object IDs 0x801, 0x802 and so on (BuildRef <index> 2049, 2050...).
"""
import os
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OBJECT_ID = 0x800                  # first free object ID in a plugin; BuildRef index 2048

# plugin file, mod folder in src/, editor ID, name, world model, inventory icon, small icon
ITEMS = [
    ("WastelandBank.esp", "Wasteland Bank", "WBBankCard", "Wasteland Bank Card",
     r"clutter\holodisk\passcardblue.nif",
     r"interface\icons\pipboyimages\items\item_passcard .dds",      # vanilla's own name, with space
     r"interface\icons\pipboyimages_small\items_small\glow_items_passcard.dds"),
    ("AutoSmoke.esp", "Wasteland Tweaks",     # Auto Smoke, part of Wasteland Tweaks since 2026-11-15
     "ASCigaretteCase", "Cigarette Case (Auto Smoke)",
     r"Clutter\Junk\CigarettePack01.NIF",
     r"smoking_edisleado\icons\cigarette_pack.dds",                 # Light Up and Smoke's icon
     None),
    ("WastelandMarket.esp", "Wasteland Market", "WMPamphlet", "Mojave Market Pamphlet",
     r"clutter\junk\militarypamphlet01.nif",
     r"interface\icons\pipboyimages\items\items_skill_mags_barter.dds",      # the barter magazine's icon
     None),
    ("SmartLoot.esp", "Smart Loot", "SLDuffel", "Scavenger's Duffel (Smart Loot)",
     r"clutter\junk\dufflebag.nif",
     r"interface\icons\pipboyimages\items\items_briefcase.dds",
     None),
]

# Plugins holding one miscellaneous item instead (object ID 0x800): plugin file, mod folder,
# editor ID, name, world model, inventory icon, value, weight
MISC_ITEMS = [
    # Fission Power: what a spent battery becomes; it is dropped at your feet when ejected.
    # Same model and icon as the vanilla Fission Battery (FalloutNV.esm 0x033BC6), worth nothing.
    ("FissionPower.esp", "Fission Power", "FPDepletedBattery", "Depleted Fission Battery",
     r"Clutter\Junk\9VoltBattery01.NIF", r"Interface\Icons\PipboyImages\Items\item_junk.dds", 0, 6.0),
]

# plugin file -> editor IDs of empty form lists, in object-ID order from 0x801
LISTS = {
    "SmartLoot.esp": ["SLWantAmmo", "SLWantMods", "SLWantRepair", "SLAlwaysTake"],
}


def sub(tag: str, data: bytes) -> bytes:
    return tag.encode() + struct.pack("<H", len(data)) + data


def z(s: str) -> bytes:
    return s.encode("latin1") + b"\0"


def record(tag: str, flags: int, formid: int, body: bytes) -> bytes:
    # type, data size, flags, FormID, version control, form version 15, unknown
    return tag.encode() + struct.pack("<IIIIHH", len(body), flags, formid, 0, 15, 0) + body


def group(label: str, body: bytes) -> bytes:
    return b"GRUP" + struct.pack("<I", 24 + len(body)) + label.encode() + struct.pack("<iHHHH", 0, 0, 0, 0, 0) + body


def plugin(edid, name, model, icon, small_icon, lists=()) -> bytes:
    body = (sub("EDID", z(edid))
            + sub("OBND", bytes(12))
            + sub("FULL", z(name))
            + sub("BMDT", bytes(8))                      # no body slots, playable
            + sub("MOD2", z(model))
            + sub("ICON", z(icon))
            + (sub("MICO", z(small_icon)) if small_icon else b"")
            + sub("ETYP", struct.pack("<i", 7))          # equipment type: body wear, as the Bank Card
            + sub("DATA", struct.pack("<iif", 0, 100, 0.0))   # value 0, health 100, weight 0
            + sub("DNAM", bytes(12))                     # no DR or DT
            + sub("BNAM", bytes(4)))
    # record flag 0x400 as on the Bank Card
    armo = record("ARMO", 0x400, 0x01000000 | OBJECT_ID, body)
    flsts = b"".join(record("FLST", 0, 0x01000000 | (OBJECT_ID + 1 + i), sub("EDID", z(e)))
                     for i, e in enumerate(lists))
    header = record("TES4", 0, 0,
                    sub("HEDR", struct.pack("<fiI", 1.34, 1 + len(lists), OBJECT_ID + 1 + len(lists)))
                    + sub("CNAM", z("fnv-personal-mod"))
                    + sub("MAST", z("FalloutNV.esm"))
                    + sub("DATA", bytes(8)))
    return header + group("ARMO", armo) + (group("FLST", flsts) if lists else b"")


# Wasteland Bank's courier squad and vault (2026-11-16). The couriers are copies of the vanilla
# mercenary group NPCs (FalloutNV.esm), which take their looks, gear and stats from the mercenary
# leveled lists, so every squad looks different. Changed: name, essential, no respawn, no factions
# and the mercenaries' own unaggressive AI data instead of the leveled list's (template flags "use
# factions" and "use AI data" off), one package (stay near where they are), no script. Read from
# the game's FalloutNV.esm at build time; without it the existing plugin is kept.
COURIERS = [   # object ID, editor ID, vanilla NPC to copy
    (0x801, "WBCourierA", 0x165066),   # VSpawnMercenaryMaleGroup01
    (0x802, "WBCourierB", 0x165064),   # VSpawnMercenaryFemaleGroup01
    (0x803, "WBCourierC", 0x165065),   # VSpawnMercenaryMaleGroup02
]
COURIER_NAME = "Bank Courier"
COURIER_PACKAGE = 0x171CEF             # DefaultSandboxCurrentLocation256NoSleepNoWanderNoConv
VAULT_CONT, VAULT_CELL, VAULT_REF = 0x804, 0x805, 0x806
VAULT_MODEL = r"Clutter\Security\GenericSafeWall01.NIF"   # the vanilla wall safe's model
FNV_DATA = Path(os.environ.get("FNV_DATA", r"C:\Program Files (x86)\Steam\steamapps\common\Fallout New Vegas\Data"))


def _subrecords(d: bytes):
    o, out = 0, []
    while o < len(d):
        tag = d[o:o + 4].decode("latin1")
        size = struct.unpack_from("<H", d, o + 4)[0]
        out.append((tag, d[o + 6:o + 6 + size]))
        o += 6 + size
    return out


def _vanilla_npcs(wanted):
    """The wanted NPC_ records from FalloutNV.esm: {formid: (record flags, [(tag, data)])}."""
    esm = FNV_DATA / "FalloutNV.esm"
    if not esm.exists():
        return None
    b = esm.read_bytes()
    found = {}
    off = 0
    while off < len(b):
        size = struct.unpack_from("<I", b, off + 4)[0]
        if b[off:off + 4] == b"GRUP" and b[off + 8:off + 12] == b"NPC_":
            o, end = off + 24, off + size
            while o < end:
                rsize = struct.unpack_from("<I", b, o + 4)[0]
                flags, fid = struct.unpack_from("<II", b, o + 8)
                if fid in wanted:
                    data = b[o + 24:o + 24 + rsize]
                    if flags & 0x40000:
                        data = zlib.decompress(data[4:])
                    found[fid] = (flags & ~0x40000, _subrecords(data))
                o += 24 + rsize
            break
        off += size if b[off:off + 4] == b"GRUP" else 24 + size
    return found if len(found) == len(wanted) else None


def _courier(objid, edid, flags, subs) -> bytes:
    body = b""
    for tag, data in subs:
        if tag in ("SNAM", "PKID", "SCRI"):
            continue                                    # factions, packages and script: ours below
        if tag == "EDID":
            data = z(edid)
        elif tag == "FULL":
            data = z(COURIER_NAME)
        elif tag == "ACBS":
            acbs = bytearray(data)
            f = struct.unpack_from("<I", acbs, 0)[0]
            struct.pack_into("<I", acbs, 0, (f | 0x02) & ~0x08)          # essential, no respawn
            t = struct.unpack_from("<H", acbs, 22)[0]
            struct.pack_into("<H", acbs, 22, t & ~(0x04 | 0x10 | 0x20 | 0x80 | 0x200))
            data = bytes(acbs)
        body += sub(tag, data)
        if tag == "AIDT":
            body += sub("PKID", struct.pack("<I", COURIER_PACKAGE))
    assert any(t == "FULL" for t, _ in subs), edid      # the mercenary records all carry a name
    return record("NPC_", flags, 0x01000000 | objid, body)


def _grup(label: bytes, gtype: int, body: bytes) -> bytes:
    return b"GRUP" + struct.pack("<I", 24 + len(body)) + label + struct.pack("<iHHHH", gtype, 0, 0, 0, 0) + body


def bank_plugin(edid, name, model, icon, small_icon):
    """WastelandBank.esp: the card (0x800), the couriers (0x801-0x803), the vault container (0x804)
    in its own interior cell (0x805) as one persistent reference (0x806). None without the ESM."""
    vanilla = _vanilla_npcs({src for _, _, src in COURIERS})
    if vanilla is None:
        return None
    card = plugin(edid, name, model, icon, small_icon)
    card_group = card[card.index(b"GRUP"):]
    npcs = b"".join(_courier(objid, ed, *vanilla[src]) for objid, ed, src in COURIERS)
    cont = record("CONT", 0, 0x01000000 | VAULT_CONT,
                  sub("EDID", z("WBVault")) + sub("OBND", bytes(12)) + sub("FULL", z("Wasteland Bank Vault"))
                  + sub("MODL", z(VAULT_MODEL)) + sub("DATA", struct.pack("<Bf", 0, 0.0)))
    cell_id = 0x01000000 | VAULT_CELL
    cell = record("CELL", 0, cell_id,
                  sub("EDID", z("WBVaultCell")) + sub("FULL", z("Wasteland Bank Vault"))
                  + sub("DATA", bytes([0x01])))                      # interior
    ref = record("REFR", 0x400, 0x01000000 | VAULT_REF,                # persistent
                 sub("EDID", z("WBVaultRef")) + sub("NAME", struct.pack("<I", 0x01000000 | VAULT_CONT))
                 + sub("DATA", bytes(24)))
    children = _grup(struct.pack("<I", cell_id), 6, _grup(struct.pack("<I", cell_id), 8, ref))
    block, subblock = VAULT_CELL % 10, (VAULT_CELL // 10) % 10
    cells = _grup(b"CELL", 0, _grup(struct.pack("<i", block), 2,
                                    _grup(struct.pack("<i", subblock), 3, cell + children)))
    n_records = 1 + len(COURIERS) + 1 + 1 + 1
    header = record("TES4", 0, 0,
                    sub("HEDR", struct.pack("<fiI", 1.34, n_records, VAULT_REF + 1))
                    + sub("CNAM", z("fnv-personal-mod"))
                    + sub("MAST", z("FalloutNV.esm"))
                    + sub("DATA", bytes(8)))
    return header + card_group + _grup(b"CONT", 0, cont) + _grup(b"NPC_", 0, npcs) + cells


def misc_plugin(edid, name, model, icon, value, weight) -> bytes:
    body = (sub("EDID", z(edid))
            + sub("OBND", bytes(12))
            + sub("FULL", z(name))
            + sub("MODL", z(model))
            + sub("ICON", z(icon))
            + sub("DATA", struct.pack("<if", value, weight)))
    misc = record("MISC", 0, 0x01000000 | OBJECT_ID, body)
    header = record("TES4", 0, 0,
                    sub("HEDR", struct.pack("<fiI", 1.34, 1, OBJECT_ID + 1))
                    + sub("CNAM", z("fnv-personal-mod"))
                    + sub("MAST", z("FalloutNV.esm"))
                    + sub("DATA", bytes(8)))
    return header + group("MISC", misc)


def main():
    for fname, mod, edid, name, model, icon, small in ITEMS:
        out = ROOT / "src" / mod / fname
        if fname == "WastelandBank.esp":
            data = bank_plugin(edid, name, model, icon, small)
            if data is None:
                print("make_plugins: FalloutNV.esm not found (set FNV_DATA); kept", out.name, "as it is")
                continue
        else:
            data = plugin(edid, name, model, icon, small, LISTS.get(fname, ()))
        if not out.exists() or out.read_bytes() != data:
            out.write_bytes(data)
            print("wrote", out.relative_to(ROOT))
    for fname, mod, edid, name, model, icon, value, weight in MISC_ITEMS:
        out = ROOT / "src" / mod / fname
        out.parent.mkdir(parents=True, exist_ok=True)
        data = misc_plugin(edid, name, model, icon, value, weight)
        if not out.exists() or out.read_bytes() != data:
            out.write_bytes(data)
            print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
