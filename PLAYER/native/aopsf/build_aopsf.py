from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "third_party" / "src" / "audacious-plugins" / "audacious-plugins-4.5" / "src" / "psf"
OUT = ROOT / "engines" / "aopsf" / "aopsf_helper.exe"
ZLIB = ROOT / "third_party" / "msys2" / "zlib-i686" / "mingw32"
GCC_BIN = ROOT / "tooling" / "w64devkit-x86" / "w64devkit" / "bin"


def find_gpp() -> Path:
    candidates = [GCC_BIN / "g++.exe"]
    if system_gpp := shutil.which("g++"):
        candidates.append(Path(system_gpp))
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    raise SystemExit("g++.exe not found. Expected portable GCC under tooling/w64devkit-x86.")


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Missing Audacious PSF source: {SRC}")
    if not ZLIB.exists():
        raise SystemExit(f"Missing zlib package: {ZLIB}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    gpp = find_gpp()

    sources = [
        Path(__file__).with_name("aopsf_helper.cc"),
        SRC / "corlett.cc",
        SRC / "eng_psf.cc",
        SRC / "eng_psf2.cc",
        SRC / "eng_spx.cc",
        SRC / "psx.cc",
        SRC / "psx_hw.cc",
        SRC / "peops" / "spu.cc",
        SRC / "peops2" / "dma.cc",
        SRC / "peops2" / "registers.cc",
        SRC / "peops2" / "spu.cc",
    ]

    cmd = [
        str(gpp),
        "-std=c++17",
        "-O2",
        "-DNDEBUG",
        "-I",
        str(Path(__file__).with_name("include")),
        "-I",
        str(SRC),
        "-I",
        str(SRC / "peops"),
        "-I",
        str(SRC / "peops2"),
        "-I",
        str(ZLIB / "include"),
        *map(str, sources),
        str(ZLIB / "lib" / "libz.a"),
        "-static",
        "-static-libgcc",
        "-static-libstdc++",
        "-o",
        str(OUT),
    ]

    env = os.environ.copy()
    env["PATH"] = str(gpp.parent) + os.pathsep + env.get("PATH", "")
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)
    print(OUT)


if __name__ == "__main__":
    main()
