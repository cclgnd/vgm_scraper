# PSF/PSF2 Backend Plan

## Current Status

The fidelity-oriented source cores have been retrieved:

- `third_party/src/highly_experimental/highly_experimental-main`
- `third_party/src/psflib/psflib-main`
- `third_party/src/audacious-plugins/audacious-plugins-4.5/src/psf`

PSF1 is active through `simpleplayer/engines/psf.py` and `engines/aopsf/aopsf_helper.exe`.
PSF2 is active through `simpleplayer/engines/psf2.py` and `engines/aopsf2/aopsf2_helper.exe`.

## Why This Core

The active PSF1 implementation uses the Audio Overload SDK copy inside Audacious because it builds cleanly as a standalone helper and does not require the BIOS initialization path that blocked the earlier Highly Experimental shim attempt.

`highly_experimental` remains historically important for PSF/PSF2 playback, but the local source snapshot was not activated. It exposes a real-time-friendly API:

- `psx_init()`
- `psx_get_state_size(version)`
- `psx_clear_state(state, version)`
- `psx_upload_psxexe(state, program, size)`
- `psx_execute(state, cycles, sound_buf, sound_samples, event_mask)`

`psflib` provides the loader API:

- `psf_load(...)`

That loader handles nested `_lib`, `_lib2`, etc. chains for `.minipsf`/`.minipsf2`.

## Active Shim

The current shim is a helper process instead of an in-process DLL:

```text
engines/aopsf/aopsf_helper.exe <file.psf|minipsf>
```

It streams 44.1 kHz stereo int16 PCM to stdout in real time. The Python adapter reads the stream and resamples to the app's 48 kHz output path.

## Build Requirements

The helper builds with the staged 32-bit w64devkit toolchain:

```powershell
python native\aopsf\build_aopsf.py
```

The helper is intentionally 32-bit and process-isolated. That is safer for older emulator code than loading it directly into the 64-bit Python UI.

## Safety Rules

- Keep `libgme` untouched.
- Keep miniPSF library file resolution inside the PSF backend.
- Keep miniPSF2 library file resolution inside the PSF2 backend.
- Do not pre-render WAV/FLAC/MP3; the shim must render frames on demand.

## Open Risk

The earlier Highly Experimental/psflib shim was not activated because the source path required BIOS initialization and failed smoke tests. Keep using helper isolation for PSF-family cores unless a specific core is proven stable in-process.

PSF2 uses the IOP (R3000A) core with SPU2 emulation, which is more complex than PSF1's PSX CPU + SPU1 path. If crashes occur, they will be isolated to the helper process.
