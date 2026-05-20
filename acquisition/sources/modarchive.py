"""
ModArchive source adapter.
https://modarchive.org - Tracker module music archive.
"""

import re

from vgm_scraper.acquisition.sources.base import BaseSource, DiscoveredResource


class ModArchiveSource(BaseSource):
    name = "modarchive"
    base_url = "https://modarchive.org"

    def discover(self, max_depth: int = 3) -> list[DiscoveredResource]:
        resources = []
        genres = [
            ("Chiptune", "https://modarchive.org/index.php?request=view_genres&query=14"),
            ("Demo", "https://modarchive.org/index.php?request=view_genres&query=18"),
            ("Keygen", "https://modarchive.org/index.php?request=view_genres&query=57"),
        ]

        for genre_name, genre_url in genres:
            try:
                soup = self.session.get_soup(genre_url)
                if not soup:
                    continue
                for a in soup.find_all("a", href=re.compile(r"moduleid=\d+")):
                    href = a.get("href", "")
                    if "downloads.php" in href:
                        title_link = a.find_next("a", class_="standard-link")
                        title = title_link.text.strip() if title_link else "Unknown Module"
                        resources.append(DiscoveredResource(
                            title=title, url=href, download_url=href,
                            node_type="track",
                            metadata={"console": f"ModArchive: {genre_name}", "format": "mod"},
                        ))
            except Exception:
                continue

        return resources

    def search(self, query: str) -> list[DiscoveredResource]:
        import urllib.parse
        url = f"{self.base_url}/index.php?request=search&query={urllib.parse.quote(query)}&submit=Find&search_type=filename_or_songtitle"
        results = []
        try:
            soup = self.session.get_soup(url)
            if not soup:
                return []
            for a in soup.find_all("a", href=re.compile(r"moduleid=\d+")):
                href = a.get("href", "")
                if "downloads.php" in href:
                    title_link = a.find_next("a", class_="standard-link")
                    title = title_link.text.strip() if title_link else "Unknown Module"
                    results.append(DiscoveredResource(
                        title=title, url=href, download_url=href,
                        node_type="track", metadata={"console": "ModArchive"},
                    ))
        except Exception:
            pass
        return results[:50]
