import os
import tempfile
import unittest

from vgm_scraper.acquisition.verifier import GameVerifier
from vgm_scraper.acquisition.zip_probe import ZipMember
from vgm_scraper.db.manager import DatabaseManager


class FakeZipProbe:
    def list_supported_members(self, url):
        return [
            ZipMember("01 Title.vgz", size=100, compressed_size=80, index=1),
            ZipMember("02 Stage.vgz", size=200, compressed_size=150, index=2),
        ]


class GameVerifierTests(unittest.TestCase):
    def test_open_game_exposes_zip_members_before_local_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = DatabaseManager(os.path.join(tmp, "test.db"))
            source_id = db.add_source("test", "https://example.test", "web")
            console_id = db.add_console("genesis", "Sega Genesis", "Sega")
            game_id = db.add_game(console_id, "Sonic")
            resource_id = db.add_resource_node(
                source_id=source_id,
                node_type="pack",
                title="Sonic",
                url="https://example.test/sonic",
                download_url="https://example.test/Sonic.zip",
                format=".zip",
            )
            db.link_resource_to_game(resource_id, game_id, is_primary=1, confidence=1.0)

            verifier = GameVerifier(db, tmp)
            verifier.zip_probe = FakeZipProbe()
            result = verifier.open_game(game_id)

            self.assertEqual("obtaining_file", result["status"])
            self.assertEqual(2, len(result["files"]))
            self.assertEqual(["Title", "Stage"], [row["title"] for row in result["files"]])
            self.assertTrue(all(row["availability_status"] == "obtaining_file" for row in result["files"]))

    def test_default_game_files_hide_known_short_durations_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = DatabaseManager(os.path.join(tmp, "test.db"))
            console_id = db.add_console("nes", "Nintendo Entertainment System", "Nintendo")
            game_id = db.add_game(console_id, "Mario")
            db.add_track("Visible Unknown", game_id=game_id, track_number=1, duration_seconds=None)
            db.add_track("Visible Music", game_id=game_id, track_number=2, duration_seconds=15.0)
            db.add_track("Hidden SFX", game_id=game_id, track_number=3, duration_seconds=14.9)

            result = db.list_player_files_for_game(game_id)

            self.assertEqual(1, result["hidden_short_file_count"])
            self.assertEqual(["Visible Unknown", "Visible Music"], [row["title"] for row in result["files"]])


if __name__ == "__main__":
    unittest.main()
