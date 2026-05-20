

## Project Overview

This project is a **VGM (Video Game Music) availability index and on-demand retrieval system**.

The goal is to build a backend that can:

- Discover and catalog videogame music from web sources and local folders
- Maintain a structured music library (Console → Game → Collection → Track)
- Track exactly where every resource comes from (provenance)
- Allow a player GUI to browse available music and request files on demand
- Handle downloading, extraction, and local caching automatically

The system must clearly separate **what music exists** from **how to obtain it**.

---

## Core Domain Separation

This project has two distinct domains that must remain separate in code and database design:

### 1. Acquisition Domain (Resource Layer)
Responsible for discovering, tracking, and retrieving physical resources.

**Responsibilities:**
- Crawling web sources and local directories
- Discovering folders, files, and archives
- Recording provenance (how and where a file was found)
- Storing retrieval instructions (direct URL, archive member, local path, etc.)
- Managing sources, crawl jobs, and resource nodes

This domain answers: *"Where does this music exist and how do I get it?"*

### 2. Catalog Domain (Library Layer)
Responsible for presenting a clean, playable music library to the GUI/player.

**Responsibilities:**
- Organizing content into Consoles, Games, Collections, and Tracks
- Providing filtering and browsing capabilities
- Tracking local availability status
- Linking logical tracks to one or more physical resources

This domain answers: *"What music is available and how is it organized?"*

These two domains must be linked but never mixed. A track in the catalog can point to multiple acquisition sources.

---

## Goals

- Build a reliable discovery system that automatically finds videogame music folders
- Create a proper database that stores both catalog data and acquisition/provenance data
- Support on-demand file retrieval triggered by the player GUI
- Track the full lifecycle of a file (discovered → downloaded → cached → playable)
- Keep the system maintainable and extensible

---

## Non-Goals (for now)

- Building the player GUI itself (we only provide the backend/API)
- Downloading entire libraries by default (focus on on-demand retrieval)
- Audio fingerprinting or advanced metadata enrichment (future work)

---

## Key Requirements

### 1. Provenance Tracking
Every discovered resource must record how it was obtained. This includes:
- Source type (`web`, `local`, `archive`)
- Original URL or filesystem path
- Parent folder/archive
- Crawl job ID
- Discovery timestamp
- Extraction context (if taken from an archive)

### 2. Automated Discovery
The system should be able to scan sources and identify likely videogame music folders using heuristics such as:
- Platform tags in folder names (PS1, PS2, SNES, etc.)
- Soundtrack-related keywords (OST, BGM, gamerip, soundtrack)
- Presence of known VGM/audio extensions
- Track-numbered filenames
- Archive files that appear to contain game music

Discovered candidates should include a confidence score and evidence.

### 3. Player Integration Workflow
The system must support the following flow:

1. Player browses the catalog (consoles → games → tracks)
2. User clicks a track or folder
3. Backend checks if the file already exists locally
4. If not, it creates a retrieval job using the best available source
5. File is downloaded/extracted to a target folder
6. Player is notified when the file is ready
7. Player plays the local file

---

## Database Guidance

Use a relational database with clear separation between domains.

Recommended high-level entities:

**Catalog Domain:**
- `consoles`
- `games`
- `collections`
- `tracks`

**Acquisition Domain:**
- `sources`
- `resource_nodes` (folders, files, archives)
- `resource_track_links`

**Supporting Tables:**
- `crawl_jobs`
- `provenance_events`
- `retrieval_jobs`
- `local_files`

Do not store acquisition details inside catalog tables. Keep them separate and link them via `resource_track_links`.

---

## Implementation Priorities

1. **Define the domain split** clearly in the codebase and schema.
2. Implement basic source and resource discovery (web + local).
3. Build the catalog models (console → game → collection → track).
4. Create the linking layer between catalog tracks and acquisition resources.
5. Implement retrieval job handling and local file tracking.
6. Add provenance recording for all discovered items.
7. Expose an API suitable for player integration.

---

## Coding Guidelines

- Prefer clear separation between Acquisition and Catalog logic.
- Store provenance structurally in the database, not only in logs.
- Use confidence scores + evidence when classifying discovered folders/files.
- Make retrieval idempotent and resumable when possible.
- Keep raw discovered data (`resource_nodes`) separate from normalized catalog data.
- Use meaningful naming (avoid vague names like `data`, `item`, or `file`).
- Add comments explaining *why* a piece of logic exists, especially around provenance and domain separation.

---

## Expected Output from Agent

When making changes, please provide:

- Summary of what was changed
- Which domain (Acquisition or Catalog) was modified
- Any schema changes or new tables
- How provenance or retrieval is handled
- Any assumptions made
- Suggested next steps

---

## Project Description (for reference)

> A provenance-aware VGM catalog and on-demand retrieval system that separates content organization from resource acquisition, enabling a player GUI to browse available music and fetch files only when requested.
```

---
