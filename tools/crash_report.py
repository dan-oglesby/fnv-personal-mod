"""Group New Vegas crash logs into kinds, to see which crashes recur and whether a change helps.

    python tools/crash_report.py               # all CrashLogger logs
    python tools/crash_report.py --since 2026-11-18

Reads the logs Crash Logger writes to the game folder's "Crash Logs" (never changes them) and
groups each crash by where it faulted (module + address) and which thread, with the kinds of
object on its stack (queued textures, animations, ...), where the player was, and the injected
overlay DLLs the log lists (Discord, Steam, RivaTuner: a common source of instability in this
32-bit DX9 engine). The known kinds are named from this load order's history (2026-11-18):
  FalloutNV+0xA61A74 < 0x43C4E0   texture streaming (QueuedTexture / IOManager, often an NPC's
                                  generated body texture, bodymods\\...modbody*.dds)
  FalloutNV+0xAAA60A              the game's memory heap, usually freeing an animation in use
  ntdll RtlSizeHeap               heap corruption (2026-11-14, before the equip-event race fix)
"""
import argparse
import collections
import re
from pathlib import Path

GAME = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Fallout New Vegas")
KNOWN = {
    ("FalloutNV", "0x00A61A74"): "texture streaming",
    ("FalloutNV", "0x00AAA60A"): "memory heap (animation in use freed)",
    ("ntdll", "0x10060DD5"): "heap corruption",
}
OVERLAYS = ("DiscordHook", "GameOverlayRenderer", "RTSSHooks", "obs-vulkan", "graphics-hook", "NahimicOSD")


def parse(path):
    t = path.read_text(encoding="utf-8", errors="replace")
    thread = re.search(r"Thread: (.*)", t)
    calls = re.findall(r"\|\s+(\S+) \((0x[0-9A-F]+)\) \|", t)
    top = calls[0] if calls else ("?", "?")
    world = re.search(r'World:\s+\S+ \("?([^)"]*)', t)
    cell = re.search(r'Cell:\s+\S+ \("?([^)"]*)', t)
    classes = collections.Counter(re.findall(r"Class: (Queued\w+|\w*Anim\w*|NiControllerSequence|MemoryHeap)", t))
    return {
        "when": path.name[12:28],
        "thread": thread.group(1).strip() if thread else "?",
        "top": top,
        "kind": KNOWN.get(top, "other"),
        "where": "%s / %s" % (world.group(1) if world else "?", cell.group(1) if cell else "?"),
        "classes": ", ".join(k for k, _ in classes.most_common(3)),
        "overlays": [o for o in OVERLAYS if o in t],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="")
    args = ap.parse_args()
    logs = sorted((GAME / "Crash Logs").glob("CrashLogger.*.log"))
    rows = [parse(p) for p in logs if p.name[12:22] >= args.since]
    if not rows:
        print("no crash logs since", args.since or "ever")
        return
    for r in rows:
        print("%s  %-22s %-28s %-26s %s%s" % (r["when"], r["kind"][:22], "%s+%s" % r["top"], r["thread"][:26],
                                             r["where"], ("  [" + r["classes"] + "]") if r["classes"] else ""))
    print()
    for kind, n in collections.Counter(r["kind"] for r in rows).most_common():
        print("%3d  %s" % (n, kind))
    seen = sorted({o for r in rows for o in r["overlays"]})
    if seen:
        print("\noverlays injected into the game in these logs:", ", ".join(seen))


if __name__ == "__main__":
    main()
