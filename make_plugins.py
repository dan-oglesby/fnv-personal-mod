"""Write the small item plugins (.esp) that some mods use as their menu item.

    python make_plugins.py      # also run by build.py

Each plugin holds one apparel item with no body slot, no script and no weight, modelled on the
Bank Card item in BankCard.esp (Nexus 39741): you equip it from the Pip-Boy's Apparel tab and the
mod's menu opens when you close the Pip-Boy. The plugins carry no script bytecode (that needs the
GECK); the mod's xNVSE scripts watch for the item being equipped (OnActorEquip) and find it by
the plugin's load-order index and the object ID below (BuildRef <index> 2048).

The only master is FalloutNV.esm, so a plugin never pulls in another mod.
"""
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OBJECT_ID = 0x800                  # first free object ID in a plugin; BuildRef index 2048

# plugin file, mod folder in src/, editor ID, name, world model, inventory icon, small icon
ITEMS = [
    ("WastelandBank.esp", "Wasteland Bank", "WBBankCard", "Wasteland Bank Card",
     r"clutter\holodisk\passcardblue.nif",
     r"interface\icons\pipboyimages\items\item_passcard .dds",      # vanilla's own name, with space
     r"interface\icons\pipboyimages_small\items_small\glow_items_passcard.dds"),
    ("AutoSmoke.esp", "Auto Smoke", "ASCigaretteCase", "Cigarette Case (Auto Smoke)",
     r"Clutter\Junk\CigarettePack01.NIF",
     r"smoking_edisleado\icons\cigarette_pack.dds",                 # Light Up and Smoke's icon
     None),
]


def sub(tag: str, data: bytes) -> bytes:
    return tag.encode() + struct.pack("<H", len(data)) + data


def z(s: str) -> bytes:
    return s.encode("latin1") + b"\0"


def record(tag: str, flags: int, formid: int, body: bytes) -> bytes:
    # type, data size, flags, FormID, version control, form version 15, unknown
    return tag.encode() + struct.pack("<IIIIHH", len(body), flags, formid, 0, 15, 0) + body


def group(label: str, body: bytes) -> bytes:
    return b"GRUP" + struct.pack("<I", 24 + len(body)) + label.encode() + struct.pack("<iHHHH", 0, 0, 0, 0, 0) + body


def plugin(edid, name, model, icon, small_icon) -> bytes:
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
    header = record("TES4", 0, 0,
                    sub("HEDR", struct.pack("<fiI", 1.34, 1, OBJECT_ID + 1))
                    + sub("CNAM", z("fnv-personal-mod"))
                    + sub("MAST", z("FalloutNV.esm"))
                    + sub("DATA", bytes(8)))
    return header + group("ARMO", armo)


def main():
    for fname, mod, edid, name, model, icon, small in ITEMS:
        out = ROOT / "src" / mod / fname
        data = plugin(edid, name, model, icon, small)
        if not out.exists() or out.read_bytes() != data:
            out.write_bytes(data)
            print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
