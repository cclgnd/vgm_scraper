"""
Database manager for VGM Scraper.

Handles both Catalog and Acquisition domains with proper separation.
"""

import os
import sqlite3
import datetime
import json
from contextlib import contextmanager

from vgm_scraper.db.schema import SCHEMA


class DatabaseManager:
    """Manages SQLite database with domain separation."""

    def __init__(self, db_path: str):
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self.connect() as conn:
            self._pre_migrate_existing_db(conn)
            conn.executescript(SCHEMA)
            self._migrate_existing_db(conn)

    def _pre_migrate_existing_db(self, conn):
        """Prepare old tables before running schema indexes that reference new columns."""
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'tracks'"
        ).fetchone()
        if not table:
            return
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tracks)").fetchall()}
        if "availability_status" not in columns:
            conn.execute("ALTER TABLE tracks ADD COLUMN availability_status TEXT DEFAULT 'obtaining_file'")

    def _migrate_existing_db(self, conn):
        """Apply small additive migrations for databases created before schema changes."""
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(tracks)").fetchall()}
        if "availability_status" not in columns:
            conn.execute("ALTER TABLE tracks ADD COLUMN availability_status TEXT DEFAULT 'obtaining_file'")

    def reset_database(self) -> dict:
        """Delete all database contents and recreate the schema.

        This only resets SQLite data. It intentionally leaves downloaded/cache
        files on disk alone so database cleanup cannot destroy acquired media.
        """
        tables = [
            "audition_events",
            "local_files",
            "retrieval_jobs",
            "provenance_events",
            "resource_track_links",
            "resource_game_links",
            "resource_nodes",
            "crawl_jobs",
            "sources",
            "tracks",
            "collections",
            "games",
            "consoles",
            "discovered_sites",
        ]
        with self.connect() as conn:
            conn.execute("PRAGMA foreign_keys = OFF;")
            for table in tables:
                conn.execute(f"DELETE FROM {table}")
            conn.execute("DELETE FROM sqlite_sequence WHERE name IN (%s)" % ",".join("?" for _ in tables), tables)
            conn.executescript(SCHEMA)
            conn.execute("PRAGMA foreign_keys = ON;")
        return self.get_stats()

    # ============================================
    # CATALOG DOMAIN
    # ============================================

    def add_console(self, slug: str, display_name: str, maker: str = "", generation: str = "") -> int:
        with self.connect() as conn:
            existing = conn.execute("SELECT id FROM consoles WHERE slug = ?", (slug,)).fetchone()
            if existing:
                return existing["id"]
            cursor = conn.execute(
                "INSERT INTO consoles (slug, display_name, maker, generation) VALUES (?, ?, ?, ?)",
                (slug, display_name, maker, generation)
            )
            return cursor.lastrowid

    def get_console(self, console_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM consoles WHERE id = ?", (console_id,)).fetchone()
            return dict(row) if row else None

    def get_console_by_slug(self, slug: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM consoles WHERE slug = ?", (slug,)).fetchone()
            return dict(row) if row else None

    def list_consoles(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM consoles ORDER BY display_name").fetchall()
            return [dict(r) for r in rows]

    def add_game(self, console_id: int, title: str, release_year: int = None, publisher: str = "", developer: str = "", genre: str = "", description: str = "", cover_art_url: str = "") -> int:
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT id FROM games WHERE console_id = ? AND title = ?",
                (console_id, title)
            ).fetchone()
            if existing:
                return existing["id"]
            cursor = conn.execute(
                "INSERT INTO games (console_id, title, release_year, publisher, developer, genre, description, cover_art_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (console_id, title, release_year, publisher, developer, genre, description, cover_art_url)
            )
            return cursor.lastrowid

    def update_game_metadata(self, game_id: int, release_year: int = None, publisher: str = None, developer: str = None, genre: str = None, description: str = None, cover_art_url: str = None):
        with self.connect() as conn:
            updates = []
            params = []
            if release_year is not None:
                updates.append("release_year = ?")
                params.append(release_year)
            if publisher is not None:
                updates.append("publisher = ?")
                params.append(publisher)
            if developer is not None:
                updates.append("developer = ?")
                params.append(developer)
            if genre is not None:
                updates.append("genre = ?")
                params.append(genre)
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if cover_art_url is not None:
                updates.append("cover_art_url = ?")
                params.append(cover_art_url)
            
            if updates:
                params.append(game_id)
                conn.execute(f"UPDATE games SET {', '.join(updates)} WHERE id = ?", params)

    def get_game(self, game_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
            return dict(row) if row else None

    def list_games(self, console_id: int = None) -> list[dict]:
        with self.connect() as conn:
            if console_id:
                rows = conn.execute(
                    "SELECT * FROM games WHERE console_id = ? ORDER BY title",
                    (console_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM games ORDER BY title").fetchall()
            return [dict(r) for r in rows]

    def add_collection(self, game_id: int, title: str, description: str = "", source_url: str = "") -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO collections (game_id, title, description, source_url) VALUES (?, ?, ?, ?)",
                (game_id, title, description, source_url)
            )
            return cursor.lastrowid

    def get_or_create_collection(self, game_id: int, title: str,
                                 description: str = "", source_url: str = "") -> int:
        with self.connect() as conn:
            row = conn.execute(
                """SELECT id FROM collections
                   WHERE game_id = ? AND title = ? AND COALESCE(source_url, '') = ?
                   LIMIT 1""",
                (game_id, title, source_url or "")
            ).fetchone()
            if row:
                return row["id"]
            cursor = conn.execute(
                "INSERT INTO collections (game_id, title, description, source_url) VALUES (?, ?, ?, ?)",
                (game_id, title, description, source_url)
            )
            return cursor.lastrowid

    def get_collection(self, collection_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM collections WHERE id = ?", (collection_id,)).fetchone()
            return dict(row) if row else None

    def list_collections(self, game_id: int = None) -> list[dict]:
        with self.connect() as conn:
            if game_id:
                rows = conn.execute(
                    "SELECT * FROM collections WHERE game_id = ? ORDER BY title",
                    (game_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM collections ORDER BY title").fetchall()
            return [dict(r) for r in rows]

    def add_track(self, title: str, collection_id: int = None, game_id: int = None,
                  track_number: int = None, duration_seconds: float = None,
                  composer: str = "", format_hint: str = "",
                  availability_status: str = "obtaining_file") -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """INSERT INTO tracks (title, collection_id, game_id, track_number,
                   duration_seconds, composer, format_hint, availability_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, collection_id, game_id, track_number, duration_seconds, composer,
                 format_hint, availability_status)
            )
            return cursor.lastrowid

    def get_or_create_track(self, title: str, collection_id: int = None, game_id: int = None,
                            track_number: int = None, duration_seconds: float = None,
                            composer: str = "", format_hint: str = "",
                            availability_status: str = "obtaining_file") -> int:
        with self.connect() as conn:
            row = conn.execute(
                """SELECT id FROM tracks
                   WHERE title = ?
                     AND COALESCE(collection_id, 0) = COALESCE(?, 0)
                     AND COALESCE(game_id, 0) = COALESCE(?, 0)
                     AND COALESCE(track_number, 0) = COALESCE(?, 0)
                   LIMIT 1""",
                (title, collection_id, game_id, track_number)
            ).fetchone()
            if row:
                return row["id"]
            cursor = conn.execute(
                """INSERT INTO tracks (title, collection_id, game_id, track_number,
                   duration_seconds, composer, format_hint, availability_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, collection_id, game_id, track_number, duration_seconds, composer,
                 format_hint, availability_status)
            )
            return cursor.lastrowid

    def get_track(self, track_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM tracks WHERE id = ?", (track_id,)).fetchone()
            return dict(row) if row else None

    def list_tracks(self, collection_id: int = None, game_id: int = None) -> list[dict]:
        with self.connect() as conn:
            if collection_id:
                rows = conn.execute(
                    "SELECT * FROM tracks WHERE collection_id = ? ORDER BY track_number",
                    (collection_id,)
                ).fetchall()
            elif game_id:
                rows = conn.execute(
                    "SELECT * FROM tracks WHERE game_id = ? ORDER BY title",
                    (game_id,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM tracks ORDER BY title").fetchall()
            return [dict(r) for r in rows]

    def list_player_files_for_game(self, game_id: int, include_short: bool = False) -> dict:
        """Return player-visible files for a game plus hidden short-file count.

        Unknown durations remain visible. Known files under 15 seconds are hidden
        from the default browser but counted for the UI hint.
        """
        with self.connect() as conn:
            hidden_count = conn.execute(
                """SELECT COUNT(*) FROM tracks
                   WHERE game_id = ? AND duration_seconds IS NOT NULL AND duration_seconds < 15""",
                (game_id,)
            ).fetchone()[0]
            if include_short:
                rows = conn.execute(
                    """SELECT * FROM tracks
                       WHERE game_id = ?
                       ORDER BY COALESCE(track_number, 999999), title""",
                    (game_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM tracks
                       WHERE game_id = ?
                         AND (duration_seconds IS NULL OR duration_seconds >= 15)
                       ORDER BY COALESCE(track_number, 999999), title""",
                    (game_id,)
                ).fetchall()
            return {
                "files": [dict(r) for r in rows],
                "hidden_short_file_count": hidden_count,
            }

    def update_track_availability(self, track_id: int, status: str):
        with self.connect() as conn:
            conn.execute("UPDATE tracks SET availability_status = ? WHERE id = ?", (status, track_id))

    def update_track_duration(self, track_id: int, duration_seconds: float | None):
        with self.connect() as conn:
            conn.execute("UPDATE tracks SET duration_seconds = ? WHERE id = ?", (duration_seconds, track_id))

    def get_catalog_tree(self) -> list[dict]:
        """Returns full catalog hierarchy: consoles → games → collections → tracks."""
        with self.connect() as conn:
            consoles = conn.execute("SELECT * FROM consoles ORDER BY display_name").fetchall()
            result = []
            for console in consoles:
                console_data = dict(console)
                games = conn.execute(
                    "SELECT * FROM games WHERE console_id = ? ORDER BY title",
                    (console["id"],)
                ).fetchall()
                console_data["games"] = []
                for game in games:
                    game_data = dict(game)
                    collections = conn.execute(
                        "SELECT * FROM collections WHERE game_id = ? ORDER BY title",
                        (game["id"],)
                    ).fetchall()
                    game_data["collections"] = []
                    for coll in collections:
                        coll_data = dict(coll)
                        tracks = conn.execute(
                            "SELECT * FROM tracks WHERE collection_id = ? ORDER BY track_number",
                            (coll["id"],)
                        ).fetchall()
                        coll_data["tracks"] = [dict(t) for t in tracks]
                        game_data["collections"].append(coll_data)
                    console_data["games"].append(game_data)
                result.append(console_data)
            return result

    def get_gui_catalog_summary(self) -> list[dict]:
        """Return the lightweight Console -> Game tree used by the GUI."""
        with self.connect() as conn:
            rows = conn.execute(
                """WITH latest_game_audition AS (
                       SELECT ae.*
                       FROM audition_events ae
                       JOIN (
                           SELECT game_id, MAX(id) AS id
                           FROM audition_events
                           WHERE game_id IS NOT NULL
                           GROUP BY game_id
                       ) latest ON latest.id = ae.id
                   ),
                   game_source AS (
                       SELECT g.id AS game_id,
                              (
                                  SELECT rn.id
                                  FROM resource_game_links rgl
                                  JOIN resource_nodes rn ON rn.id = rgl.resource_id
                                  WHERE rgl.game_id = g.id
                                  ORDER BY rgl.is_primary DESC, rgl.confidence DESC, rn.discovered_at DESC
                                  LIMIT 1
                              ) AS resource_id,
                              (
                                  SELECT rn.url
                                  FROM resource_game_links rgl
                                  JOIN resource_nodes rn ON rn.id = rgl.resource_id
                                  WHERE rgl.game_id = g.id
                                  ORDER BY rgl.is_primary DESC, rgl.confidence DESC, rn.discovered_at DESC
                                  LIMIT 1
                              ) AS source_url,
                              (
                                  SELECT rn.download_url
                                  FROM resource_game_links rgl
                                  JOIN resource_nodes rn ON rn.id = rgl.resource_id
                                  WHERE rgl.game_id = g.id
                                  ORDER BY rgl.is_primary DESC, rgl.confidence DESC, rn.discovered_at DESC
                                  LIMIT 1
                              ) AS download_url
                       FROM games g
                   )
                   SELECT c.id AS console_id,
                          c.display_name AS console_name,
                          g.id AS game_id,
                          g.title AS game_title,
                          COUNT(DISTINCT t.id) AS track_count,
                          MAX(CASE WHEN lf.id IS NOT NULL THEN 1 ELSE 0 END) AS has_files,
                          COALESCE(lga.status, 'pending') AS audition_status,
                          COALESCE(gs.source_url, '') AS source_url,
                          COALESCE(gs.download_url, '') AS download_url,
                          gs.resource_id AS resource_id
                   FROM consoles c
                   LEFT JOIN games g ON g.console_id = c.id
                   LEFT JOIN collections col ON col.game_id = g.id
                   LEFT JOIN tracks t ON t.collection_id = col.id
                   LEFT JOIN local_files lf ON lf.track_id = t.id AND lf.is_available = 1
                   LEFT JOIN latest_game_audition lga ON lga.game_id = g.id
                   LEFT JOIN game_source gs ON gs.game_id = g.id
                   GROUP BY c.id, g.id
                   ORDER BY c.display_name, g.title"""
            ).fetchall()

            consoles = {}
            for row in rows:
                console_id = row["console_id"]
                console = consoles.setdefault(console_id, {
                    "id": console_id,
                    "display_name": row["console_name"],
                    "games": [],
                })
                if row["game_id"] is not None:
                    console["games"].append({
                        "id": row["game_id"],
                        "title": row["game_title"],
                        "track_count": row["track_count"] or 0,
                        "has_files": bool(row["has_files"]),
                        "audition_status": row["audition_status"],
                        "source_url": row["source_url"],
                        "download_url": row["download_url"],
                        "resource_id": row["resource_id"],
                    })
            return list(consoles.values())

    # ============================================
    # ACQUISITION DOMAIN
    # ============================================

    def add_source(self, name: str, base_url: str = "", source_type: str = "web") -> int:
        with self.connect() as conn:
            existing = conn.execute("SELECT id FROM sources WHERE name = ?", (name,)).fetchone()
            if existing:
                return existing["id"]
            cursor = conn.execute(
                "INSERT INTO sources (name, base_url, source_type) VALUES (?, ?, ?)",
                (name, base_url, source_type)
            )
            return cursor.lastrowid

    def get_source(self, source_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()
            return dict(row) if row else None

    def get_source_by_name(self, name: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM sources WHERE name = ?", (name,)).fetchone()
            return dict(row) if row else None

    def list_sources(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM sources ORDER BY name").fetchall()
            return [dict(r) for r in rows]

    def add_crawl_job(self, source_id: int, status: str = "pending") -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO crawl_jobs (source_id, status, started_at) VALUES (?, ?, ?)",
                (source_id, status, datetime.datetime.utcnow().isoformat())
            )
            return cursor.lastrowid

    def update_crawl_job(self, job_id: int, status: str, items_found: int = None, error_message: str = None):
        with self.connect() as conn:
            if items_found is not None:
                conn.execute(
                    "UPDATE crawl_jobs SET status = ?, items_found = ?, completed_at = ? WHERE id = ?",
                    (status, items_found, datetime.datetime.utcnow().isoformat(), job_id)
                )
            elif error_message is not None:
                conn.execute(
                    "UPDATE crawl_jobs SET status = ?, error_message = ?, completed_at = ? WHERE id = ?",
                    (status, error_message, datetime.datetime.utcnow().isoformat(), job_id)
                )
            else:
                conn.execute(
                    "UPDATE crawl_jobs SET status = ?, completed_at = ? WHERE id = ?",
                    (status, datetime.datetime.utcnow().isoformat(), job_id)
                )

    def add_resource_node(self, source_id: int, node_type: str, title: str = "",
                          url: str = "", download_url: str = "", parent_id: int = None,
                          crawl_job_id: int = None, archive_path: str = "",
                          size_bytes: int = None, format: str = "", confidence: float = 1.0) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """INSERT INTO resource_nodes
                   (source_id, crawl_job_id, parent_id, node_type, title, url,
                    download_url, archive_path, size_bytes, format, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (source_id, crawl_job_id, parent_id, node_type, title, url,
                 download_url, archive_path, size_bytes, format, confidence)
            )
            return cursor.lastrowid

    def get_resource_node(self, resource_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM resource_nodes WHERE id = ?", (resource_id,)).fetchone()
            return dict(row) if row else None

    def get_resource_parent(self, resource_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                """SELECT parent.*
                   FROM resource_nodes child
                   JOIN resource_nodes parent ON parent.id = child.parent_id
                   WHERE child.id = ?""",
                (resource_id,)
            ).fetchone()
            return dict(row) if row else None

    def find_resource_by_url(self, url: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM resource_nodes WHERE url = ?", (url,)).fetchone()
            return dict(row) if row else None

    def list_resources(self, source_id: int = None, node_type: str = None) -> list[dict]:
        with self.connect() as conn:
            query = "SELECT * FROM resource_nodes WHERE 1=1"
            params = []
            if source_id:
                query += " AND source_id = ?"
                params.append(source_id)
            if node_type:
                query += " AND node_type = ?"
                params.append(node_type)
            query += " ORDER BY discovered_at DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def link_resource_to_track(self, resource_id: int, track_id: int,
                               is_primary: int = 0, confidence: float = 1.0):
        with self.connect() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO resource_track_links
                   (resource_id, track_id, is_primary, confidence)
                   VALUES (?, ?, ?, ?)""",
                (resource_id, track_id, is_primary, confidence)
            )

    def link_resource_to_game(self, resource_id: int, game_id: int,
                              is_primary: int = 0, confidence: float = 1.0):
        """Link a raw acquisition resource to a catalog game.

        This is intentionally separate from catalog tables: the catalog keeps
        clean game identity, while acquisition keeps the exact pack/source that
        can retrieve it.
        """
        with self.connect() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO resource_game_links
                   (resource_id, game_id, is_primary, confidence)
                   VALUES (?, ?, ?, ?)""",
                (resource_id, game_id, is_primary, confidence)
            )

    def get_track_resources(self, track_id: int) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT rn.*, rtl.is_primary, rtl.confidence as link_confidence
                   FROM resource_track_links rtl
                   JOIN resource_nodes rn ON rtl.resource_id = rn.id
                   WHERE rtl.track_id = ?
                   ORDER BY rtl.is_primary DESC, rtl.confidence DESC""",
                (track_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_game_resources(self, game_id: int, include_failed: bool = False) -> list[dict]:
        with self.connect() as conn:
            failed_clause = "" if include_failed else (
                """AND NOT EXISTS (
                       SELECT 1 FROM audition_events ae
                       WHERE ae.resource_id = rn.id AND ae.status = 'failed'
                   )"""
            )
            rows = conn.execute(
                f"""SELECT rn.*, rgl.is_primary, rgl.confidence AS link_confidence
                    FROM resource_game_links rgl
                    JOIN resource_nodes rn ON rn.id = rgl.resource_id
                    WHERE rgl.game_id = ? {failed_clause}
                    ORDER BY rgl.is_primary DESC, rgl.confidence DESC, rn.confidence DESC, rn.discovered_at DESC""",
                (game_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def add_provenance_event(self, resource_id: int = None, track_id: int = None,
                             event_type: str = "", details: str = ""):
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO provenance_events (resource_id, track_id, event_type, details) VALUES (?, ?, ?, ?)",
                (resource_id, track_id, event_type, details)
            )

    def get_provenance(self, resource_id: int = None, track_id: int = None) -> list[dict]:
        with self.connect() as conn:
            query = "SELECT * FROM provenance_events WHERE 1=1"
            params = []
            if resource_id:
                query += " AND resource_id = ?"
                params.append(resource_id)
            if track_id:
                query += " AND track_id = ?"
                params.append(track_id)
            query += " ORDER BY created_at DESC"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    # ============================================
    # SUPPORTING TABLES
    # ============================================

    def add_retrieval_job(self, track_id: int, resource_id: int = None, status: str = "pending") -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO retrieval_jobs (track_id, resource_id, status, started_at) VALUES (?, ?, ?, ?)",
                (track_id, resource_id, status, datetime.datetime.utcnow().isoformat())
            )
            return cursor.lastrowid

    def update_retrieval_job(self, job_id: int, status: str, local_path: str = None, error_message: str = None):
        with self.connect() as conn:
            if local_path:
                conn.execute(
                    "UPDATE retrieval_jobs SET status = ?, local_path = ?, completed_at = ? WHERE id = ?",
                    (status, local_path, datetime.datetime.utcnow().isoformat(), job_id)
                )
            elif error_message:
                conn.execute(
                    "UPDATE retrieval_jobs SET status = ?, error_message = ?, completed_at = ? WHERE id = ?",
                    (status, error_message, datetime.datetime.utcnow().isoformat(), job_id)
                )
            else:
                conn.execute(
                    "UPDATE retrieval_jobs SET status = ?, completed_at = ? WHERE id = ?",
                    (status, datetime.datetime.utcnow().isoformat(), job_id)
                )

    def get_pending_retrieval_jobs(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM retrieval_jobs WHERE status = 'pending' ORDER BY created_at"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_active_retrieval_job(self, track_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                """SELECT * FROM retrieval_jobs
                   WHERE track_id = ? AND status IN ('pending', 'downloading')
                   ORDER BY created_at DESC
                   LIMIT 1""",
                (track_id,),
            ).fetchone()
            return dict(row) if row else None

    def add_local_file(self, track_id: int, file_path: str, size_bytes: int = None,
                       fingerprint: str = "", is_available: int = 1) -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO local_files
                   (track_id, file_path, size_bytes, fingerprint, is_available)
                   VALUES (?, ?, ?, ?, ?)""",
                (track_id, file_path, size_bytes, fingerprint, is_available)
            )
            return cursor.lastrowid

    def find_local_file(self, track_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM local_files WHERE track_id = ? AND is_available = 1",
                (track_id,)
            ).fetchone()
            return dict(row) if row else None

    def find_local_file_by_path(self, file_path: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM local_files WHERE file_path = ?",
                (file_path,)
            ).fetchone()
            return dict(row) if row else None

    def mark_file_unavailable(self, file_id: int):
        with self.connect() as conn:
            conn.execute(
                "UPDATE local_files SET is_available = 0 WHERE id = ?",
                (file_id,)
            )

    def add_audition_event(self, event_type: str, status: str,
                           resource_id: int = None, game_id: int = None,
                           track_id: int = None, details: dict | str = None) -> int:
        """Record a structured verification/audition outcome.

        Audition events sit in the supporting layer because they describe whether
        acquired resources are actually usable without changing catalog identity.
        """
        if isinstance(details, str):
            details_json = json.dumps({"message": details})
        else:
            details_json = json.dumps(details or {})

        with self.connect() as conn:
            cursor = conn.execute(
                """INSERT INTO audition_events
                   (resource_id, game_id, track_id, event_type, status, details_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (resource_id, game_id, track_id, event_type, status, details_json)
            )
            return cursor.lastrowid

    def get_audition_events(self, resource_id: int = None, game_id: int = None,
                            track_id: int = None, status: str = None) -> list[dict]:
        with self.connect() as conn:
            query = "SELECT * FROM audition_events WHERE 1=1"
            params = []
            if resource_id:
                query += " AND resource_id = ?"
                params.append(resource_id)
            if game_id:
                query += " AND game_id = ?"
                params.append(game_id)
            if track_id:
                query += " AND track_id = ?"
                params.append(track_id)
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY created_at DESC, id DESC"
            rows = conn.execute(query, params).fetchall()
            return [self._decode_audition_event(r) for r in rows]

    def get_latest_audition_event(self, resource_id: int = None, game_id: int = None,
                                  track_id: int = None) -> dict | None:
        events = self.get_audition_events(resource_id=resource_id, game_id=game_id, track_id=track_id)
        return events[0] if events else None

    def get_game_audition_status(self, game_id: int) -> str:
        latest = self.get_latest_audition_event(game_id=game_id)
        return latest["status"] if latest else "pending"

    def get_track_audition_status(self, track_id: int) -> str:
        latest = self.get_latest_audition_event(track_id=track_id)
        return latest["status"] if latest else "pending"

    def get_audition_status_counts(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT status, COUNT(*) AS count
                   FROM audition_events
                   GROUP BY status
                   ORDER BY count DESC, status"""
            ).fetchall()
            return [dict(r) for r in rows]

    def get_audition_source_stats(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT COALESCE(s.name, 'unknown') AS source,
                          ae.status,
                          COUNT(*) AS count
                   FROM audition_events ae
                   LEFT JOIN resource_nodes rn ON rn.id = ae.resource_id
                   LEFT JOIN sources s ON s.id = rn.source_id
                   GROUP BY COALESCE(s.name, 'unknown'), ae.status
                   ORDER BY source, count DESC, ae.status"""
            ).fetchall()
            return [dict(r) for r in rows]

    def get_audition_queue(self, status: str = "needs_audition", limit: int = 100) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT ae.id AS event_id,
                          ae.status,
                          ae.event_type,
                          ae.created_at,
                          ae.resource_id,
                          ae.game_id,
                          ae.track_id,
                          ae.details_json,
                          g.title AS game_title,
                          c.display_name AS console_name,
                          t.title AS track_title,
                          lf.file_path AS local_path,
                          s.name AS source_name
                   FROM audition_events ae
                   LEFT JOIN games g ON g.id = ae.game_id
                   LEFT JOIN consoles c ON c.id = g.console_id
                   LEFT JOIN tracks t ON t.id = ae.track_id
                   LEFT JOIN local_files lf ON lf.track_id = ae.track_id AND lf.is_available = 1
                   LEFT JOIN resource_nodes rn ON rn.id = ae.resource_id
                   LEFT JOIN sources s ON s.id = rn.source_id
                   WHERE ae.status = ?
                   ORDER BY ae.created_at DESC, ae.id DESC
                   LIMIT ?""",
                (status, limit)
            ).fetchall()
            return [self._decode_audition_event(r) for r in rows]

    @staticmethod
    def _decode_audition_event(row) -> dict:
        data = dict(row)
        try:
            data["details"] = json.loads(data.get("details_json") or "{}")
        except json.JSONDecodeError:
            data["details"] = {"raw": data.get("details_json") or ""}
        return data

    # ============================================
    # DISCOVERY ENGINE
    # ============================================

    def add_discovered_site(self, url: str, name: str = "", discovered_from: str = "",
                            confidence: float = 0.0, status: str = "candidate") -> int:
        with self.connect() as conn:
            existing = conn.execute("SELECT id FROM discovered_sites WHERE url = ?", (url,)).fetchone()
            if existing:
                return existing["id"]
            cursor = conn.execute(
                "INSERT INTO discovered_sites (url, name, discovered_from, confidence, status) VALUES (?, ?, ?, ?, ?)",
                (url, name, discovered_from, confidence, status)
            )
            return cursor.lastrowid

    def update_site_status(self, site_id: int, status: str, confidence: float = None,
                           profile_json: str = None, items_found: int = None):
        with self.connect() as conn:
            updates = ["status = ?", "last_checked = ?"]
            params = [status, datetime.datetime.utcnow().isoformat()]
            if confidence is not None:
                updates.append("confidence = ?")
                params.append(confidence)
            if profile_json is not None:
                updates.append("profile_json = ?")
                params.append(profile_json)
            if items_found is not None:
                updates.append("items_found = ?")
                params.append(items_found)
            params.append(site_id)
            conn.execute(f"UPDATE discovered_sites SET {', '.join(updates)} WHERE id = ?", params)

    def mark_site_crawled(self, site_id: int, items_found: int = 0):
        with self.connect() as conn:
            conn.execute(
                "UPDATE discovered_sites SET last_crawled = ?, items_found = ? WHERE id = ?",
                (datetime.datetime.utcnow().isoformat(), items_found, site_id)
            )

    def get_discovered_sites(self, status: str = None) -> list[dict]:
        with self.connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM discovered_sites WHERE status = ? ORDER BY confidence DESC",
                    (status,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM discovered_sites ORDER BY confidence DESC"
                ).fetchall()
            return [dict(r) for r in rows]

    def get_site_by_url(self, url: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM discovered_sites WHERE url = ?", (url,)).fetchone()
            return dict(row) if row else None

    def get_candidate_sites(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM discovered_sites WHERE status = 'candidate' ORDER BY confidence DESC"
            ).fetchall()
            return [dict(r) for r in rows]

    def get_active_sites(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM discovered_sites WHERE status = 'active' ORDER BY last_crawled ASC"
            ).fetchall()
            return [dict(r) for r in rows]

    # ============================================
    # STATISTICS
    # ============================================

    def get_stats(self) -> dict:
        with self.connect() as conn:
            return {
                "consoles": conn.execute("SELECT COUNT(*) FROM consoles").fetchone()[0],
                "games": conn.execute("SELECT COUNT(*) FROM games").fetchone()[0],
                "collections": conn.execute("SELECT COUNT(*) FROM collections").fetchone()[0],
                "tracks": conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0],
                "sources": conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
                "resource_nodes": conn.execute("SELECT COUNT(*) FROM resource_nodes").fetchone()[0],
                "crawl_jobs_running": conn.execute("SELECT COUNT(*) FROM crawl_jobs WHERE status = 'running'").fetchone()[0],
                "crawl_jobs_completed": conn.execute("SELECT COUNT(*) FROM crawl_jobs WHERE status = 'completed'").fetchone()[0],
                "crawl_jobs_failed": conn.execute("SELECT COUNT(*) FROM crawl_jobs WHERE status = 'failed'").fetchone()[0],
                "retrieval_jobs_pending": conn.execute("SELECT COUNT(*) FROM retrieval_jobs WHERE status = 'pending'").fetchone()[0],
                "retrieval_jobs_downloading": conn.execute("SELECT COUNT(*) FROM retrieval_jobs WHERE status = 'downloading'").fetchone()[0],
                "retrieval_jobs_completed": conn.execute("SELECT COUNT(*) FROM retrieval_jobs WHERE status = 'completed'").fetchone()[0],
                "retrieval_jobs_failed": conn.execute("SELECT COUNT(*) FROM retrieval_jobs WHERE status = 'failed'").fetchone()[0],
                "local_files": conn.execute("SELECT COUNT(*) FROM local_files WHERE is_available = 1").fetchone()[0],
                "audition_events": conn.execute("SELECT COUNT(*) FROM audition_events").fetchone()[0],
                "discovered_sites": conn.execute("SELECT COUNT(*) FROM discovered_sites").fetchone()[0],
                "active_sites": conn.execute("SELECT COUNT(*) FROM discovered_sites WHERE status = 'active'").fetchone()[0],
                "candidate_sites": conn.execute("SELECT COUNT(*) FROM discovered_sites WHERE status = 'candidate'").fetchone()[0],
            }
