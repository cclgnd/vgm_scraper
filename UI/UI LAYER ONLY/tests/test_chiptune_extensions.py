import unittest
import os
import zipfile
import tempfile
import shutil
from sqlalchemy import text
from chiptunepalace.services.track_service import TrackService, SUPPORTED_EXTS
from chiptunepalace.db.orm_stubs import DatabaseManager

class TestChiptuneExtensionsIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_manager = DatabaseManager(db_path='chiptunepalace/db/test.db')
        with cls.db_manager.engine.connect() as conn:
            conn.execute(text("DELETE FROM tracks"))
            conn.commit()
            
        # Create temp folder for mock zip files
        cls.temp_dir = tempfile.mkdtemp()
        cls.mock_zip_path = os.path.join(cls.temp_dir, "Super_Mario_World_(SNES).zip")
        
        # Build mock ZIP with diverse chiptune formats
        with zipfile.ZipFile(cls.mock_zip_path, 'w') as zf:
            # Add SNES format (SPC)
            zf.writestr("01 Super Mario World (Title).spc", b"MOCK_SPC_DATA")
            # Add PlayStation format (PSF)
            zf.writestr("02 Forest.psf", b"MOCK_PSF_DATA")
            # Add Nintendo 64 format (USF)
            zf.writestr("03 Zelda.usf", b"MOCK_USF_DATA")
            # Add NES format (NSF)
            zf.writestr("04 Mario Bros.nsf", b"MOCK_NSF_DATA")
            # Add non-playable text file
            zf.writestr("manual.txt", b"Should not be indexed")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir)

    def setUp(self):
        self.track_service = TrackService()
        self.track_service.db_manager = self.db_manager

    def test_supported_extensions_contain_classics(self):
        # Verify SPC, PSF, USF, GBS, NSF are in our supported set
        self.assertIn('.spc', SUPPORTED_EXTS)
        self.assertIn('.psf', SUPPORTED_EXTS)
        self.assertIn('.usf', SUPPORTED_EXTS)
        self.assertIn('.gbs', SUPPORTED_EXTS)
        self.assertIn('.nsf', SUPPORTED_EXTS)
        # Verify standard modern extensions are also supported
        self.assertIn('.mp3', SUPPORTED_EXTS)
        self.assertIn('.wav', SUPPORTED_EXTS)

    def test_indexing_diverse_zip_formats(self):
        indexed_ids = self.track_service.index_zip_pack(
            zip_path=self.mock_zip_path,
            console_name="Nintendo SNES",
            game_name="Super Mario World"
        )
        
        # We expect exactly 4 tracks to be indexed (spc, psf, usf, nsf)
        self.assertEqual(len(indexed_ids), 4)
        
        # Verify they are correctly retrieved from database
        tracks = self.track_service.get_tracks_by_console_and_game("Nintendo SNES", "Super Mario World")
        self.assertEqual(len(tracks), 4)
        
        titles = {t['title'] for t in tracks}
        formats = {t['format'] for t in tracks}
        
        self.assertIn("Super Mario World (Title)", titles)
        self.assertIn("Forest", titles)
        self.assertIn("Zelda", titles)
        self.assertIn("Mario Bros", titles)
        
        self.assertIn("SPC", formats)
        self.assertIn("PSF", formats)
        self.assertIn("USF", formats)
        self.assertIn("NSF", formats)

    def test_indexing_raw_non_zip_file(self):
        # Create a mock raw module file (saved with .zip suffix to emulate our downloader)
        raw_track_path = os.path.join(self.temp_dir, "mock_tracker_song.zip")
        # Extended Module starts with "Extended Module:"
        with open(raw_track_path, "wb") as f:
            f.write(b"Extended Module: Mock XM Song Data")
            
        indexed_ids = self.track_service.index_zip_pack(
            zip_path=raw_track_path,
            console_name="MODARCHIVE",
            game_name="Mock Game XM",
            source_url="https://api.modarchive.org/downloads.php?moduleid=9999"
        )
        
        # Verify 1 track indexed
        self.assertEqual(len(indexed_ids), 1)
        
        # Verify database record
        tracks = self.track_service.get_tracks_by_console_and_game("MODARCHIVE", "Mock Game XM")
        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0]['format'], "XM")
        self.assertIsNone(tracks[0]['member_name']) # Assert it's indexed as a raw file, not ZIP member
        
        # Verify the file was renamed with .xm suffix
        expected_renamed_path = raw_track_path[:-4] + ".xm"
        self.assertTrue(os.path.exists(expected_renamed_path))
        self.assertFalse(os.path.exists(raw_track_path))

if __name__ == '__main__':
    unittest.main()
