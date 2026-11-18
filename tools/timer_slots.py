"""Timer slots: keep our repeating scripts from landing in the same frame.

    python tools/timer_slots.py            the schedule and how crowded its worst frames are
    python tools/timer_slots.py --assign   the best offset for every timer (to copy into loaders)
    python tools/timer_slots.py --suggest 1 heavy   the best free offset for a new timer

Why: every mod's loader (ln_*.txt) runs in the same frame when a save loads. A repeating timer
registered there with CallWhilePerSeconds first fires one interval later, so every 1-second timer
fired in the same frame, every second, for the whole session: about ten scripts in one frame, and
fifteen every tenth second when the slower ones lined up. That is a regular hitch.

The rule (2026-11-18): a loader never registers a repeating timer directly. It starts it at its
own offset within the second:
    CallAfterSeconds <offset> rStart 1 rTick rTrue <interval> <flags>
where rStart is the mod's <Prefix>/Start.txt (it calls CallWhilePerSeconds with those arguments).
xNVSE drops a timer's overshoot each time it fires (oldTime = now), so timers with the same
interval keep their spacing at a steady frame rate, and frozen timers (menus, pause) keep their
phase. Every load starts the pattern over.

check_scripts.py runs check() on every build:
  - a CallWhilePerSeconds anywhere other than a Start.txt needs "; slot: exempt (why)" on its line
    (for on-demand, per-frame work such as the typewriter while it types);
  - two heavy timers may never fire within the same SLOT (25 ms, one or two frames);
  - no slot may hold more than MAX_PER_SLOT timers.
A timer is heavy when its script (with the scripts it compiles and calls) loops over inventories
or the references around the player, or has several loops, unless its script says
"; slot weight: light (why)" (a cheap check that only sometimes calls the heavy part).
"""
import argparse
import re
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
SLOT = Fraction(1, 40)          # 25 ms: the grid offsets sit on, and the window two timers collide in
MAX_PER_SLOT = 2
START_RE = re.compile(r"^\s*CallAfterSeconds\s+([\d.]+)\s+(\w+)\s+1\s+(\w+)\s+(\w+)\s+([\d.]+)\s+(\d+)", re.M)
COMPILE_RE = re.compile(r'let\s+(?:ref\s+)?(\w+)\s*:=\s*CompileScript\s+"([^"]+)"')
HEAVY_RE = re.compile(r"GetInventoryObject|GetInvRefsForItem|GetNumItems|GetFirstRef|GetNextRef|"
                      r"GetRefs\b|GetActorsByProcessingLevel|GetNumRefs|GetItems\b")


def udf(path):
    p = list(SRC.glob("*/nvse/user_defined_functions/" + path))
    return p[0] if p else None


def weight(path, seen=None):
    """'heavy' or 'light', from what the script and the scripts it calls do."""
    seen = seen if seen is not None else set()
    p = udf(path)
    if not p or path in seen:
        return 0, 0
    seen.add(path)
    t = p.read_text(encoding="latin1")
    scans = len(HEAVY_RE.findall(t))
    loops = len(re.findall(r"^\s*(?:while|foreach)\b", t, re.M))
    for sub in re.findall(r'CompileScript\s+"([^"]+)"', t):
        s, l = weight(sub, seen)
        scans, loops = scans + s, loops + l
    return scans, loops


def timers():
    """Every slotted timer: {file, line, offset, interval, script, heavy}."""
    out = []
    for ln in sorted(SRC.glob("*/nvse/plugins/scripts/ln_*.txt")):
        t = ln.read_text(encoding="latin1")
        compiled = dict(COMPILE_RE.findall(t))
        for m in START_RE.finditer(t):
            off, _, fn, _, every, _ = m.groups()
            script = compiled.get(fn, fn)
            scans, loops = weight(script)
            top = udf(script)
            light = top is not None and "slot weight: light" in top.read_text(encoding="latin1")
            out.append({"file": ln.relative_to(ROOT).as_posix(), "line": t.count("\n", 0, m.start()) + 1,
                        "offset": Fraction(off), "interval": Fraction(every), "script": script,
                        "heavy": not light and (scans > 0 or loops >= 4), "scans": scans, "loops": loops})
    return out


def horizon(ts):
    """A span after which the whole pattern repeats: a common multiple of the intervals (to 120 s)."""
    h = Fraction(1)
    while not all((h / t["interval"]).denominator == 1 for t in ts) and h < 120:
        h += Fraction(1, 4)
    return h


