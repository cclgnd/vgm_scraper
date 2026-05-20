-- CHIPTUNEPALACE DATABASE SCHEMA
-- SQLite WAL Mode enabled

CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    artist TEXT,
    file_path TEXT NOT NULL UNIQUE,
    format TEXT,
    duration REAL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS playlist (
    track_id INTEGER,
    position INTEGER,
    FOREIGN KEY (track_id) REFERENCES tracks(id)
);
