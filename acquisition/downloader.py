"""
Downloader for acquisition domain.

Handles downloading and extraction of resources.
"""

import os
import io
import time
import zipfile
import hashlib
import logging
from urllib.parse import unquote, urlparse
from email.message import Message

import requests

from vgm_scraper.config import DOWNLOAD_CHUNK_SIZE, AUDIO_EXTENSIONS, ARCHIVE_EXTENSIONS

logger = logging.getLogger("vgm_scraper")

STALE_TIMEOUT = 20  # seconds without data before aborting


class Downloader:
    """Downloads and extracts resources."""

    def __init__(self, download_dir: str):
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)

    def download(self, url: str, dest_dir: str) -> dict:
        """Download a file from URL into dest_dir using the remote filename.

        Uses a staleness-based timeout: only aborts if no data
        has been received for STALE_TIMEOUT seconds (default 20s).
        Large/slow downloads are allowed to continue as long as
        data keeps arriving.
        """
        result = {"success": False, "file_path": "", "error": None, "content_type": "", "final_url": url}
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            resp = requests.get(url, stream=True, headers=headers, timeout=30)
            resp.raise_for_status()
            result["content_type"] = resp.headers.get("Content-Type", "")
            result["final_url"] = resp.url

            filename = self._filename_from_response(url, resp)
            if not filename:
                result["error"] = "Download URL does not expose a real filename"
                return result

            dest_path = os.path.join(dest_dir, filename)
            result["file_path"] = dest_path

            last_activity = time.time()
            total_bytes = 0

            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        total_bytes += len(chunk)
                        last_activity = time.time()
                    else:
                        # Empty chunk — check staleness
                        if time.time() - last_activity > STALE_TIMEOUT:
                            logger.warning(f"Download stalled for {STALE_TIMEOUT}s: {url}")
                            result["error"] = "Download stalled"
                            return result

            result["success"] = os.path.exists(dest_path) and os.path.getsize(dest_path) > 0
            if not result["success"]:
                result["error"] = "Downloaded file is empty"
            return result
        except requests.exceptions.Timeout:
            logger.error(f"Download timed out (connection stalled): {url}")
            result["error"] = "Download timed out"
            return result
        except Exception as e:
            logger.error(f"Download failed: {url} - {e}")
            result["error"] = str(e)
            return result

    def _download_is_html(self, filepath: str) -> bool:
        try:
            with open(filepath, "rb") as f:
                head = f.read(512).lstrip().lower()
            return head.startswith(b"<!doctype html") or head.startswith(b"<html") or b"<head>" in head[:200]
        except Exception:
            return False

    def download_and_extract(self, url: str, download_url: str = "", title: str = "unknown",
                             console: str = "unknown") -> dict:
        """Download a pack, extract it, return info about extracted files."""
        console_dir = os.path.join(self.download_dir, self._safe_name(console))
        pack_dir = os.path.join(console_dir, self._safe_name(title))
        os.makedirs(pack_dir, exist_ok=True)

        dl_url = download_url or url

        result = {
            "success": False,
            "files": [],
            "error": None,
            "pack_dir": pack_dir,
            "archive_path": "",
            "archive_member_count": 0,
            "skipped_files": [],
            "download_url": dl_url,
        }

        try:
            download_result = self.download(dl_url, pack_dir)
            if not download_result["success"]:
                result["error"] = download_result.get("error") or "Download failed"
                return result
            filepath = download_result["file_path"]
            result["archive_path"] = filepath

            if self._download_is_html(filepath):
                result["error"] = "Downloaded HTML page instead of a playable file/archive"
                logger.warning("Downloaded HTML instead of media/archive for %s: %s", title, dl_url)
                return result

            if filepath.lower().endswith(".zip"):
                extracted, skipped, member_count = self._extract_zip(filepath, pack_dir)
                result["files"] = extracted
                result["skipped_files"] = skipped
                result["archive_member_count"] = member_count
            else:
                result["files"] = [filepath]

            if not result["files"]:
                result["error"] = "No supported audio or archive files were extracted"
                logger.warning(
                    "Download produced no playable files for %s: %s (%s archive members, %s skipped)",
                    title,
                    filepath,
                    result["archive_member_count"],
                    len(result["skipped_files"]),
                )
                return result

            result["success"] = True
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Download failed for {title}: {e}")

        return result

    def _extract_zip(self, zip_path: str, extract_dir: str) -> tuple[list[str], list[str], int]:
        extracted = []
        skipped = []
        member_count = 0
        try:
            with zipfile.ZipFile(zip_path) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    member_count += 1
                    name = info.filename
                    ext = os.path.splitext(name)[1].lower()
                    if ext in AUDIO_EXTENSIONS or ext in ARCHIVE_EXTENSIONS:
                        zf.extract(info, extract_dir)
                        full_path = os.path.join(extract_dir, name)
                        extracted.append(full_path)
                    else:
                        skipped.append(name)
        except Exception as e:
            logger.error(f"Extraction error: {e}")
        return extracted, skipped, member_count

    @staticmethod
    def fingerprint_file(filepath: str) -> str:
        hasher = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return ""

    @staticmethod
    def _safe_name(name: str) -> str:
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in name)
        return safe[:100] or "unknown"

    def _filename_from_response(self, requested_url: str, resp) -> str:
        disposition_name = self._filename_from_content_disposition(resp.headers.get("Content-Disposition", ""))
        if disposition_name:
            return self._safe_remote_filename(disposition_name)

        final_name = self._filename_from_url(resp.url)
        if final_name:
            return self._safe_remote_filename(final_name)

        requested_name = self._filename_from_url(requested_url)
        if requested_name:
            return self._safe_remote_filename(requested_name)
        return ""

    @staticmethod
    def _filename_from_content_disposition(value: str) -> str:
        if not value:
            return ""
        msg = Message()
        msg["content-disposition"] = value
        filename = msg.get_filename()
        return unquote(filename) if filename else ""

    @staticmethod
    def _filename_from_url(url: str) -> str:
        name = unquote(os.path.basename(urlparse(url).path))
        if not name or "." not in name:
            return ""
        return name

    @staticmethod
    def _safe_remote_filename(name: str) -> str:
        return os.path.basename(name.replace("\\", "/")).strip()
