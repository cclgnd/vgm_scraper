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

Use a stable four-zone layout.

```text
+--------------------------------------------------------------------+
| Header: app title | search | source/status | settings              |
+----------------------+---------------------------------------------+
| Catalog browser      | Track table                                  |
| Maker separators     | # | Title | Status | Duration | Format       |
| Console folders      |                                             |
| Game rows            |                                             |
|                      |                                             |
| Selected-game action |                                             |
+----------------------+--------------------------+------------------+
| Queue / current game strip                       | Inspector       |
| compact, collapsible                             | jobs, details   |
+--------------------------------------------------------------------+
| Playback bar: previous | play/pause | next | timeline | volume     |
+--------------------------------------------------------------------+
```

### Header

The header is for global actions only:

- Search.
- Refresh catalog.
- Settings.
- Backend connection/status.

Do not put play, download, or per-game actions here.

### Catalog Browser

The browser follows the agreed catalog shape:

- Maker is a visual separator, not a folder.
- Console is the first real folder.
- Game rows live under consoles.
- Collections are not part of this view for now.

Selecting a game reveals a single contextual action:

- `Play Selected Game` if verified/local playable files exist.
- `Open Game` if availability has not been verified yet.
- `Retry Game` if the last verification failed.

This button belongs near the selected game, not in the playback bar.

### Track Table

The track table is the source of the playable playlist. If a row is hidden by
the current filter, it is not part of play-selected-game.

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

### Inspector

The inspector is for additional info and job state:

- Selected console/game/track metadata.
- Provenance summary for the selected item.
- Verification/retrieval job history.
- Error details for failed files.
- Manual retry for selected file.

Metadata is helpful here, but not required in the browser tree.

### Queue Strip

The queue is a separate view of what will play. It should not mutate when the
track table updates live during verification.

Rules:

- A playlist snapshot is created from currently listed playable rows.
- Live row updates can change status text, duration, and local availability.
- The active queue remains stable until the user explicitly starts/rebuilds it.

### Playback Bar

Playback controls are always bottom-aligned and never mixed with scraping or
catalog actions:

- Previous.
- Play/pause.
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
- File actions go inside the track row context menu or inspector.
- Playback actions go only in the playback bar.
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

