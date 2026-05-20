# VGM Scraper v2.4 — Full App Report

> **Purpose**: Provenance-aware VGM catalog and on-demand retrieval system.
> **Location**: `D:\vgm_scraper`
> **Date**: 2026-05-19
> **Version**: 2.4.0 (dark mode + split-pane catalog with live log)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI / GUI Layer                       │
│  __main__.py (argparse)  │  gui.py (Tkinter Tree+Queue)     │
└────────────────────┬──────────────────────────┬──────────────┘
                     │                          │
┌────────────────────▼─────────┐  ┌────────────▼──────────────┐
│       Catalog Domain         │  │     Acquisition Domain     │
│  catalog/models.py           │  │  acquisition/sources/      │
│  catalog/library.py          │  │  acquisition/crawler.py    │
│                              │  │  acquisition/local_scanner │
│  Console → Game → Collection │  │  acquisition/downloader.py │
│  → Track                     │  │  acquisition/retrieval.py  │
└────────────┬─────────────────┘  └────────────┬──────────────┘
             │                                 │
┌────────────▼─────────────────────────────────▼──────────────┐
│                    Database Layer                            │
│  db/schema.py (full schema definition)                       │
│  db/manager.py (operations for both domains)                 │
└─────────────────────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                    API Layer                                 │
│  api/server.py (HTTP/JSON for player integration)            │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Domain Separation

### Catalog Domain (`catalog/`)
**Answers**: "What music is available and how is it organized?"

| File | Purpose |
|---|---|
| `models.py` | Data classes: Console, Game, Collection, Track |
| `library.py` | LibraryManager: browsing, filtering, search, hierarchy |

**Hierarchy**: Console → Game → Collection → Track

### Acquisition Domain (`acquisition/`)
**Answers**: "Where does this music exist and how do I get it?"

| File | Purpose |
|---|---|
| `sources/base.py` | BaseSource abstract class, DiscoveredResource |
| `sources/*.py` | 9 source adapters (vgmrips, modarchive, zophar, etc) |
| `crawler.py` | WebCrawler: orchestrates sources, populates both domains |
| `local_scanner.py` | LocalScanner: folder scanning with heuristics + confidence |
| `downloader.py` | Downloader: download + extract + fingerprint |
| `retrieval.py` | RetrievalManager: on-demand retrieval with job tracking |

### Database Layer (`db/`)
| File | Purpose |
|---|---|
| `schema.py` | Full SQL schema with domain separation |
| `manager.py` | DatabaseManager: all CRUD operations for both domains |

### API Layer (`api/`)
| File | Purpose |
|---|---|
| `server.py` | APIServer: HTTP/JSON API for player integration |

---

## 3. Database Schema

### Catalog Tables
| Table | Columns | Purpose |
|---|---|---|
| `consoles` | id, slug, display_name, maker, generation | Platform/system |
| `games` | id, console_id, title, release_year, publisher | Game title |
| `collections` | id, game_id, title, description, source_url | Music pack/album |
| `tracks` | id, collection_id, game_id, title, track_number, duration, composer, format_hint | Individual track |

### Acquisition Tables
| Table | Columns | Purpose |
|---|---|---|
| `sources` | id, name, base_url, source_type, is_active | Web/local source |
| `crawl_jobs` | id, source_id, status, started_at, completed_at, items_found | Crawl execution |
| `resource_nodes` | id, source_id, crawl_job_id, parent_id, node_type, title, url, download_url, size_bytes, format, confidence | Discovered resource |
| `resource_track_links` | id, resource_id, track_id, is_primary, confidence | Link between acquisition and catalog |
| `provenance_events` | id, resource_id, track_id, event_type, details | Full provenance trail |

### Supporting Tables
| Table | Columns | Purpose |
|---|---|---|
| `retrieval_jobs` | id, track_id, resource_id, status, local_path, error_message | On-demand download jobs |
| `local_files` | id, track_id, file_path, size_bytes, fingerprint, is_available | Local file cache |

---

## 4. CLI Commands

```
python -m vgm_scraper <command> [options]
```

| Command | Description | Key Options |
|---|---|---|
| `list-sources` | List all 9 sources | — |
| `crawl` | Crawl web sources | `--source`, `--all-sources`, `--max-depth` |
| `scan` | Scan local directory | `--dir` |
| `retrieve` | Request track retrieval | `--track-id` |
| `process-jobs` | Process pending retrieval jobs | — |
| `search` | Search catalog | `--query` |
| `tree` | Show catalog hierarchy | — |
| `stats` | Show statistics (both domains) | — |
| `api-start` | Start HTTP API server | `--host`, `--port` |

