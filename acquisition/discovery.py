"""
Autonomous discovery engine for VGM Scraper.

Discovers new VGM repositories by:
1. Crawling from seed URLs to find candidate sites
2. Scoring pages for VGM repository likelihood
3. Registering active sites for the generic resource scraper
"""

import json
import re
import time
import logging
import threading
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from vgm_scraper.core import ScraperSession
from vgm_scraper.db.manager import DatabaseManager
from vgm_scraper.config import (
    DISCOVERY_MAX_DEPTH,
    DISCOVERY_CANDIDATE_THRESHOLD,
    DISCOVERY_ACTIVE_THRESHOLD,
    DISCOVERY_REVISIT_INTERVAL,
    SYNTH_FORMATS,
    SUPPORTED_CONSOLES,
)

logger = logging.getLogger("vgm_scraper.discovery")

# Seed URLs: known VGM directories (fast, reliable)
SEED_URLS = [
    "https://vgmrips.net/packs/systems",
    "https://www.zophar.net/music",
    "https://modarchive.org",
    "https://www.snesmusic.org",
]

# Keywords that suggest a page is a VGM repository
VGM_KEYWORDS = [
    "vgm", "chiptune", "video game music", "game soundtrack",
    "game rip", "gamerip", "ost", "bgm", "soundtrack",
    "nsf", "spc", "vgm format", "chipmusic", "mod archive",
    "psf", "usf", "ssflib", "game audio", "retro game music",
    "download vgm", "game music download",
]

# Keywords that suggest a page is NOT a VGM repository
EXCLUDE_KEYWORDS = [
    "mp3 download", "free mp3", "spotify", "apple music",
    "streaming", "youtube music", "soundcloud",
    "buy soundtrack", "purchase album", "itunes",
]

# URL patterns that suggest VGM content
VGM_URL_PATTERNS = [
    r"/vgm", r"/chiptune", r"/game[-_]music", r"/soundtrack",
    r"/ost", r"/downloads", r"/packs", r"/rips",
    r"\.vgm", r"\.spc", r"\.nsf", r"\.psf", r"\.usf",
    r"/music/", r"/audio/",
]


class CandidateSite:
    """Represents a discovered candidate VGM site."""

    def __init__(self, url: str, name: str = "", discovered_from: str = ""):
        self.url = url
        self.name = name
        self.discovered_from = discovered_from
        self.confidence = 0.0
        self.evidence = []
        self.profile = None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "name": self.name,
            "discovered_from": self.discovered_from,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "profile": self.profile,
        }


