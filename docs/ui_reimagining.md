# UI Reimagining

This document defines the target UI before merging the backend, audio engine, and
salvaged player visuals. The old UI folder is a reference snapshot only. It must
not decide architecture or button placement.

## Product Shape

The player is a library workbench, not a scraper control panel. The main screen
should make these jobs visually separate:

1. Browse catalog.
2. Verify or retrieve files on demand.
3. Build a playable list.
4. Control playback.

Scraping and retrieval state can be visible, but it should not dominate the
player. The user should mostly feel like they are opening albums and playing
tracks.

## Screen Layout

Use a stable two-column layout. Each column occupies 50% of the window width and
resizes evenly when the user drags the lateral window edges.

```text
+------------------------------------------------------------------------+
| Header: app title | search | source/status | settings                  |
+------------------------------------+-----------------------------------+
| Left column                         | Right column                      |
|                                    | General game info                 |
| File browser                        | from Libretro/resources           |
| Maker separators                    |                                   |
| Console folders                     | Image/artwork window              |
| Game rows                           |                                   |
| Track/file rows                     | File info                         |
|                                    | selected file/status/provenance   |
| Game/file action row                |                                   |
|                                    | Playback row                      |
| Playlist queue                      | prev | play | stop | next | etc.  |
|                                    | timeline | volume                 |
+------------------------------------+-----------------------------------+
```

### Header

The header is for global actions only:

- Search.
- Refresh catalog.
- Settings.
- Backend connection/status.

Do not put play, download, or per-game actions here.

### Left Column: Browser And Queue

The left column is the work list. It contains the file browser and playlist
queue stacked vertically. Both sections stretch with window height. The file
browser gets priority and should be as tall as possible so many folders/games
are visible at once.

Recommended vertical split:

- File browser: about 65-75% of left-column height.
- Action row: compact fixed height.
- Playlist queue: about 25-35% of left-column height.

The split can be user-resizable later, but the default must favor the browser.

### Catalog Browser

The browser follows the agreed catalog shape:

- Maker is a visual separator, not a folder.
- Console is the first real folder.
- Game rows live under consoles.
- Collections are not part of this view for now.

Selecting a game reveals contextual actions in the separator row between browser
and queue:

- `Play Selected Game` if verified/local playable files exist.
- `Open Game` if availability has not been verified yet.
- `Retry Game` if the last verification failed.

This button belongs near the selected game, not in the playback bar.

### Track/File Rows

The browser may use a tree or table, but the file rows inside an opened game are
the source of the playable playlist. If a row is hidden by the current filter,
it is not part of play-selected-game.

Columns:

- Track number.
- Title.
- Availability status: Online, Obtaining file, Local, Failed.
- Duration.
- Format.

Duration display:

- Empty if duration is null.
- `MM:SS` for normal tracks.
- `HH:MM:SS` if longer than 60 minutes.

SFX filtering:

- Duration under 15 seconds hides the track from the next game-open refresh.
- During the live verification cycle, replace that row text with `moved to sfx`
  so the table does not jump around.
- No per-track category flag is needed in the catalog.

### Right Column: Game Info, Art, File Info, Player

The right column is the listening surface. From top to bottom:

1. General game info scraped from Libretro/resources and compatible game image
   databases.
2. Image/artwork window.
3. Selected file info.
4. Player controls.

This creates a clear reading order: what game this is, what it looks like, what
file is selected, then how to play it.

### General Game Info

This area is for the selected game, not the selected file:

- Game title.
- Console.
- Maker shown through the console relationship, if useful.
- Year, developer/publisher, genre, region, or description when available.
- Source attribution for scraped metadata.

Metadata is helpful here, but not required in the browser tree.

### Image Window

The image window should preserve the old UI's best quality: a strong arcade
visual identity. It can show:

- Box art.
- Screenshot.
- Title screen.
- Fallback neon/pixel artwork from the saved assets.

Image controls, if needed, should be minimal. Avoid scattering `next visual`
style buttons around the player controls.

### File Info

The file info area sits directly above the player buttons. It is for the
selected or currently playing file:

- Track title.
- Status: Online, Obtaining file, Local, Failed.
- Duration when known.
- Format.
- Provenance summary for the selected item.
- Verification/retrieval job history.
- Error details for failed files.
- Manual retry for selected file.

### Queue Strip

The queue lives under the browser in the left column. It is a separate view of
what will play. It should not mutate when the browser updates live during
verification.

Rules:

- A playlist snapshot is created from currently listed playable rows.
- Live row updates can change status text, duration, and local availability.
- The active queue remains stable until the user explicitly starts/rebuilds it.

### Playback Bar

Playback controls live in one horizontal row at the bottom of the right column
and never mix with scraping or catalog actions:

- Previous.
- Play/pause.
- Stop.
- Next.
- Seek timeline.
- Time display.
- Volume.
- Repeat/shuffle if needed.

The playback bar talks to the extracted audio engine only. It should not know
how retrieval or scraping works.

## State Names

Use the simple names already chosen:

- Online.
- Obtaining file.
- Local.
- Failed.

Avoid `candidate` in user-facing UI.

## Button Placement Rules

- Global actions go in the header.
- Game actions go beside or below the selected game area.
- Game/file availability actions go in the compact row between browser and queue.
- File details and file retry live in the file info area.
- Playback actions go only in the single player row.
- Debug actions go in the inspector or a hidden developer panel.

This is the main fix for the old button mess.

## Salvage From Old UI

Keep as reference:

- Visual style ideas from `theme.py`.
- Asset direction from `assets/`.
- Keyboard shortcut behavior.
- Queue behavior concepts.
- Tree/table interaction patterns.

Do not salvage:

- Old audio engine.
- Vendor decoder binaries.
- Old site-specific scraper service.
- Old downloader.
- Old SQLite database shape.
- Runtime logs, backups, launch scripts, and packed archives.

## Integration Contract

The clean UI should depend on narrow interfaces:

- `CatalogClient`: list makers, consoles, games, and verified files.
- `AvailabilityClient`: open game, retry failed file/game, watch statuses.
- `PlaybackController`: load local file, play, pause, stop, seek, volume.

The UI must not import acquisition internals, database managers, or scraper
classes directly.
