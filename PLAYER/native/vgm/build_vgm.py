#!/usr/bin/env python3
"""Build script for VGM helper (vgm_helper.exe) using libvgm."""

import os
import sys
import subprocess
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[1]
LIBVGM_SRC = SCRIPT_DIR / "libvgm-master"
BUILD_DIR = SCRIPT_DIR / "build"
OUTPUT_EXE = SCRIPT_DIR / "build" / "vgm_helper.exe"

ZLIB_64 = PROJECT_ROOT / "third_party" / "msys2" / "zlib" / "ucrt64"
PY_GCC_PKG = PROJECT_ROOT / "tooling" / "py_gcc" / "py_win_x86_64_gcc" / "data_pack"
CMAKE_BIN = PROJECT_ROOT / "tooling" / "cmake-3.28.3-windows-x86_64" / "bin" / "cmake.exe"


def find_64bit_gcc():
    sys.path.insert(0, str(PY_GCC_PKG.parent.parent))
    from py_win_x86_64_gcc import get_tool
    gcc = get_tool("gcc")
    gpp = get_tool("g++")
    if gcc and gpp:
        return Path(gcc), Path(gpp)
    return None, None


def build_libvgm_with_cmake(gcc_path: Path, gpp_path: Path) -> dict:
    cmake_build = BUILD_DIR / "libvgm"
    cmake_build.mkdir(parents=True, exist_ok=True)

    cmake_exe = str(CMAKE_BIN)
    if not Path(cmake_exe).exists():
        print(f"ERROR: CMake not found at {cmake_exe}")
        sys.exit(1)

    env = os.environ.copy()
    env["CC"] = str(gcc_path)
    env["CXX"] = str(gpp_path)
    w64devkit_bin = str(gcc_path.parent)
    env["PATH"] = w64devkit_bin + os.pathsep + env.get("PATH", "")

    cmake_cmd = [
        cmake_exe,
        "-S", str(LIBVGM_SRC),
        "-B", str(cmake_build),
        "-G", "Ninja",
        "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_C_COMPILER={str(gcc_path).replace(chr(92), chr(47))}",
        f"-DCMAKE_CXX_COMPILER={str(gpp_path).replace(chr(92), chr(47))}",
        "-DLINK_STATIC_LIBS=ON",
        "-DBUILD_PLAYER=OFF",
        "-DBUILD_VGM2WAV=OFF",
        "-DBUILD_TESTS=OFF",
        "-DLIBRARY_TYPE=STATIC",
        "-DSNDEMU__ALL=ON",
        f"-DZLIB_ROOT={str(ZLIB_64).replace(chr(92), chr(47))}",
        "-DUTIL_CHARCNV_ICONV=OFF",
        "-DUTIL_CHARCNV_WINAPI=ON",
        "-DUSE_SANITIZERS=OFF",
        f"-DCMAKE_MAKE_PROGRAM={str(PY_GCC_PKG / 'w64devkit' / 'bin' / 'ninja.exe').replace(chr(92), chr(47))}",
    ]

    print("Configuring libvgm with CMake...")
    result = subprocess.run(cmake_cmd, capture_output=True, text=True, cwd=cmake_build, env=env)
    if result.returncode != 0:
        print("CMAKE CONFIG FAILED", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    print("Building libvgm static libraries...")
    make_cmd = [cmake_exe, "--build", str(cmake_build), "--parallel"]
    result = subprocess.run(make_cmd, capture_output=True, text=True, cwd=cmake_build, env=env)
    if result.returncode != 0:
        print("BUILD FAILED", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    bin_dir = cmake_build / "bin"
    libs = {}
    for lib_name in ["libvgm-player.a", "libvgm-emu.a", "libvgm-utils.a"]:
        lib_path = bin_dir / lib_name
        if lib_path.exists():
            libs[lib_name] = str(lib_path)
            print(f"  Found {lib_name}")
        else:
            print(f"  WARNING: {lib_name} not found in {bin_dir}")

    return libs


def build_helper(libs: dict, gpp_path: Path):
    OUTPUT_EXE.parent.mkdir(parents=True, exist_ok=True)

    include_dir = str(LIBVGM_SRC)
    zlib_include = str(ZLIB_64 / "include")

    sources = [str(SCRIPT_DIR / "vgm_helper.cpp")]

    lib_files = list(libs.values())
    zlib_lib = str(ZLIB_64 / "lib" / "libz.a")

    cmd = [
        str(gpp_path),
        "-O2",
        "-std=c++11",
        "-D_WIN32_WINNT=0x0500",
        "-D_CRT_SECURE_NO_WARNINGS",
        "-I", include_dir,
        "-I", zlib_include,
        *sources,
        *lib_files,
        zlib_lib,
        "-lws2_32",
        "-lwsock32",
        "-lm",
        "-static",
        "-static-libgcc",
        "-static-libstdc++",
        "-o", str(OUTPUT_EXE),
    ]

    env = os.environ.copy()
    env["PATH"] = str(gpp_path.parent) + os.pathsep + env.get("PATH", "")

    print("Linking vgm_helper.exe...")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(BUILD_DIR), env=env)
    if result.returncode != 0:
        print("LINK FAILED", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return 1

    size = OUTPUT_EXE.stat().st_size
    print(f"Built: {OUTPUT_EXE} ({size / 1024 / 1024:.1f} MB)")
    return 0


def main():
    gcc, gpp = find_64bit_gcc()
    if not gcc or not gpp:
        print("ERROR: 64-bit w64devkit not found", file=sys.stderr)
        return 1

    print(f"Using gcc: {gcc}")
    print(f"Using g++: {gpp}")

    libs = build_libvgm_with_cmake(gcc, gpp)
    if not libs:
        print("ERROR: No libraries built", file=sys.stderr)
        return 1

    return build_helper(libs, gpp)


if __name__ == "__main__":
    sys.exit(main())
