import unittest
from unittest.mock import MagicMock, patch
import sounddevice as sd
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings

from simpleplayer.audio import RealtimeAudioOutput
from simpleplayer.app import MainWindow

# Initialize QApplication once for tests
app = QApplication.instance() or QApplication([])

class TestAudioDeviceSelection(unittest.TestCase):
    def setUp(self):
        settings = QSettings("SimplePlayer", "SimplePlayer")
        settings.clear()

    def test_audio_output_device_id(self):
        audio = RealtimeAudioOutput()
        self.assertIsNone(audio.device_id)
        audio.set_device(2)
        self.assertEqual(audio.device_id, 2)

    @patch('sounddevice.OutputStream')
    def test_audio_output_stream_uses_device_id(self, mock_stream):
        audio = RealtimeAudioOutput()
        audio.device_id = 3
        audio.start()
        mock_stream.assert_called_once()
        self.assertEqual(mock_stream.call_args[1].get('device'), 3)

    @patch('sounddevice.query_devices')
    @patch('sounddevice.query_hostapis')
    def test_restore_audio_device(self, mock_hostapis, mock_devices):
        mock_devices.return_value = [
            {'name': 'Speaker', 'hostapi': 0, 'max_output_channels': 2},
            {'name': 'Bluetooth Headphones', 'hostapi': 1, 'max_output_channels': 2},
        ]
        mock_hostapis.return_value = [
            {'name': 'MME'},
            {'name': 'Windows WASAPI'},
        ]
        
        # Save device name and hostapi
        settings = QSettings("SimplePlayer", "SimplePlayer")
        settings.setValue("audio/device_name", "Bluetooth Headphones")
        settings.setValue("audio/device_hostapi", "Windows WASAPI")

        win = MainWindow()
        # Since it was called in init, let's verify
        self.assertEqual(win.audio.device_id, 1)

    @patch('sounddevice.query_devices')
    @patch('sounddevice.query_hostapis')
    def test_populate_audio_menu(self, mock_hostapis, mock_devices):
        mock_devices.return_value = [
            {'name': 'Speaker', 'hostapi': 0, 'max_output_channels': 2},
            {'name': 'Bluetooth Headphones', 'hostapi': 1, 'max_output_channels': 2},
        ]
        mock_hostapis.return_value = [
            {'name': 'MME'},
            {'name': 'Windows WASAPI'},
        ]
        
        win = MainWindow()
        win.audio.device_id = 1
        
        # Trigger population
        win._populate_audio_menu()
        
        # Check actions
        actions = win.audio_menu.actions()
        # Should have Default Device, Separator, Speaker, Bluetooth Headphones (4 elements total)
        self.assertEqual(len(actions), 4)
        self.assertFalse(actions[0].isChecked()) # Default Device (not checked because device_id is 1)
        self.assertTrue(actions[3].isChecked()) # Bluetooth Headphones (checked)
