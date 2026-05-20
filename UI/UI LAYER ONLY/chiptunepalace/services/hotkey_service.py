import ctypes
import threading
from ctypes import wintypes
from PySide6.QtCore import QThread, Signal

# Windows Constants
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3
WM_HOTKEY = 0x0312


class HotkeyThread(QThread):
    hotkey_pressed = Signal(int)

    def __init__(self):
        super().__init__()
        self.user32 = ctypes.windll.user32
        self._thread_id = None

    def run(self):
        # Capture the native thread ID so we can post messages to it later
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()

        self.user32.RegisterHotKey(None, 1, 0, VK_MEDIA_PLAY_PAUSE)
        self.user32.RegisterHotKey(None, 2, 0, VK_MEDIA_NEXT_TRACK)
        self.user32.RegisterHotKey(None, 3, 0, VK_MEDIA_PREV_TRACK)

        try:
            msg = wintypes.MSG()
            while True:
                ret = self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret == 0 or ret == -1:
                    # WM_QUIT received or error — exit loop
                    break
                if msg.message == WM_HOTKEY:
                    self.hotkey_pressed.emit(msg.wParam)
        finally:
            self.user32.UnregisterHotKey(None, 1)
            self.user32.UnregisterHotKey(None, 2)
            self.user32.UnregisterHotKey(None, 3)

    def stop(self):
        if self._thread_id:
            # Post WM_QUIT to the *hotkey thread's* message queue
            ctypes.windll.user32.PostThreadMessageW(
                self._thread_id, 0x0012, 0, 0  # WM_QUIT = 0x0012
            )


class HotkeyService:
    """Global media key handler (Windows only)."""

    def __init__(self, audio_engine, queue_manager):
        self.audio_engine = audio_engine
        self.queue_manager = queue_manager
        self.thread = HotkeyThread()
        self.thread.hotkey_pressed.connect(self._on_hotkey)
        self.thread.start()

    def _on_hotkey(self, hk_id):
        if hk_id == 1:
            if self.audio_engine.state == "Playing":
                self.audio_engine.pause()
            else:
                self.audio_engine.play()
        elif hk_id == 2:
            self.queue_manager.advance_to_next_track()
        elif hk_id == 3:
            self.queue_manager.previous_track()

    def cleanup(self):
        self.thread.stop()
        self.thread.wait(2000)  # wait at most 2 seconds
        if self.thread.isRunning():
            self.thread.terminate()  # force-kill if still stuck
