import os
import tempfile
import unittest

from chiptunepalace.db.orm_stubs import DatabaseManager
from chiptunepalace.services.console_canonicalizer import ConsoleCanonicalizer


class TestConsoleCanonicalizer(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "canon_test.db")
        self.db = DatabaseManager(db_path=self.db_path)
        self.canon = ConsoleCanonicalizer(db_manager=self.db)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_region_aliases_merge_to_single_console(self):
        a = self.canon.resolve("Nintendo Entertainment System (US)", source="test")
        b = self.canon.resolve("NES (Japan)", source="test")
        self.assertEqual(a["slug"], b["slug"])
        self.assertEqual(a["display_name"], b["display_name"])

    def test_known_synonyms_merge(self):
        a = self.canon.resolve("Sega Mega Drive", source="test")
        b = self.canon.resolve("Sega Genesis", source="test")
        self.assertEqual(a["slug"], b["slug"])


if __name__ == "__main__":
    unittest.main()
