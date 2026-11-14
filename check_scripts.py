"""Static checks on the mods' NVSE script files, run by build.py before anything is built.

    python check_scripts.py

1. Variable names that clash with a command name. The game's script compiler rejects them, xNVSE
   then has no function for that file, and timers or event handlers that call it fail. On
   2026-11-13 a variable named iMod (the short name of the console command ApplyImageSpaceModifier,
   "imod") stopped five Auto Smoke functions compiling and New Vegas crashed in nvse_1_4.dll.
   Command names come from nvse.log (every command xNVSE and its plugins register) plus a list of
   vanilla console short names, which nvse.log doesn't record.
2. if/endif, while/loop and foreach/loop balance.

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


EXPR_START = re.compile(r"^(let|while|foreach|return|setfunctionvalue|(else)?if\s+eval|call)\b", re.I)


def compile_traps(text):
    """Patterns that made whole files fail to precompile in xNVSE 6.4.9 (2026-11-14), silently
    for some: a ';' inside a string (the compiler cuts the line there), an array element used
    outside an NVSE expression (classic commands and plain 'if' can't take aFoo[i]), and setting a
    JIP aux string from "" or a $variable."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
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
    return out


def main():
    names = command_names()
    problems = []
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
