import os
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtCore import QObject

class KeyboardShortcutModule(QObject):
    """Module responsible for registering and managing all application keyboard shortcuts."""
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.register_shortcuts()
        
    def register_shortcuts(self):
        # 1. Space: Play/Pause
        self._add_shortcut("Space", self.main_window.toggle_play_pause)
        
        # 2. Media Play/Pause (Multimedia key support)
        self._add_shortcut("Media Play", self.main_window.toggle_play_pause)
        
        # 3. Media Next
        self._add_shortcut("Media Next", self.main_window.play_next_track)
        self._add_shortcut("Ctrl+Right", self.main_window.play_next_track)
        
        # 4. Media Previous
        self._add_shortcut("Media Previous", self.main_window.play_previous_track)
        self._add_shortcut("Ctrl+Left", self.main_window.play_previous_track)
        
        # 5. Seek Forward (Right Arrow)
        self._add_shortcut("Right", self.main_window.seek_forward_step)
        
        # 6. Seek Backward (Left Arrow)
        self._add_shortcut("Left", self.main_window.seek_backward_step)
        
        # 7. Volume Up (Up Arrow)
        self._add_shortcut("Up", self.main_window.volume_up_step)
        
        # 8. Volume Down (Down Arrow)
        self._add_shortcut("Down", self.main_window.volume_down_step)
        
        # 9. Toggle Shuffle (Ctrl+S)
        self._add_shortcut("Ctrl+S", self.main_window.toggle_shuffle)
        
        # 10. Toggle Repeat (Ctrl+R)
        self._add_shortcut("Ctrl+R", self.main_window.toggle_repeat)
        
        # 11. Focus Local Filter (Ctrl+F)
        self._add_shortcut("Ctrl+F", self.main_window.focus_local_filter)
        
        # 12. Focus Online Search (Ctrl+Shift+F)
        self._add_shortcut("Ctrl+Shift+F", self.main_window.focus_online_search)
        
        # 13. Clear Search / Escape (Esc)
        self._add_shortcut("Esc", self.main_window.clear_search_and_focus)
        
        # 14. Open Settings (Ctrl+,)
        self._add_shortcut("Ctrl+,", self.main_window.show_settings_dialog)

    def _add_shortcut(self, key_str, callback):
        shortcut = QShortcut(QKeySequence(key_str), self.main_window)
        shortcut.activated.connect(callback)
        return shortcut
