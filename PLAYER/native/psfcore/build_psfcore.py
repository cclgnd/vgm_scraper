from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "third_party/src/highly_experimental/highly_experimental-main/Core"
PSFLIB = ROOT / "third_party/src/psflib/psflib-main"
ZLIB = ROOT / "third_party/msys2/zlib/ucrt64"
ZLIB_I686 = ROOT / "third_party/msys2/zlib-i686/mingw32"
OUT = ROOT / "engines/psfcore.dll"
HELPER_OUT = ROOT / "engines/psfhelper.exe"
BUILD = ROOT / "build/psfcore"


def main() -> int:
    sys.path.insert(0, str((ROOT / "tooling/py_gcc").resolve()))
    from py_win_x86_64_gcc import get_tool

    gcc = Path(get_tool("gcc"))
    env = os.environ.copy()
    env["PATH"] = str(gcc.parent) + os.pathsep + env["PATH"]
    BUILD.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    sources = [
        Path(__file__).with_name("psfcore.c"),
        PSFLIB / "psflib.c",
        CORE / "bios.c",
        CORE / "iop.c",
        CORE / "ioptimer.c",
        CORE / "mkhebios.c",
        CORE / "psx.c",
        CORE / "r3000.c",
        CORE / "r3000asm.c",
        CORE / "r3000dis.c",
        CORE / "spu.c",
        CORE / "spucore.c",
        CORE / "vfs.c",
    ]

    cmd = [
        str(gcc),
        "-shared",
        "-O2",
        "-std=c99",
        "-include",
        "ctype.h",
        "-DHAVE_STDINT_H",
        "-DEMU_COMPILE",
        "-DEMU_LITTLE_ENDIAN",
        "-I",
        str(CORE),
        "-I",
        str(PSFLIB),
        "-I",
        str(ZLIB / "include"),
        *map(str, sources),
        "-L",
        str(ZLIB / "lib"),
        "-lz",
        "-o",
        str(OUT),
    ]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True, env=env, cwd=BUILD)
    print(OUT)

    x86_gcc = ROOT / "tooling/w64devkit-x86/w64devkit/bin/gcc.exe"
    if x86_gcc.exists():
        x86_env = os.environ.copy()
        x86_env["PATH"] = str(x86_gcc.parent) + os.pathsep + x86_env["PATH"]
        helper_cmd = [
            str(x86_gcc),
            "-O2",
            "-std=c99",
            "-include",
            "ctype.h",
            "-DHAVE_STDINT_H",
            "-DEMU_COMPILE",
            "-DEMU_LITTLE_ENDIAN",
            "-I",
            str(CORE),
            "-I",
            str(PSFLIB),
            "-I",
            str(ZLIB_I686 / "include"),
            str(Path(__file__).with_name("psfhelper.c")),
            str(Path(__file__).with_name("psfcore.c")),
            str(PSFLIB / "psflib.c"),
            str(CORE / "bios.c"),
            str(CORE / "iop.c"),
            str(CORE / "ioptimer.c"),
            str(CORE / "mkhebios.c"),
            str(CORE / "psx.c"),
            str(CORE / "r3000.c"),
            str(CORE / "r3000asm.c"),
            str(CORE / "r3000dis.c"),
            str(CORE / "spu.c"),
            str(CORE / "spucore.c"),
            str(CORE / "vfs.c"),
            str(ZLIB_I686 / "lib/libz.a"),
            "-static",
            "-static-libgcc",
            "-o",
            str(HELPER_OUT),
        ]
        print(" ".join(helper_cmd))
        subprocess.run(helper_cmd, check=True, env=x86_env, cwd=BUILD)
        print(HELPER_OUT)
    else:
        print("warning: 32-bit w64devkit not found; skipping psfhelper.exe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
