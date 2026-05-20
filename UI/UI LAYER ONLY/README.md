## Audio Engine Architecture (2026)

The audio system has been redesigned for real chip emulation.

See:
- `docs/audio_engine_vision.md` — overall goal
- `audio/readme.md` — module overview
- `audio/backends/specifications.md` — strict backend contract (most important)

The old WAV-transcoding pipeline (VGMPlay/vgmstream) is deprecated for all formats supported by libgme. The new system loads tracks in memory and generates samples in real time using emulated sound chips.