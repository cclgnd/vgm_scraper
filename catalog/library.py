"""
Catalog domain library manager.

Handles browsing, filtering, and organizing the music library.
Links catalog items to acquisition resources.
"""

from vgm_scraper.db.manager import DatabaseManager
from vgm_scraper.catalog.models import Console, Game, Collection, Track


class LibraryManager:
    """Manages the catalog domain: consoles, games, collections, tracks."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    # Console operations

    def add_console(self, slug: str, display_name: str, maker: str = "", generation: str = "") -> int:
        return self.db.add_console(slug, display_name, maker, generation)

    def get_console(self, console_id: int) -> Console | None:
        data = self.db.get_console(console_id)
        return Console(**data) if data else None

    def get_console_by_slug(self, slug: str) -> Console | None:
        data = self.db.get_console_by_slug(slug)
        return Console(**data) if data else None

    def list_consoles(self) -> list[Console]:
        return [Console(**d) for d in self.db.list_consoles()]

    # Game operations

    def add_game(self, console_id: int, title: str, release_year: int = None, publisher: str = "") -> int:
        return self.db.add_game(console_id, title, release_year, publisher)

    def get_game(self, game_id: int) -> Game | None:
        data = self.db.get_game(game_id)
        return Game(**data) if data else None

    def list_games(self, console_id: int = None) -> list[Game]:
        return [Game(**d) for d in self.db.list_games(console_id)]

    # Collection operations

    def add_collection(self, game_id: int, title: str, description: str = "", source_url: str = "") -> int:
        return self.db.add_collection(game_id, title, description, source_url)

    def get_collection(self, collection_id: int) -> Collection | None:
        data = self.db.get_collection(collection_id)
        return Collection(**data) if data else None

    def list_collections(self, game_id: int = None) -> list[Collection]:
        return [Collection(**d) for d in self.db.list_collections(game_id)]

    # Track operations

    def add_track(self, title: str, collection_id: int = None, game_id: int = None,
                  track_number: int = None, duration_seconds: float = None,
                  composer: str = "", format_hint: str = "") -> int:
        return self.db.add_track(title, collection_id, game_id, track_number,
                                 duration_seconds, composer, format_hint)

    def get_track(self, track_id: int) -> Track | None:
        data = self.db.get_track(track_id)
        if not data:
            return None
        track = Track(**data)
        local_file = self.db.find_local_file(track_id)
        if local_file:
            track.is_locally_available = True
            track.local_path = local_file["file_path"]
        return track

    def list_tracks(self, collection_id: int = None, game_id: int = None) -> list[Track]:
        tracks_data = self.db.list_tracks(collection_id, game_id)
        tracks = []
        for data in tracks_data:
            track = Track(**data)
            local_file = self.db.find_local_file(track.id)
            if local_file:
                track.is_locally_available = True
                track.local_path = local_file["file_path"]
            tracks.append(track)
        return tracks

    # Hierarchy operations

    def get_full_tree(self) -> list[dict]:
        """Returns full catalog hierarchy with local availability status."""
        tree = self.db.get_catalog_tree()
        for console in tree:
            for game in console.get("games", []):
                game["audition_status"] = self.db.get_game_audition_status(game["id"])
                for coll in game.get("collections", []):
                    for track in coll.get("tracks", []):
                        local_file = self.db.find_local_file(track["id"])
                        track["is_locally_available"] = local_file is not None
                        track["local_path"] = local_file["file_path"] if local_file else ""
                        track["audition_status"] = self.db.get_track_audition_status(track["id"])
        return tree

    def search(self, query: str) -> list[dict]:
        """Search across consoles, games, collections, and tracks."""
        results = []
        query_lower = query.lower()

        for console in self.list_consoles():
            if query_lower in console.display_name.lower() or query_lower in console.maker.lower():
                results.append({"type": "console", "data": console.to_dict()})

        for game in self.list_games():
            if query_lower in game.title.lower():
                results.append({"type": "game", "data": game.to_dict()})

        for track in self.list_tracks():
            if query_lower in track.title.lower() or query_lower in track.composer.lower():
                results.append({"type": "track", "data": track.to_dict()})

        return results

    def get_or_create_console(self, slug: str, display_name: str, maker: str = "", generation: str = "") -> int:
        existing = self.db.get_console_by_slug(slug)
        if existing:
            return existing["id"]
        return self.db.add_console(slug, display_name, maker, generation)

    def get_or_create_game(self, console_id: int, title: str, release_year: int = None, publisher: str = "") -> int:
        games = self.db.list_games(console_id)
        for game in games:
            if game["title"].lower() == title.lower():
                return game["id"]
        return self.db.add_game(console_id, title, release_year, publisher)
