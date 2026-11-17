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
# Their script: vanilla vHDLegateCampExitDoorScript (0x148137), an empty OnActivate block, so
# activating a courier starts no mercenary dialogue; the bank's own activation handler opens
# their services instead (CourierAct.txt, 2026-11-17).
COURIER_SCRIPT = 0x148137
VAULT_CONT, VAULT_CELL, VAULT_REF = 0x804, 0x805, 0x806
SELL_CONT, SELL_REF = 0x807, 0x808     # the couriers' consignment box (things to sell), same cell
# Mojave Express (2026-11-17): the catalogue you order from, and the orders in transit until you
# collect them at a dropbox; both in the same cell. Their object IDs follow the bank notes.
CAT_CONT, CAT_REF, SHIP_CONT, SHIP_REF = 0x80B, 0x80C, 0x80D, 0x80E
# Courier delivery (2026-11-17): catalogue orders a courier squad carries out to you, wherever you
# are, until they hand them over (CatClose.txt, SqGive.txt). Same cell.
DELIV_CONT, DELIV_REF = 0x815, 0x816
# The game's Mojave Express Dropbox (vMojaveExpressBox 0x14B05F), overridden with the couriers'
# empty activation script, so opening a dropbox shows the bank's Mojave Express menu (MEAct.txt)
# instead of the vanilla shipping messages. Copied from FalloutNV.esm with only the script changed.
ME_BOX = 0x14B05F
# Debt collectors (2026-11-17): the same mercenary copies as the couriers, but not essential, named
# Debt Collector; sent when a loan is two weeks overdue (ColTick.txt). Same empty activation script.
# Caravan ventures (2026-11-17): the Caravan Manifest you carry while your caravan is on the road
# (CvTick.txt). Weightless, worthless, flagged a quest item (record flag 0x400) so it isn't dropped
# or sold. The model and icon of vanilla's Dr. Richard's Medical Report (a clipboard, the note icon).
MANIFEST = (0x812, "WBCaravanManifest", "Caravan Manifest")
# Representatives (2026-11-17): stand at the places their business is done and open it when you
# talk to them (RepTick.txt places them, RepAct.txt), in place of any bank-card menu. Copies like
# the couriers (stay near where they are, the empty activation script): the Caravan Agent at the
# Crimson Caravan Company (caravan ventures) from vanilla CrimsonCaravaneerCM, essential and with
# no factions; and the Publicanus at Cottonwood Cove (the Legion's caravans) from vanilla
# LegionaryExplorer, mortal and keeping the Legion's factions, so he stands and falls with the Cove.
# Object ID, editor ID, vanilla NPC, name, essential and faction-free.
# Hired guards (2026-11-17): hired from the Caravan Agent for wages (Guards.txt), copies of vanilla
# CrimsonCaravanGuardCM / AF (their leveled looks and gear), mortal, no factions, the empty
# activation script (GuardAct.txt opens their orders), and their own package follows you
# (DefaultFollowPlayerFar 0x1554DC); waiting is a script package on top (GuardBtn.txt).
GUARDS = [(0x817, "WBGuardA", 971986), (0x818, "WBGuardB", 971987)]
GUARD_NAME, GUARD_PACKAGE = "Hired Guard", 0x1554DC
# The Dam papers (2026-11-17): what the winner owes the Courier (StipDay.txt). Books copied from
# vanilla's Wasteland Survival Guide (MS03SurvivalGuideBookItem 808500: its model and icon), with
# the policy as their text; no skill, worthless to traders, light.
PAPER_BOOK = 808500
PAPERS = [(2073, 'WBAnnuityNCR', "Hero's Annuity", "REPUBLIC OF NEW CALIFORNIA<br>Office of Veterans and Special Services<br><br>HERO'S ANNUITY<br><br>In recognition of services rendered to the Republic at Hoover Dam, the Republic grants the holder of this policy a weekly annuity in NCR dollars, paid through Wasteland Bank to the holder's NCR-dollar account.<br><br>Schedule, by the holder's standing with the Republic, per week:<br>Neutral: $250<br>Accepted: $625<br>Liked: $1,250<br>Idolized: $2,500<br>Vilified: payments suspended.<br><br>Payment is made to the holder only. This policy may be sold to Wasteland Bank. Annuity income is subject to the Republic's tax on profits.<br><br>Countersigned, Office of the President."), (2074, 'WBAnnuityLegion', "Legate's Grant", "BY THE WILL OF CAESAR<br><br>LEGATE'S GRANT<br><br>For service to Rome at the Dam, the bearer of this grant is owed a weekly stipend in denarii, paid through Wasteland Bank to the bearer's denarius account, for as long as Rome holds the bearer in honour.<br><br>Per week, by the bearer's standing with the Legion:<br>Neutral: 25 denarii<br>Accepted: 60 denarii<br>Liked: 125 denarii<br>Idolized: 250 denarii<br>Vilified: nothing.<br><br>The stipend goes to the bearer alone. The grant may be sold to Wasteland Bank.<br><br>Ave, true to Caesar."), (2075, 'WBLucky38Shares', 'Lucky 38 Share Certificate', "THE LUCKY 38<br>Office of the Chief Executive<br><br>SHARE CERTIFICATE<br><br>The holder owns a stake in Mr. House's enterprises on the Strip, issued for services at Hoover Dam.<br><br>The stake is valued at the price of RobCo Industries stock and pays its holder one percent of its value every week, through Wasteland Bank.<br><br>Mr. House does not pay salaries. He pays returns.<br><br>Transferable. Wasteland Bank will buy it at ninety percent of its value.")]
REPS = [(0x813, "WBRepCaravan", 971993, "Caravan Agent", True),
        (0x814, "WBRepPublicanus", 1177872, "Publicanus", False)]
