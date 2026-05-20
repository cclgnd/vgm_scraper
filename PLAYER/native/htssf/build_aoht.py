#!/usr/bin/env python3
"""Build script for Highly Theoretical SSF/DSF helper (aoht_helper.exe)."""

import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
HT_CORE_DIR = os.path.join(PROJECT_ROOT, "third_party", "src", "highly_theoretical", "highly_theoretical-main", "Core")
PSFLIB_DIR = os.path.join(PROJECT_ROOT, "third_party", "src", "psflib", "psflib-main")
BUILD_DIR = os.path.join(SCRIPT_DIR, "build")
OUTPUT_EXE = os.path.join(BUILD_DIR, "aoht_helper.exe")

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

def find_zlib():
    """Find zlib header and library."""
    paths = [
        (
            os.path.join(PROJECT_ROOT, "third_party", "msys2", "zlib-i686", "mingw32", "include"),
            os.path.join(PROJECT_ROOT, "third_party", "msys2", "zlib-i686", "mingw32", "lib"),
        ),
        (
            os.path.join(PROJECT_ROOT, "third_party", "msys2", "zlib", "ucrt64", "include"),
            os.path.join(PROJECT_ROOT, "third_party", "msys2", "zlib", "ucrt64", "lib"),
        ),
    ]
    for inc, lib in paths:
        if os.path.isfile(os.path.join(inc, "zlib.h")) and os.path.isfile(os.path.join(lib, "libz.a")):
            return inc, lib
    return None, None

def main():
    w64devkit_bin = find_w64devkit()
    if not w64devkit_bin:
        print("ERROR: w64devkit not found", file=sys.stderr)
        return 1

    os.environ["PATH"] = w64devkit_bin + os.pathsep + os.environ.get("PATH", "")

    cc = os.path.join(w64devkit_bin, "i686-w64-mingw32-g++.exe")
    gcc = os.path.join(w64devkit_bin, "i686-w64-mingw32-gcc.exe")
    os.makedirs(BUILD_DIR, exist_ok=True)

    zlib_include, zlib_lib = find_zlib()
    if not zlib_include or not zlib_lib:
        print("ERROR: zlib not found", file=sys.stderr)
        return 1

    ht_sources = [
        os.path.join(HT_CORE_DIR, "arm.c"),
        os.path.join(HT_CORE_DIR, "dcsound.c"),
        os.path.join(HT_CORE_DIR, "satsound.c"),
        os.path.join(HT_CORE_DIR, "sega.c"),
        os.path.join(HT_CORE_DIR, "yam.c"),
    ]

    psflib_sources = [
        os.path.join(PSFLIB_DIR, "psflib.c"),
        os.path.join(PSFLIB_DIR, "psf2fs.c"),
    ]

    helper_src = os.path.join(SCRIPT_DIR, "htssf_helper.cc")

    # Compile C sources with gcc
    c_sources = ht_sources + psflib_sources
    c_objects = []
    for src in c_sources:
        obj = os.path.join(BUILD_DIR, os.path.basename(src).replace(".c", ".o"))
        cmd_c = [
            gcc,
            "-m32",
            "-O2",
            "-std=c99",
            "-DWIN32",
            "-DUSE_STARSCREAM",
            "-DNDEBUG",
            "-D_LIB",
            "-DEMU_COMPILE",
            "-DEMU_LITTLE_ENDIAN",
            "-I" + HT_CORE_DIR,
            "-I" + PSFLIB_DIR,
            "-I" + zlib_include,
            "-c", src,
            "-o", obj,
        ]
        print(f"Compiling {os.path.basename(src)}...")
        result = subprocess.run(cmd_c, capture_output=True, text=True, cwd=SCRIPT_DIR)
        if result.returncode != 0:
            print(f"FAILED: {os.path.basename(src)}", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return 1
        c_objects.append(obj)

    # Compile C++ helper with g++
    helper_obj = os.path.join(BUILD_DIR, "htssf_helper.o")
    cmd_cpp = [
        cc,
        "-m32",
        "-O2",
        "-std=c++17",
        "-fpermissive",
        "-I" + HT_CORE_DIR,
        "-I" + PSFLIB_DIR,
        "-I" + os.path.join(SCRIPT_DIR, "include"),
        "-c", helper_src,
        "-o", helper_obj,
    ]
    print("Compiling htssf_helper.cc...")
    result = subprocess.run(cmd_cpp, capture_output=True, text=True, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        print("FAILED: htssf_helper.cc", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return 1

    S68000_OBJ = os.path.join(HT_CORE_DIR, "Starscream", "s68000.obj")

    # Link everything (library must come after object files that use it)
    cmd_link = [
        cc,
        "-m32",
        "-O2",
        "-o", OUTPUT_EXE,
        helper_obj,
    ] + c_objects + [
        S68000_OBJ,
        zlib_lib + "/libz.a",
    ]

    print(f"Linking {OUTPUT_EXE}...")

    try:
        result = subprocess.run(cmd_link, capture_output=True, text=True, cwd=SCRIPT_DIR)
        if result.returncode != 0:
            print("LINK FAILED", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return 1

        print(f"Built: {OUTPUT_EXE}")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
