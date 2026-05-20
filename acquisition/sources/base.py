"""
Base class for all acquisition sources.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from vgm_scraper.core import ScraperSession
from vgm_scraper.db.manager import DatabaseManager


@dataclass
class DiscoveredResource:
    """A resource discovered by a source adapter."""
    title: str
    url: str
    download_url: str = ""
    node_type: str = "pack"
    parent_url: str = ""
    parent_id: int = None
    size_bytes: int = None
    format: str = ""
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "download_url": self.download_url,
            "node_type": self.node_type,
            "parent_url": self.parent_url,
            "parent_id": self.parent_id,
            "size_bytes": self.size_bytes,
            "format": self.format,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


class BaseSource(ABC):
    """Abstract base class for VGM music sources."""

    name: str = "base"
    base_url: str = ""
    source_type: str = "web"

    def __init__(self, session: ScraperSession, db: DatabaseManager):
        self.session = session
        self.db = db
        self._source_id: int | None = None

    @property
    def source_id(self) -> int:
        if self._source_id is None:
            self._source_id = self.db.add_source(self.name, self.base_url, self.source_type)
        return self._source_id

    @abstractmethod
    def discover(self, max_depth: int = 3) -> list[DiscoveredResource]:
        """Discover resources from this source. Returns list of DiscoveredResource."""
        pass

    def get_tracks(self, resource: DiscoveredResource) -> list[DiscoveredResource]:
        """Get individual tracks from a pack/album resource. Override if source provides track listings."""
        return []

    def search(self, query: str) -> list[DiscoveredResource]:
        """Search for resources. Override if source supports search."""
        return []

    def log_provenance(self, resource_id: int, event_type: str, details: str = ""):
        self.db.add_provenance_event(resource_id=resource_id, event_type=event_type, details=details)
