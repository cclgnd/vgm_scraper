"""
Retrieval manager for acquisition domain.

Handles on-demand retrieval of tracks: checks local availability,
creates retrieval jobs, downloads/extracts, and updates catalog.
"""

import os
import logging

from vgm_scraper.db.manager import DatabaseManager
from vgm_scraper.acquisition.downloader import Downloader
from vgm_scraper.acquisition.duration import DurationProbe

logger = logging.getLogger("vgm_scraper")


class RetrievalManager:
    """Manages on-demand retrieval of tracks from acquisition resources."""

    def __init__(self, db: DatabaseManager, download_dir: str):
        self.db = db
        self.downloader = Downloader(download_dir)
        self.duration_probe = DurationProbe()

    def request_track(self, track_id: int) -> dict:
        """
        Request a track for playback.
        Returns immediately with status and local path if available.

        Flow:
        1. Check if file already exists locally
        2. If not, find best resource source
        3. Create retrieval job
        4. Start download in background
        5. Return status
        """
        # Check local availability
        local_file = self.db.find_local_file(track_id)
        if local_file and os.path.exists(local_file["file_path"]):
            self.db.update_track_availability(track_id, "local")
            return {
                "status": "local",
                "local_path": local_file["file_path"],
                "track_id": track_id,
            }

        # Find resources for this track
        resources = self.db.get_track_resources(track_id)
        if not resources:
            return {
                "status": "no_source",
                "track_id": track_id,
                "message": "No acquisition source found for this track",
            }

        active_job = self.db.get_active_retrieval_job(track_id)
        if active_job:
            return {
                "status": "obtaining_file",
                "track_id": track_id,
                "job_id": active_job["id"],
                "resource_id": active_job["resource_id"],
                "message": f"Retrieval job already {active_job['status']}",
            }

        # Pick best resource (primary first, then highest confidence)
        best_resource = resources[0]

        # Create retrieval job
        job_id = self.db.add_retrieval_job(track_id, best_resource["id"], "pending")
        self.db.update_track_availability(track_id, "obtaining_file")

        return {
            "status": "obtaining_file",
            "track_id": track_id,
            "job_id": job_id,
            "resource_id": best_resource["id"],
            "message": "Retrieval job created",
        }

    def process_pending_jobs(self) -> list[dict]:
        """Process all pending retrieval jobs. Returns results."""
        jobs = self.db.get_pending_retrieval_jobs()
        results = []

        for job in jobs:
            result = self._process_job(job)
            results.append(result)

        return results

    def _process_job(self, job: dict) -> dict:
        """Process a single retrieval job."""
        job_id = job["id"]
        track_id = job["track_id"]
        resource_id = job["resource_id"]

        try:
            self.db.update_retrieval_job(job_id, "downloading")

            # Get resource details
            resource = self.db.get_resource_node(resource_id)
            if not resource:
                self.db.update_retrieval_job(job_id, "failed", error_message="Resource not found")
                return {"job_id": job_id, "status": "failed", "error": "Resource not found"}

            # Get track details
            track = self.db.get_track(track_id)
            if not track:
                self.db.update_retrieval_job(job_id, "failed", error_message="Track not found")
                return {"job_id": job_id, "status": "failed", "error": "Track not found"}

            context = self._get_track_context(track_id)
            download_resource = resource
            member_path = ""
            if resource["node_type"] == "archive_member":
                parent = self.db.get_resource_parent(resource_id)
                if not parent:
                    self.db.update_retrieval_job(job_id, "failed", error_message="Archive parent not found")
                    self.db.update_track_availability(track_id, "failed")
                    return {"job_id": job_id, "status": "failed", "error": "Archive parent not found"}
                download_resource = parent
                member_path = resource["url"] or resource["title"]

            pack_title = download_resource["title"] or track["title"]
            console_name = context.get("console") or "unknown"

            # Download and extract
            result = self.downloader.download_and_extract(
                url=download_resource["url"],
                download_url=download_resource["download_url"],
                title=pack_title,
                console=console_name,
            )

            if result["success"]:
                matched_files = self._match_result_files(result["files"], result["pack_dir"], member_path)
                if not matched_files:
                    self.db.update_retrieval_job(job_id, "failed", error_message="Requested file not found in archive")
                    self.db.update_track_availability(track_id, "failed")
                    return {"job_id": job_id, "status": "failed", "error": "Requested file not found in archive"}

                for filepath in matched_files:
                    fp = self.downloader.fingerprint_file(filepath)
                    size = os.path.getsize(filepath)
                    self.db.add_local_file(track_id, filepath, size, fp)
                    duration = self.duration_probe.probe(filepath)
                    if duration is not None:
                        self.db.update_track_duration(track_id, duration)

                self.db.update_retrieval_job(job_id, "completed", local_path=result["pack_dir"])
                self.db.update_track_availability(track_id, "local")
                self.db.add_audition_event(
                    resource_id=resource_id,
                    game_id=context.get("game_id"),
                    track_id=track_id,
                    event_type="retrieval_completed",
                    status="needs_audition",
                    details={
                        "local_path": result["pack_dir"],
                        "files": matched_files,
                        "archive_path": result.get("archive_path"),
                        "archive_member_count": result.get("archive_member_count", 0),
                        "skipped_file_count": len(result.get("skipped_files", [])),
                    },
                )
                self.db.add_provenance_event(
                    resource_id=resource_id,
                    track_id=track_id,
                    event_type="retrieved",
                    details=f"Downloaded to {result['pack_dir']}"
                )
                return {
                    "job_id": job_id,
                    "status": "local",
                    "local_path": result["pack_dir"],
                    "files": matched_files,
                }
            else:
                self.db.update_retrieval_job(job_id, "failed", error_message=result.get("error"))
                self.db.update_track_availability(track_id, "failed")
                self.db.add_audition_event(
                    resource_id=resource_id,
                    game_id=context.get("game_id"),
                    track_id=track_id,
                    event_type="retrieval_failed",
                    status="empty_extract" if result.get("archive_member_count", 0) else "failed",
                    details={
                        "error": result.get("error"),
                        "archive_path": result.get("archive_path"),
                        "archive_member_count": result.get("archive_member_count", 0),
                        "skipped_files": result.get("skipped_files", []),
                    },
                )
                return {"job_id": job_id, "status": "failed", "error": result.get("error")}

        except Exception as e:
            self.db.update_retrieval_job(job_id, "failed", error_message=str(e))
            self.db.update_track_availability(track_id, "failed")
            return {"job_id": job_id, "status": "failed", "error": str(e)}

    @staticmethod
    def _match_result_files(files: list[str], pack_dir: str, member_path: str = "") -> list[str]:
        existing = [f for f in files if os.path.exists(f)]
        if not member_path:
            return existing[:1] if existing else []

        normalized_member = member_path.replace("\\", "/").lower()
        for filepath in existing:
            rel = os.path.relpath(filepath, pack_dir).replace("\\", "/").lower()
            if rel == normalized_member:
                return [filepath]
        return []

    def _get_track_context(self, track_id: int) -> dict:
        """Look up catalog context without mixing it into acquisition tables."""
        with self.db.connect() as conn:
            row = conn.execute(
                """SELECT g.id AS game_id, g.title AS game, c.display_name AS console
                   FROM tracks t
                   LEFT JOIN games g ON g.id = t.game_id
                   LEFT JOIN consoles c ON c.id = g.console_id
                   WHERE t.id = ?""",
                (track_id,),
            ).fetchone()
            return dict(row) if row else {}

    def get_track_status(self, track_id: int) -> dict:
        """Get the current status of a track (local availability, retrieval jobs)."""
        local_file = self.db.find_local_file(track_id)
        jobs = self.db.get_pending_retrieval_jobs()
        track_jobs = [j for j in jobs if j["track_id"] == track_id]

        return {
            "track_id": track_id,
            "availability_status": "local" if local_file else self.db.get_track(track_id).get("availability_status"),
            "is_locally_available": local_file is not None,
            "local_path": local_file["file_path"] if local_file else None,
            "pending_jobs": len(track_jobs),
            "audition_status": self.db.get_track_audition_status(track_id),
            "latest_audition_event": self.db.get_latest_audition_event(track_id=track_id),
        }
