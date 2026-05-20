from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup

from chiptunepalace.db.orm_stubs import DatabaseManager


@dataclass
class DiscoveredLink:
    title: str
    url: str
    confidence: float
    node_type: str  # console|game|track|page


class DiscoveryCrawler:
    """
    Generic crawler scaffold for autonomous discovery.
    Keeps discovered graph in DB and returns scored entities.
    """

    def __init__(self, db_manager: DatabaseManager | None = None, session: requests.Session | None = None):
        self.db = db_manager or DatabaseManager()
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def discover_console_links(self, source: str, seed_url: str) -> list[DiscoveredLink]:
        html = self._fetch(seed_url)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            title = a.get_text(strip=True)
            if not href or not title:
                continue
            full_url = urljoin(seed_url, href)
            score = self._score_console_link(full_url, title)
            if score < 0.55:
                continue
            links.append(DiscoveredLink(title=title, url=full_url, confidence=score, node_type="console"))
            self.db.upsert_discovered_node(source=source, node_type="console", url=full_url, title=title, parent_url=seed_url, confidence=score)
        return self._dedupe(links)

    def discover_game_links(self, source: str, console_url: str) -> list[DiscoveredLink]:
        links = []
        for page_url in self._paginate(console_url):
            html = self._fetch(page_url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            page_links = self._extract_repeated_links(soup, page_url)
            for link in page_links:
                score = self._score_game_link(link.url, link.title)
                if score < 0.5:
                    continue
                links.append(DiscoveredLink(title=link.title, url=link.url, confidence=score, node_type="game"))
                self.db.upsert_discovered_node(source=source, node_type="game", url=link.url, title=link.title, parent_url=console_url, confidence=score)
            if not page_links:
                break
        return self._dedupe(links)

    def _fetch(self, url: str) -> str:
        try:
            res = self.session.get(url, timeout=12)
            res.raise_for_status()
            return res.text
        except Exception:
            return ""

    def _extract_repeated_links(self, soup: BeautifulSoup, base_url: str) -> list[DiscoveredLink]:
        candidates = []
        for a in soup.find_all("a", href=True):
            title = a.get_text(strip=True)
            href = a.get("href", "").strip()
            if not title or not href:
                continue
            if len(title) < 2:
                continue
            full_url = urljoin(base_url, href)
            candidates.append(DiscoveredLink(title=title, url=full_url, confidence=0.0, node_type="page"))
        return candidates

    def _paginate(self, base_url: str, limit: int = 20):
        yield base_url
        for p in range(2, limit + 1):
            yield self._with_page_param(base_url, p)

    def _with_page_param(self, url: str, page: int) -> str:
        parsed = urlparse(url)
        q = parse_qs(parsed.query)
        q["p"] = [str(page)]
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(q, doseq=True), parsed.fragment))

    def _score_console_link(self, url: str, title: str) -> float:
        text = f"{url} {title}".lower()
        score = 0.0
        if "system" in text or "console" in text:
            score += 0.35
        if "music" in text or "packs" in text:
            score += 0.20
        if len(title) > 3:
            score += 0.25
        if any(k in text for k in ("vgm", "mod", "zophar", "archive")):
            score += 0.20
        return min(score, 1.0)

    def _score_game_link(self, url: str, title: str) -> float:
        text = f"{url} {title}".lower()
        score = 0.0
        if any(k in text for k in ("pack", "album", "game", "title")):
            score += 0.35
        if ".zip" in text or "download" in text:
            score += 0.25
        if len(title) > 2:
            score += 0.20
        if "http" in url:
            score += 0.20
        return min(score, 1.0)

    def _dedupe(self, links: list[DiscoveredLink]) -> list[DiscoveredLink]:
        by_url = {}
        for link in links:
            prev = by_url.get(link.url)
            if not prev or link.confidence > prev.confidence:
                by_url[link.url] = link
        return list(by_url.values())
