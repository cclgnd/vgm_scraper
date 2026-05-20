# ASAP Backend Plan

ASAP is the fidelity-oriented Atari backend candidate.

## Why ASAP

ASAP emulates the Atari 8-bit POKEY sound chip and 6502 processor. It supports more Atari-native formats than `libgme`, including:

- `.sap`
- `.cmc`
- `.cm3`
- `.cmr`
- `.cms`
- `.dmc`
- `.dlt`
- `.fc`
- `.mpt`
- `.mpd`
- `.rmt`
- `.tmc`
- `.tm8`
- `.tm2`

Official sources say ASAP is a portable development library and is available in several generated language forms, including Python.

References:

- https://asap.sourceforge.net/
- https://asap.sourceforge.net/sap-format.html
- https://asap.sourceforge.net/contact.html
- https://sourceforge.net/p/asap/code/ci/master/tree/

## Current Status

The backend is registered as `selected; runtime needed`, but it is not activated.

Attempted retrieval notes:

- `https://sourceforge.net/p/asap/code/ci/master/tree/python/asap2wav.py?format=raw` was successfully staged at `third_party/src/asap_python/asap2wav.py`.
- The required generated `asap` Python module was not directly present in the SourceForge `python/` tree; it appears to be produced by the release/build process.
- SourceForge release tarball retrieval returned HTML or timed out in this environment, so the full source/runtime is not staged yet.

## Required Next Step

Use one of these integration paths:

1. Retrieve a release package that includes the generated Python `asap` module and import it directly.
2. Build the C/C++ ASAP library and expose a tiny `render(frames)` shim.
3. Use `asapconv --raw` only if it can stream PCM in real time without pre-rendering a file.

Do not replace `libgme` `.sap` playback until ASAP can render fixtures successfully.
