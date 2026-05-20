"""Dynamic source adapter backed by the generic web scraper."""

import json
import logging

from vgm_scraper.acquisition.sources.base import BaseSource, DiscoveredResource
from vgm_scraper.acquisition.generic_scraper import GenericWebScraper

logger = logging.getLogger("vgm_scraper.dynamic")


class DynamicSource(BaseSource):
    """A source adapter created from a discovered site."""

    source_type = "web"

    def __init__(self, session, db, site_record: dict):
        self._site_record = site_record
        self.name = site_record.get("name", site_record["url"])
        self.base_url = site_record["url"]
        self._profile = json.loads(site_record["profile_json"]) if site_record.get("profile_json") else {}
        super().__init__(session, db)
        # Override source_id to use the discovered site's identity
        self._source_id = self.db.add_source(self.name, self.base_url, "web")

    def discover(self, max_depth: int = 3) -> list[DiscoveredResource]:
        """Discover resources using site-neutral link/resource patterns."""
        max_pages = self._profile.get("max_pages", max(25, max_depth * 25))
        scraper = GenericWebScraper(self.session, self.base_url, same_domain=True)
        resources = scraper.discover(max_depth=max_depth, max_pages=max_pages)
        self.db.mark_site_crawled(self._site_record["id"], len(resources))
        return resources

    def search(self, query: str) -> list[DiscoveredResource]:
        """Search is not supported for dynamic sources."""
        return []
