# KSS Playback Notes

KSS is not a normal multitrack module. It contains ripped Z80 code and data, similar in spirit to NSF. The selector passed to the player is an init/subsong selector, not a mixer layer.

The KSS header does not provide a reliable track count or playlist. `libgme` therefore exposes up to 256 possible selectors. Some are songs, some are silence, and some may be sound effects or invalid init states.

Sources:

- https://sources.debian.org/src/game-music-emu/0.5.5-2/gme.txt/
- https://ocremix.org/info/KSS_Format_Specification
- https://vgmpf.com/Wiki/index.php?title=KSS

## SIMPLEPLAYER Workaround

For `.kss` files only:

1. Open through `libgme`.
2. Render each selector briefly.
3. Keep selectors that produce audible PCM.
4. Present only those selectors in the track dropdown.
5. Start playback from the first audible selector.

This keeps already-good selector `0` files working while avoiding silent startup for files whose first real music selector is elsewhere.
