import os
import zipfile
import re
from chiptunepalace.db.orm_stubs import DatabaseManager, Track


SUPPORTED_EXTS = {
    # SNES
    '.spc',
    # NES
    '.nsf', '.nsfe',
    # Game Boy / Game Boy Color
    '.gbs',
    # Game Boy Advance
    '.gsf', '.minigsf',
    # Nintendo DS
    '.2sf', '.mini2sf',
    # Nintendo 64
    '.usf', '.miniusf',
    # Sega Genesis / Mega Drive
    '.vgm', '.vgz', '.gym',
    # Sega Master System / Game Gear
    '.sgc',
    # Sega Saturn
    '.ssf', '.minissf',
    # Sega Dreamcast
    '.dsf', '.minidsf',
    # Sony PlayStation
    '.psf', '.minipsf',
    # Sony PlayStation 2
    '.psf2', '.minipsf2',
    # PC Engine / TurboGrafx-16
    '.hes',
    # Atari ST / Amstrad CPC / ZX Spectrum
    '.ym', '.vtx',
    # Commodore 64 / SID
    '.sid',
    # Amiga Tracker / ProTracker modules
    '.mod', '.xm', '.it', '.s3m',
    # Other classic module formats
    '.stm', '.mtm', '.okt', '.med',
    # Standard modern formats (natively decoded by VLC)
    '.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma'
}


