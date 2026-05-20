"""
VGMdb source adapter.
https://vgmdb.net - Video game music database (metadata-focused).

NOTE (2026-05-19): VGMdb returns 403 on all automated requests.
The site blocks non-browser user agents. Could potentially work
with proper browser headers or their API, but currently disabled.
"""

import re

from vgm_scraper.acquisition.sources.base import BaseSource, DiscoveredResource


class VGMdbSource(BaseSource):
    name = "vgmdb"
    base_url = "https://vgmdb.net"

    def discover(self, max_depth: int = 3) -> list[DiscoveredResource]:
        """Site blocks automated requests (403). Returns empty."""
        return []

    def search(self, query: str) -> list[DiscoveredResource]:
        """Site blocks automated requests (403). Returns empty."""
        return []
