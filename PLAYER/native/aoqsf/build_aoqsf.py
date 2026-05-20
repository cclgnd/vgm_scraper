#!/usr/bin/env python3
"""Build script for QSF helper (aoqsf_helper.exe)."""

import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
AOSDK_SRC = os.path.join(PROJECT_ROOT, "native", "aosdk-master")
BUILD_DIR = os.path.join(SCRIPT_DIR, "build")
OUTPUT_EXE = os.path.join(BUILD_DIR, "aoqsf_helper.exe")


def find_w64devkit():
    paths = [
        os.path.join(PROJECT_ROOT, "tooling", "w64devkit-x86", "w64devkit", "bin"),
        r"C:\w64devkit\bin",
        r"C:\Program Files\w64devkit\bin",
        r"D:\w64devkit\bin",
    ]
    for p in paths:
        if os.path.isfile(os.path.join(p, "i686-w64-mingw32-g++.exe")):
            return p
    return None


def main():
    w64devkit_bin = find_w64devkit()
    if not w64devkit_bin:
        print("ERROR: w64devkit not found", file=sys.stderr)
        return 1

    os.environ["PATH"] = w64devkit_bin + os.pathsep + os.environ.get("PATH", "")

    cc = os.path.join(w64devkit_bin, "i686-w64-mingw32-g++.exe")
    gcc = os.path.join(w64devkit_bin, "i686-w64-mingw32-gcc.exe")
    os.makedirs(BUILD_DIR, exist_ok=True)

    eng_qsf_dir = os.path.join(AOSDK_SRC, "eng_qsf")
    zlib_dir = os.path.join(AOSDK_SRC, "zlib")

    sources = [
        os.path.join(SCRIPT_DIR, "aoqsf_helper.cc"),
        os.path.join(eng_qsf_dir, "eng_qsf.c"),
        os.path.join(eng_qsf_dir, "qsound.c"),
        os.path.join(eng_qsf_dir, "kabuki.c"),
        os.path.join(eng_qsf_dir, "z80.c"),
        os.path.join(AOSDK_SRC, "corlett.c"),
        os.path.join(AOSDK_SRC, "utils.c"),
    ]

    zlib_sources = [
        "adler32.c",
        "compress.c",
        "crc32.c",
        "deflate.c",
        "gzio.c",
        "infback.c",
        "inffast.c",
        "inflate.c",
        "inftrees.c",
        "trees.c",
        "uncompr.c",
        "zutil.c",
    ]

    for src in zlib_sources:
        sources.append(os.path.join(zlib_dir, src))

    include_dirs = [
        AOSDK_SRC,
        eng_qsf_dir,
        zlib_dir,
    ]

    objects = []
    for src in sources:
        obj = os.path.join(
            BUILD_DIR,
            os.path.basename(src).replace(".c", ".o").replace(".cpp", ".o").replace(".cc", ".o"),
        )
        is_c = src.endswith(".c")
        compiler = gcc if is_c else cc

        cmd = [compiler, "-m32", "-O2", "-std=c++17" if not is_c else "-std=c99", "-DWIN32", "-DLSB_FIRST=1", "-D__LITTLE_ENDIAN__=1", "-fpermissive", "-fvisibility=default", "-fomit-frame-pointer", "-fno-exceptions", "-ffunction-sections", "-fdata-sections"]

        if not is_c:
            cmd.extend(["-fno-rtti", "-nostdlib++"])

        for inc in include_dirs:
            cmd.append("-I" + inc)

        cmd.extend(["-c", src, "-o", obj])

        print(f"Compiling {os.path.basename(src)}...")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPT_DIR)
        if result.returncode != 0:
            print(f"FAILED: {os.path.basename(src)}", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return 1
        objects.append(obj)

    cmd_link = [
        cc,
        "-m32",
        "-O2",
        "-o",
        OUTPUT_EXE,
        "-nostdlib++",
        "-static-libgcc",
        "-Wl,--gc-sections",
        "-Wl,--enable-stdcall-fixup",
    ] + objects

    print(f"Linking {OUTPUT_EXE}...")
    result = subprocess.run(cmd_link, capture_output=True, text=True, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        print("LINK FAILED", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return 1

    print(f"Built: {OUTPUT_EXE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
