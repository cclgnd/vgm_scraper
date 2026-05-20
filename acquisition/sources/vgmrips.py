"""
VGMRips source adapter.
https://vgmrips.net - Largest chiptune rip archive.
"""

import re

from vgm_scraper.acquisition.sources.base import BaseSource, DiscoveredResource


MAKER_MAP = {
    "sega": "Sega", "nintendo": "Nintendo", "nec": "NEC", "sharp": "Sharp",
    "ibm": "IBM", "snk": "SNK", "capcom": "Capcom", "atari": "Atari",
    "commodore": "Commodore", "sinclair": "Sinclair", "apple": "Apple",
    "microsoft": "Microsoft", "sony": "Sony", "bandai": "Bandai",
    "konami": "Konami", "namco": "Namco", "taito": "Taito",
    "toaplan": "Toaplan", "hudson": "Hudson", "fujitsu": "Fujitsu",
    "seibu": "Seibu", "cave": "Cave",
}


class VGMRipsSource(BaseSource):
    name = "vgmrips"
    base_url = "https://vgmrips.net"

    def discover(self, max_depth: int = 1) -> list[DiscoveredResource]:
        return list(self.iter_discover(max_depth=max_depth))

    def iter_discover(self, max_depth: int = 1):
        """Yield packs as they are found so the catalog fills during a crawl."""
        consoles = self._get_consoles()
        # max_depth=1 → 5 consoles, 2 → 10, 3 → 15, etc.
        max_consoles = max(5, max_depth * 5)
        consoles = consoles[:max_consoles]

        for console in consoles:
            console_resource = DiscoveredResource(
                title=console["name"],
                url=console["url"],
                node_type="console",
                metadata={"console": console["name"]},
            )
            console_id = self.db.add_resource_node(
                source_id=self.source_id,
                node_type="console",
                title=console["name"],
                url=console["url"],
            )
            console_resource.parent_id = console_id

            # max_depth=1 → 3 pages, 2 → 6 pages, 3 → 10 pages
            max_pages = max(3, max_depth * 3)
            packs = self._get_packs(console["url"], console["name"], max_pages=max_pages)
            for pack in packs:
                pack.parent_id = console_id
                pack.metadata["console"] = console["name"]
                yield pack

    def search(self, query: str) -> list[DiscoveredResource]:
        import urllib.parse
        url = f"{self.base_url}/packs/search?q={urllib.parse.quote(query)}"
        resp = self.session.get(url)
        if not resp:
            return []

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        if "/packs/pack/" in resp.url:
            title = ""
            h1 = soup.find("h1")
            title = h1.text.strip() if h1 else soup.title.text.strip().split(" vgm music")[0] if soup.title else ""
            zip_url = ""
            for a in soup.find_all("a"):
                if a.text.strip() == "Download" and ".zip" in a.get("href", "").lower():
                    zip_url = self.session.resolve_url(a.get("href", ""), self.base_url)
                    break
            if title and zip_url:
                results.append(DiscoveredResource(
                    title=title, url=resp.url, download_url=zip_url,
                    node_type="pack",
                ))
            return results

        for h2 in soup.find_all("h2", class_="title"):
            links = h2.find_all("a")
            if len(links) >= 3:
                sys_name = links[0].text.strip()
                title = links[1].text.strip()
                detail_url = self.session.resolve_url(links[1].get("href", ""), self.base_url)
                zip_url = self.session.resolve_url(links[2].get("href", ""), self.base_url)
                if detail_url and ".zip" in zip_url.lower():
                    results.append(DiscoveredResource(
                        title=title, url=detail_url, download_url=zip_url,
                        node_type="pack", metadata={"console": sys_name},
                    ))
        return results

    def _get_consoles(self) -> list[dict]:
        soup = self.session.get_soup(f"{self.base_url}/packs/systems")
        if not soup:
            return []

        consoles = []
        for a in soup.find_all("a", href=re.compile(r"/packs/system/")):
            name = a.text.strip()
            href = a.get("href", "")
            if name and not name.isdigit() and "PACKS" not in name.upper():
                full_url = self.session.resolve_url(href, self.base_url)
                maker = ""
                match = re.search(r"/packs/system/([^/]+)/", href)
                if match:
                    slug = match.group(1).lower()
                    if slug not in ("other", "various"):
                        maker = MAKER_MAP.get(slug, slug.title())
                if maker and not name.lower().startswith(maker.lower()):
                    name = f"{maker} {name}"
                consoles.append({"name": name, "url": full_url})

        seen = set()
        unique = []
        for c in consoles:
            if c["name"] not in seen:
                unique.append(c)
                seen.add(c["name"])
        return unique

    def _get_packs(self, console_url: str, console_name: str, max_pages: int = 10) -> list[DiscoveredResource]:
        results = []
        for page in range(1, max_pages + 1):
            page_url = console_url
            if page > 1:
                sep = "&" if "?" in console_url else "?"
                page_url = f"{console_url}{sep}p={page}"

            soup = self.session.get_soup(page_url)
            if not soup:
                break

            page_results = []
            for h2 in soup.find_all("h2", class_="title"):
                links = h2.find_all("a")
                if len(links) >= 3:
                    title = links[1].text.strip()
                    detail_url = self.session.resolve_url(links[1].get("href", ""), self.base_url)
                    zip_url = self.session.resolve_url(links[2].get("href", ""), self.base_url)
                    if detail_url and ".zip" in zip_url.lower():
                        page_results.append(DiscoveredResource(
                            title=title, url=detail_url, download_url=zip_url,
                            node_type="pack",
                        ))

            if not page_results:
                break
            results.extend(page_results)

        return results

    def get_tracks(self, resource: DiscoveredResource) -> list[DiscoveredResource]:
        """Fetch track listing from VGMRips pack detail page."""
        soup = self.session.get_soup(resource.url)
        if not soup:
            return []
        tracks = []
        for i, td in enumerate(soup.find_all("td", class_="title"), 1):
            name = td.text.strip()
            if name:
                tracks.append(DiscoveredResource(
                    title=name,
                    url=resource.url,
                    node_type="track",
                    metadata={"track_number": i, "parent_pack": resource.title},
                ))
        return tracks
