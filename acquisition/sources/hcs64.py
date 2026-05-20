"""
HCS64 source adapter.
https://hcs64.com - Home to vgmstream and game music tools.

NOTE (2026-05-19): Site no longer hosts game music packs.
Individual format pages (usf.html, dsf.html, etc.) return 404.
The /files/ directory only contains dev tools and misc files.
This adapter is disabled and returns empty results.
"""

from vgm_scraper.acquisition.sources.base import BaseSource, DiscoveredResource


class Hcs64Source(BaseSource):
    name = "hcs64"
    base_url = "https://hcs64.com"

    def discover(self, max_depth: int = 3) -> list[DiscoveredResource]:
        """Site no longer hosts game music packs. Returns empty."""
        return []
