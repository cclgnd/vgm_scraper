# Milestone: 2026-05-19 — Multi-Backend Console Expansion

## Summary
Expanded SIMPLEPLAYER from 3 backends (libgme, PSF1, PSF2) to 7 backends, adding SSF/DSF, GSF, and USF support. All new backends use the isolated helper process pattern to prevent emulator crashes from taking down the Python UI.

## Installed Backends (7)

| Backend | Formats | Helper | Core Source | Build Script |
| --- | --- | --- | --- | --- |
| libgme | `.ay .gbs .gym .hes .kss .nsf .nsfe .sap .spc .vgm .vgz` | in-process | Game Music Emu 0.6.4 | N/A (bundled DLL) |
| PSF1 | `.psf .minipsf` | `engines/aopsf/aopsf_helper.exe` | Audio Overload (Audacious) | `native/aopsf/build_aopsf.py` |
| PSF2 | `.psf2 .minipsf2` | `engines/aopsf2/aopsf2_helper.exe` | Audio Overload PSF2 (Audacious) | `native/aopsf2/build_aopsf2.py` |
| SSF/DSF | `.ssf .minissf .dsf .minidsf` | `engines/aoht/aoht_helper.exe` | Highly Theoretical | `native/htssf/build_aoht.py` |
| GSF | `.gsf .minigsf` | `engines/aogsf/aogsf_helper.exe` | playgsf (VBA-derived) | `native/aogsf/build_aogsf.py` |
| USF | `.usf .miniusf` | `engines/aousf/aousf_helper.exe` | lazyusf2 (Mupen64Plus-derived) | `native/aousf/build_aousf.py` |
| ASAP | Atari formats | — | ASAP 7.0.0 | — (selected, not built) |

## Planned Backends (2)

| Backend | Formats | Notes |
| --- | --- | --- |
| 2SF | `.2sf .mini2sf` | vio2sf/DeSmuME-derived |
| QSF | `.qsf .miniqsf` | aoqsf/QSound-oriented |

## Architecture Pattern

All console backends follow the same isolated helper pattern:
1. Native helper process streams real-time 44.1 kHz stereo PCM over stdout
2. Python adapter (`simpleplayer/engines/*.py`) reads PCM and resamples to 48 kHz
3. Helper processes are tracked globally and cleaned up on exit via `atexit`
4. Each helper runs in a new process group (`CREATE_NEW_PROCESS_GROUP`) to prevent orphaning
5. Mini-format library resolution (`.gsflib`, `_lib`, etc.) handled by psflib or equivalent

## Build Tooling

| Toolchain | Path | Used By |
| --- | --- | --- |
| 32-bit w64devkit | `tooling/w64devkit-x86/w64devkit/bin/` | PSF1, PSF2, SSF/DSF, GSF |
| 64-bit w64devkit | `tooling/py_gcc/py_win_x86_64_gcc/data_pack/w64devkit/bin/` | USF |
| 32-bit zlib | `third_party/msys2/zlib-i686/mingw32/` | PSF1, PSF2, SSF/DSF, GSF |
| 64-bit zlib | `third_party/msys2/zlib/ucrt64/` | USF |

## Key Decisions

- **USF uses cached interpreter** (no dynarec) for Windows portability — dynarec requires POSIX `mmap` with `PROT_EXEC`
- **GSF requires linker script** (`flags.ld`) to resolve VBA CPU flag symbol aliases via `--defsym`
- **All helpers are 32-bit except USF** which requires 64-bit due to N64 memory model
- **Merged `chiptunes/` and `future_chiptunes/`** into single directory with system-named folders

## Fixture Status

- 263 files across 26 extensions in `chiptunes/`
- Manifest: `chiptunes/MANIFEST.json`
- Tests: `tests/test_chiptune_fixtures.py`, `tests/test_future_backend_fixtures.py`

## Backup
- `D:\SIMPLEPLAYER_BACKUP_MULTI_20260519-151755` (100.6 MB, excludes tooling and .venv)