class DiscoveryEngine:
    """Autonomous discovery engine that finds new VGM repositories."""

    DISCOVERY_TIMEOUT = 5  # seconds per request
    DISCOVERY_RETRIES = 1  # minimal retries for discovery

    def __init__(self, db: DatabaseManager, session: ScraperSession):
        self.db = db
        self.session = session
        self._visited = set()
        self._running = False
        self._thread = None
        self._discovery_session = None

    def _get_discovery_session(self):
        """Get a session optimized for discovery (faster timeout, fewer retries)."""
        if self._discovery_session is None:
            import requests
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

            sess = requests.Session()
            sess.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            })
            sess.verify = False
            self._discovery_session = sess
        return self._discovery_session

    def _get_soup_fast(self, url: str):
        """Get soup with fast timeout and minimal retries."""
        sess = self._get_discovery_session()
        try:
            resp = sess.get(url, timeout=self.DISCOVERY_TIMEOUT)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except Exception:
            return None

    def discover_once(self, seeds: list[str] = None, max_sites: int = 20) -> list[CandidateSite]:
        """
        Run one discovery pass. Returns list of candidate sites found.
        """
        seeds = seeds or SEED_URLS
        candidates = []
        self._visited = set()
        self._start_time = time.time()
        self._max_time = 60  # 60 second total timeout

        # Skip URLs from already-known sources
        known_sources = self.db.list_sources()
        known_urls = {s["base_url"] for s in known_sources if s.get("base_url")}
        seeds = [s for s in seeds if not any(s.startswith(k) for k in known_urls)]

        for seed_url in seeds:
            if len(candidates) >= max_sites:
                break
            if time.time() - self._start_time > self._max_time:
                logger.info(f"[DISCOVERY] Timeout reached after {self._max_time}s")
                break
            self._crawl_from_seed(seed_url, depth=0, max_depth=DISCOVERY_MAX_DEPTH,
                                  candidates=candidates, max_sites=max_sites)

        return candidates

    def start_continuous(self, interval: int = 3600, seeds: list[str] = None, max_sites: int = 10):
        """Start continuous background discovery."""
        if self._running:
            return

        self._running = True

        def _loop():
            while self._running:
                try:
                    self.discover_once(seeds, max_sites=max_sites)
                except Exception as e:
                    logger.error(f"Discovery error: {e}")
                for _ in range(interval):
                    if not self._running:
                        break
                    time.sleep(1)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop_continuous(self):
        self._running = False

    def _crawl_from_seed(self, url: str, depth: int, max_depth: int,
                         candidates: list, max_sites: int):
        """Crawl from a seed URL, discovering candidate sites."""
        if depth > max_depth or len(candidates) >= max_sites:
            return
        if url in self._visited:
            return
        if time.time() - self._start_time > self._max_time:
            return
        self._visited.add(url)

        soup = self._get_soup_fast(url)
        if not soup:
            return

        # Score this page
        score, evidence = self._score_page(url, soup)
        logger.debug(f"[DISCOVERY] Scored {url}: {score:.2f} {evidence}")

        if score >= DISCOVERY_ACTIVE_THRESHOLD:
            # This is likely a VGM repository
            candidate = CandidateSite(url, self._extract_title(soup), discovered_from=url)
            candidate.confidence = score
            candidate.evidence = evidence

            candidate.profile = self._generic_profile(url)

            self._register_candidate(candidate)
            candidates.append(candidate)
            logger.info(f"[DISCOVERY] Found active site: {url} (score: {score:.2f})")

        elif score >= DISCOVERY_CANDIDATE_THRESHOLD:
            # Interesting but not confirmed
            candidate = CandidateSite(url, self._extract_title(soup), discovered_from=url)
            candidate.confidence = score
            candidate.evidence = evidence
            self._register_candidate(candidate)

        # Follow links
        links = self._extract_links(url, soup)
        for link_url in links:
            if link_url in self._visited:
                continue
            # Skip non-HTML resources
            if any(link_url.lower().endswith(ext) for ext in [".zip", ".7z", ".rar", ".mp3", ".flac", ".wav"]):
                continue
            self._crawl_from_seed(link_url, depth + 1, max_depth, candidates, max_sites)

    def _score_page(self, url: str, soup: BeautifulSoup) -> tuple[float, list[str]]:
        """Score a page for VGM repository likelihood."""
        score = 0.0
        evidence = []
        text = soup.get_text(" ", strip=True).lower()
        url_lower = url.lower()

        # URL signals
        for pattern in VGM_URL_PATTERNS:
            if re.search(pattern, url_lower):
                score += 0.15
                evidence.append(f"url_match:{pattern}")
                break

        # Keyword signals
        for keyword in VGM_KEYWORDS:
            if keyword in text:
                score += 0.1
                evidence.append(f"keyword:{keyword}")
                break

        # Exclude signals
        for keyword in EXCLUDE_KEYWORDS:
            if keyword in text:
                score -= 0.3
                evidence.append(f"exclude:{keyword}")
                break

        # Download link signals
        download_links = self._find_download_links(soup)
        if download_links:
            synth_links = [l for l in download_links if self._is_synth_link(l.get("href", ""))]
            if synth_links:
                ratio = len(synth_links) / len(download_links)
                score += ratio * 0.3
                evidence.append(f"synth_links:{len(synth_links)}/{len(download_links)}")

        # Console name signals
        for console_key in SUPPORTED_CONSOLES:
            if console_key.replace("-", " ") in text or console_key in text:
                score += 0.05
                evidence.append(f"console:{console_key}")
                break

        # Structure signals: repeated elements suggest a catalog
        repeated = self._find_repeated_patterns(soup)
        if repeated:
            score += 0.1
            evidence.append("repeated_pattern:yes")

        return max(0.0, min(score, 1.0)), evidence

    def _generic_profile(self, url: str) -> dict:
        """Return a site-neutral crawl profile for dynamic sources."""
        return {
            "base_url": f"{urlparse(url).scheme}://{urlparse(url).netloc}",
            "version": 2,
            "scraper": "generic",
            "max_pages": 100,
        }

    def _register_candidate(self, candidate: CandidateSite):
        """Register a candidate site in the database."""
        site_id = self.db.add_discovered_site(
            url=candidate.url,
            name=candidate.name,
            discovered_from=candidate.discovered_from,
            confidence=candidate.confidence,
            status="active" if candidate.confidence >= DISCOVERY_ACTIVE_THRESHOLD else "candidate"
        )

        if candidate.profile:
            self.db.update_site_status(
                site_id,
                status="active",
                profile_json=json.dumps(candidate.profile)
            )

    def _extract_links(self, base_url: str, soup: BeautifulSoup) -> list[str]:
        """Extract outbound links from a page."""
        links = []
        base_domain = urlparse(base_url).netloc

        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue

            full_url = urljoin(base_url, href)
            parsed = urlparse(full_url)

            # Only follow HTTP(S) links
            if parsed.scheme not in ("http", "https"):
                continue

            # Same-domain always allowed
            if parsed.netloc == base_domain:
                links.append(full_url)
            # Cross-domain: only allow if URL contains VGM keywords
            elif any(kw in full_url.lower() for kw in ["vgm", "chiptune", "music", "soundtrack", "ost", "download", "packs", "rips"]):
                links.append(full_url)

        return links

    def _find_download_links(self, soup: BeautifulSoup) -> list:
        """Find links that look like download links."""
        links = []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").lower()
            text = a.get_text(strip=True).lower()
            if any(ext in href for ext in [".zip", ".7z", ".rar", ".vgm", ".spc", ".nsf", ".psf", ".usf", ".mod", ".xm"]):
                links.append(a)
            elif any(kw in text for kw in ["download", "get", "rip"]):
                links.append(a)
        return links

    def _is_synth_link(self, href: str) -> bool:
        """Check if a link points to a synth/chiptune format."""
        href_lower = href.lower()
        # Check for synth formats
        if any(href_lower.endswith(ext) for ext in SYNTH_FORMATS):
            return True
        # Check for archives (likely contain synth files)
        if any(href_lower.endswith(ext) for ext in [".zip", ".7z", ".rar"]):
            return True
        return False

    def _find_repeated_patterns(self, soup: BeautifulSoup) -> list:
        """Find repeated element patterns that suggest a catalog."""
        patterns = []
        for tag in ["table", "ul", "ol", "div"]:
            elements = soup.find_all(tag)
            for el in elements:
                children = el.find_all(["tr", "li", "a"], recursive=False)
                if len(children) >= 3:
                    patterns.append({"tag": tag, "children": len(children)})
        return patterns

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str:
        """Extract page title."""
        if soup.title:
            return soup.title.string.strip()
        return ""
