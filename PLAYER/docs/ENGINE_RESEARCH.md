# Engine Research

## Requirement

The player must use emulated audio engines with real-time decoding. That rules out a pipeline that converts dropped files to WAV/FLAC/MP3 first, and it also means a general streamed-audio decoder should not be treated as the main engine.

## Chosen First Engine: Game Music Emu

Game Music Emu (`libgme`) is the simplest strong first backend:

- It exposes a small C API that Python can call safely through `ctypes`.
- `gme_play()` renders signed 16-bit stereo PCM on demand, which maps directly to an audio-device callback.
- It supports important native console and arcade/chip formats: AY, GBS, GYM, HES, KSS, NSF/NSFE, SAP, SPC, VGM/VGZ.
- VGM/VGZ gives us a broad arcade/console chip-log path while NSF/SPC/GBS/etc. cover common system-specific rips.

Primary references:

- https://github.com/libgme/game-music-emu
- https://raw.githubusercontent.com/libgme/game-music-emu/master/gme/gme.h
- https://docs.libretro.com/library/game_music_emu/
- https://packages.msys2.org/package/mingw-w64-ucrt-x86_64-libgme

## Windows Runtime Source

The local `engines/libgme.dll` was taken from the official MSYS2 UCRT64 package:

- Package: `mingw-w64-ucrt-x86_64-libgme`
- Version: `0.6.4-2`
- SHA256: `895013da34b309380b8c85d7de7c439acd25f1e31a370bef1aba92fec4ab07c2`

Runtime dependency DLLs were also copied from official MSYS2 UCRT64 packages:

- `mingw-w64-ucrt-x86_64-gcc-libs` for `libgcc_s_seh-1.dll` and `libstdc++-6.dll`
- `mingw-w64-ucrt-x86_64-zlib` for `zlib1.dll`
- `mingw-w64-ucrt-x86_64-libwinpthread` for `libwinpthread-1.dll`

## Multi-Backend Architecture

The player now uses `BackendRegistry` to select exactly one backend for a dropped file. `libgme` stays isolated and installed; PSF/USF/GSF/2SF/SSF/DSF/QSF/Hoot/MAME are registered as planned slots until each has a trustworthy real-time adapter.

This prevents new emulator experiments from interfering with working `libgme` playback.

## Fidelity Policy

When adding a new backend, prefer the most faithful mature emulator core that can be integrated into our real-time pipeline. Convenience-only decoders or player plugins are secondary unless they expose a clean API or can be wrapped as a real-time helper process.

Examples:

- Prefer Highly Experimental/psflib-derived code for PSF/PSF2.
- Prefer mGBA-derived code for GSF.
- Prefer lazyusf2-derived code for USF.
- Prefer Highly Theoretical-derived code for SSF/DSF.
- Prefer ASAP for Atari-specific SAP/CMC/RMT fidelity expansion over relying only on broad `libgme` coverage.

## Investigated But Not Default: vgmstream

`vgmstream` is excellent for streamed game audio and supports hundreds of formats, but its purpose is decoding prerecorded game audio streams rather than emulating console/arcade sound hardware. It may become an optional non-strict mode later, but it should not be enabled in the strict emulated-engine path.

Primary references:

- https://github.com/vgmstream/vgmstream
- https://github.com/vgmstream/vgmstream/blob/master/doc/FORMATS.md

## Coverage Reality

No single engine plays every native game-music format ever made. The clean path is a backend chain:

- `libgme` now for classic console and VGM/VGZ chip logs.
- Add specialized emulated cores later for PSF/PSF2, USF, GSF, 2SF, QSF, SSF/DSF, and Hoot/MAME-derived arcade sets if strict coverage needs to expand.
- Keep streamed decoders behind an explicit opt-in because they violate the strict emulated-only goal.

## Current Runtime Shape

Dropped file -> `GmeEngine.open()` -> audio device callback -> `GmeEngine.render(frames)` -> `gme_play()` -> speaker.

There is no WAV pre-rendering step and no intermediate audio file.
