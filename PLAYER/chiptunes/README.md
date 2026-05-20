# Chiptune Fixture Pack

This folder contains real native music files for SIMPLEPLAYER development tests.

Each readily playable `libgme` type has 10 fixtures:

- `ay`
- `gbs`
- `gym`
- `hes`
- `kss`
- `nsf`
- `nsfe`
- `sap`
- `spc`
- `vgm`
- `vgz`

Use these files to test real-time emulated playback. Do not replace them with rendered WAV/FLAC/MP3 files.

`MANIFEST.json` records source URLs, repositories, sizes, and SHA256 hashes.

Notes:

- `.vgz` is gzipped `.vgm`; the `.vgm` fixtures were derived losslessly from downloaded `.vgz` files to exercise raw VGM loading.
- Some `.gym` downloads were stored in `GYMX` containers. They were normalized by inflating the embedded zlib payload so `libgme` receives the raw GYM event stream.
- The smoke test is `python -m unittest tests.test_chiptune_fixtures`.
