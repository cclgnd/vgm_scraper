"""
Project 2612 source adapter.
http://project2612.org - Sega Genesis/Mega Drive music archive.

NOTE (2026-05-19): Site is down (returns default nginx page).
Returns empty results.
"""

import re

from vgm_scraper.acquisition.sources.base import BaseSource, DiscoveredResource


class Project2612Source(BaseSource):
    name = "project2612"
    base_url = "http://project2612.org"

    def discover(self, max_depth: int = 3) -> list[DiscoveredResource]:
        """Site is down. Returns empty."""
        return []

    def search(self, query: str) -> list[DiscoveredResource]:
        """Site is down. Returns empty."""
        return []
