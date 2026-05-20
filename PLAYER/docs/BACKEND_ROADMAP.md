# Backend Roadmap

The implementation now uses a backend registry. New decoders should be added as isolated adapters, not by modifying the existing `libgme` code.

## Installed

### Game Music Emu / libgme

- Formats: `.ay`, `.gbs`, `.gym`, `.hes`, `.kss`, `.nsf`, `.nsfe`, `.sap`, `.spc`, `.vgm`, `.vgz`
- Runtime: local DLLs in `engines/`
- Integration style: in-process `ctypes` C API
- Status: working

### PSF1 / Audio Overload

- Formats: `.psf`, `.minipsf`
- Runtime: isolated helper process in `engines/aopsf/aopsf_helper.exe`
- Integration style: helper streams real-time stereo PCM over stdout; Python resamples 44.1 kHz to the app's 48 kHz output path
- Status: working and fixture-tested

### PSF2 / Audio Overload

- Formats: `.psf2`, `.minipsf2`
- Runtime: isolated helper process in `engines/aopsf2/aopsf2_helper.exe`
- Integration style: helper streams real-time stereo PCM over stdout; Python resamples 44.1 kHz to the app's 48 kHz output path
- Status: working and fixture-tested

### SSF/DSF / Highly Theoretical

- Formats: `.ssf`, `.minissf`, `.dsf`, `.minidsf`
- Runtime: isolated helper process in `engines/aoht/aoht_helper.exe`
- Integration style: helper streams real-time stereo PCM over stdout; Python resamples 44.1 kHz to the app's 48 kHz output path
- Status: working and fixture-tested

### GSF / playgsf (VBA-derived)

- Formats: `.gsf`, `.minigsf`
- Runtime: isolated helper process in `engines/aogsf/aogsf_helper.exe`
- Integration style: helper streams real-time stereo PCM over stdout; Python resamples 44.1 kHz to the app's 48 kHz output path
- Build: `python native/aogsf/build_aogsf.py` (requires 32-bit w64devkit and zlib)
- Notes: linker script `native/aogsf/flags.ld` resolves VBA CPU flag symbol aliases (`N_FLAG`, `Z_FLAG`, `C_FLAG`, `V_FLAG`) via `--defsym`
- Status: working and fixture-tested

### USF / lazyusf2 (Mupen64Plus-derived)

- Formats: `.usf`, `.miniusf`
- Runtime: isolated helper process in `engines/aousf/aousf_helper.exe`
- Integration style: helper streams real-time stereo PCM over stdout; Python resamples 44.1 kHz to the app's 48 kHz output path
- Build: `python native/aousf/build_aousf.py` (requires 64-bit w64devkit and zlib)
- Notes: uses cached interpreter mode (no dynarec) for Windows portability; psflib handles `_lib` resolution
- Status: working and fixture-tested

## Planned Backend Slots

These slots are already registered so the UI can route files safely and produce a clear message instead of touching the wrong engine.

| Backend | Formats | Safe integration target |
| --- | --- | --- |
| 2SF | `.2sf`, `.mini2sf` | vio2sf/DeSmuME-derived adapter |
| QSF | `.qsf`, `.miniqsf` | aoqsf/QSound-oriented adapter |
| Hoot/MAME arcade | `.hoot`, `.m1`, `.xml` | External heavy backend with ROM/metadata resolution |

## Fidelity-First Priority

The goal is not just to make files play. The goal is to pick cores that are known for accuracy, then adapt them carefully.

1. 32-bit consoles first: `GSF` is complete. PSF1, PSF2, and SSF/DSF are already active.
2. 64-bit consoles next: `USF` is complete.
3. Arcade and similar after that: `QSF`, then Hoot/MAME-style systems. Fidelity can be excellent, but ROM/metadata management and real-time control make these heavier backends.
4. Handheld/adjacent formats such as `2SF/NCSF` can be pulled forward when the dependency-loader pattern is stable.
5. `ASAP` remains the selected Atari fidelity target because it is a mature portable library that emulates 6502 + POKEY and supports more Atari formats than `libgme`.

## Rules For Adding A Backend

1. Create a new module under `simpleplayer/engines/`.
2. Implement the same methods as `GmeEngine`: `open`, `tracks`, `start_track`, `render`, `seek_ms`, `tell_ms`, and `close`.
3. Load native libraries lazily inside the backend class.
4. Do not start audio, create UI widgets, or mutate global app state inside the backend.
5. Register the backend in `default_backend_specs()` only after a minimal load/render smoke test passes.
6. Keep mini-format library resolution inside that backend. Examples: `.minipsf` needs PSF libraries; `.minigsf` needs `.gsflib`.

## Dependency Research Notes

The foobar2000 component repository is useful for mapping mature emulator projects and source trees, but the component binaries themselves are not directly usable here because they are foobar plugins, not standalone DLL APIs.

Useful references:

- Game-music components list: https://www.foobar2000.org/components/tag/game%2Bmusic/system/x86
- PSF Decoder: https://www.foobar2000.org/components/view/foo_psf/release/2.3.1
- Highly Experimental source archive: `third_party/src/highly_experimental-main.zip`
- psflib source archive: `third_party/src/psflib-main.zip`
- USF Decoder: https://www.foobar2000.org/components/view/foo_input_usf
- GSF Decoder: https://www.foobar2000.org/components/view/foo_input_gsf
- SSF/DSF Decoder: https://www.foobar2000.org/components/view/foo_input_ht
- ASAP: https://asap.sourceforge.net/
- ASAP SAP format notes: https://asap.sourceforge.net/sap-format.html
- MAME plugin documentation: https://docs.mamedev.org/plugins/index.html

## Why Not Download Every Foobar Component?

Those components are useful proof that the emulation cores exist, but dropping `.fb2k-component` files into this project would not give Python a clean real-time `render(frames)` function. For SIMPLEPLAYER, we need either:

- a native library with a C-compatible API, or
- a small helper process that streams PCM in real time over stdout/shared memory without rendering to an intermediate file.

Until a backend has one of those two integration paths, it stays registered as `planned` rather than half-installed.
