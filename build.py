"""Package each mod under src/ as a zip in dist/, ready to drag into Vortex.

    python build.py

Each src/<Mod Name>/ folder mirrors the game's Data folder (nvse/..., meshes/..., *.esp).
"""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    (ROOT / "dist").mkdir(exist_ok=True)
    for mod in sorted(p for p in (ROOT / "src").iterdir() if p.is_dir()):
        out = ROOT / "dist" / (mod.name + ".zip")
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(mod.rglob("*")):
                if f.is_file():
                    z.write(f, f.relative_to(mod).as_posix())
        print("built", out.relative_to(ROOT), "-", ", ".join(z.namelist() if False else
              [n for n in zipfile.ZipFile(out).namelist()]))


if __name__ == "__main__":
    main()
