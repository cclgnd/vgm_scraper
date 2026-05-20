# Windows Integration Scripts

Run:

```bat
scripts\register_file_associations.bat
```

This registers Explorer `Open with` support for the current user for:

```text
.ay .gbs .gym .hes .kss .nsf .nsfe .sap .spc .vgm .vgz
```

Remove the associations with:

```bat
scripts\register_file_associations.bat uninstall
```

The script writes under `HKCU\Software\Classes`, so it should not require administrator rights.
