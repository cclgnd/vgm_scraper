import unittest

from bs4 import BeautifulSoup

from vgm_scraper.acquisition.generic_scraper import GenericWebScraper


class FakeSession:
    def __init__(self, pages):
        self.pages = pages

    def get_soup(self, url):
        html = self.pages.get(url)
        return BeautifulSoup(html, "html.parser") if html else None


class GenericWebScraperTests(unittest.TestCase):
    def test_extracts_downloads_with_console_metadata(self):
        session = FakeSession({
            "https://example.test/music": """
                <html><head><title>VGM Archive</title></head>
                <body>
                  <ul>
                    <li>Sega classics
                      <a href="/files/Sonic%20(Mega%20Drive%2C%20Genesis).zip">Download</a>
                    </li>
                    <li><a href="/browse.html">Browse</a></li>
                  </ul>
                </body></html>
            """,
            "https://example.test/browse.html": """
                <html><body>
                  <a href="/files/Mario%20(NES).zip">Mario pack</a>
                  <a href="/style.css">Style</a>
                </body></html>
            """,
        })

        scraper = GenericWebScraper(session, "https://example.test/music")
        resources = scraper.discover(max_depth=1)

        self.assertEqual(2, len(resources))
        by_download = {resource.download_url: resource for resource in resources}
        sonic = by_download["https://example.test/files/Sonic%20(Mega%20Drive%2C%20Genesis).zip"]
        mario = by_download["https://example.test/files/Mario%20(NES).zip"]

        self.assertEqual("Sega Genesis", sonic.metadata["console"])
        self.assertEqual("genesis", sonic.metadata["console_slug"])
        self.assertEqual("Nintendo Entertainment System", mario.metadata["console"])
        self.assertEqual("nes", mario.metadata["console_slug"])

    def test_ignores_non_resource_links(self):
        session = FakeSession({
            "https://example.test/music": """
                <html><body>
                  <a href="/cover.jpg">cover</a>
                  <a href="/song.mp3">recording</a>
                  <a href="/pack.spc">Track</a>
                </body></html>
            """,
        })

        scraper = GenericWebScraper(session, "https://example.test/music")
        resources = scraper.discover(max_depth=0)

        self.assertEqual(["https://example.test/pack.spc"], [resource.download_url for resource in resources])
        self.assertEqual(["pack"], [resource.title for resource in resources])


if __name__ == "__main__":
    unittest.main()
