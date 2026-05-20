"""
Local folder scanner for acquisition domain.

Scans local directories for VGM/audio files and folders,
applies heuristics to identify game music, and tracks provenance.
Populates both acquisition and catalog domains for high-confidence matches.
"""

import os
import re
import logging
import hashlib
from pathlib import Path

from vgm_scraper.db.manager import DatabaseManager
from vgm_scraper.config import AUDIO_EXTENSIONS
from vgm_scraper.catalog.library import LibraryManager
from vgm_scraper.acquisition.console_classifier import classify_console

logger = logging.getLogger("vgm_scraper")


class LocalScanner:
    """Scans local folders for VGM files and identifies game music."""

    SOUNDTRACK_KEYWORDS = ("ost", "bgm", "soundtrack", "gamerip", "rip", "music", "sound", "audio")

    CATALOG_CONFIDENCE_THRESHOLD = 0.5

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.library = LibraryManager(db)

    def scan_directory(self, directory: str, source_name: str = "local") -> list[dict]:
        """
        Scan a directory for VGM files.
        Returns list of discovered resources with confidence scores.
        For high-confidence matches, also populates the catalog domain.
        """
        directory = os.path.abspath(directory)
        if not os.path.isdir(directory):
            logger.error(f"Directory not found: {directory}")
            return []

        source_id = self.db.add_source(source_name, directory, "local")
        crawl_job_id = self.db.add_crawl_job(source_id, "running")

        discovered = []
        for root, dirs, files in os.walk(directory):
            audio_files = [f for f in files if self._is_audio_file(f)]

            if audio_files:
                confidence, evidence = self._score_folder(root, audio_files)

                resource_id = self.db.add_resource_node(
                    source_id=source_id,
                    crawl_job_id=crawl_job_id,
                    node_type="folder",
                    title=os.path.basename(root),
                    url=root,
                    size_bytes=sum(os.path.getsize(os.path.join(root, f)) for f in audio_files),
                    confidence=confidence,
                )

                # For high-confidence matches, populate catalog domain
                created_tracks = []
                if confidence >= self.CATALOG_CONFIDENCE_THRESHOLD:
                    created_tracks = self._populate_catalog_from_folder(root, audio_files, resource_id, evidence)
                    self.db.add_audition_event(
                        resource_id=resource_id,
                        game_id=created_tracks[0]["game_id"] if created_tracks else None,
                        event_type="local_folder_verified",
                        status="needs_audition",
                        details={
                            "folder_path": root,
                            "confidence": confidence,
                            "evidence": evidence,
                            "audio_file_count": len(audio_files),
                        },
                    )

                for filename in audio_files:
                    filepath = os.path.join(root, filename)
                    file_id = self.db.add_resource_node(
                        source_id=source_id,
                        crawl_job_id=crawl_job_id,
                        parent_id=resource_id,
                        node_type="file",
                        title=filename,
                        url=filepath,
                        size_bytes=os.path.getsize(filepath),
                        format=os.path.splitext(filename)[1].lower(),
                    )

                    # Register as local file if catalog entry exists
                    track_id = self._find_matching_track(root, filename)
                    if track_id:
                        fp = self._fingerprint_file(filepath)
                        size = os.path.getsize(filepath)
                        self.db.add_local_file(track_id, filepath, size, fp)
                        self.db.link_resource_to_track(file_id, track_id, is_primary=1)
                        self.db.add_audition_event(
                            resource_id=file_id,
                            track_id=track_id,
                            event_type="local_track_discovered",
                            status="needs_audition",
                            details={
                                "file_path": filepath,
                                "size_bytes": size,
                                "format": os.path.splitext(filename)[1].lower(),
                                "folder_confidence": confidence,
                            },
                        )

                    self.db.add_provenance_event(
                        resource_id=file_id,
                        event_type="discovered",
                        details=f"Found in {root} (confidence: {confidence:.2f}, evidence: {', '.join(evidence)})"
                    )

                discovered.append({
                    "path": root,
                    "files": audio_files,
                    "confidence": confidence,
                    "evidence": evidence,
                    "resource_id": resource_id,
                })

        self.db.update_crawl_job(crawl_job_id, "completed", items_found=len(discovered))
        return discovered

    def _populate_catalog_from_folder(self, folder_path: str, files: list[str],
                                       folder_resource_id: int, evidence: list[str]):
        """Create catalog entries from a high-confidence local folder."""
        folder_name = os.path.basename(folder_path)
        parent_name = os.path.basename(os.path.dirname(folder_path))

        console_match = classify_console(folder_name, parent_name, folder_path)

        # Use parent folder as game title, current folder as collection
        game_title = parent_name if parent_name else folder_name
        collection_title = folder_name

        console_id = self.library.get_or_create_console(
            console_match.slug,
            console_match.canonical_name,
            console_match.maker,
        )
        game_id = self.library.get_or_create_game(console_id, game_title)
        self.db.link_resource_to_game(folder_resource_id, game_id, is_primary=1, confidence=console_match.confidence)
        collection_id = self.db.get_or_create_collection(game_id, collection_title, source_url=folder_path)
        created_tracks = []

        # Create track entries for each file
        for i, filename in enumerate(sorted(files), 1):
            title = os.path.splitext(filename)[0]
            # Clean up track numbers from filename
            title = re.sub(r"^\d+[\s\-\._]+", "", title).strip()
            if not title:
                title = filename

            fmt = os.path.splitext(filename)[1].lower()
            track_id = self.db.get_or_create_track(
                title=title,
                collection_id=collection_id,
                game_id=game_id,
                track_number=i,
                format_hint=fmt,
            )

            # Link folder resource to this track
            self.db.link_resource_to_track(folder_resource_id, track_id, is_primary=1)
            self.db.add_provenance_event(
                resource_id=folder_resource_id,
                track_id=track_id,
                event_type="track_discovered_local",
                details=f"Local track '{title}' from {folder_path}"
            )
            created_tracks.append({"track_id": track_id, "game_id": game_id})

        return created_tracks

    def _find_matching_track(self, folder_path: str, filename: str) -> int | None:
        """Find an existing catalog track that matches this local file."""
        title = os.path.splitext(filename)[0]
        title = re.sub(r"^\d+[\s\-\._]+", "", title).strip()
        if not title:
            return None

        # Search within the same local collection first. Generic titles like
        # "Title" and "Opening" are common across games and should not link globally.
        with self.db.connect() as conn:
            row = conn.execute(
                """SELECT t.id
                   FROM tracks t
                   JOIN collections c ON c.id = t.collection_id
                   WHERE t.title = ? AND c.source_url = ?
                   LIMIT 1""",
                (title, folder_path)
            ).fetchone()
            return row["id"] if row else None

    @staticmethod
    def _fingerprint_file(filepath: str) -> str:
        hasher = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""

    def _is_audio_file(self, filename: str) -> bool:
        ext = os.path.splitext(filename)[1].lower()
        return ext in AUDIO_EXTENSIONS

    def _score_folder(self, folder_path: str, files: list[str]) -> tuple[float, list[str]]:
        """Score a folder's likelihood of containing game music."""
        folder_name = os.path.basename(folder_path).lower()
        parent_name = os.path.basename(os.path.dirname(folder_path)).lower()
        combined = f"{parent_name} {folder_name}"

        score = 0.0
        evidence = []

        console_match = classify_console(combined)
        if console_match.is_known:
            score += 0.3
            evidence.append(f"platform:{console_match.slug}")
            evidence.extend(console_match.evidence)

        # Check for soundtrack keywords
        for keyword in self.SOUNDTRACK_KEYWORDS:
            if keyword in combined:
                score += 0.2
                evidence.append(f"keyword:{keyword}")
                break

        # Check for track-numbered files
        track_pattern = re.compile(r"^\d+[\s\-\._]")
        numbered = sum(1 for f in files if track_pattern.match(f))
        if numbered > 0:
            ratio = numbered / len(files)
            score += ratio * 0.3
            evidence.append(f"track_numbered:{numbered}/{len(files)}")

        # Check for VGM-specific extensions
        vgm_exts = {".vgm", ".vgz", ".spc", ".nsf", ".usf", ".psf", ".ssf", ".dsf"}
        vgm_files = sum(1 for f in files if os.path.splitext(f)[1].lower() in vgm_exts)
        if vgm_files > 0:
            ratio = vgm_files / len(files)
            score += ratio * 0.2
            evidence.append(f"vgm_format:{vgm_files}/{len(files)}")

        # Bonus for multiple audio files
        if len(files) > 5:
            score += 0.1
            evidence.append("multiple_files")

        score = min(score, 1.0)
        return score, evidence

    @staticmethod
    def _slugify(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
        return slug.strip("-") or "unknown"
