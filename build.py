"""Package each mod under src/ as a zip in dist/, and stage a copy in Vortex.

    python build.py              # build zips and stage every mod in Vortex
    python build.py --no-stage   # zips only

Each src/<Mod Name>/ folder mirrors the game's Data folder (nvse/..., meshes/..., *.esp).

Staging: each mod is
mirrored into Vortex's New Vegas staging folder as <Mod Name>/, so it appears in Vortex's Mods list
(after Vortex refreshes or restarts) ready to enable and deploy. Files are rewritten in place, not
replaced, so a copy Vortex has already deployed (hardlinked into the game) updates with it; files
removed from src/ are removed from the staged copy too, and so is the copy Vortex deployed into
the game, but only when it is that same hardlinked file (2026-11-18: otherwise Vortex saw the
deployed copy as an "external change" and put it back into staging after every build, and the
game kept compiling the removed scripts). Files Vortex's deployment manifest says came from one of
these mods but that no longer exist in src/ are removed from the game the same way. Only folders
named after a mod in src/ are touched. Nothing is staged while FalloutNV.exe is running.
"""
import filecmp
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import check_scripts
import make_plugins

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
import exchange_sim  # noqa: E402
import gen_exchange  # noqa: E402
import gen_needs_meters  # noqa: E402
import gen_load_order_patch  # noqa: E402
import gen_ammo_boxes  # noqa: E402

ROOT = Path(__file__).resolve().parent
STAGING = Path(os.environ.get("APPDATA", "")) / "Vortex" / "falloutnv" / "mods"
GAME_DATA = make_plugins.FNV_DATA


def game_running() -> bool:
    """True if FalloutNV.exe is running (Windows only; staging into a running game is never safe)."""
    if os.name != "nt":
        return False
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq FalloutNV.exe"], capture_output=True, text=True)
    return "FalloutNV.exe" in r.stdout


def remove_deployed(staged: Path, rel: Path) -> bool:
    """Remove the game's copy of a staged file that is going away, if it is the same hardlinked file."""
    deployed = GAME_DATA / rel
    try:
        if deployed.is_file() and os.path.samefile(staged, deployed):
            deployed.unlink()
            return True
    except OSError:
        pass
    return False


def remove_orphans(mod: Path) -> int:
    """Remove files Vortex deployed from this mod that are no longer in src/ (and no longer staged)."""
    manifest = GAME_DATA / "vortex.deployment.json"
    if not manifest.is_file():
        return 0
    try:
        entries = json.loads(manifest.read_text(encoding="utf-8")).get("files", [])
    except (OSError, ValueError):
        return 0
    gone = 0
    for e in entries:
        if e.get("source") != mod.name:
            continue
        rel = Path(e.get("relPath", ""))
        if not rel.parts or rel.is_absolute() or ".." in rel.parts:
            continue                                    # only plain paths inside Data
        if (mod / rel).exists() or (STAGING / mod.name / rel).exists():
            continue
        f = GAME_DATA / rel
        if f.is_file():
            f.unlink()
            print("  removed stale %s from the game (no longer in %s)" % (rel, mod.name))
            gone += 1
    return gone


def build_zip(mod: Path) -> Path:
    out = ROOT / "dist" / (mod.name + ".zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(mod.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(mod).as_posix())
    return out


def stage(mod: Path) -> str:
    dest = STAGING / mod.name
    changed = 0
    wanted = set()
    for f in sorted(mod.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(mod)
        wanted.add(rel)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and filecmp.cmp(f, target, shallow=False):
            continue
        with open(f, "rb") as src, open(target, "r+b" if target.exists() else "wb") as dst:
            data = src.read()
            dst.seek(0)
            dst.write(data)
            dst.truncate()          # same file, so a deployed hardlink sees the new content
        changed += 1
    removed = 0
    if dest.exists():
        for f in sorted(dest.rglob("*"), reverse=True):
            rel = f.relative_to(dest)
            if f.is_file() and rel not in wanted:
                if remove_deployed(f, rel):
                    print("  removed %s from the game too" % rel)
                f.unlink()
                removed += 1
            elif f.is_dir() and not any(f.iterdir()):
                f.rmdir()
    removed += remove_orphans(mod)
    return "%s (%d updated, %d removed)" % (dest, changed, removed)


def main(argv):
    gen_exchange.main()             # Wasteland Exchange's generated data and event scripts
    gen_needs_meters.main()         # Needs Meters' HUD file
    if exchange_sim.main():         # the exchange's maths, checked offline
        sys.exit("build stopped: Wasteland Exchange simulation failed")
    if check_scripts.main():        # a script that would not compile in game stops the build
        sys.exit("build stopped: fix the script problems above")
    make_plugins.main()             # the small item plugins some mods use as their menu item
    gen_load_order_patch.main()     # local only: forwards fixes later plugins undo (not committed)
    gen_ammo_boxes.main()           # local only: Ammo Boxing's boxes and table, from the load order
    (ROOT / "dist").mkdir(exist_ok=True)
    do_stage = "--no-stage" not in argv
    if do_stage and game_running():
        print("FalloutNV.exe is running: zips only, nothing staged (close the game and build again)")
        do_stage = False
    if do_stage and not (STAGING / "__vortex_staging_folder").exists():
        print("Vortex staging folder not found at %s - zips only" % STAGING)
        do_stage = False
    for mod in sorted(p for p in (ROOT / "src").iterdir() if p.is_dir()):
        out = build_zip(mod)
        print("built", out.relative_to(ROOT), "-", len(zipfile.ZipFile(out).namelist()), "files")
        if do_stage:
            print("  staged", stage(mod))
    if do_stage:
        print("In Vortex: refresh the Mods page (or restart Vortex), then enable and deploy.")


if __name__ == "__main__":
    main(sys.argv[1:])