---

## 5. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/consoles` | List all consoles |
| GET | `/api/consoles/{id}/games` | List games for console |
| GET | `/api/games/{id}/collections` | List collections for game |
| GET | `/api/collections/{id}/tracks` | List tracks for collection |
| GET | `/api/tracks/{id}` | Get track status (local/remote) |
| POST | `/api/tracks/{id}/request` | Request on-demand retrieval |
| GET | `/api/tree` | Full catalog hierarchy |
| GET | `/api/search?query=...` | Search catalog |
| GET | `/api/stats` | System statistics |

---

## 6. Provenance Tracking

Every discovered resource records:
- **Source**: which source found it (vgmrips, local, etc)
- **URL**: original location
- **Parent**: archive or folder it came from
- **Crawl job**: which crawl discovered it
- **Timestamp**: when it was found
- **Confidence**: how certain we are it's game music
- **Events**: full lifecycle (discovered → linked → retrieved)

---

## 7. Retrieval Flow

```
1. Player requests track → GET /api/tracks/{id}
2. Backend checks local_files table
3. If available → return local_path
4. If not → find best resource via resource_track_links
5. Create retrieval_job → POST /api/tracks/{id}/request
6. Download/extract → update retrieval_job status
7. Register local_file → update track availability
8. Player notified → plays local file
```

---

## 8. Source Adapters

| Source | Type | Consoles | Search | Notes |
|---|---|---|---|---|
| vgmrips | web | Dynamic (scraped) | Yes | Largest chiptune archive |
| modarchive | web | 3 genres | Yes | Tracker modules |
| zophar | web | 10 hardcoded | No | Multi-format rips |
| project2612 | web | 1 (Genesis) | Yes | Genesis only |
| hcs64 | web | 8 format pages | No | USF/DSF/SSF specialist |
| snesmusic | web | 1 (SNES) | No | SNES SPC rips |
| opengameart | web | 3 categories | No | Free game music |
| vgmdb | web | 3 categories | Yes | Metadata only |
| archive | web | 3 categories | Yes | Internet Archive API |
| local | local | N/A | N/A | Folder scanner with heuristics |

---

## 9. Launch Methods

```
# CLI
D:\vgm_scraper\run.bat <command>
python -m vgm_scraper <command>  # from D:\

# GUI
D:\vgm_scraper\run_gui.bat
python -m vgm_scraper.gui  # from D:\

# API Server
python -m vgm_scraper api-start --port 8765
```

---

## 10. Dependencies

| Package | Version | Used by |
|---|---|---|
| `requests` | >=2.31.0 | All HTTP operations |
| `beautifulsoup4` | >=4.12.0 | HTML parsing in web sources |

GUI uses stdlib `tkinter` only. API uses stdlib `http.server`.

---

## 11. File Structure

```
D:\vgm_scraper/
├── __init__.py          # Package init, version 2.0.0
├── __main__.py          # CLI entry point (argparse)
├── config.py            # Constants, paths, settings
├── core.py              # ScraperSession (HTTP + retry + rate limit)
├── gui.py               # Tkinter GUI (tree view + queue)
├── requirements.txt     # Python dependencies
├── run.bat              # CLI launcher batch
├── run_gui.bat          # GUI launcher batch
├── AGENTS.md            # Project overview and architecture guide
├── REPORT.md            # This file
├── catalog/             # Catalog Domain
│   ├── __init__.py
│   ├── models.py        # Console, Game, Collection, Track
│   └── library.py       # LibraryManager
├── acquisition/         # Acquisition Domain
│   ├── __init__.py
│   ├── sources/         # Source adapters
│   │   ├── __init__.py  # Source registry
│   │   ├── base.py      # BaseSource, DiscoveredResource
│   │   ├── vgmrips.py
│   │   ├── modarchive.py
│   │   ├── zophar.py
│   │   ├── project2612.py
│   │   ├── hcs64.py
│   │   ├── snesmusic.py
│   │   ├── opengameart.py
│   │   ├── vgmdb.py
│   │   └── archive.py
│   ├── crawler.py       # WebCrawler
│   ├── local_scanner.py # LocalScanner
│   ├── downloader.py    # Downloader
│   └── retrieval.py     # RetrievalManager
├── db/                  # Database Layer
│   ├── __init__.py
│   ├── schema.py        # Full SQL schema
│   └── manager.py       # DatabaseManager
└── api/                 # API Layer
    ├── __init__.py
    └── server.py        # APIServer, APIHandler
```

