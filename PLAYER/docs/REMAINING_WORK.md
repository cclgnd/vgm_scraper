# Remaining Work

This note captures what is left after the current checkpoint.

## Current Working Playback

The active playback backends are `libgme`, an isolated Audio Overload PSF1 helper, an isolated Audio Overload PSF2 helper, an isolated Highly Theoretical SSF/DSF helper, and an isolated playgsf (VBA-derived) GSF helper.

Ready and tested formats:

- `.ay`
- `.gbs`
- `.gym`
- `.hes`
- `.kss`
- `.nsf`
- `.nsfe`
- `.sap`
- `.spc`
- `.vgm`
- `.vgz`
- `.psf`
- `.minipsf`
- `.psf2`
- `.minipsf2`
- `.ssf`
- `.minissf`
- `.dsf`
- `.minidsf`
- `.gsf`
- `.minigsf`
- `.usf`
- `.miniusf`

KSS-specific selector scanning is implemented and tested. This hides silent selectors and starts playback from the first audible selector.

PSF1 playback is implemented through `simpleplayer/engines/psf.py` and `engines/aopsf/aopsf_helper.exe`. The helper streams 44.1 kHz stereo PCM in real time; the Python adapter resamples to the app's 48 kHz output path. It resolves miniPSF companion libraries from the same folder as the opened file.

PSF2 playback is implemented through `simpleplayer/engines/psf2.py` and `engines/aopsf2/aopsf2_helper.exe`. The helper streams 44.1 kHz stereo PCM in real time; the Python adapter resamples to the app's 48 kHz output path. It resolves miniPSF2 companion libraries from the same folder as the opened file.

SSF/DSF playback is implemented through `simpleplayer/engines/ssf_dsf.py` and `engines/aoht/aoht_helper.exe`. The helper streams 44.1 kHz stereo PCM in real time; the Python adapter resamples to the app's 48 kHz output path. It resolves miniSSF/miniDSF companion libraries from the same folder as the opened file.

GSF playback is implemented through `simpleplayer/engines/gsf.py` and `engines/aogsf/aogsf_helper.exe`. The helper streams 44.1 kHz stereo PCM in real time; the Python adapter resamples to the app's 48 kHz output path. It resolves miniGSF companion `.gsflib` libraries from the same folder as the opened file. Build with `python native/aogsf/build_aogsf.py` (requires 32-bit w64devkit and zlib).

USF playback is implemented through `simpleplayer/engines/usf.py` and `engines/aousf/aousf_helper.exe`. The helper streams 44.1 kHz stereo PCM in real time; the Python adapter resamples to the app's 48 kHz output path. It resolves miniUSF companion `_lib` files from the same folder as the opened file. Build with `python native/aousf/build_aousf.py` (requires 64-bit w64devkit and zlib). Uses cached interpreter mode for Windows portability.

## Fixture State

Ready-format fixtures:

- Folder: `chiptunes/`
- Manifest: `chiptunes/MANIFEST.json`
- Test: `python -m unittest tests.test_chiptune_fixtures`
- Status: complete, 10 files per currently playable type.

Future-format fixtures:

- Folder: `chiptunes/` (merged with ready fixtures)
- Manifest: `chiptunes/MANIFEST.json`
- Test scaffold: `python -m unittest tests.test_future_backend_fixtures`
- Status: partially collected.

Collected future fixture counts at last pass:

- `.psf`: 10
- `.minipsf`: 10
- `.psf2`: 10
- `.minipsf2`: 10
- `.gsf`: 10
- `.minigsf`: 10
- `.2sf`: 8
- `.mini2sf`: 10
- `.usf`: 2
- `.miniusf`: 10
- `.ssf`: 10
- `.minissf`: 10
- `.dsf`: 10
- `.minidsf`: 10
- `.miniqsf`: 10

Still incomplete or missing:

- `.2sf`: needs 2 more
- `.usf`: needs 8 more
- `.usfmini`: none found yet
- `.qsf`: none found yet

Do not spend more time on fixture collection unless explicitly requested; the user asked to stop non-code work.

## Backend Implementation Priority

User preference:

1. 32-bit consoles.
2. 64-bit consoles.
3. Arcade/MAME/similar.

Recommended implementation order:

1. ~~`GSF`~~ — complete
2. ~~`USF`~~ — complete
3. `2SF`
4. ~~`SSF/DSF`~~ — complete
5. `QSF`
6. `Hoot/MAME`
7. `ASAP` can be inserted when Atari fidelity expansion is wanted, but it is not in the console priority path.

## Required Rule For Every New Engine

Every new engine must include a real playback test before being considered complete.

Minimum acceptance test for each backend:

1. Load at least one real fixture file.
2. Resolve companion library files if the format uses mini/lib pairs.
3. Start playback through the backend.
4. Render PCM frames in real time.
5. Assert the PCM buffer is the expected stereo frame length.
6. Assert the render is not silent unless the fixture is intentionally silent.

Future tests should extend `tests/test_future_backend_fixtures.py`.

## Tooling State

Local compiler tooling is now staged:

- 32-bit C/C++: `tooling/w64devkit-x86/w64devkit/bin/g++.exe`
- 64-bit C: `tooling/py_gcc/py_win_x86_64_gcc/.../gcc.exe`
- 32-bit zlib: `third_party/msys2/zlib-i686/mingw32`
- 64-bit zlib: `third_party/msys2/zlib/ucrt64`

Most fidelity-oriented backends need either:

- a native DLL shim built from source, or
- a helper process that streams PCM in real time.

`git` is still not installed, so source updates still rely on downloaded archives unless that changes.

## PSF State

Staged source:

- `third_party/src/highly_experimental-main.zip`
- `third_party/src/psflib-main.zip`
- `third_party/src/audacious-plugins-4.5.tar.bz2`

