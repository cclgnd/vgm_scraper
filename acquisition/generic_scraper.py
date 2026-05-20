"""
Generic web scraper for acquisition resources.

This scraper treats every website the same way: crawl HTML pages, find links to
archives or synth formats, classify those links with shared domain heuristics,
and leave all raw source details in acquisition metadata/provenance.
"""

from dataclasses import dataclass, field
import os
import re
from urllib.parse import unquote, urljoin, urlparse, urldefrag

from bs4 import BeautifulSoup

from vgm_scraper.acquisition.console_classifier import classify_console
from vgm_scraper.acquisition.sources.base import DiscoveredResource
from vgm_scraper.config import ARCHIVE_EXTENSIONS, AUDIO_EXTENSIONS, EXCLUDED_FORMATS


@dataclass(frozen=True)
class PageLink:
    url: str
    text: str = ""
    context: str = ""
    page_url: str = ""
    page_title: str = ""
    evidence: list[str] = field(default_factory=list)


class GenericWebScraper:
    """Resource-first crawler that does not rely on per-site selectors."""

    SKIP_SCHEMES = ("mailto:", "javascript:", "tel:", "data:")
    HTML_EXTENSIONS = {".html", ".htm", ".php", ".asp", ".aspx", ".jsp"}
    NOISE_EXTENSIONS = {
        ".css", ".js", ".json", ".xml", ".rss", ".ico", ".png", ".jpg", ".jpeg",
        ".gif", ".svg", ".webp", ".pdf", ".txt",
    }

    def __init__(self, session, start_url: str, same_domain: bool = True):
        self.session = session
        self.start_url = start_url
        self.same_domain = same_domain
        self.base_domain = urlparse(start_url).netloc

    def discover(self, max_depth: int = 2, max_pages: int = 100) -> list[DiscoveredResource]:
        queue = [(self.start_url, 0)]
        visited_pages = set()
        seen_resources = set()
        resources = []

        while queue and len(visited_pages) < max_pages:
            page_url, depth = queue.pop(0)
            page_url = self._canonicalize_url(page_url)
            if page_url in visited_pages or depth > max_depth:
                continue
            visited_pages.add(page_url)

            soup = self.session.get_soup(page_url)
            if not soup:
                continue

            page_title = self._page_title(soup)
            for link in self._extract_links(page_url, page_title, soup):
                if self._is_resource_url(link.url):
                    canonical_resource_url = self._canonicalize_url(link.url)
                    if canonical_resource_url in seen_resources:
                        continue
                    seen_resources.add(canonical_resource_url)
                    resources.append(self._to_resource(link))
                elif depth < max_depth and self._should_follow(link.url):
                    queue.append((link.url, depth + 1))

        return resources

    def _extract_links(self, page_url: str, page_title: str, soup: BeautifulSoup) -> list[PageLink]:
        links = []
        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href or href.startswith("#") or href.lower().startswith(self.SKIP_SCHEMES):
                continue

            full_url = urljoin(page_url, href)
            text = " ".join(a.get_text(" ", strip=True).split())
            context = self._nearby_text(a)
            evidence = []
            if text:
                evidence.append("anchor_text")
            if context:
                evidence.append("nearby_text")
            links.append(PageLink(
                url=full_url,
                text=text,
                context=context,
                page_url=page_url,
                page_title=page_title,
                evidence=evidence,
            ))
        return links

    def _to_resource(self, link: PageLink) -> DiscoveredResource:
        path = unquote(urlparse(link.url).path)
        ext = self._extension(path)
        title = self._title_from_link(link, path)
        console_match = classify_console(
            link.text,
            path,
            link.context,
            link.page_title,
            link.page_url,
        )
        metadata = {
            "console": console_match.canonical_name,
            "console_slug": console_match.slug,
            "console_confidence": console_match.confidence,
            "console_evidence": console_match.evidence,
            "source_page": link.page_url,
            "source_page_title": link.page_title,
            "link_text": link.text,
            "link_context": link.context[:500],
            "scraper": "generic",
        }
        node_type = "pack" if self._is_archive_extension(ext) else "track"
        return DiscoveredResource(
            title=title,
            url=link.page_url or link.url,
            download_url=link.url,
            node_type=node_type,
            format=ext,
            confidence=0.8 if console_match.is_known else 0.55,
            metadata=metadata,
        )

    def _should_follow(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        if self.same_domain and parsed.netloc != self.base_domain:
            return False

        ext = self._extension(unquote(parsed.path))
        if ext in self.NOISE_EXTENSIONS or ext in EXCLUDED_FORMATS:
            return False
        if self._is_resource_url(url):
            return False
        return not ext or ext in self.HTML_EXTENSIONS

    def _is_resource_url(self, url: str) -> bool:
        ext = self._extension(unquote(urlparse(url).path))
        return ext in AUDIO_EXTENSIONS or self._is_archive_extension(ext)

    @staticmethod
    def _is_archive_extension(ext: str) -> bool:
        return ext in ARCHIVE_EXTENSIONS or ext in {".zip", ".7z", ".rar"}

    @staticmethod
    def _extension(path: str) -> str:
        lowered = path.lower()
        for compound in (".tar.gz", ".tar.bz2"):
            if lowered.endswith(compound):
                return compound
        return os.path.splitext(lowered)[1]

    @staticmethod
    def _canonicalize_url(url: str) -> str:
        return urldefrag(url)[0].strip()

    @staticmethod
    def _page_title(soup: BeautifulSoup) -> str:
        if soup.title and soup.title.string:
            return " ".join(soup.title.string.split())
        heading = soup.find(["h1", "h2"])
        return " ".join(heading.get_text(" ", strip=True).split()) if heading else ""

    @staticmethod
    def _nearby_text(anchor) -> str:
        container = anchor.find_parent(["li", "tr", "article", "section", "div", "p"])
        if not container:
            return ""
        return " ".join(container.get_text(" ", strip=True).split())

    @staticmethod
    def _title_from_link(link: PageLink, path: str) -> str:
        if link.text and len(link.text) > 2 and not re.fullmatch(r"download|get|zip|file", link.text, re.I):
            return link.text[:200]

        filename = unquote(os.path.basename(path)).strip()
        stem = os.path.splitext(filename)[0] if filename else ""
        stem = re.sub(r"[_\-]+", " ", stem)
        stem = re.sub(r"\s*\((?:[^)]*?(?:mega drive|genesis|nes|snes|psf|spc|nsf)[^)]*)\)\s*$", "", stem, flags=re.I)
        stem = " ".join(stem.split())
        return stem[:200] or link.page_title or filename or "Unknown Resource"
