"""Lazy game verification and file-row exposure for player browsing."""

import os
import re
import threading
from urllib.parse import unquote

from vgm_scraper.acquisition.downloader import Downloader
from vgm_scraper.acquisition.duration import DurationProbe
from vgm_scraper.acquisition.zip_probe import RemoteZipProbe
from vgm_scraper.config import AUDIO_EXTENSIONS


class GameVerifier:
    """Verify best game resource on demand and expose playable file rows."""

    def __init__(self, db, download_dir: str):
        self.db = db
        self.downloader = Downloader(download_dir)
        self.zip_probe = RemoteZipProbe()
        self.duration_probe = DurationProbe()

    def open_game(self, game_id: int, retry_failed: bool = False) -> dict:
        existing = self.db.list_player_files_for_game(game_id)
        if existing["files"] and not retry_failed:
            return {"status": "already_listed", **existing}

        resources = self.db.get_game_resources(game_id, include_failed=retry_failed)
        if not resources and not retry_failed:
            resources = self.db.get_game_resources(game_id, include_failed=True)
        if not resources:
            return {"status": "no_online_resource", **existing}

        for resource in resources:
            exposed = self._expose_resource_files(game_id, resource)
            if exposed:
                self._fetch_zophar_metadata(game_id, resource)
                self.db.add_audition_event(
                    resource_id=resource["id"],
                    game_id=game_id,
                    event_type="resource_verified",
                    status="obtaining_file",
                    details={"file_count": len(exposed), "method": "remote_listing"},
                )
                return {"status": "obtaining_file", **self.db.list_player_files_for_game(game_id)}

            self.db.add_audition_event(
                resource_id=resource["id"],
                game_id=game_id,
                event_type="resource_verification_failed",
                status="failed",
                details={"reason": "No compatible files found"},
            )

        return {"status": "failed", **self.db.list_player_files_for_game(game_id, include_short=True)}

    def _expose_resource_files(self, game_id: int, resource: dict) -> list[int]:
        download_url = resource.get("download_url") or resource.get("url") or ""
        if download_url.lower().split("?")[0].endswith(".zip"):
            members = self.zip_probe.list_supported_members(download_url)
            return self._create_member_tracks(game_id, resource, members)

        if self._is_supported_direct_file(download_url):
            return [self._create_direct_track(game_id, resource)]
        return []

    def _fetch_zophar_metadata(self, game_id: int, resource: dict):
        url = resource.get("url")
        if not url or "zophar.net/music/" not in url:
            return
            
        import urllib.request
        from bs4 import BeautifulSoup
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8')
                
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find the cover art
            cover_url = None
            cover_img = soup.select_one('#music_cover img')
            if cover_img and cover_img.has_attr('src'):
                cover_url = cover_img['src']
                
            # Find metadata table
            developer = None
            publisher = None
            release_year = None
            
            music_info = soup.select_one('#music_info')
            if music_info:
                for tr in music_info.select('tr'):
                    tds = tr.select('td')
                    if len(tds) >= 2:
                        label = tds[0].text.strip().lower()
                        value = tds[1].text.strip()
                        if 'developer' in label:
                            developer = value
                        elif 'publisher' in label:
                            publisher = value
                        elif 'release year' in label:
                            try:
                                release_year = int(value)
                            except ValueError:
                                pass
                                
            self.db.update_game_metadata(
                game_id,
                release_year=release_year,
                publisher=publisher,
                developer=developer,
                cover_art_url=cover_url
            )
        except Exception:
            pass

    def _create_member_tracks(self, game_id: int, archive_resource: dict, members) -> list[int]:
        collection_id = self.db.get_or_create_collection(
            game_id,
            archive_resource.get("title") or "Verified Archive",
            source_url=archive_resource.get("url") or archive_resource.get("download_url") or "",
        )
        track_ids = []
        source_id = archive_resource["source_id"]
        for member in members:
            member_resource_id = self.db.add_resource_node(
                source_id=source_id,
                parent_id=archive_resource["id"],
                node_type="archive_member",
                title=member.name,
                url=member.name,
                size_bytes=member.size,
                format=os.path.splitext(member.name.lower())[1],
                confidence=1.0,
            )
            track_id = self.db.get_or_create_track(
                title=self._display_title(member.name),
                collection_id=collection_id,
                game_id=game_id,
                track_number=member.index,
                format_hint=os.path.splitext(member.name.lower())[1],
                availability_status="obtaining_file",
            )
            self.db.link_resource_to_track(member_resource_id, track_id, is_primary=1, confidence=1.0)
            self.db.add_provenance_event(
                resource_id=member_resource_id,
                track_id=track_id,
                event_type="archive_member_listed",
                details=f"Listed from remote ZIP central directory: {member.name}",
            )
            track_ids.append(track_id)
        return track_ids

    def _create_direct_track(self, game_id: int, resource: dict) -> int:
        collection_id = self.db.get_or_create_collection(
            game_id,
            resource.get("title") or "Direct Files",
            source_url=resource.get("url") or resource.get("download_url") or "",
        )
        track_id = self.db.get_or_create_track(
            title=self._display_title(resource.get("title") or resource.get("download_url") or "Track"),
            collection_id=collection_id,
            game_id=game_id,
            track_number=1,
            format_hint=os.path.splitext((resource.get("download_url") or "").lower())[1],
            availability_status="obtaining_file",
        )
        self.db.link_resource_to_track(resource["id"], track_id, is_primary=1, confidence=1.0)
        return track_id

    def measure_cached_file_async(self, track_id: int, file_path: str):
        thread = threading.Thread(target=self._measure_cached_file, args=(track_id, file_path), daemon=True)
        thread.start()

    def _measure_cached_file(self, track_id: int, file_path: str):
        duration = self.duration_probe.probe(file_path)
        if duration is not None:
            self.db.update_track_duration(track_id, duration)

    @staticmethod
    def _is_supported_direct_file(url: str) -> bool:
        return os.path.splitext(url.lower().split("?")[0])[1] in AUDIO_EXTENSIONS

    @staticmethod
    def _display_title(path_or_url: str) -> str:
        name = unquote(path_or_url).replace("\\", "/").rstrip("/").split("/")[-1]
        stem = os.path.splitext(name)[0]
        stem = re.sub(r"^\d+[\s\-_.]+", "", stem)
        return stem or name or "Unknown Track"