---

## 12. Key Changes from v1.0

| Aspect | v1.0 | v2.0 |
|---|---|---|
| Architecture | Flat scraper | Domain-separated (Catalog + Acquisition) |
| DB Schema | Single packs/tracks table | 10 tables with relationships |
| Retrieval | Bulk download all | On-demand per track |
| Provenance | None | Full event tracking |
| Local scanning | None | Heuristic-based with confidence scores |
| Player integration | None | HTTP/JSON API |
| Source adapters | Tightly coupled | Abstract base + registry pattern |

---

## 13. Changelog v2.4.0

**Dark mode theme (dark/grey/olive palette):**
- Full dark theme applied to all ttk widgets via `clam` theme customization
- Color palette: `#1a1d1e` (bg), `#24282a` (secondary), `#7a8a5e` (olive accent), `#c8cec8` (text)
- Treeview status tags: "downloaded" (olive dark bg), "pending" (muted text)
- Text/Listbox widgets themed manually (not controlled by ttk.Style)
- Progressbar, scrollbars, buttons, entries all themed consistently

**Split-pane Catalog tab:**
- Left: Console → Game tree view
- Right: Live scraper activity log with auto-scroll
- Date selector dropdown to view historical logs by date
- "Today (live)" shows current session with real-time updates

---

## 14. Changelog v2.3.0

**Simplified catalog: Console → Game only**
- Tree view now shows only Console → Game hierarchy (no collections/tracks pre-download)
- Tracks appear in library ONLY after game content is downloaded and extracted
- "Download Checked" button downloads selected games, extracts ZIP, discovers real files
- Post-download: actual file names, formats, and sizes are recorded as tracks
- Queue tab repurposed to show downloaded games with track counts and local paths

**Crawler changes:**
- Crawler now creates only console + game entries (no collections/tracks during crawl)
- Dramatically faster crawl: no track scraping overhead
- Games show status: "pending" (not downloaded) or "downloaded" (with track count)

**Benefits:**
- No phantom tracks — library only contains files that actually exist
- Accurate metadata — real file names, real formats, real sizes
- Cleaner UI — flat Console → Game list, easy to browse and select
- Faster crawling — fewer HTTP requests per game

---

## 14. Changelog v2.1.0

**Track-level resource linking:**
- Added `get_tracks()` method to `BaseSource` abstract class
- Implemented `get_tracks()` for VGMRips (scrapes pack detail page for track list)
- Implemented `get_tracks()` for Zophar (scrapes track rows from detail page)
- Crawler now creates individual `tracks` entries for each discovered track
- Each track is linked to its source resource via `resource_track_links` table
- Provenance events recorded per track (`track_discovered`, `track_discovered_local`)

**Local scanner catalog population:**
- LocalScanner now creates catalog entries (console → game → collection → tracks) for high-confidence folders (threshold: 0.5)
- Auto-detects console from folder name heuristics
- Creates track entries with cleaned filenames (removes leading track numbers)
- Registers local files with MD5 fingerprints
- Links file resources to catalog tracks automatically

**Bug fixes:**
- Fixed `logging.py` name collision with Python stdlib (renamed to `app_logging.py`)
- Fixed DB path resolution (now uses project dir instead of parent dir)
- Fixed VGMRips crawl performance (limited consoles, reduced pages)
- Fixed Windows console encoding issue (replaced Unicode checkmarks with ASCII `[+]`/`[ ]`)
- Crawler `max_depth` now properly limits pages per console
- Removed stale `db.py`, `downloader.py`, `sources/` from v1.0

**Verified flow:**
```
Local scan → confidence 1.0 → catalog populated → tracks linked → local files registered
Console: "Nes" → Game: "test_music" → Collection: "SNES-Zelda OST" → 3 tracks
```

---

## 15. Next Steps

1. **Resume download support** — Range headers for interrupted downloads
2. **Archive extraction** — Add `py7zr`/`rarfile` for .7z/.rar
3. **Audio metadata** — Integrate `mutagen` for tag reading
4. **Batch operations** — Select multiple tracks, download all
5. **Cache invalidation** — Detect moved/deleted local files
6. **Source health checks** — Monitor source availability
7. **Advanced search** — Full-text search across catalog
8. **Player GUI** — Build actual music player that consumes the API
