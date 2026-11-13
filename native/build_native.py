"""Build the native (C++) xNVSE plugins with Visual Studio Build Tools (x86).

    python native/build_native.py

Each native/<Name>/<Name>.cpp becomes src/<Mod folder>/nvse/plugins/<Name>.dll (see TARGETS). The
built DLLs are committed, so build.py doesn't need a compiler; run this after changing the C++.
The CRT is linked statically (/MT), so the DLLs need no Visual C++ redistributable.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {"ScanNullFix": "Scan Null Fix"}


def vcvars() -> Path:
    vswhere = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe")
    vs = subprocess.run([str(vswhere), "-products", "*", "-latest", "-property", "installationPath"],
                        capture_output=True, text=True, check=True).stdout.strip()
    return Path(vs) / "VC" / "Auxiliary" / "Build" / "vcvars32.bat"


def main():
    bat = vcvars()
    for name, mod in TARGETS.items():
        src = ROOT / "native" / name / (name + ".cpp")
        out_dir = ROOT / "src" / mod / "nvse" / "plugins"
        out_dir.mkdir(parents=True, exist_ok=True)
        obj_dir = ROOT / "native" / name / "obj"
        obj_dir.mkdir(exist_ok=True)
        dll = out_dir / (name + ".dll")
        # cmd /c mangles nested quotes, so the commands go in a batch file
        lines = [
            f'@call "{bat}" >nul',
            f'cd /d "{obj_dir}"',
            f'cl /nologo /O2 /MT /EHsc /W3 /LD "{src}" /Fe"{dll}" '
            f'/link /NOLOGO /INCREMENTAL:NO /IMPLIB:"{obj_dir / (name + ".lib")}"',
        ]
        bat_file = obj_dir / "build.bat"
        bat_file.write_text("\r\n".join(lines) + "\r\n")
        r = subprocess.run(["cmd", "/c", str(bat_file)], capture_output=True, text=True)
        print(r.stdout.strip())
        if r.returncode:
            print(r.stderr.strip())
            sys.exit("build failed: " + name)
        for junk in (out_dir / (name + ".exp"), out_dir / (name + ".lib")):
            junk.unlink(missing_ok=True)
        print("built", dll.relative_to(ROOT))


if __name__ == "__main__":
    main()
