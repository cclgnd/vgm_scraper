# SIMPLEPLAYER

SIMPLEPLAYER is a small Python drag-and-drop player for native console and arcade music formats. It uses real-time emulated audio engines: no WAV pre-rendering, no intermediate files, and no fake playback pipeline.

## Current Engines

The primary backend is `libgme` / Game Music Emu. It is intentionally small, mature, and powerful for classic chip/log formats:

- `.ay` - ZX Spectrum / Amstrad CPC
- `.gbs` - Nintendo Game Boy
- `.gym` - Sega Genesis / Mega Drive logs
- `.hes` - PC Engine / TurboGrafx-16
- `.kss` - MSX and other Z80 systems
- `.nsf`, `.nsfe` - NES / Famicom
- `.sap` - Atari POKEY
- `.spc` - SNES / Super Famicom
- `.vgm`, `.vgz` - multi-chip console and arcade logs

The first added console core is `PSF1 / Audio Overload`, isolated in `engines/aopsf/aopsf_helper.exe` so PlayStation emulation crashes cannot take down the UI:

- `.psf`, `.minipsf` - Sony PlayStation sequenced music, including companion library resolution for miniPSF files

The second added console core is `PSF2 / Audio Overload`, isolated in `engines/aopsf2/aopsf2_helper.exe` so PlayStation 2 emulation crashes cannot take down the UI:

- `.psf2`, `.minipsf2` - Sony PlayStation 2 sequenced music, including companion library resolution for miniPSF2 files

The third added console core is `SSF/DSF / Highly Theoretical`, isolated in `engines/aoht/aoht_helper.exe` so Saturn/Dreamcast emulation crashes cannot take down the UI:

- `.ssf`, `.minissf` - Sega Saturn sequenced music
- `.dsf`, `.minidsf` - Sega Dreamcast sequenced music

The fourth added console core is `GSF / playgsf (VBA-derived)`, isolated in `engines/aogsf/aogsf_helper.exe` so Game Boy Advance emulation crashes cannot take down the UI:

- `.gsf`, `.minigsf` - Nintendo Game Boy Advance sequenced music, including companion `.gsflib` library resolution for miniGSF files

The fifth added console core is `USF / lazyusf2 (Mupen64Plus-derived)`, isolated in `engines/aousf/aousf_helper.exe` so Nintendo 64 emulation crashes cannot take down the UI:

- `.usf`, `.miniusf` - Nintendo 64 sequenced music, including companion `_lib` library resolution for miniUSF files

`vgmstream` was investigated too, but it primarily decodes streamed/prerecorded game audio. That is useful for a broader game-audio player, but it is not the right default for the strict “emulated audio engines only” requirement.

## Backend Expansion

The app now has a backend registry so additional emulators can be plugged in safely without touching the working `libgme` adapter. Registered planned slots include USF, GSF, 2SF, SSF/DSF, QSF, and Hoot/MAME-style arcade playback.

See `docs/BACKEND_ROADMAP.md` for the rules and dependency notes.

## Development Fixtures

Real music fixtures live in `chiptunes/`, with 10 files for each currently playable `libgme` type. Use them for smoke testing real-time emulated decoding:

```powershell
python -m unittest tests.test_chiptune_fixtures
```

The fixture manifest is `chiptunes/MANIFEST.json`. All fixtures are tested with:

```powershell
python -m unittest tests.test_chiptune_fixtures
python -m unittest tests.test_future_backend_fixtures
```

## KSS Playback Note

KSS files do not reliably store a real track count or playlist. `libgme` exposes possible selectors across `0-255`, and many selectors can be silence or sound effects. For `.kss` files, SIMPLEPLAYER scans the selectors at open time and builds a playable list from selectors that render audible PCM, preserving selector `0` when it is already audible.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .
```

This repository includes the official MSYS2 UCRT64 `libgme.dll` runtime and the needed MinGW runtime DLLs in `engines/`. The PSF1 helper is built from the staged Audacious/Audio Overload source with the local 32-bit w64devkit toolchain:

```powershell
python native\aopsf\build_aopsf.py
```

The SSF/DSF helper is built from the Highly Theoretical source with the same 32-bit toolchain:

```powershell
python native\htssf\build_aoht.py
```

The GSF helper is built from the playgsf (VBA-derived) source with 32-bit w64devkit and zlib:

```powershell
python native\aogsf\build_aogsf.py
```

The USF helper is built from the lazyusf2 (Mupen64Plus-derived) source with 64-bit w64devkit and zlib:

```powershell
python native\aousf\build_aousf.py
```

If you want to replace the engine manually, place `gme.dll` or `libgme.dll` in one of these locations:

- `D:\SIMPLEPLAYER\engines\gme.dll`
- `D:\SIMPLEPLAYER\gme.dll`
- any folder on `PATH`
- set `SIMPLEPLAYER_GME_DLL` to the full DLL path

Then run:

```powershell
.\.venv\Scripts\simpleplayer
```

Or from the project checkout:

```powershell
python run_simpleplayer.py
```

Open a file directly:

```powershell
python run_simpleplayer.py "D:\SIMPLEPLAYER\chiptunes\Nintendo NES\01_10-yard fight.nsf"
```

## Windows Explorer Integration

Register Explorer `Open with` support for the currently playable formats:

```bat
scripts\register_file_associations.bat
```

Remove it later with:

```bat
scripts\register_file_associations.bat uninstall
```

SIMPLEPLAYER runs as a single instance. If one player window is already open, opening another supported file from Explorer sends that file to the existing window and replaces the current playback.

## Bundled Engine Provenance

The Windows DLLs were downloaded from the official MSYS2 mirror, not from generic DLL sites.

- `libgme.dll`: `mingw-w64-ucrt-x86_64-libgme-0.6.4-2-any.pkg.tar.zst`, SHA256 `895013da34b309380b8c85d7de7c439acd25f1e31a370bef1aba92fec4ab07c2`
- `libgcc_s_seh-1.dll`, `libstdc++-6.dll`: `mingw-w64-ucrt-x86_64-gcc-libs-16.1.0-5-any.pkg.tar.zst`, SHA256 `4dab54c95756da3e18ca375ae4c7fdeb709fc04bf209eb131c120e27704fb5b3`
- `zlib1.dll`: `mingw-w64-ucrt-x86_64-zlib-1.3.2-2-any.pkg.tar.zst`, SHA256 `841401182976d2f9e17e5c0ebaac51f2a8014140ea53d67625e91c8fb3c85ea0`
- `libwinpthread-1.dll`: `mingw-w64-ucrt-x86_64-libwinpthread-14.0.0.r37.g2bfe61fba-1-any.pkg.tar.zst`, SHA256 `7c5e33a71f47095f6d129318f6833b4bbc27df376f4479577f4685350ec3a904`

License files are stored under `engines/licenses/`.

## Why This Shape

The app is split into a Python UI, a real-time audio stream, and native emulator backends. That keeps the Python code simple while leaving the hard accuracy work to battle-tested audio emulators.

## Remaining Work

See `docs/REMAINING_WORK.md` for the current backend implementation backlog, future fixture status, test requirements, and restore points.

Research anchors:

- Game Music Emu supports AY, GBS, GYM, HES, KSS, NSF/NSFE, SAP, SPC, VGM/VGZ via a stable C API.
- `gme_play()` generates stereo 16-bit PCM on demand, which fits a real-time audio callback.
- `vgmstream` supports hundreds of streamed game-audio formats, but those are decoded streams rather than chip-emulated music.
