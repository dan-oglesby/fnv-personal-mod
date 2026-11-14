"""Generate the data-driven parts of Wasteland Exchange (stocks inside Wasteland Bank).

    python tools/gen_exchange.py      # also run by build.py

Writes into src/Wasteland Bank/nvse/user_defined_functions/WastelandBank/:
  ExData.txt              the listings (re-applied on every load, so tuning takes effect)
  ExEvents1..3.txt        the news events: quest stages / deaths -> price shocks and permanent changes
and refreshes the function-check list in ln_wasteland_bank.txt.

Design: docs/wasteland-exchange-design.md. Form IDs are from FalloutNV.esm (and HonestHearts.esm),
read from the game data with the session's plugin reader; quest stages are the game's own.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UDF = ROOT / "src" / "Wasteland Bank" / "nvse" / "user_defined_functions" / "WastelandBank"
LN = ROOT / "src" / "Wasteland Bank" / "nvse" / "plugins" / "scripts" / "ln_wasteland_bank.txt"

NVX, HX, BOTH, HIDDEN = 0, 1, 2, 9          # HIDDEN: priced like a stock, not traded (currencies)
ARMS, TRADE, CASINO, TECH, NCR, NCRCUR, LEGCUR = range(7)

# ticker, name, exchange, start price (caps), daily vol, annual dividend yield, sector, daily trend (log)
TICKERS = [
    ("GUN",  "Gun Runners",              BOTH, 120, 0.020, 0.03, ARMS,   0.0015),
    ("CRIM", "Crimson Caravan Company",  HX,    80, 0.020, 0.05, TRADE,  0.0010),
    ("VGE",  "Van Graff Energy",         NVX,   60, 0.040, 0.00, ARMS,   0.0005),
    ("MEX",  "Mojave Express",           NVX,   30, 0.030, 0.02, TRADE,  0.0005),
    ("TOPS", "The Tops Casino",          NVX,   50, 0.020, 0.04, CASINO, 0.0010),
    ("GOMR", "Gomorrah",                 NVX,   45, 0.030, 0.04, CASINO, 0.0005),
    ("ULUX", "Ultra-Luxe",               NVX,   70, 0.020, 0.03, CASINO, 0.0008),
    ("WRNG", "Atomic Wrangler",          NVX,   15, 0.040, 0.02, CASINO, 0.0000),
    ("RBCO", "RobCo Industries",         NVX,  200, 0.025, 0.01, TECH,   0.0020),
    ("HAPY", "Happy Trails Caravan Co.", HX,    25, 0.030, 0.03, TRADE,  0.0000),
    ("WTRM", "Water Merchants",          HX,    90, 0.010, 0.06, NCR,    0.0005),
    ("FGO",  "Far Go Traders",           HX,    35, 0.025, 0.04, TRADE,  0.0005),
    ("BRMN", "Brahmin Barons Index",     HX,   100, 0.015, 0.04, NCR,    0.0007),
    ("NCRB", "NCR War Bonds",            HX,   100, 0.005, 0.08, NCR,    0.0000),
    # Currencies: a multiplier on the vanilla value (1.0 = vanilla), moved by the same news engine.
    # FxApply.txt turns them into item values; ExRate and ConvertNow use them exactly.
    ("NCRD", "NCR dollar",               HIDDEN, 1, 0.006, 0.00, NCRCUR, 0.0000),
    ("LEGD", "Legion denarius",          HIDDEN, 1, 0.008, 0.00, LEGCUR, 0.0000),
]
T = {t[0]: i for i, t in enumerate(TICKERS)}
ALL_NVX = [t[0] for t in TICKERS if t[2] in (NVX, BOTH)]
ALL_HX = [t[0] for t in TICKERS if t[2] in (HX, BOTH)]
STRIP = ["TOPS", "GOMR", "ULUX"]

FNV, HH = "FalloutNV.esm", "HonestHearts.esm"
# condition helpers -> (form-building lines, test expression); ids are hex object IDs
def stage(q, s, mod=FNV): return ("stage", mod, q, s)
def done(q, mod=FNV):     return ("done", mod, q)
def dead(r, mod=FNV):     return ("dead", mod, r)
def alive(r, mod=FNV):    return ("alive", mod, r)
def loaded(mod):          return ("loaded", mod)

# Each event: id, comment, conditions (list of alternatives; each alternative = list of ANDed terms),
# effects [(ticker, shock pct, permanent multiplier)], delist (ticker, recovery) or None, headline.
EVENTS = [
    (0, "Van Graffs wiped out (Jean-Baptiste Cutting and Gloria Van Graff dead)",
     [[dead(0x10D8E5), dead(0x10D8E7)]],
     [("CRIM", 0.20, 1.10), ("GUN", 0.05, 1.05)], ("VGE", 0.05),
     "Silver Rush massacre: Van Graff Energy delisted. Crimson Caravan and Gun Runners rally"),
    (1, "Birds of a Feather: the Big Deal goes through (VMS29a 100)",
     [[stage(0x124123, 100)]], [("VGE", 0.35, 1.15)], None,
     "Van Graffs close their Big Deal: Van Graff Energy soars"),
    (2, "Alice McLafferty killed",
     [[dead(0xEC7B8)]], [("CRIM", -0.35, 0.85), ("FGO", 0.05, 1.0)], None,
     "Crimson Caravan chief Alice McLafferty found dead: Crimson stock tumbles"),
    (3, "You Can Depend on Me completed with Alice alive",
     [[done(0xEDB37), alive(0xEC7B8)]], [("CRIM", 0.15, 1.05)], None,
     "Crimson Caravan secures its Mojave supply line"),
    (4, "My Kind of Town: NCR sheriff for Primm (stage 110)",
     [[stage(0xDA115, 110)]], [("MEX", 0.20, 1.10), ("NCRB", 0.02, 1.0)], None,
     "NCR sends a sheriff to Primm: Mojave Express up on safer roads"),
    (5, "My Kind of Town: Meyers or Primm Slim (120/130)",
     [[stage(0xDA115, 120)], [stage(0xDA115, 130)]], [("MEX", 0.10, 1.03)], None,
     "Primm has a sheriff again: Mojave Express edges higher"),
    (6, "My Kind of Town: every candidate dead (100)",
     [[stage(0xDA115, 100)]], [("MEX", -0.30, 0.90)], None,
     "Primm left lawless: Mojave Express slides"),
    (7, "Johnson Nash killed",
     [[dead(0xE2882)]], [("MEX", -0.25, 0.85)], None,
     "Mojave Express founder Johnson Nash dead: shares slump"),
    (8, "How Little We Know: Omerta plot foiled (VMS21 50)",
     [[stage(0x110A63, 50)]], [("GOMR", -0.40, 0.90), ("TOPS", 0.05, 1.0), ("ULUX", 0.05, 1.0)], None,
     "Omerta plot against the Strip exposed: Gomorrah plunges on the scandal"),
    (9, "How Little We Know: the player helped the Omertas (VMS21 55)",
     [[stage(0x110A63, 55)]], [("GOMR", 0.10, 1.0), ("TOPS", -0.15, 1.0), ("ULUX", -0.15, 1.0), ("WRNG", -0.10, 1.0)], None,
     "Violence on the Strip: casino stocks sell off, Gomorrah aside"),
    (10, "Securitrons upgraded at the Fort (House II 100 or Wild Card 100)",
     [[stage(0x147886, 100)], [stage(0x16A161, 100)]],
     [("RBCO", 0.30, 1.60)] + [(t, 0.05, 1.0) for t in ALL_NVX if t != "RBCO"], None,
     "Securitron army upgraded: RobCo Industries surges, the Strip rallies"),
    (11, "Securitrons destroyed at the Fort (House II 110 or Wild Card 110)",
     [[stage(0x147886, 110)], [stage(0x16A161, 110)]], [("RBCO", -0.50, 0.50)], None,
     "Securitron army destroyed: RobCo Industries collapses"),
    (12, "Mr. House killed (Lucky 38 basement)",
     [[dead(0x171B46)]], [("RBCO", -0.40, 0.40)] + [(t, -0.25, 0.95) for t in STRIP], None,
     "Mr. House is dead: RobCo crashes, panic on the Strip"),
    (13, "House: Boomers secured (House III 100)",
     [[stage(0x147887, 100)]], [("RBCO", 0.05, 1.10)], None,
     "Boomers back Mr. House: RobCo gains"),
    (14, "House: RACKET handled for House (House IV 100/105)",
     [[stage(0x147888, 100)], [stage(0x147888, 105)]], [("RBCO", 0.03, 1.05)], None,
     "House consolidates the Strip families: RobCo firms"),
    (15, "House: Brotherhood dealt with (House V 100/110)",
     [[stage(0x147889, 100)], [stage(0x147889, 110)]], [("RBCO", 0.03, 1.05)], None,
     "Brotherhood question settled in House's favor: RobCo firms"),
    (16, "President Kimball saved (House VI 100)",
     [[stage(0x14788A, 100)]], [("NCRB", 0.05, 1.03), ("CRIM", 0.05, 1.0), ("BRMN", 0.05, 1.0)], None,
     "President Kimball survives assassination attempt: NCR markets rally"),
    (17, "President Kimball killed (House VI 120/130 or Arizona Killer 100)",
     [[stage(0x14788A, 120)], [stage(0x14788A, 130)], [stage(0x131F09, 100)]],
     [("NCRB", -0.20, 0.85), ("CRIM", -0.15, 1.0), ("FGO", -0.15, 1.0), ("BRMN", -0.15, 1.0), ("WTRM", -0.10, 1.0)], None,
     "President Kimball assassinated at Hoover Dam: NCR markets in turmoil"),
    (18, "Restoring Hope: Nelson retaken (VMS30 170)",
     [[stage(0x1214AA, 170)]], [("NCRB", 0.05, 1.0), ("CRIM", 0.05, 1.05)], None,
     "NCR retakes Nelson: bonds and caravans gain"),
    (19, "Oh My Papa: Khans break with the Legion (VMS45 50)",
     [[stage(0x140C3A, 50)]], [("CRIM", 0.05, 1.0), ("FGO", 0.05, 1.0), ("MEX", 0.05, 1.0)], None,
     "Great Khans break with Caesar: caravan routes look safer"),
    (20, "Isaac (Gun Runners) killed",
     [[dead(0xF8B13)]], [("GUN", -0.30, 0.80)], None,
     "Gun Runners' Isaac killed: Gun Runners shares fall"),
    (21, "James Garret killed",
     [[dead(0x10D8E6)]], [("WRNG", -0.40, 0.70)], None,
     "James Garret dead: Atomic Wrangler shares plunge"),
    (22, "Ring-a-Ding-Ding! completed (Benny's scheme ends)",
     [[done(0x11345D)]], [("TOPS", -0.15, 0.95)], None,
     "Chairmen in disarray after Benny affair: The Tops slips"),
    (23, "Talent Pool completed (VMSTopsTalentPool 60)",
     [[stage(0x116504, 60)]], [("TOPS", 0.10, 1.05)], None,
     "New acts packing the Tops: shares climb"),
    (24, "Honest Hearts: the Happy Trails expedition is ambushed (Arrival at Zion 5)",
     [[stage(0x008893, 5, HH)], [stage(0x008891, 100, HH)]], [("HAPY", -0.80, 0.20)], None,
     "Happy Trails expedition ambushed in Zion: Happy Trails stock collapses"),
    (25, "Gun Runners' Arsenal loaded",
     [[loaded("GunRunnersArsenal.esm")]], [("GUN", 0.0, 1.10)], None,
     "Gun Runners expand their catalog"),
    (26, "NCR heads to the Dam (For the Republic 2, stage 100)",
     [[stage(0x136166, 100)]], [("NCRB", 0.10, 1.25)] + [(t, 0.10, 1.10) for t in ALL_HX if t not in ("NCRB", "GUN")] + [("RBCO", -0.20, 0.85)], None,
     "Battle for Hoover Dam: markets bet on the NCR"),
    (27, "House heads to the Dam (House VIII 80)",
     [[stage(0x14788B, 80)]], [("RBCO", 0.20, 2.10)] + [(t, 0.10, 1.20) for t in STRIP] + [("NCRB", -0.10, 1.0)], None,
     "Mr. House moves on Hoover Dam: RobCo soars, the Strip celebrates"),
    (28, "Yes Man heads to the Dam (Wild Card: Finishing Touches 100)",
     [[stage(0x15827D, 100)]], [(t, 0.15, 1.10) for t in ALL_NVX if t != "RBCO"] + [("RBCO", 0.10, 1.20), ("NCRB", -0.10, 1.0)], None,
     "An independent Vegas makes its move on Hoover Dam: New Vegas Exchange rallies"),
    (29, "Legion heads to the Dam (Render Unto Caesar 100)",
     [[stage(0x129D14, 100)]], [("NCRB", -0.50, 0.20)] + [(t, -0.30, 0.80) for t in ALL_HX if t != "NCRB"] + [(t, -0.25, 1.0) for t in ALL_NVX], None,
     "Legion marches on Hoover Dam: NCR bonds in default panic, markets crash"),
]


# The currencies react to who is gaining power. Extra effects on the events above:
CURRENCY = {
    4:  [("NCRD", 0.01, 1.02)],                             # NCR sheriff in Primm
    16: [("NCRD", 0.05, 1.05), ("LEGD", -0.03, 1.0)],       # Kimball saved
    17: [("NCRD", -0.15, 0.85), ("LEGD", 0.10, 1.10)],      # Kimball killed
    18: [("NCRD", 0.03, 1.03), ("LEGD", -0.05, 0.95)],      # Nelson retaken
    19: [("LEGD", -0.05, 0.95)],                            # Khans break with Caesar
    26: [("NCRD", 0.10, 1.15), ("LEGD", -0.10, 0.90)],      # NCR heads to the Dam
    27: [("NCRD", -0.10, 0.85), ("LEGD", -0.05, 1.0)],      # House heads to the Dam
    28: [("NCRD", -0.10, 0.85), ("LEGD", -0.05, 1.0)],      # Yes Man heads to the Dam
    29: [("NCRD", -0.30, 0.60), ("LEGD", 0.25, 1.40)],      # Legion heads to the Dam
}
EVENTS = [(e[0], e[1], e[2], e[3] + CURRENCY.get(e[0], []), e[4], e[5]) for e in EVENTS]
EVENTS += [
    (30, "Caesar killed", [[dead(0x121FF0)]], [("LEGD", -0.40, 0.50), ("NCRD", 0.05, 1.05)], None,
     "Caesar is dead: the denarius collapses as the Legion's future comes into doubt"),
    (31, "Legate Lanius killed", [[dead(0x137A9D)]], [("LEGD", -0.20, 0.80), ("NCRD", 0.03, 1.0)], None,
     "Legate Lanius falls: Legion coin slides"),
    (32, "General Lee Oliver killed", [[dead(0x134DB4)], [dead(0x1483F1)]], [("NCRD", -0.20, 0.85), ("LEGD", 0.05, 1.0)], None,
     "General Oliver killed: the NCR dollar sinks"),
    (33, "Things That Go Boom: the Boomers will help the NCR (VMS23 100)", [[stage(0x116B41, 100)]],
     [("NCRD", 0.03, 1.03)], None, "Boomers pledge air support to the NCR: the dollar firms"),
    (34, "Restoring Hope completed (VMS30 200)", [[stage(0x1214AA, 200)]],
     [("NCRD", 0.02, 1.02), ("LEGD", -0.02, 1.0)], None, "Camp Forlorn Hope restored: NCR confidence up"),
    (35, "Render Unto Caesar: House dead, Caesar told (VMQ02 15)", [[stage(0x129D14, 15)]],
     [("LEGD", 0.05, 1.05)], None, "Caesar's agent strikes in Vegas: the denarius gains"),
    (36, "Chief Hanlon killed", [[dead(0x106D79)]], [("NCRD", -0.05, 0.97)], None,
     "NCR Ranger Chief Hanlon dead: dollar dips"),
]


def term_code(term, n):
    """Lines that set iOK to 0 when this term is false (form ref in rA<n>)."""
    kind, mod = term[0], term[1]
    r = f"rA{n}"
    lines = []
    if kind == "loaded":
        lines.append(f'if eval (IsModLoaded "{mod}") == 0')
        lines.append("\tlet iOK := 0")
        lines.append("endif")
        return lines
    idx = "0" if mod == FNV else "iHH"
    obj = term[2]
    if mod != FNV:
        lines.append(f'if eval (IsModLoaded "{mod}") == 0')
        lines.append("\tlet iOK := 0")
        lines.append("else")
        lines.append(f'\tlet iHH := GetModIndex "{mod}"')
        pre = "\t"
    else:
        pre = ""
    lines.append(f"{pre}let {r} := BuildRef {idx} {obj}\t; 0x{obj:06X}")
    if kind == "stage":
        lines.append(f"{pre}if eval (GetStageDone {r} {term[3]}) == 0")
    elif kind == "done":
        lines.append(f"{pre}if eval (GetQuestCompleted {r}) == 0")
    elif kind == "dead":
        lines.append(f"{pre}if eval ({r}.GetDead) == 0")
    elif kind == "alive":
        lines.append(f"{pre}if eval ({r}.GetDead) == 1")
    lines.append(f"{pre}\tlet iOK := 0")
    lines.append(f"{pre}endif")
    if mod != FNV:
        lines.append("endif")
    return lines


def event_code(ev):
    eid, comment, alts, effects, delist, headline = ev
    out = [f"\t; E{eid}: {comment}", f'\tif eval (player.AuxVarGetFlt "_wxE" {eid}) == 0', "\t\tlet iHit := 0"]
    for alt in alts:
        out.append("\t\tif iHit == 0")
        out.append("\t\t\tlet iOK := 1")
        for n, term in enumerate(alt):
            out += ["\t\t\t" + l for l in term_code(term, n)]
        out.append("\t\t\tlet iHit := iOK")
        out.append("\t\tendif")
    out.append("\t\tif iHit")
    out.append(f'\t\t\tplayer.AuxVarSetFlt "_wxE" 1 {eid}')
    for tk, pct, mult in effects:
        out.append(f"\t\t\tcall rHit {T[tk]} {pct} {mult}\t; {tk}")
    if delist:
        out.append(f"\t\t\tcall rDelist {T[delist[0]]} {delist[1]}\t; {delist[0]}")
    out.append(f'\t\t\tcall rNews "{headline}"')
    out.append("\t\t\tlet iFired += 1")
    out.append("\t\tendif")
    out.append("\tendif")
    return out


def events_file(part, evs):
    head = [
        f"; Wasteland Exchange: news events, part {part} (GENERATED by tools/gen_exchange.py; edit there).",
        "; Each event fires once per character: a fading price shock plus a permanent change (ExHit),",
        "; or a delisting (ExDelist), and a headline (ExNews). Returns how many fired.",
        "int iOK", "int iHit", "int iFired", "int iHH",
        "ref rA0", "ref rA1", "ref rHit", "ref rDelist", "ref rNews", "",
        "begin Function {}",
        '\tlet rHit := CompileScript "WastelandBank/ExHit.txt"',
        '\tlet rDelist := CompileScript "WastelandBank/ExDelist.txt"',
        '\tlet rNews := CompileScript "WastelandBank/ExNews.txt"',
        "\tlet iFired := 0",
    ]
    body = []
    for ev in evs:
        body += event_code(ev)
    return "\n".join(head + body + ["\tSetFunctionValue iFired", "end", ""])


def data_file():
    lines = [
        "; Wasteland Exchange: the listings (GENERATED by tools/gen_exchange.py; edit there).",
        "; Re-applied on every load. Index = ticker number. _wxEx: 0 New Vegas Exchange, 1 Hub, 2 both.",
        "; _wxP0 start price in caps, _wxVol daily volatility, _wxYld annual dividend yield,",
        "; _wxSec sector (0 arms, 1 trade, 2 casino, 3 tech, 4 NCR), _wxTr daily trend (log).",
        "begin Function {}",
        f'\tplayer.AuxVarSetFlt "_wxCount" {len(TICKERS)}',
    ]
    for i, (tk, name, ex, p0, vol, yld, sec, tr) in enumerate(TICKERS):
        lines += [
            f"\t; {i} {tk}",
            f'\tplayer.AuxVarSetStr "_wxTk" "{tk}" {i}',
            f'\tplayer.AuxVarSetStr "_wxNm" "{name}" {i}',
            f'\tplayer.AuxVarSetFlt "_wxEx" {ex} {i}',
            f'\tplayer.AuxVarSetFlt "_wxP0" {p0} {i}',
            f'\tplayer.AuxVarSetFlt "_wxVol" {vol} {i}',
            f'\tplayer.AuxVarSetFlt "_wxYld" {yld} {i}',
            f'\tplayer.AuxVarSetFlt "_wxSec" {sec} {i}',
            f'\tplayer.AuxVarSetFlt "_wxTr" {tr} {i}',
        ]
    return "\n".join(lines + ["end", ""])


def refresh_ln_check():
    """Rebuild the 'every function compiled' list in ln_wasteland_bank.txt from the folder."""
    s = LN.read_text()
    begin = s.index("let int iBad := 0\n")
    end = s.index("if iBad > 0")
    names = sorted(f.stem for f in UDF.glob("*.txt"))
    block = ["let int iBad := 0", 'let ref rChk := CompileScript "WastelandBank/%s.txt"' % names[0],
             "if eval (IsFormValid rChk) == 0", "\tlet iBad += 1", "endif"]
    for n in names[1:]:
        block += ['let rChk := CompileScript "WastelandBank/%s.txt"' % n,
                  "if eval (IsFormValid rChk) == 0", "\tlet iBad += 1", "endif"]
    s = s[:begin] + "\n".join(block) + "\n" + s[end:]
    LN.write_text(s, newline="\n")


def write(path, text):
    if not path.exists() or path.read_text() != text:
        path.write_text(text, newline="\n")
        print("wrote", path.relative_to(ROOT))


def main():
    write(UDF / "ExData.txt", data_file())
    third = (len(EVENTS) + 2) // 3
    for part in range(3):
        write(UDF / f"ExEvents{part + 1}.txt", events_file(part + 1, EVENTS[part * third:(part + 1) * third]))
    refresh_ln_check()


if __name__ == "__main__":
    main()
