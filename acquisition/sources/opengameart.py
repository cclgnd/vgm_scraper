"""
OpenGameArt source adapter.
https://opengameart.org - Free game art and music.

NOTE (2026-05-19): Search results are rendered via JavaScript/AJAX
and cannot be scraped via simple HTTP requests. Returns empty.
"""

from vgm_scraper.acquisition.sources.base import BaseSource, DiscoveredResource


class OpenGameArtSource(BaseSource):
    name = "opengameart"
    base_url = "https://opengameart.org"

    def discover(self, max_depth: int = 3) -> list[DiscoveredResource]:
        """Search results require JS rendering. Returns empty."""
        return []
