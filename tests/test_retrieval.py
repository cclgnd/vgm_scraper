import os
import tempfile
import unittest

from vgm_scraper.acquisition.retrieval import RetrievalManager
from vgm_scraper.db.manager import DatabaseManager


class RetrievalManagerTests(unittest.TestCase):
    def test_request_track_reuses_active_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = DatabaseManager(os.path.join(tmp, "test.db"))
            source_id = db.add_source("test", "https://example.test", "web")
            console_id = db.add_console("genesis", "Sega Genesis", "Sega")
            game_id = db.add_game(console_id, "Sonic")
            track_id = db.add_track("Opening", game_id=game_id)
            resource_id = db.add_resource_node(
                source_id=source_id,
                node_type="track",
                title="Opening",
                download_url="https://example.test/opening.vgz",
                format=".vgz",
            )
            db.link_resource_to_track(resource_id, track_id, is_primary=1, confidence=1.0)

            retrieval = RetrievalManager(db, tmp)
            first = retrieval.request_track(track_id)
            second = retrieval.request_track(track_id)

            self.assertEqual("obtaining_file", first["status"])
            self.assertEqual("obtaining_file", second["status"])
            self.assertEqual(first["job_id"], second["job_id"])
            with db.connect() as conn:
                count = conn.execute("SELECT COUNT(*) FROM retrieval_jobs WHERE track_id = ?", (track_id,)).fetchone()[0]
            self.assertEqual(1, count)


if __name__ == "__main__":
    unittest.main()
