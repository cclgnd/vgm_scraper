Place native audio engine DLLs and helper runtimes here.

For the current backend, add one of:

- `gme.dll`
- `libgme.dll`

You can also point directly to the DLL with:

```powershell
$env:SIMPLEPLAYER_GME_DLL = "C:\path\to\gme.dll"
```

PSF1 playback uses the isolated helper:

- `aopsf/aopsf_helper.exe`

Rebuild it with:

```powershell
python native\aopsf\build_aopsf.py
```

PSF2 playback uses the isolated helper:

- `aopsf2/aopsf2_helper.exe`

Rebuild it with:

```powershell
python native\aopsf2\build_aopsf2.py
```