class TrackService:
    """Handles all database interactions and indexing related to tracks."""

    def __init__(self):
        self.db_manager = DatabaseManager()

    def get_all_tracks(self):
        """Returns a list of dicts, one per track."""
        return self.db_manager.get_all_tracks()

    def get_track_by_id(self, track_id: int):
        """Returns a single track dict or None."""
        return self.db_manager.get_track_by_id(track_id)

    def add_track(self, title: str, artist: str, file_path: str, **kwargs):
        """Adds a new track; returns the track_id."""
        return self.db_manager.add_track(title, artist, file_path, **kwargs)

    @staticmethod
    def _safe_text(value: str) -> str:
        """
        Normalizes text to a DB-safe UTF-8 round-trip string.
        This prevents rare malformed filenames from aborting ZIP indexing.
        """
        if value is None:
            return ""
        return str(value).encode("utf-8", "replace").decode("utf-8")

    def index_zip_pack(self, zip_path: str, console_name: str, game_name: str, source_url: str = None) -> list:
        """
        Scans a downloaded ZIP file for track extensions, calculates MD5 content fingerprints,
        and adds them to the database for instant ZIP streaming.
        Supports both valid multi-track ZIP archives and single raw audio/tracker file downloads.
        """
        indexed_ids = []
        fingerprint = self.db_manager.get_fingerprint(zip_path)
        
        # Check if the file is a raw chiptune/tracker file rather than a ZIP archive
        if not zipfile.is_zipfile(zip_path):
            ext = ".vgm" # Default fallback
            try:
                if os.path.exists(zip_path):
                    with open(zip_path, "rb") as f:
                        header = f.read(1084)
                    if header.startswith(b"Extended Module:"):
                        ext = ".xm"
                    elif header.startswith(b"IMPM"):
                        ext = ".it"
                    elif len(header) >= 48 and b"SCRM" in header[44:48]:
                        ext = ".s3m"
                    elif header.startswith(b"VGM ") or header.startswith(b"\x1f\x8b"):
                        ext = ".vgm"
                    elif header.startswith(b"NESM\x1a"):
                        ext = ".nsf"
                    elif header.startswith(b"SNES-SPC700"):
                        ext = ".spc"
                    elif header.startswith(b"PSF"):
                        ext = ".psf"
                    elif len(header) >= 1084 and any(tag in header[1080:1084] for tag in [b"M.K.", b"M!K!", b"4CHN", b"6CHN", b"8CHN", b"FLT4", b"FLT8"]):
                        ext = ".mod"
            except Exception as e:
                print(f"TrackService: Header detection error: {e}")
            
            if ext == ".vgm" and source_url:
                for e in SUPPORTED_EXTS:
                    if e in source_url.lower():
                        ext = e
                        break
                if ext == ".vgm" and "modarchive" in source_url.lower():
                    ext = ".mod"
                    
            correct_path = zip_path
            if zip_path.endswith('.zip'):
                correct_path = zip_path[:-4]
            if not correct_path.lower().endswith(ext):
                correct_path += ext
                
            try:
                if os.path.exists(zip_path):
                    if os.path.exists(correct_path):
                        os.remove(correct_path)
                    os.rename(zip_path, correct_path)
                    print(f"TrackService: Renamed raw download {zip_path} -> {correct_path}")
            except Exception as e:
                print(f"TrackService: Failed to rename file: {e}")
                correct_path = zip_path
                
            title = game_name
            title = re.sub(r'^\d+[\s\-_]*', '', title).replace('_', ' ').strip()
            
            track_id = self.db_manager.add_track(
                title=title,
                artist="Various",
                console=console_name,
                game=game_name,
                file_path=correct_path,
                member_name=None,
                fingerprint=fingerprint,
                source_url=source_url,
                format=ext[1:].upper()
            )
            indexed_ids.append(track_id)
            print(f"TrackService: Indexed 1 raw track from {correct_path}")
            return indexed_ids

        # Otherwise, process as standard ZIP archive
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                failed_members = 0
                for member in zf.namelist():
                    # Normalize extension checking
                    ext = os.path.splitext(member)[1].lower()
                    if ext in SUPPORTED_EXTS:
                        safe_member = self._safe_text(member)
                        base_name = os.path.basename(safe_member)
                        if not base_name:
                            continue
                        
                        # Extract title and clean it up
                        title = os.path.splitext(base_name)[0]
                        # Strip common track number prefixes like "01 - ", "04_", etc.
                        title = re.sub(r'^\d+[\s\-_]*', '', title).replace('_', ' ').strip()
                        title = self._safe_text(title)
                        
                        # Add track to DB (duplicate avoidance handled by add_track internally).
                        # Important: continue indexing even if one member fails.
                        try:
                            track_id = self.db_manager.add_track(
                                title=title,
                                artist="Various",
                                console=self._safe_text(console_name),
                                game=self._safe_text(game_name),
                                file_path=zip_path,
                                member_name=safe_member,
                                fingerprint=fingerprint,
                                source_url=source_url,
                                format=ext[1:].upper()
                            )
                            indexed_ids.append(track_id)
                        except Exception as member_err:
                            failed_members += 1
                            print(f"TrackService: Failed to index member '{safe_member}' in {zip_path}: {member_err}")
                if failed_members:
                    print(f"TrackService: ZIP indexing completed with {failed_members} member errors for {zip_path}")
            print(f"TrackService: Indexed {len(indexed_ids)} tracks from ZIP {zip_path}")
        except Exception as e:
            print(f"TrackService: Failed to index ZIP {zip_path}: {e}")
        return indexed_ids

    def get_tracks_by_console_and_game(self, console_name: str, game_name: str) -> list:
        """Returns all tracks belonging to a specific console and game."""
        session = self.db_manager.Session()
        try:
            tracks = session.query(Track).filter(
                Track.console == console_name,
                Track.game == game_name
            ).order_by(Track.title).all()
            if tracks:
                return [self.db_manager._to_dict(t) for t in tracks]

            # Explorer nodes can come from different sources/caches, so console
            # and game labels may vary by case, markup, or source suffix.
            def normalize(value):
                value = re.sub(r'<[^<]+?>', '', str(value or ""))
                value = re.sub(r'\([^)]*\)', '', value)
                return re.sub(r'[^a-z0-9]', '', value.lower())

            target_console = normalize(console_name)
            target_game = normalize(game_name)
            if not target_console or not target_game:
                return []

            candidates = session.query(Track).order_by(Track.title).all()
            fuzzy_tracks = []
            for t in candidates:
                candidate_console = normalize(t.console)
                candidate_game = normalize(t.game)
                console_matches = (
                    candidate_console == target_console
                    or target_console in candidate_console
                    or candidate_console in target_console
                )
                game_matches = (
                    candidate_game == target_game
                    or target_game in candidate_game
                    or candidate_game in target_game
                )
                if console_matches and game_matches:
                    fuzzy_tracks.append(t)
            return [self.db_manager._to_dict(t) for t in fuzzy_tracks]
        finally:
            session.close()

    def get_library_hierarchy(self) -> dict:
        """
        Returns a nested dictionary representing the local library catalog:
        { ConsoleName: { GameName: [TrackDicts] } }
        """
        all_tracks = self.get_all_tracks()
        catalog = {}
        for t in all_tracks:
            console = t.get('console', 'Unknown Console')
            game = t.get('game', 'Unknown Game')
            if console not in catalog:
                catalog[console] = {}
            if game not in catalog[console]:
                catalog[console][game] = []
            catalog[console][game].append(t)
        return catalog