COLLECTORS = [(0x80F, "WBCollectorA", 0x165066), (0x810, "WBCollectorB", 0x165064), (0x811, "WBCollectorC", 0x165065)]
# Wasteland Bank notes (2026-11-16): the bank's own paper money. Face value 10 and 100 caps at
# issue; their worth follows the bank's share price (BankNotes.txt sets it on load and daily).
# Paper weight as NCR notes; the vanilla $20 NCR note's model and icons.
BANK_NOTES = [(0x809, "WBNote10", "Wasteland Bank Note (10)", 10),
              (0x80A, "WBNote100", "Wasteland Bank Note (100)", 100)]
NOTE_MODEL = r"clutter\Money\NCRMoney20.nif"
NOTE_ICON = r"interface\icons\pipboyimages\items\items_money_NCR_20.dds"
NOTE_MICO = r"interface\icons\pipboyimages_small\items_small\glow_items_money_NCR_20.dds"
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


def _courier(objid, edid, flags, subs, name=None, essential=True, factions=False, package=COURIER_PACKAGE) -> bytes:
    body = b""
    for tag, data in subs:
        if tag in ("PKID", "SCRI") or (tag == "SNAM" and not factions):
            continue                                    # factions, packages and script: ours below
        if tag == "EDID":
            data = z(edid)
        elif tag == "FULL":
            data = z(name or COURIER_NAME)
        elif tag == "ACBS":
            acbs = bytearray(data)
            f = struct.unpack_from("<I", acbs, 0)[0]
            f = (f | 0x02) if essential else (f & ~0x02)                  # essential (couriers) or not
            struct.pack_into("<I", acbs, 0, f & ~0x08)                   # no respawn
            t = struct.unpack_from("<H", acbs, 22)[0]
            struct.pack_into("<H", acbs, 22, t & ~(0x04 | 0x10 | 0x20 | 0x80 | 0x200))
            data = bytes(acbs)
        body += sub(tag, data)
        if tag == "EAMT":
            body += sub("SCRI", struct.pack("<I", COURIER_SCRIPT))
        if tag == "AIDT":
            body += sub("PKID", struct.pack("<I", package))
    assert any(t == "FULL" for t, _ in subs), edid      # the mercenary records all carry a name
    return record("NPC_", flags, 0x01000000 | objid, body)


def _grup(label: bytes, gtype: int, body: bytes) -> bytes:
    return b"GRUP" + struct.pack("<I", 24 + len(body)) + label + struct.pack("<iHHHH", gtype, 0, 0, 0, 0) + body


