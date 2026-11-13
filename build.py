"""Package each mod under src/ as a zip in dist/, and stage a copy in Vortex.

    python build.py              # build zips and stage every mod in Vortex
    python build.py --no-stage   # zips only

Each src/<Mod Name>/ folder mirrors the game's Data folder (nvse/..., meshes/..., *.esp).

Staging (Dan, 2026-11-11: "staging a copy of anything we work on in the vortex folder"): each mod is
mirrored into Vortex's New Vegas staging folder as <Mod Name>/, so it appears in Vortex's Mods list
(after Vortex refreshes or restarts) ready to enable and deploy. Files are rewritten in place, not
replaced, so a copy Vortex has already deployed (hardlinked into the game) updates with it; files
removed from src/ are removed from the staged copy too. Only folders named after a mod in src/
are touched.
"""
import filecmp
import os
import shutil
import sys
import zipfile
from pathlib import Path

import check_scripts
import make_plugins

ROOT = Path(__file__).resolve().parent
STAGING = Path(os.environ.get("APPDATA", "")) / "Vortex" / "falloutnv" / "mods"


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
                f.unlink()
                removed += 1
            elif f.is_dir() and not any(f.iterdir()):
                f.rmdir()
    return "%s (%d updated, %d removed)" % (dest, changed, removed)


def main(argv):
    if check_scripts.main():        # a script that would not compile in game stops the build
        sys.exit("build stopped: fix the script problems above")
    make_plugins.main()             # the small item plugins some mods use as their menu item
    (ROOT / "dist").mkdir(exist_ok=True)
    do_stage = "--no-stage" not in argv
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
