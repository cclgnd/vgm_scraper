# Third-Party Source Staging

This folder is for source archives and extracted code used to build native emulator backends.

The files here are not automatically imported by Python. A backend only becomes active after we build a small runtime DLL/helper that exposes the SIMPLEPLAYER real-time API.

## Current PSF/PSF2 Sources

Downloaded from official GitLab project archive URLs linked by the foobar2000 PSF Decoder page:

- `src/highly_experimental-main.zip`
  - Source: `https://gitlab.com/kode54/highly_experimental/-/archive/main/highly_experimental-main.zip`
  - SHA256: `921098128ad0cf8069e0537f0d99cc5a2c7416c254c455fafed42927c60971ab`
  - Role: PlayStation / PlayStation 2 emulation core with real-time `psx_execute()`.
- `src/psflib-main.zip`
  - Source: `https://gitlab.com/kode54/psflib/-/archive/main/psflib-main.zip`
  - SHA256: `a803716ae872673f2c285213e342dd16a1b74a90ad61b604bb88aae6b0b5c124`
  - Role: PSF/minipsf/psflib chain loader and metadata parser.

`foo_psf` was not staged because GitLab returned HTTP 403 for the archive in this environment, and the foobar component wrapper is less important than the emulator core and loader.

## Legal/Fidelity Note

`highly_experimental` is fidelity-oriented and exposes a useful real-time execution API, but its own README states that the core embeds a reduced BIOS-derived payload. Do not ship a built PSF runtime without reviewing this tradeoff and license/compliance requirements.
