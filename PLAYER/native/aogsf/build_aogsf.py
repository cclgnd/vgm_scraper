#!/usr/bin/env python3
"""Build script for GSF helper (aogsf_helper.exe)."""

import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
GSF_SRC_DIR = os.path.join(PROJECT_ROOT, "third_party", "src", "gsf-playgsf")
VBA_DIR = os.path.join(GSF_SRC_DIR, "VBA")
LIBRESAMPLE_DIR = os.path.join(GSF_SRC_DIR, "libresample", "src")
BUILD_DIR = os.path.join(SCRIPT_DIR, "build")
OUTPUT_EXE = os.path.join(BUILD_DIR, "aogsf_helper.exe")

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

    zlib_include = os.path.join(PROJECT_ROOT, "third_party", "msys2", "zlib-i686", "mingw32", "include")
    zlib_lib = os.path.join(PROJECT_ROOT, "third_party", "msys2", "zlib-i686", "mingw32", "lib")

    if not os.path.isfile(os.path.join(zlib_include, "zlib.h")):
        print("ERROR: zlib.h not found", file=sys.stderr)
        return 1

    sources = [
        os.path.join(SCRIPT_DIR, "aogsf_helper.cc"),
        os.path.join(VBA_DIR, "Globals.cpp"),
        os.path.join(GSF_SRC_DIR, "gsf.cpp"),
        os.path.join(VBA_DIR, "GBA.cpp"),
        os.path.join(VBA_DIR, "Sound.cpp"),
        os.path.join(VBA_DIR, "Util.cpp"),
        os.path.join(VBA_DIR, "bios.cpp"),
        os.path.join(VBA_DIR, "memgzio.c"),
        os.path.join(VBA_DIR, "snd_interp.cpp"),
        os.path.join(VBA_DIR, "unzip.cpp"),
        os.path.join(VBA_DIR, "psftag.c"),
        os.path.join(LIBRESAMPLE_DIR, "filterkit.c"),
        os.path.join(LIBRESAMPLE_DIR, "resample.c"),
        os.path.join(LIBRESAMPLE_DIR, "resamplesubs.c"),
    ]

    asm_sources = []

    objects = []
    for src in sources:
        obj = os.path.join(BUILD_DIR, os.path.basename(src).replace(".c", ".o").replace(".cpp", ".o"))
        is_c = src.endswith(".c")
        compiler = gcc if is_c else cc
        cmd = [
            compiler,
            "-m32",
            "-O2",
            "-std=c++17" if not is_c else "-std=c99",
            "-DLINUX",
            "-DWIN32",
            "-fpermissive",
            "-fvisibility=default",
            "-I" + GSF_SRC_DIR,
            "-I" + VBA_DIR,
            "-I" + os.path.join(GSF_SRC_DIR, "libresample", "include"),
            "-I" + zlib_include,
            "-c", src,
            "-o", obj,
        ]
        print(f"Compiling {os.path.basename(src)}...")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPT_DIR)
        if result.returncode != 0:
            print(f"FAILED: {os.path.basename(src)}", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return 1
        objects.append(obj)

    for src in asm_sources:
        obj = os.path.join(BUILD_DIR, os.path.basename(src).replace(".s", ".o"))
        cmd = [
            cc,
            "-m32",
            "-c", src,
            "-o", obj,
        ]
        print(f"Assembling {os.path.basename(src)}...")
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
        "-o", OUTPUT_EXE,
        "-Wl,--defsym,N_FLAG=_N_FLAG",
        "-Wl,--defsym,Z_FLAG=_Z_FLAG",
        "-Wl,--defsym,C_FLAG=_C_FLAG",
        "-Wl,--defsym,V_FLAG=_V_FLAG",
    ] + objects + [
        zlib_lib + "/libz.a",
    ]

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
