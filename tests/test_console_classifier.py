import unittest

from vgm_scraper.acquisition.console_classifier import classify_console
from vgm_scraper.config import normalize_console_name


class ConsoleClassifierTests(unittest.TestCase):
    def test_genesis_does_not_match_nes_substring(self):
        cases = [
            "Sega Genesis",
            "Sega Genesis / Mega Drive",
            "Mega Drive, Genesis",
            "The Great Waldo Search (Mega Drive, Genesis).zip",
            "genesis",
        ]

        for value in cases:
            with self.subTest(value=value):
                match = classify_console(value)
                self.assertEqual("genesis", match.slug)
                self.assertEqual("Sega Genesis", match.canonical_name)

    def test_short_aliases_match_as_tokens_only(self):
        self.assertEqual(("Nintendo Entertainment System", "nes"), normalize_console_name("game (NES).zip"))
        self.assertEqual(("Sega Genesis", "genesis"), normalize_console_name("genesis"))

    def test_longest_alias_wins(self):
        self.assertEqual(("Nintendo Game Boy Color", "gbc"), normalize_console_name("Nintendo Game Boy Color"))
        self.assertEqual(("Nintendo Game Boy Advance", "gba"), normalize_console_name("game boy advance"))

    def test_unknown_stays_unknown(self):
        self.assertEqual(("Unknown Console", "unknown"), normalize_console_name("original soundtrack"))


if __name__ == "__main__":
    unittest.main()