def bank_plugin(edid, name, model, icon, small_icon):
    """WastelandBank.esp: the card (0x800), the couriers (0x801-0x803), the vault container (0x804)
    in its own interior cell (0x805) as one persistent reference (0x806), and the consignment box
    (0x807, reference 0x808) in the same cell. None without the ESM."""
    vanilla = _vanilla_npcs({src for _, _, src in COURIERS + COLLECTORS + GUARDS} | {r[2] for r in REPS})
    if vanilla is None:
        return None
    card = plugin(edid, name, model, icon, small_icon)
    card_group = card[card.index(b"GRUP"):]
    npcs = b"".join(_courier(objid, ed, *vanilla[src]) for objid, ed, src in COURIERS)
    npcs += b"".join(_courier(objid, ed, *vanilla[src], name="Debt Collector", essential=False)
                      for objid, ed, src in COLLECTORS)
    npcs += b"".join(_courier(objid, ed, *vanilla[src], name=nm, essential=ess, factions=not ess)
                      for objid, ed, src, nm, ess in REPS)
    npcs += b"".join(_courier(objid, ed, *vanilla[src], name=GUARD_NAME, essential=False, package=GUARD_PACKAGE)
                      for objid, ed, src in GUARDS)
    cont = record("CONT", 0, 0x01000000 | VAULT_CONT,
                  sub("EDID", z("WBVault")) + sub("OBND", bytes(12)) + sub("FULL", z("Wasteland Bank Vault"))
                  + sub("MODL", z(VAULT_MODEL)) + sub("DATA", struct.pack("<Bf", 0, 0.0)))
    cont += record("CONT", 0, 0x01000000 | SELL_CONT,
                   sub("EDID", z("WBConsign")) + sub("OBND", bytes(12)) + sub("FULL", z("Courier Consignment: to sell"))
                   + sub("MODL", z(VAULT_MODEL)) + sub("DATA", struct.pack("<Bf", 0, 0.0)))
    notes = b"".join(record("MISC", 0, 0x01000000 | objid,
                            sub("EDID", z(ed)) + sub("OBND", bytes(12)) + sub("FULL", z(nm))
                            + sub("MODL", z(NOTE_MODEL)) + sub("ICON", z(NOTE_ICON)) + sub("MICO", z(NOTE_MICO))
                            + sub("DATA", struct.pack("<if", face, 0.0022)))
                     for objid, ed, nm, face in BANK_NOTES)
    for objid, ed, nm in ((CAT_CONT, "WBCatalogue", "Mojave Express Catalogue"),
                          (SHIP_CONT, "WBInTransit", "Mojave Express: in transit"),
                          (DELIV_CONT, "WBDelivery", "Courier delivery: on its way")):
        cont += record("CONT", 0, 0x01000000 | objid,
                       sub("EDID", z(ed)) + sub("OBND", bytes(12)) + sub("FULL", z(nm))
                       + sub("MODL", z(VAULT_MODEL)) + sub("DATA", struct.pack("<Bf", 0, 0.0)))
    book = _vanilla_records("BOOK", {PAPER_BOOK})
    if book is None:
        return None
    bkflags, bksubs = book[PAPER_BOOK]
    books = b""
    for objid, ed, nm, text in PAPERS:
        body = b""
        for t, d in bksubs:
            if t == "EDID":
                d = z(ed)
            elif t == "FULL":
                d = z(nm)
            elif t == "DESC":
                d = z(text)
            elif t == "DATA":
                d = struct.pack("<BbIf", 0, -1, 0, 0.5)
            body += sub(t, d)
        books += record("BOOK", 0, 0x01000000 | objid, body)
    box = _vanilla_records("CONT", {ME_BOX})
    if box is None:
        return None
    bflags, bsubs = box[ME_BOX]
    cont += record("CONT", bflags, ME_BOX,
                   b"".join(sub(t, struct.pack("<I", COURIER_SCRIPT) if t == "SCRI" else d) for t, d in bsubs))
    notes += record("MISC", 0x400, 0x01000000 | MANIFEST[0],
                    sub("EDID", z(MANIFEST[1])) + sub("OBND", bytes(12)) + sub("FULL", z(MANIFEST[2]))
                    + sub("MODL", z(r"clutter\office\clipboard01.nif"))
                    + sub("ICON", z(r"interface\icons\pipboyimages\items\items_note.dds"))
                    + sub("DATA", struct.pack("<if", 0, 0.0)))
    cell_id = 0x01000000 | VAULT_CELL
    cell = record("CELL", 0, cell_id,
                  sub("EDID", z("WBVaultCell")) + sub("FULL", z("Wasteland Bank Vault"))
                  + sub("DATA", bytes([0x01])))                      # interior
    ref = record("REFR", 0x400, 0x01000000 | VAULT_REF,                # persistent
                 sub("EDID", z("WBVaultRef")) + sub("NAME", struct.pack("<I", 0x01000000 | VAULT_CONT))
                 + sub("DATA", bytes(24)))
    ref += record("REFR", 0x400, 0x01000000 | SELL_REF,
                  sub("EDID", z("WBConsignRef")) + sub("NAME", struct.pack("<I", 0x01000000 | SELL_CONT))
                  + sub("DATA", struct.pack("<6f", 0.0, 64.0, 0.0, 0.0, 0.0, 0.0)))
    for objid, ed, base, y in ((CAT_REF, "WBCatalogueRef", CAT_CONT, 128.0), (SHIP_REF, "WBInTransitRef", SHIP_CONT, 192.0),
                               (DELIV_REF, "WBDeliveryRef", DELIV_CONT, 256.0)):
        ref += record("REFR", 0x400, 0x01000000 | objid,
                      sub("EDID", z(ed)) + sub("NAME", struct.pack("<I", 0x01000000 | base))
                      + sub("DATA", struct.pack("<6f", 0.0, y, 0.0, 0.0, 0.0, 0.0)))
    children = _grup(struct.pack("<I", cell_id), 6, _grup(struct.pack("<I", cell_id), 8, ref))
    block, subblock = VAULT_CELL % 10, (VAULT_CELL // 10) % 10
    cells = _grup(b"CELL", 0, _grup(struct.pack("<i", block), 2,
                                    _grup(struct.pack("<i", subblock), 3, cell + children)))
    n_records = 1 + len(COURIERS) + len(COLLECTORS) + len(REPS) + len(GUARDS) + len(PAPERS) + 5 + len(BANK_NOTES) + 1 + 1 + 4 + 2
    header = record("TES4", 0, 0,
                    sub("HEDR", struct.pack("<fiI", 1.34, n_records, 0x81C))
                    + sub("CNAM", z("fnv-personal-mod"))
                    + sub("MAST", z("FalloutNV.esm"))
                    + sub("DATA", bytes(8)))
    return (header + card_group + _grup(b"BOOK", 0, books) + _grup(b"CONT", 0, cont) + _grup(b"MISC", 0, notes)
            + _grup(b"NPC_", 0, npcs) + cells)


# Wasteland Tweaks (in its plugin, AutoSmoke.esp): power armor's footstep foley. FalloutNV.esm's
# FOLArmorPowerWalk (0x13F296) and FOLArmorPowerRun (0x13F295) point at fx\fol\powerarmor_walkrun\,
# a folder no sound archive has: every power-armor step logged "Could not open file" (12,149
# lines in one session's falloutnv_error.log, 2026-11-15) and made no sound. Overridden to
# fx\fol\heavyarmor_runwalk\, a heavy armor foley folder in Fallout - Sound.bsa that nothing else uses
# (other heavy armor uses heavyarmor_runwalk2), so power armor gets its own heavy step. The
# records are copied from the game's FalloutNV.esm at build time with only the folder changed.
SOUND_FIXES = {"AutoSmoke.esp": [(0x13F296, "fx\\fol\\heavyarmor_runwalk\\"),
                                 (0x13F295, "fx\\fol\\heavyarmor_runwalk\\")]}


def _vanilla_records(tag, wanted):
    """Records of one type from FalloutNV.esm: {formid: (record flags, [(tag, data)])}."""
    esm = FNV_DATA / "FalloutNV.esm"
    if not esm.exists():
        return None
    b = esm.read_bytes()
    found = {}
    off = 0
    while off < len(b):
        size = struct.unpack_from("<I", b, off + 4)[0]
        if b[off:off + 4] == b"GRUP" and b[off + 8:off + 12] == tag.encode():
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


def with_sound_fixes(fname, data):
    """Adds SOUND_FIXES overrides (a SOUN group, before ARMO as the game orders groups)."""
    fixes = SOUND_FIXES.get(fname)
    if not fixes:
        return data
    vanilla = _vanilla_records("SOUN", {fid for fid, _ in fixes})
    if vanilla is None:
        return None
    recs = b""
    for fid, folder in fixes:
        flags, subs = vanilla[fid]
        body = b"".join(sub(t, z(folder) if t == "FNAM" else d) for t, d in subs)
        recs += record("SOUN", flags, fid, body)
    hsize = struct.unpack_from("<I", data, 4)[0]
    header = bytearray(data[:24 + hsize])
    i = header.index(b"HEDR") + 6
    ver, n, nxt = struct.unpack_from("<fiI", header, i)
    struct.pack_into("<fiI", header, i, ver, n + len(fixes), nxt)
    return bytes(header) + group("SOUN", recs) + data[24 + hsize:]


# Fission Power (in FissionPower.esp, object ID 0x801): Nutrient Paste, the suit's food
# (2026-11-17). Copied from FalloutNV.esm's Cram (0x08C552) at build time: its model, icon, sound
# and Hardcore condition, with a new name, no radiation, 40 hunger a serving, a quarter pound and
# worth 3 caps. Effects kept: Cram's small heal (0x14E) and RestoreStarvationLevel (0x162BCC).
PASTE = {"FissionPower.esp": (0x801, 0x8C552, "FPNutrientPaste", "Nutrient Paste", 40, 0.25, 3)}


def with_paste(fname, data):
    """Adds PASTE's aid item (an ALCH group after the plugin's other groups)."""
    spec = PASTE.get(fname)
    if not spec:
        return data
    objid, src, edid, name, hunger, weight, value = spec
    vanilla = _vanilla_records("ALCH", {src})
    if vanilla is None:
        return None
    flags, subs = vanilla[src]
    body = b""
    skip = False
    for t, d in subs:
        if t == "EFID":
            skip = struct.unpack("<I", d)[0] == 0x20516      # DamageRadiationLevel: none in paste
        if skip and t in ("EFID", "EFIT", "CTDA"):
            continue
        if t == "EDID":
            d = z(edid)
        elif t == "FULL":
            d = z(name)
        elif t == "DATA":
            d = struct.pack("<f", weight)
        elif t == "ENIT":
            d = struct.pack("<i", value) + d[4:]
        elif t == "EFIT" and body.endswith(sub("EFID", struct.pack("<I", 0x162BCC))):
            d = struct.pack("<I", hunger) + d[4:]
        body += sub(t, d)
    alch = record("ALCH", flags, 0x01000000 | objid, body)
    hsize = struct.unpack_from("<I", data, 4)[0]
    header = bytearray(data[:24 + hsize])
    i = header.index(b"HEDR") + 6
    ver, n, nxt = struct.unpack_from("<fiI", header, i)
    struct.pack_into("<fiI", header, i, ver, n + 1, max(nxt, objid + 1))
    return bytes(header) + data[24 + hsize:] + group("ALCH", alch)


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
            data = with_sound_fixes(fname, data)
            if data is None:
                print("make_plugins: FalloutNV.esm not found (set FNV_DATA); kept", out.name, "as it is")
                continue
        if not out.exists() or out.read_bytes() != data:
            out.write_bytes(data)
            print("wrote", out.relative_to(ROOT))
    for fname, mod, edid, name, model, icon, value, weight in MISC_ITEMS:
        out = ROOT / "src" / mod / fname
        out.parent.mkdir(parents=True, exist_ok=True)
        data = misc_plugin(edid, name, model, icon, value, weight)
        data = with_paste(fname, data)
        if data is None:
            print("make_plugins: FalloutNV.esm not found (set FNV_DATA); kept", out.name, "as it is")
            continue
        if not out.exists() or out.read_bytes() != data:
            out.write_bytes(data)
            print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
