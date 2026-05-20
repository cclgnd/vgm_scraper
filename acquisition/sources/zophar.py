"""
Zophar's Domain source adapter.
https://www.zophar.net - Video game music rips and soundfonts.

Updated 2026-05-19: URLs changed from old format to new format.
"""

from vgm_scraper.acquisition.sources.base import BaseSource, DiscoveredResource


class ZopharSource(BaseSource):
    name = "zophar"
    base_url = "https://www.zophar.net"

    # Updated console directory paths (2026-05-19)
    CONSOLE_DIRS = [
        ("NES", "/music/nintendo-nes-nsf"),
        ("SNES", "/music/nintendo-snes-spc"),
        ("Game Boy", "/music/gameboy-gbs"),
        ("Game Boy Advance", "/music/gameboy-advance-gsf"),
        ("Nintendo DS", "/music/nintendo-ds-2sf"),
        ("Nintendo 64", "/music/nintendo-64-usf"),
        ("PlayStation", "/music/playstation-psf"),
        ("PlayStation 2", "/music/playstation2-psf2"),
        ("PSP", "/music/playstation-portable-psp"),
        ("Sega Game Gear", "/music/sega-game-gear-sgc"),
        ("Sega Master System", "/music/sega-master-system-vgm"),
        ("Sega Genesis / Mega Drive", "/music/sega-mega-drive-genesis"),
        ("Sega Saturn", "/music/sega-saturn-ssf"),
        ("Sega Dreamcast", "/music/sega-dreamcast-dsf"),
        ("TurboGrafx-16", "/music/turbografx-16-hes"),
        ("Amiga", "/music/amiga"),
        ("Arcade", "/music/arcade"),
        ("Atari ST", "/music/atari-st"),
        ("Commodore 64", "/music/commodore-64"),
        ("MSX", "/music/msx2"),
        ("PC-88", "/music/pc-8801"),
        ("PC-98", "/music/pc-9801"),
    ]

    def discover(self, max_depth: int = 3) -> list[DiscoveredResource]:
        resources = []
        for console_name, path in self.CONSOLE_DIRS:
            console_url = f"{self.base_url}{path}"
            soup = self.session.get_soup(console_url)
            if not soup:
                continue
            for td in soup.find_all("td", class_="name"):
                a = td.find("a")
                if a and a.get("href"):
                    title = a.text.strip()
                    href = self.session.resolve_url(a.get("href", ""), self.base_url)
                    resources.append(DiscoveredResource(
                        title=title, url=href, download_url="",
                        node_type="pack",
                        metadata={"console": console_name},
                    ))
        return resources

    def resolve_original_download_url(self, detail_url: str) -> str:
        """Return Zophar's original emulated-music ZIP URL for a detail page."""
        soup = self.session.get_soup(detail_url)
        if not soup:
            return ""

        candidates = []
        for a in soup.find_all("a", href=True):
            text = " ".join(a.get_text(" ", strip=True).lower().split())
            href = a.get("href", "")
            href_lower = href.lower()

            if "download original music files" in text:
                return self.session.resolve_url(href, self.base_url)

            if ".zophar.zip" in href_lower and "flac" not in href_lower and "mp3" not in href_lower:
                candidates.append(href)
            elif "(emu)" in href_lower or "%28emu%29" in href_lower:
                candidates.append(href)

        if candidates:
            return self.session.resolve_url(candidates[0], self.base_url)
        return ""

    def get_tracks(self, resource: DiscoveredResource) -> list[DiscoveredResource]:
        """Fetch track listing from Zophar pack detail page."""
        soup = self.session.get_soup(resource.url)
        if not soup:
            return []
        tracks = []
        for i, tr in enumerate(soup.find_all("tr", class_="trackrow"), 1):
            td_name = tr.find("td", class_="name")
            if td_name:
                name = td_name.text.strip()
                if name:
                    tracks.append(DiscoveredResource(
                        title=name, url=resource.url,
                        node_type="track",
                        metadata={"track_number": i, "parent_pack": resource.title},
                    ))
        return tracks
