# VGM Audio Engine

Extracted audio engine from the provided `PLAYER` project.

This folder intentionally keeps only the playback engine layer:

- `simpleplayer/audio.py` real-time audio output wrapper
- `simpleplayer/engines/` Python backend registry and engine adapters
- `engines/` native DLLs, helper executables, and license files
- `native/aoqsf/build/aoqsf_helper.exe` for the QSF adapter path used by the current engine code

The UI, fixtures, source archives, build tooling, and unrelated player app files are intentionally excluded.

The package still uses the `simpleplayer` Python module name for compatibility with the extracted engine code. A later integration pass can rename or wrap this API once the new UI layer is available.
