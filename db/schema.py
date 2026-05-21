"""
Database schema definition for VGM Scraper.

Domain separation:
- Catalog Domain: consoles, games, collections, tracks
- Acquisition Domain: sources, resource_nodes, resource_track_links, provenance_events
- Supporting: crawl_jobs, retrieval_jobs, local_files
"""

SCHEMA = """
-- ============================================
-- CATALOG DOMAIN
-- ============================================

CREATE TABLE IF NOT EXISTS consoles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    maker TEXT,
    generation TEXT,
    logo_url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    console_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    release_year INTEGER,
    publisher TEXT,
    developer TEXT,
    genre TEXT,
    description TEXT,
    cover_art_url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (console_id) REFERENCES consoles(id),
    UNIQUE(console_id, title)
);

CREATE TABLE IF NOT EXISTS collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    source_url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(id)
);

CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_id INTEGER,
    game_id INTEGER,
    title TEXT NOT NULL,
    track_number INTEGER,
    duration_seconds REAL,
    composer TEXT,
    format_hint TEXT,
    availability_status TEXT DEFAULT 'obtaining_file',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collection_id) REFERENCES collections(id),
    FOREIGN KEY (game_id) REFERENCES games(id)
);

-- ============================================
-- ACQUISITION DOMAIN
-- ============================================

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    base_url TEXT,
    source_type TEXT NOT NULL DEFAULT 'web',
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crawl_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    started_at TEXT,
    completed_at TEXT,
    items_found INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS resource_nodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    crawl_job_id INTEGER,
    parent_id INTEGER,
    node_type TEXT NOT NULL,
    title TEXT,
    url TEXT,
    download_url TEXT,
    archive_path TEXT,
    size_bytes INTEGER,
    format TEXT,
    confidence REAL DEFAULT 1.0,
    discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(id),
    FOREIGN KEY (crawl_job_id) REFERENCES crawl_jobs(id),
    FOREIGN KEY (parent_id) REFERENCES resource_nodes(id)
);

CREATE TABLE IF NOT EXISTS resource_track_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER NOT NULL,
    track_id INTEGER NOT NULL,
    is_primary INTEGER DEFAULT 0,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (resource_id) REFERENCES resource_nodes(id),
    FOREIGN KEY (track_id) REFERENCES tracks(id),
    UNIQUE(resource_id, track_id)
);

CREATE TABLE IF NOT EXISTS resource_game_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER NOT NULL,
    game_id INTEGER NOT NULL,
    is_primary INTEGER DEFAULT 0,
    confidence REAL DEFAULT 1.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (resource_id) REFERENCES resource_nodes(id),
    FOREIGN KEY (game_id) REFERENCES games(id),
    UNIQUE(resource_id, game_id)
);

CREATE TABLE IF NOT EXISTS provenance_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER,
    track_id INTEGER,
    event_type TEXT NOT NULL,
    details TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (resource_id) REFERENCES resource_nodes(id),
    FOREIGN KEY (track_id) REFERENCES tracks(id)
);

-- ============================================
-- SUPPORTING TABLES
-- ============================================

CREATE TABLE IF NOT EXISTS retrieval_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,
    resource_id INTEGER,
    status TEXT DEFAULT 'pending',
    local_path TEXT,
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (track_id) REFERENCES tracks(id),
    FOREIGN KEY (resource_id) REFERENCES resource_nodes(id)
);

CREATE TABLE IF NOT EXISTS local_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,
    file_path TEXT NOT NULL UNIQUE,
    size_bytes INTEGER,
    fingerprint TEXT,
    is_available INTEGER DEFAULT 1,
    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (track_id) REFERENCES tracks(id)
);

CREATE TABLE IF NOT EXISTS audition_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER,
    game_id INTEGER,
    track_id INTEGER,
    event_type TEXT NOT NULL,
    status TEXT NOT NULL,
    details_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (resource_id) REFERENCES resource_nodes(id),
    FOREIGN KEY (game_id) REFERENCES games(id),
    FOREIGN KEY (track_id) REFERENCES tracks(id)
);

-- ============================================
-- DISCOVERY ENGINE
-- ============================================

CREATE TABLE IF NOT EXISTS discovered_sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    name TEXT,
    status TEXT DEFAULT 'candidate',
    confidence REAL DEFAULT 0.0,
    profile_json TEXT,
    discovered_from TEXT,
    discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_checked TEXT,
    last_crawled TEXT,
    items_found INTEGER DEFAULT 0
);

-- ============================================
-- INDEXES
-- ============================================

CREATE INDEX IF NOT EXISTS idx_games_console ON games(console_id);
CREATE INDEX IF NOT EXISTS idx_collections_game ON collections(game_id);
CREATE INDEX IF NOT EXISTS idx_tracks_collection ON tracks(collection_id);
CREATE INDEX IF NOT EXISTS idx_tracks_game ON tracks(game_id);
CREATE INDEX IF NOT EXISTS idx_tracks_availability_status ON tracks(availability_status);
CREATE INDEX IF NOT EXISTS idx_resource_nodes_source ON resource_nodes(source_id);
CREATE INDEX IF NOT EXISTS idx_resource_nodes_parent ON resource_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_resource_nodes_type_title ON resource_nodes(node_type, title);
CREATE INDEX IF NOT EXISTS idx_resource_track_links_resource ON resource_track_links(resource_id);
CREATE INDEX IF NOT EXISTS idx_resource_track_links_track ON resource_track_links(track_id);
CREATE INDEX IF NOT EXISTS idx_resource_game_links_resource ON resource_game_links(resource_id);
CREATE INDEX IF NOT EXISTS idx_resource_game_links_game ON resource_game_links(game_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_jobs_track ON retrieval_jobs(track_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_jobs_status ON retrieval_jobs(status);
CREATE INDEX IF NOT EXISTS idx_local_files_track ON local_files(track_id);
CREATE INDEX IF NOT EXISTS idx_local_files_fingerprint ON local_files(fingerprint);
CREATE INDEX IF NOT EXISTS idx_audition_events_resource ON audition_events(resource_id);
CREATE INDEX IF NOT EXISTS idx_audition_events_game ON audition_events(game_id);
CREATE INDEX IF NOT EXISTS idx_audition_events_track ON audition_events(track_id);
CREATE INDEX IF NOT EXISTS idx_audition_events_status ON audition_events(status);
"""
