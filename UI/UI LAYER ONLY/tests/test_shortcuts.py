import sys
import os
import unittest
from PySide6.QtWidgets import QApplication

# Ensure chiptunepalace is in the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtGui import QShortcut
from chiptunepalace.gui.main_window import MainWindow
from chiptunepalace.gui.shortcuts import KeyboardShortcutModule

class TestKeyboardShortcuts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a single QApplication instance for all tests
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)

    def test_shortcut_module_registration(self):
        # Instantiate MainWindow
        window = MainWindow()
        self.assertIsNotNone(window.shortcuts)
        self.assertIsInstance(window.shortcuts, KeyboardShortcutModule)
        
        # Verify that shortcuts are active children of MainWindow
        shortcuts = window.findChildren(QShortcut)
        self.assertGreater(len(shortcuts), 0)
        
        # Verify a couple of key shortcuts
        registered_keys = [s.key().toString() for s in shortcuts]
        self.assertIn("Space", registered_keys)
        self.assertIn("Ctrl+S", registered_keys)
        self.assertIn("Ctrl+R", registered_keys)
        self.assertIn("Ctrl+F", registered_keys)
        self.assertIn("Esc", registered_keys)
        
        # Clean up Qt widgets and event loop
        window.close()
        window.deleteLater()
        self.app.processEvents()

    def test_shortcuts_help_dialog(self):
        from chiptunepalace.gui.main_window import ShortcutsHelpDialog
        dialog = ShortcutsHelpDialog()
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.windowTitle(), "HOTKEY MANUAL")
        dialog.close()
        dialog.deleteLater()
        self.app.processEvents()

    def test_folder_recursive_track_collection(self):
        from chiptunepalace.gui.main_window import MainWindow
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtCore import Qt
        
        window = MainWindow()
        
        # Build a dummy hierarchy: game -> children tracks
        game_item = QTreeWidgetItem()
        game_item.setData(0, Qt.UserRole, "game_local")
        
        child1 = QTreeWidgetItem(game_item)
        child1.setData(0, Qt.UserRole, "track")
        child1.setData(1, Qt.UserRole, 101)
        
        child2 = QTreeWidgetItem(game_item)
        child2.setData(0, Qt.UserRole, "track")
        child2.setData(1, Qt.UserRole, 102)
        
        # Test collection
        tracks = window.get_all_tracks_under_item(game_item)
        self.assertEqual(len(tracks), 2)
        self.assertEqual(tracks[0].data(1, Qt.UserRole), 101)
        self.assertEqual(tracks[1].data(1, Qt.UserRole), 102)
        
        window.close()
        window.deleteLater()
        self.app.processEvents()

    def test_dynamic_search_filtering_with_highlights(self):
        from chiptunepalace.gui.main_window import MainWindow
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtCore import Qt
        
        window = MainWindow()
        
        # Clear tree and add a custom test node
        window.library_tree.clear()
        
        console_item = QTreeWidgetItem(window.library_tree)
        console_item.setData(0, Qt.UserRole, "console_local")
        console_item.setData(2, Qt.UserRole, "PlayStation")
        console_item.setText(0, "PLAYSTATION")
        
        game_item = QTreeWidgetItem(console_item)
        game_item.setData(0, Qt.UserRole, "game_local")
        game_item.setData(2, Qt.UserRole, "Tennis World")
        game_item.setData(3, Qt.UserRole, "Local")
        game_item.setText(0, "★ Tennis World")
        
        # Filter the tree
        window.filter_library_tree("World")
        
        # Verify that it remains visible and display text got dynamic HTML hot-pink highlights
        self.assertFalse(console_item.isHidden())
        self.assertFalse(game_item.isHidden())
        
        game_text = game_item.text(0)
        self.assertIn("span style=", game_text)
        self.assertIn("#ff007f", game_text)  # Dynamic hot pink highlight color code
        
        window.close()
        window.deleteLater()
        self.app.processEvents()

    def test_single_click_playback_and_label_toggle(self):
        from chiptunepalace.gui.main_window import MainWindow
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtCore import Qt
        
        window = MainWindow()
        window.library_tree.clear()
        
        console_item = QTreeWidgetItem(window.library_tree)
        console_item.setData(0, Qt.UserRole, "console_local")
        console_item.setData(2, Qt.UserRole, "NES")
        console_item.setText(0, "NES")
        console_item.setExpanded(False)
        
        # Click on console item
        window.on_library_item_clicked(console_item, 0)
        
        # Verify that clicking the console item label successfully toggled expansion state to True
        self.assertTrue(console_item.isExpanded())
        
        # Click again to collapse
        window.on_library_item_clicked(console_item, 0)
        self.assertFalse(console_item.isExpanded())
        
        window.close()
        window.deleteLater()
        self.app.processEvents()

    def test_conditional_scan_button_folder_playback(self):
        from chiptunepalace.gui.main_window import MainWindow
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtCore import Qt
        
        window = MainWindow()
        window.library_tree.clear()
        
        console_item = QTreeWidgetItem(window.library_tree)
        console_item.setData(0, Qt.UserRole, "console_local")
        console_item.setData(2, Qt.UserRole, "Sega Genesis")
        console_item.setText(0, "SEGA GENESIS")
        
        # Select the item
        window.library_tree.setCurrentItem(console_item)
        
        # Verify that the button text updated dynamically to PLAY FOLDER CONTENT
        self.assertEqual(window.btn_scan_folder.text(), "PLAY FOLDER CONTENT")
        
        # De-select the item
        window.library_tree.setCurrentItem(None)
        self.assertEqual(window.btn_scan_folder.text(), "SCAN FOLDER")
        
        window.close()
        window.deleteLater()
        self.app.processEvents()

    def test_file_view_shows_extensions(self):
        from chiptunepalace.gui.main_window import MainWindow
        
        window = MainWindow()
        
        # Test default extension mappings for key consoles
        self.assertEqual(window.get_console_default_extension("SNES"), ".spc")
        self.assertEqual(window.get_console_default_extension("Nintendo Entertainment System"), ".nsf")
        self.assertEqual(window.get_console_default_extension("Sega Genesis"), ".vgm")
        self.assertEqual(window.get_console_default_extension("Sony PlayStation 1"), ".psf")
        self.assertEqual(window.get_console_default_extension("Amiga"), ".mod")
        
        window.close()
        window.deleteLater()
        self.app.processEvents()

    def test_on_tracks_loaded_handles_malformed_entries(self):
        from chiptunepalace.gui.main_window import MainWindow
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtCore import Qt

        window = MainWindow()
        window.library_tree.clear()

        console_item = QTreeWidgetItem(window.library_tree)
        console_item.setData(0, Qt.UserRole, "console")
        console_item.setData(2, Qt.UserRole, "SNES")

        game_item = QTreeWidgetItem(console_item)
        game_item.setData(0, Qt.UserRole, "game")
        game_item.setData(2, Qt.UserRole, "Chrono Trigger")

        dummy = QTreeWidgetItem(game_item)
        dummy.setData(0, Qt.UserRole, "dummy")

        malformed_tracks = [None, {}, {"foo": "bar"}, {"title": "Battle Theme"}]
        window.on_tracks_loaded(game_item, "Chrono Trigger", "https://example.com/pack.zip", "VGMRips", malformed_tracks)

        self.assertEqual(game_item.childCount(), 1)
        child = game_item.child(0)
        self.assertIn("Battle Theme", child.text(0))
        self.assertIn(child.data(0, Qt.UserRole), ("track", "online_track"))

        window.close()
        window.deleteLater()
        self.app.processEvents()

if __name__ == "__main__":
    unittest.main()
