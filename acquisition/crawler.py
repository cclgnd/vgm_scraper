"""
Web crawler for acquisition domain.

Orchestrates source adapters to discover resources, populate the catalog,
and track provenance in the acquisition domain.
"""

import logging
import datetime
from urllib.parse import urljoin

from vgm_scraper.db.manager import DatabaseManager
from vgm_scraper.core import ScraperSession
from vgm_scraper.catalog.library import LibraryManager
from vgm_scraper.acquisition.sources.base import BaseSource, DiscoveredResource
from vgm_scraper.acquisition.console_classifier import classify_console

logger = logging.getLogger("vgm_scraper")


class WebCrawler:
    """Crawls web sources and populates both catalog and acquisition domains."""

    def __init__(self, db: DatabaseManager, session: ScraperSession):
        self.db = db
        self.session = session
        self.library = LibraryManager(db)

    def crawl_source(self, source: BaseSource, max_depth: int = 3) -> int:
        """
        Crawl a single source. Discovers resources, creates catalog entries,
        and links them to acquisition resources.

        Returns number of resources discovered.
        """
        crawl_job_id = self.db.add_crawl_job(source.source_id, "running")
        resources_discovered = 0

        try:
            if hasattr(source, "iter_discover"):
                resources_iter = source.iter_discover(max_depth=max_depth)
                resources = None
            else:
                resources = source.discover(max_depth=max_depth)
                logger.info(f"[{source.name}] Discovered {len(resources)} resources")
                resources_iter = resources

            for resource in resources_iter:
                self._process_resource(source, resource, crawl_job_id)
                resources_discovered += 1
                if resources_discovered % 50 == 0:
                    self.db.update_crawl_job(crawl_job_id, "running", items_found=resources_discovered)

            self.db.update_crawl_job(crawl_job_id, "completed", items_found=resources_discovered)
            source.log_provenance(None, "crawl_completed", f"{resources_discovered} resources found")

        except Exception as e:
            logger.error(f"[{source.name}] Crawl failed: {e}")
            self.db.update_crawl_job(crawl_job_id, "failed", error_message=str(e))
            source.log_provenance(None, "crawl_failed", str(e))

        return resources_discovered

    def _process_resource(self, source: BaseSource, resource: DiscoveredResource, crawl_job_id: int):
        """Process a single discovered resource: create catalog entries and track provenance."""

        # Create resource node in acquisition domain
        resource_id = self.db.add_resource_node(
            source_id=source.source_id,
            crawl_job_id=crawl_job_id,
            parent_id=resource.parent_id,
            node_type=resource.node_type,
            title=resource.title,
            url=resource.url,
            download_url=resource.download_url,
            size_bytes=resource.size_bytes,
            format=resource.format,
            confidence=resource.confidence,
        )

        # Log discovery event
        self.db.add_provenance_event(
            resource_id=resource_id,
            event_type="discovered",
            details=f"Found via {source.name} at {resource.url}"
        )

        # If this is a pack/album, create catalog entries (console + game only)
        if resource.node_type in ("pack", "album", "collection"):
            self._create_game_entry(source, resource, resource_id)

    def _create_game_entry(self, source: BaseSource, resource: DiscoveredResource, resource_id: int):
        """Create console and game entries only. Tracks are created post-download."""
        metadata = resource.metadata

        # Source metadata is the strongest acquisition-side signal. Title and
        # source name are only fallback hints, keeping catalog identity separate
        # from raw resource storage.
        console_match = classify_console(
            metadata.get("console", ""),
            resource.title,
            resource.download_url,
            resource.url,
            source.name,
        )

        console_id = self.library.get_or_create_console(
            console_match.slug,
            console_match.canonical_name,
            console_match.maker,
        )

        # Determine game
        game_title = metadata.get("game", resource.title)
        game_id = self.library.get_or_create_game(console_id, game_title)
        self.db.link_resource_to_game(resource_id, game_id, is_primary=1, confidence=console_match.confidence)

        self.db.add_provenance_event(
            resource_id=resource_id,
            event_type="game_discovered",
            details=(
                f"game_id={game_id}; Game '{game_title}' on {console_match.canonical_name} "
                f"via {source.name}; confidence={console_match.confidence:.2f}; "
                f"evidence={','.join(console_match.evidence)}"
            )
        )

    @staticmethod
    def _slugify(name: str) -> str:
        import re
        slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
        return slug.strip("-") or "unknown"