Docs:

- `docs/PSF_BACKEND_PLAN.md`

Status:

- PSF1 `.psf` and `.minipsf` are active through the Audio Overload/Audacious core.
- `python native/aopsf/build_aopsf.py` builds `engines/aopsf/aopsf_helper.exe`.
- `python -m unittest tests.test_future_backend_fixtures` verifies real PSF1 fixture playback.
- PSF1 GUI crash fixed: added `voice_names()` and `mute_voice()` stubs to `PsfEngine` so the app no longer crashes when opening PSF files.
- PSF2 `.psf2` and `.minipsf2` are active through the Audio Overload/Audacious PSF2 core.
- `python native/aopsf2/build_aopsf2.py` builds `engines/aopsf2/aopsf2_helper.exe`.
- `python -m unittest tests.test_future_backend_fixtures` verifies real PSF2 fixture playback.
- Both PSF1 and PSF2 use isolated helper processes; neither can crash the Python UI.

Important risk:

- The earlier Highly Experimental/psflib shim attempt was not activated because the source path required BIOS initialization and crashed in helper smoke tests.
- Keep PSF-family cores helper-isolated unless they are proven safe in-process.

## GSF State

Staged source:

- `third_party/src/gsf-playgsf/` — playgsf (VBA-derived GSF player)

Build:

- `python native/aogsf/build_aogsf.py` builds `engines/aogsf/aogsf_helper.exe`
- Requires 32-bit w64devkit (`tooling/w64devkit-x86/`) and 32-bit zlib (`third_party/msys2/zlib-i686/`)
- Linker script `native/aogsf/flags.ld` resolves VBA CPU flag symbol aliases (`N_FLAG`, `Z_FLAG`, `C_FLAG`, `V_FLAG`) via `--defsym`

Status:

- `.gsf` and `.minigsf` are active through the playgsf/VBA-derived core.
- Helper streams 44.1 kHz stereo PCM over stdout; Python adapter (`simpleplayer/engines/gsf.py`) resamples to 48 kHz.
- Fixture-tested with 10 `.gsf` and 10 `.minigsf` files in `chiptunes/Nintendo Game Boy Advance/`.
- Uses isolated helper process; cannot crash the Python UI.

## USF State

Staged source:

- `third_party/src/lazyusf2/lazyusf2-master/` — lazyusf2 (Mupen64Plus-derived USF player)
- `third_party/src/psflib/psflib-main/` — psflib (PSF/USF file parser)

Build:

- `python native/aousf/build_aousf.py` builds `engines/aousf/aousf_helper.exe`
- Requires 64-bit w64devkit (`tooling/py_gcc/py_win_x86_64_gcc/data_pack/w64devkit/`) and 64-bit zlib (`third_party/msys2/zlib/ucrt64/`)
- Uses cached interpreter mode (no dynarec) for Windows portability; dynarec requires POSIX `mmap` with `PROT_EXEC`

Status:

- `.usf` and `.miniusf` are active through the lazyusf2/Mupen64Plus-derived core.
- Helper streams 44.1 kHz stereo PCM over stdout; Python adapter (`simpleplayer/engines/usf.py`) resamples to 48 kHz.
- Fixture-tested with USF files in `chiptunes/Nintendo 64/`.
- Uses isolated helper process; cannot crash the Python UI.
- Note: cached interpreter is slower than dynarec; performance is acceptable for most USF files on modern hardware.

## SSF/DSF State

Staged source:

- `third_party/src/highly_experimental-main.zip` — Highly Theoretical (Saturn/Dreamcast)

Build:

- `python native/htssf/build_aoht.py` builds `engines/aoht/aoht_helper.exe`

Status:

- `.ssf`, `.minissf`, `.dsf`, `.minidsf` are active through the Highly Theoretical-derived core.
- Helper streams 44.1 kHz stereo PCM over stdout; Python adapter (`simpleplayer/engines/ssf_dsf.py`) resamples to 48 kHz.
- Fixture-tested with 10 files each in `chiptunes/Sega Saturn/` and `chiptunes/Sega Dreamcast/`.
- Uses isolated helper process; cannot crash the Python UI.

## ASAP State

Docs:

- `docs/ASAP_BACKEND_PLAN.md`

Status:

- Selected Atari fidelity target.
- Python wrapper `asap2wav.py` was staged, but the generated `asap` Python module/runtime was not obtained.
- Backend remains inactive.

## Windows Integration State

Implemented:

- Explorer file association script: `scripts/register_file_associations.bat`
- Single-instance handoff: `simpleplayer/single_instance.py`
- `.psf` and `.minipsf` are included in the current-user Explorer associations.
- `.psf2`, `.minipsf2`, `.ssf`, `.minissf`, `.dsf`, `.minidsf`, `.gsf`, and `.minigsf` should be added to the Explorer associations script when ready.

Behavior:

- Opening a supported file from Explorer sends it to the already-running player if one exists.
- Otherwise, a new player starts.

## Restore Points

Useful backups:

- `D:\SIMPLEPLAYER_BACKUP_20260518-194401`
- `D:\SIMPLEPLAYER_BACKUP_KSS_20260518-203956`
- `D:\SIMPLEPLAYER_BACKUP_PSF1_CHECK_20260518-221402`
- `D:\SIMPLEPLAYER_BACKUP_PSF1_FIX_20260518-222433`
- `D:\SIMPLEPLAYER_BACKUP_MULTI_20260519-151755` — Multi-backend milestone (7 backends: libgme, PSF1, PSF2, SSF/DSF, GSF, USF)

Use the KSS backup if the selector-scanning logic needs to be reverted.
Use the PSF1 fix backup if the GUI stub methods need to be reverted.
