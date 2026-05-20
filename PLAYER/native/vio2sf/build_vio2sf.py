#!/usr/bin/env python3
"""Build script for 2SF helper (vio2sf_helper.exe)."""

import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
VIO2SF_SRC = os.path.join(PROJECT_ROOT, "native", "vio2sf-fork-splayer-mod")
BUILD_DIR = os.path.join(SCRIPT_DIR, "build")
OUTPUT_EXE = os.path.join(BUILD_DIR, "vio2sf_helper.exe")


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

    desmume_dir = os.path.join(VIO2SF_SRC, "src", "vio2sf", "desmume")
    zlib_dir = os.path.join(VIO2SF_SRC, "src", "plugins", "vio2sf", "zlib")
    xsfc_dir = os.path.join(VIO2SF_SRC, "src", "plugins", "xsfc")
    vio2sf_plugin_dir = os.path.join(VIO2SF_SRC, "src", "plugins", "vio2sf")
    custom_dir = os.path.join(VIO2SF_SRC, "src", "plugins", "custom")
    plugins_dir = os.path.join(VIO2SF_SRC, "src", "plugins")

    desmume_sources = [
        "armcpu.c",
        "arm_instructions.c",
        "barray.c",
        "bios.c",
        "cp15.c",
        "FIFO.c",
        "GPU.c",
        "isqrt.c",
        "matrix.c",
        "mc.c",
        "MMU.c",
        "NDSSystem.c",
        "resampler.c",
        "state.c",
        "SPU.cpp",
        "thumb_instructions.c",
    ]

    zlib_sources = [
        "adler32.c",
        "crc32.c",
        "infback.c",
        "inffast.c",
        "inflate.c",
        "inftrees.c",
        "uncompr.c",
        "zutil.c",
    ]

    # Note: we don't include xsfdrv.c because it has its own xsf_get_lib
    # that relies on a callback. We provide our own in the helper.
    sources = [os.path.join(SCRIPT_DIR, "vio2sf_helper.cc")]
    sources.append(os.path.join(vio2sf_plugin_dir, "drvimpl.c"))
    sources.append(os.path.join(custom_dir, "nostdc++.cpp"))

    for src in desmume_sources:
        sources.append(os.path.join(desmume_dir, src))

    for src in zlib_sources:
        sources.append(os.path.join(zlib_dir, src))

    include_dirs = [
        os.path.join(VIO2SF_SRC, "src", "vio2sf"),
        desmume_dir,
        zlib_dir,
        xsfc_dir,
        plugins_dir,
        vio2sf_plugin_dir,
    ]

    objects = []
    for src in sources:
        obj = os.path.join(
            BUILD_DIR,
            os.path.basename(src).replace(".c", ".o").replace(".cpp", ".o"),
        )
        is_c = src.endswith(".c")
        compiler = gcc if is_c else cc

        cmd = [compiler, "-m32", "-O2", "-std=c++17" if not is_c else "-std=c99", "-DWIN32", "-fpermissive", "-fvisibility=default", "-fomit-frame-pointer", "-fno-exceptions", "-fno-asynchronous-unwind-tables", "-fno-unwind-tables", "-ffunction-sections", "-fdata-sections"]

        if not is_c:
            cmd.append("-fno-rtti")

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
