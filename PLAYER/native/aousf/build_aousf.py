#!/usr/bin/env python3
"""Build script for USF helper (aousf_helper.exe)."""

import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
USF_SRC_DIR = os.path.join(PROJECT_ROOT, "third_party", "src", "lazyusf2", "lazyusf2-master")
PSFLIB_DIR = os.path.join(PROJECT_ROOT, "third_party", "src", "psflib", "psflib-main")
BUILD_DIR = os.path.join(SCRIPT_DIR, "build")
OUTPUT_EXE = os.path.join(BUILD_DIR, "aousf_helper.exe")

def find_w64devkit_64():
    paths = [
        os.path.join(PROJECT_ROOT, "tooling", "py_gcc", "py_win_x86_64_gcc", "data_pack", "w64devkit", "bin"),
        r"C:\w64devkit\bin",
        r"C:\Program Files\w64devkit\bin",
        r"D:\w64devkit\bin",
    ]
    for p in paths:
        if os.path.isfile(os.path.join(p, "x86_64-w64-mingw32-gcc.exe")):
            return p
    return None

def main():
    w64devkit_bin = find_w64devkit_64()
    if not w64devkit_bin:
        print("ERROR: 64-bit w64devkit not found", file=sys.stderr)
        return 1

    os.environ["PATH"] = w64devkit_bin + os.pathsep + os.environ.get("PATH", "")

    cc = os.path.join(w64devkit_bin, "x86_64-w64-mingw32-gcc.exe")
    ar = os.path.join(w64devkit_bin, "x86_64-w64-mingw32-ar.exe")
    os.makedirs(BUILD_DIR, exist_ok=True)

    zlib_include = os.path.join(PROJECT_ROOT, "third_party", "msys2", "zlib", "ucrt64", "include")
    zlib_lib = os.path.join(PROJECT_ROOT, "third_party", "msys2", "zlib", "ucrt64", "lib")

    if not os.path.isfile(os.path.join(zlib_include, "zlib.h")):
        print("ERROR: zlib.h not found", file=sys.stderr)
        return 1

    # lazyusf2 source files (cached interpreter for Windows portability)
    usf_sources = [
        "ai/ai_controller.c",
        "api/callbacks.c",
        "debugger/dbg_decoder.c",
        "main/main.c",
        "main/rom.c",
        "main/savestates.c",
        "main/util.c",
        "memory/memory.c",
        "pi/cart_rom.c",
        "pi/pi_controller.c",
        "r4300/cached_interp.c",
        "r4300/cp0.c",
        "r4300/cp1.c",
        "r4300/empty_dynarec.c",
        "r4300/exception.c",
        "r4300/interupt.c",
        "r4300/mi_controller.c",
        "r4300/pure_interp.c",
        "r4300/r4300.c",
        "r4300/r4300_core.c",
        "r4300/recomp.c",
        "r4300/reset.c",
        "r4300/tlb.c",
        "rdp/rdp_core.c",
        "ri/rdram.c",
        "ri/rdram_detection_hack.c",
        "ri/ri_controller.c",
        "rsp/rsp_core.c",
        "rsp_hle/alist.c",
        "rsp_hle/alist_audio.c",
        "rsp_hle/alist_naudio.c",
        "rsp_hle/alist_nead.c",
        "rsp_hle/audio.c",
        "rsp_hle/cicx105.c",
        "rsp_hle/hle.c",
        "rsp_hle/hvqm.c",
        "rsp_hle/jpeg.c",
        "rsp_hle/memory.c",
        "rsp_hle/mp3.c",
        "rsp_hle/musyx.c",
        "rsp_hle/plugin.c",
        "rsp_hle/re2.c",
        "rsp_lle/rsp.c",
        "si/cic.c",
        "si/game_controller.c",
        "si/n64_cic_nus_6105.c",
        "si/pif.c",
        "si/si_controller.c",
        "usf/usf.c",
        "usf/barray.c",
        "usf/resampler.c",
        "vi/vi_controller.c",
    ]

    # Build psflib first
    psflib_sources = ["psflib.c"]
    psflib_objs = []
    for src in psflib_sources:
        obj = os.path.join(BUILD_DIR, "psflib_" + os.path.basename(src).replace(".c", ".o"))
        cmd = [
            cc,
            "-m64",
            "-O2",
            "-std=c99",
            "-I" + zlib_include,
            "-c", os.path.join(PSFLIB_DIR, src),
            "-o", obj,
        ]
        print(f"Compiling psflib {src}...")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPT_DIR)
        if result.returncode != 0:
            print(f"FAILED: {src}", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return 1
        psflib_objs.append(obj)

    psflib_a = os.path.join(BUILD_DIR, "libpsflib.a")
    cmd_ar = [ar, "rcs", psflib_a] + psflib_objs
    subprocess.run(cmd_ar, capture_output=True)
    print(f"Built {psflib_a}")

    # Build lazyusf2 objects
    usf_objs = []
    for src in usf_sources:
        obj = os.path.join(BUILD_DIR, "usf_" + src.replace("/", "_").replace(".c", ".o"))
        is_rsp_lle = src.startswith("rsp_lle/")
        cmd = [
            cc,
            "-m64",
            "-O2",
            "-std=c99",
            "-I" + USF_SRC_DIR,
            "-I" + PSFLIB_DIR,
            "-I" + zlib_include,
            "-c", os.path.join(USF_SRC_DIR, src),
            "-o", obj,
        ]
        print(f"Compiling {src}...")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPT_DIR)
        if result.returncode != 0:
            print(f"FAILED: {src}", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return 1
        usf_objs.append(obj)

    # Build helper source
    helper_src = os.path.join(SCRIPT_DIR, "aousf_helper.c")
    helper_obj = os.path.join(BUILD_DIR, "aousf_helper.o")
    cmd = [
        cc,
        "-m64",
        "-O2",
        "-std=c99",
        "-I" + USF_SRC_DIR,
        "-I" + PSFLIB_DIR,
        "-I" + zlib_include,
        "-c", helper_src,
        "-o", helper_obj,
    ]
    print("Compiling aousf_helper.c...")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        print("FAILED: aousf_helper.c", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return 1

    # Link
    cmd_link = [
        cc,
        "-m64",
        "-O2",
        "-o", OUTPUT_EXE,
        helper_obj,
    ] + usf_objs + [
        psflib_a,
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