def schedule(ts):
    """{slot index within the cycle: [timer, ...]} over one full cycle after the first second."""
    h = horizon(ts)
    slots = {}
    for i, t in enumerate(ts):
        when = t["offset"] + t["interval"]
        while when < t["offset"] + t["interval"] + h:
            slots.setdefault(int((when % h) / SLOT), []).append(i)
            when += t["interval"]
    return slots


def problems(ts):
    out = []
    for slot, who in sorted(schedule(ts).items()):
        heavy = [i for i in who if ts[i]["heavy"]]
        if len(heavy) > 1:
            out.append("slot %.3f s: heavy timers together: %s" % (float(slot * SLOT), ", ".join(ts[i]["script"] for i in heavy)))
        if len(who) > MAX_PER_SLOT:
            out.append("slot %.3f s: %d timers together: %s" % (float(slot * SLOT), len(who), ", ".join(ts[i]["script"] for i in who)))
    return sorted(set(out))


def cost(ts):
    """Lower is better: two heavy timers in one slot weigh most, then crowding, then heavy timers in
    neighbouring slots (25 ms apart is still within a slow frame), so the load spreads out."""
    sched = schedule(ts)
    c = 0
    for slot, who in sched.items():
        h = sum(ts[i]["heavy"] for i in who)
        c += 1000 * max(0, h - 1) + 100 * max(0, len(who) - MAX_PER_SLOT) + 10 * max(0, len(who) - 1)
        if h:
            near = sum((3 if abs(d) == 1 else 1) * ts[i]["heavy"]
                       for d in (-2, -1, 1, 2) for i in sched.get(slot + d, []))
            c += 3 * h * near
    return c


def assign(ts):
    """Offsets for every timer: the heaviest and most frequent placed first, each in its best slot."""
    order = sorted(range(len(ts)), key=lambda i: (not ts[i]["heavy"], ts[i]["interval"], -ts[i]["scans"]))
    placed = []
    grid = [SLOT * k for k in range(int(1 / SLOT))]
    for i in order:
        best = None
        for off in grid:
            trial = placed + [dict(ts[i], offset=off)]
            c = cost(trial)
            if best is None or c < best[0]:
                best = (c, off)
        placed.append(dict(ts[i], offset=best[1]))
    return placed


def check(verbose=False):
    """Problems for check_scripts.py: unslotted timers and collisions."""
    errs = []
    for p in sorted(SRC.glob("*/nvse/**/*.txt")):
        if p.name == "Start.txt":
            continue
        for n, line in enumerate(p.read_text(encoding="latin1").splitlines(), 1):
            code = line.split(";")[0]
            if re.search(r"\b(CallWhilePerSeconds|CallWhile|CallForSeconds)\b", code) and "slot: exempt" not in line:
                errs.append("%s:%d: repeating timer without a slot: start it with CallAfterSeconds <offset> "
                            "rStart 1 ... (tools/timer_slots.py --suggest), or mark it '; slot: exempt (why)'"
                            % (p.relative_to(ROOT).as_posix(), n))
    ts = timers()
    errs += ["timer slots: " + e for e in problems(ts)]
    return errs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assign", action="store_true")
    ap.add_argument("--suggest", nargs=2, metavar=("INTERVAL", "heavy|light"))
    a = ap.parse_args()
    ts = timers()
    if a.suggest:
        new = {"file": "(new)", "line": 0, "offset": Fraction(0), "interval": Fraction(a.suggest[0]),
               "script": "(new timer)", "heavy": a.suggest[1] == "heavy", "scans": 1, "loops": 0}
        best = min((cost(ts + [dict(new, offset=SLOT * k)]), SLOT * k) for k in range(int(1 / SLOT)))
        print("best offset for a new %s %s s timer: %.3f (cost %d)" % (a.suggest[1], a.suggest[0], float(best[1]), best[0]))
        return
    if a.assign:
        ts = assign(ts)
    for t in sorted(ts, key=lambda t: (t["offset"], t["interval"])):
        print("%6.3f  every %-5s %-5s %-34s %s:%d" % (float(t["offset"]), float(t["interval"]),
                                                    "HEAVY" if t["heavy"] else "light", t["script"], t["file"], t["line"]))
    probs = problems(ts)
    print("\n%d timers; worst slot holds %d; %s" % (len(ts), max((len(v) for v in schedule(ts).values()), default=0),
                                                   "no collisions" if not probs else "%d problem slot(s)" % len(probs)))
    for p in probs:
        print("  " + p)
    errs = check()
    if errs and not a.assign:
        sys.exit("\n".join(errs))


if __name__ == "__main__":
    main()
