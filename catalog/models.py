"""
Catalog domain models.

Represents the clean, playable music library organized as:
Console → Game → Collection → Track
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Console:
    id: int = None
    slug: str = ""
    display_name: str = ""
    maker: str = ""
    generation: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "slug": self.slug,
            "display_name": self.display_name,
            "maker": self.maker,
            "generation": self.generation,
        }


@dataclass
class Game:
    id: int = None
    console_id: int = None
    title: str = ""
    release_year: int = None
    publisher: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "console_id": self.console_id,
            "title": self.title,
            "release_year": self.release_year,
            "publisher": self.publisher,
        }


@dataclass
class Collection:
    """A music pack/album containing multiple tracks from a game."""
    id: int = None
    game_id: int = None
    title: str = ""
    description: str = ""
    source_url: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "game_id": self.game_id,
            "title": self.title,
            "description": self.description,
            "source_url": self.source_url,
        }


@dataclass
class Track:
    id: int = None
    collection_id: int = None
    game_id: int = None
    title: str = ""
    track_number: int = None
    duration_seconds: float = None
    composer: str = ""
    format_hint: str = ""
    availability_status: str = "obtaining_file"
    is_locally_available: bool = False
    local_path: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "collection_id": self.collection_id,
            "game_id": self.game_id,
            "title": self.title,
            "track_number": self.track_number,
            "duration_seconds": self.duration_seconds,
            "composer": self.composer,
            "format_hint": self.format_hint,
            "availability_status": self.availability_status,
            "is_locally_available": self.is_locally_available,
            "local_path": self.local_path,
        }
