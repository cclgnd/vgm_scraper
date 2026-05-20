"""
Core scraper engine with session management, rate limiting, and retry logic.
"""

import time
import logging
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from vgm_scraper.config import USER_AGENT, REQUEST_TIMEOUT, REQUEST_RETRIES, REQUEST_DELAY

logger = logging.getLogger("vgm_scraper")


class ScraperSession:
    """HTTP session with retry logic and rate limiting."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        self.session.verify = False  # Skip SSL verification for broader compatibility
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self._last_request = 0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
        self._last_request = time.time()

    def get(self, url: str, **kwargs) -> requests.Response | None:
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        for attempt in range(REQUEST_RETRIES):
            try:
                self._rate_limit()
                resp = self.session.get(url, **kwargs)
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{REQUEST_RETRIES}): {url} - {e}")
                if attempt < REQUEST_RETRIES - 1:
                    time.sleep(2 ** attempt)
        return None

    def get_soup(self, url: str, **kwargs) -> BeautifulSoup | None:
        resp = self.get(url, **kwargs)
        if resp:
            return BeautifulSoup(resp.text, "html.parser")
        return None

    def resolve_url(self, url: str, base: str) -> str:
        if url.startswith("http"):
            return url
        return urljoin(base, url)
