"""
SNESmusic source adapter.
https://www.snesmusic.org - Super Nintendo music archive.

Updated 2026-05-19: Fixed URL structure to use sets browsing.
"""

import re

from vgm_scraper.acquisition.sources.base import BaseSource, DiscoveredResource


class SNESmusicSource(BaseSource):
    name = "snesmusic"
    base_url = "https://www.snesmusic.org"

    def discover(self, max_depth: int = 3) -> list[DiscoveredResource]:
        results = []
        # Browse by character (A-Z, 0-9)
        chars = ["n1-9"] + [chr(c) for c in range(ord("A"), ord("Z") + 1)]
        # max_depth=1 → 10 chars, 2 → 20 chars, 3 → all 27
        max_chars = max(10, max_depth * 9)
        chars = chars[:max_chars]

        for char in chars:
            url = f"{self.base_url}/v2/select.php?view=sets&char={char}&limit=0"
            soup = self.session.get_soup(url)
            if not soup:
                continue

            for a in soup.find_all("a", href=lambda x: x and "profile.php?profile=set" in x):
                title = a.text.strip()
                href = a.get("href", "")
                if title and len(title) > 1 and "company" not in href and "composer" not in href:
                    detail_url = self.session.resolve_url(href, self.base_url)
                    results.append(DiscoveredResource(
                        title=title, url=detail_url,
                        node_type="pack", metadata={"console": "Nintendo Super Nintendo Entertainment System"},
                    ))

        return results
