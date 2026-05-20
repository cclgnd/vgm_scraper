import os
import tempfile
import unittest

from vgm_scraper.acquisition.crawler import WebCrawler
from vgm_scraper.acquisition.sources.base import BaseSource, DiscoveredResource
from vgm_scraper.acquisition.verifier import GameVerifier
from vgm_scraper.db.manager import DatabaseManager


class DirectFileSource(BaseSource):
    name = "direct-test"
    base_url = "https://example.test"
    source_type = "web"

    def discover(self, max_depth: int = 3) -> list[DiscoveredResource]:
        return [
            DiscoveredResource(
                title="Sonic Stage 1",
                url="https://example.test/sonic",
                download_url="https://example.test/Sonic%20Stage%201.vgz",
                node_type="track",
                format=".vgz",
                confidence=0.9,
                metadata={"console": "Sega Genesis", "game": "Sonic"},
            )
        ]


class CrawlerDirectFileTests(unittest.TestCase):
    def test_direct_file_resource_creates_openable_game_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = DatabaseManager(os.path.join(tmp, "test.db"))
            crawler = WebCrawler(db, session=None)

            discovered = crawler.crawl_source(DirectFileSource(session=None, db=db), max_depth=0)

            self.assertEqual(1, discovered)
            games = db.list_games()
            self.assertEqual(["Sonic"], [game["title"] for game in games])

            verifier = GameVerifier(db, tmp)
            result = verifier.open_game(games[0]["id"])

            self.assertEqual("obtaining_file", result["status"])
            self.assertEqual(["Sonic Stage 1"], [row["title"] for row in result["files"]])
            self.assertEqual("obtaining_file", result["files"][0]["availability_status"])


if __name__ == "__main__":
    unittest.main()
