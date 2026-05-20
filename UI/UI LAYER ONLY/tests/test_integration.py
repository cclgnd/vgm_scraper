import unittest
from sqlalchemy import text
from chiptunepalace.services.track_service import TrackService
from chiptunepalace.services.audio_engine import AudioEngine, PlaybackState
from chiptunepalace.services.queue_manager import QueueManager
from chiptunepalace.db.orm_stubs import DatabaseManager

class TestMusicPlaybackIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use a separate test database
        cls.db_manager = DatabaseManager(db_path='chiptunepalace/db/test.db')
        with cls.db_manager.engine.connect() as conn:
            conn.execute(text("DELETE FROM tracks"))
            conn.commit()

    def setUp(self):
        self.track_service = TrackService()
        # Point track service to test DB
        self.track_service.db_manager = self.db_manager
        self.audio_engine = AudioEngine()
        self.queue_manager = QueueManager(self.track_service, self.audio_engine)
        
        # Manually insert a dummy track
        self.dummy_track_id = self.track_service.add_track(
            title="Test Tune", 
            artist="Opencode", 
            file_path="/mock/path/test.vgm"
        )

    def test_track_loading_and_state(self):
        track_data = self.track_service.get_track_by_id(self.dummy_track_id)
        self.assertIsNotNone(track_data)
        
        res = self.audio_engine.load_track(track_data['file_path'])
        self.assertTrue(res)

    def test_queue_management(self):
        # Test shuffle toggle
        self.assertFalse(self.queue_manager.is_shuffling)
        self.queue_manager.toggle_shuffle()
        self.assertTrue(self.queue_manager.is_shuffling)
        
        # Test loading playlist
        self.queue_manager.load_playlist([1, 2, 3])
        self.assertEqual(len(self.queue_manager.original_playlist), 3)

if __name__ == '__main__':
    unittest.main()
