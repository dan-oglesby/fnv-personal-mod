"""Static checks on the mods' NVSE script files, run by build.py before anything is built.

    python check_scripts.py

1. Variable names that clash with a command name. The game's script compiler rejects them, xNVSE
   then has no function for that file, and timers or event handlers that call it fail. On
   2026-11-13 a variable named iMod (the short name of the console command ApplyImageSpaceModifier,
   "imod") stopped five Auto Smoke functions compiling and New Vegas crashed in nvse_1_4.dll.
   Command names come from nvse.log (every command xNVSE's plugins register), tools/xnvse_commands.txt
   (xNVSE's own commands, which nvse.log doesn't list; taken from its CommandTable.cpp) and a list of
   vanilla console short names.
2. if/endif, while/loop and foreach/loop balance.
3. Menu XML files are well-formed (the game's parser is lenient, so a bad tag can silently break a
   HUD element instead of failing).

Exits 1 if anything is wrong.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NVSE_LOG = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Fallout New Vegas\nvse.log")

# Vanilla console commands' short names (and a few long ones) that look like variable names.
VANILLA = """imod rimod tcl tgm tm tfc tai tcai tdetect coc cow kah killall sw fw sv tdt tb ts tg tll
tmm sq sqv sqs sqt inv psb sa sae pms sms ra rm sr fov caqs ss sb sf ar eval pcb qqq tlb tlv twf
tws tfow tgt tmg tcs tdm tfh tlrl tlad tml tmn ttv twr spf lp sun sp sos sqo sexchange sifh
getav setav modav forceav rav damageav restoreav player playerref""".split()

DECL = re.compile(r"^\s*(?:let\s+)?(?:int|short|long|float|ref|reference|string_var|array_var)\s+(\w+)",
                  re.I | re.M)


def command_names():
    names = {n.lower() for n in VANILLA}
    core = ROOT / "tools" / "xnvse_commands.txt"
    if core.exists():
        names |= {n.strip().lower() for n in core.read_text().split() if n.strip()}
    if NVSE_LOG.exists():
        log = NVSE_LOG.read_text(encoding="latin1", errors="replace")
        for m in re.finditer(r"Reg\w*Command\s+\[\w+\]\s+(\w+)(?:\s+\((\w+)\))?", log):
            names.add(m.group(1).lower())
            if m.group(2):
                names.add(m.group(2).lower())
    else:
        print("note: %s not found; checking against vanilla short names only" % NVSE_LOG)
    return names


def balance(text):
    depth = {"if": 0, "loop": 0}
    for line in text.splitlines():
        t = line.split(";")[0].strip().lower()
        if re.match(r"^if\b", t):
            depth["if"] += 1
        elif t == "endif":
            depth["if"] -= 1
        elif re.match(r"^(while|foreach)\b", t):
            depth["loop"] += 1
        elif t == "loop":
            depth["loop"] -= 1
        if min(depth.values()) < 0:
            return "closes a block it never opened: %r" % line.strip()
    if any(depth.values()):
        return "unclosed block(s): %s" % depth
    return None


# Functions that act on a reference and silently read 0 when called without one inside a function file.
REF_ONLY = ["IsHardcore", "GetAV", "GetActorValue", "GetItemCount", "IsInCombat", "GetDead",
            "GetHealthPercentage", "GetEquippedObject", "GetEquippedCurrentHealth", "HasMagicEffect",
            "GetRadiationLevel", "GetNumItems", "GetInventoryObject", "IsSneaking"]

EXPR_START = re.compile(r"^(let|while|foreach|return|setfunctionvalue|(else)?if\s+eval|call)\b", re.I)


def compile_traps(text):
    """Patterns that made whole files fail to precompile in xNVSE 6.4.9 (2026-11-14), silently
    for some: a ';' inside a string (the compiler cuts the line there), an array element used
    outside an NVSE expression (classic commands and plain 'if' can't take aFoo[i]), and setting a
    JIP aux string from "" or a $variable."""
    out = []
    # settings versions: blocks like  if eval (player.AuxVarGetFlt "_wbSet") < N  must come in
    # rising N. A block placed after a higher one never runs once that one has set the version
    # (Wasteland Bank's version 2 sat last, so its selling cut was never set: 2026-11-17).
    # Only blocks that set the version count (a chain that tests one saved value and sets it once
    # at the end, as Smart Loot's does, is fine).
    last, open_blk = {}, {}
    for n, line in enumerate(text.splitlines(), 1):
        code = line.split(";")[0].rstrip()
        m = re.search(r'AuxVarGetFlt\s+"(_\w+)"\)\s*<\s*(\d+)\s*$', code)
        if m and line.strip().lower().startswith("if"):
            var, ver = m.group(1), int(m.group(2))
            if var in last and ver < last[var]:
                out.append("line %d: settings version %s < %d comes after a block for < %d that sets it"
                           " (it would never run)" % (n, var, ver, last[var]))
            open_blk[var] = ver
            continue
        s = re.search(r'AuxVarSetFlt\s+"(_\w+)"', code)
        if s and s.group(1) in open_blk:
            var = s.group(1)
            last[var] = max(open_blk[var], last.get(var, 0))
    for n, line in enumerate(text.splitlines(), 1):
        if len(line) > 500:     # the compiler's hard limit is 512 characters a line
            out.append("line %d: %d characters (script lines are limited to 512)" % (n, len(line)))
        code = line.strip()
        if not code or code.startswith(";"):
            continue
        for s in re.findall(r'"([^"]*)"', code):
            if ";" in s:
                out.append("line %d: ';' inside a string" % n)
        bare = re.sub(r'"[^"]*"', '""', code).split(";")[0]
        if re.search(r"[A-Za-z_]\w*\[", bare) and not EXPR_START.match(bare):
            out.append("line %d: array element outside an NVSE expression (copy it into a variable first)" % n)
        if re.search(r'AuxVarSetStr\s+"[^"]*"\s+(""|\$)', code, re.I):
            out.append("line %d: AuxVarSetStr from \"\" or a $variable" % n)
        # High-traffic game events must be filtered: xNVSE queues events fired on background threads
        # (NPCs equipping gear during cell loads) onto an unlocked list, a race that crashed the
        # loaders on 2026-11-14. A filter (e.g. "second"::yourItem) drops other events first.
        # "eval" switches a condition to an NVSE expression and must come right after if/elseif.
        # Put mid-condition ("if x == 1 && eval ...") it doesn't compile (written twice on 2026-11-15).
        if re.match(r"(else)?if\b", bare, re.I) and re.search(r"\beval\b", bare, re.I) \
                and not re.match(r"(else)?if\s+eval\b", bare, re.I):
            out.append("line %d: 'eval' must come right after if/elseif" % n)
        # No backslashes inside strings: use / in paths (MCM's convention). On 2026-11-15 every
        # SetUIFloat "HUDMainMenu\_trait" in Needs Meters failed at run time ("failed to evaluate
        # expression", 5,089 times in one session), most likely because a runtime-compiled string
        # treats the backslash as an escape.
        for s in re.findall(r'"([^"]*)"', code.split(";")[0]):
            if "\\" in s:
                out.append("line %d: backslash inside a string (use / in paths)" % n)
        # Reference functions need a reference: a user-defined function has no calling reference, so
        # a bare call reads 0. On 2026-11-15 a bare "if IsHardcore" in Needs Meters hid the needs
        # rows for good. Write player.IsHardcore (or rSomething.X).
        for fn in REF_ONLY:
            if re.search(r"(?<![\w.])%s\b" % fn, bare, re.I):
                out.append("line %d: %s without a reference (write player.%s)" % (n, fn, fn))
        # A form ID written in decimal must match the hex in its comment: on 2026-11-15 a hand
        # conversion put 1191988 for 0x123054 (1192020), so the item was never matched.
        b = re.search(r"BuildRef\s+\S+\s+(\d+)", line)
        h = re.search(r";.*?0x([0-9A-Fa-f]+)", line)
        if b and h and int(b.group(1)) != int(h.group(1), 16) % 0x1000000:
            out.append("line %d: BuildRef %s does not match the comment's 0x%s (= %d)"
                       % (n, b.group(1), h.group(1), int(h.group(1), 16) % 0x1000000))
        m = re.match(r'SetEventHandler\s+"(OnActorEquip|OnActorUnequip|OnAdd|OnDrop|OnHit|OnHitWith)"', code, re.I)
        if m and "::" not in code:
            out.append("line %d: unfiltered %s handler (add a filter such as \"second\"::item)" % (n, m.group(1)))
    return out


def xml_problems(text):
    """Parse a menu XML file with the game's entities (&true; etc.) stubbed out."""
    import xml.dom.minidom
    body = re.sub(r"<!--.*?-->", "", re.sub(r"&[A-Za-z_][\w-]*;", "0", text), flags=re.S)
    try:
        xml.dom.minidom.parseString("<root>" + body + "</root>")
    except Exception as e:  # expat's message names the line and column
        return ["XML not well-formed: %s" % e]
    return []


def main():
    names = command_names()
    problems = []
    for f in sorted((ROOT / "src").rglob("*.xml")):
        for p in xml_problems(f.read_text(encoding="utf-8-sig", errors="replace")):
            problems.append("%s: %s" % (f.relative_to(ROOT), p))
    for f in sorted((ROOT / "src").rglob("*.txt")):
        text = f.read_text(encoding="utf-8", errors="replace")
        rel = f.relative_to(ROOT)
        for var in DECL.findall(text):
            if var.lower() in names:
                problems.append("%s: variable %s has the same name as a command" % (rel, var))
        for trap in compile_traps(text):
            problems.append("%s: %s" % (rel, trap))
        err = balance(text)
        if err:
            problems.append("%s: %s" % (rel, err))
    for p in problems:
        print("SCRIPT PROBLEM:", p)
    if not problems:
        print("scripts checked: no command-name clashes, blocks balanced (%d command names)" % len(names))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
