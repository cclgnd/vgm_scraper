from __future__ import annotations

import sys
from pathlib import Path

import sounddevice as sd
from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from .audio import RealtimeAudioOutput
from .engines import AudioEngine, BackendRegistry, EngineError, TrackInfo
from .single_instance import SingleInstanceServer, send_to_running_instance


def _format_ms(ms: int) -> str:
    if ms < 0:
        return "--:--"
    total = ms // 1000
    return f"{total // 60:02d}:{total % 60:02d}"


class DropPanel(QWidget):
    def __init__(self, on_files) -> None:
        super().__init__()
        self._on_files = on_files
        self.setAcceptDrops(True)
        self.setObjectName("dropPanel")

        layout = QVBoxLayout(self)
        self.title = QLabel("Drop NSF, SPC, VGM/VGZ, GBS, HES, KSS, SAP, AY, or GYM")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setObjectName("dropTitle")
        self.subtitle = QLabel("Real-time emulation through libgme. No WAV pre-rendering.")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle.setObjectName("dropSubtitle")
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        files = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if files:
            self._on_files(files)
            event.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self, startup_files: list[Path] | None = None) -> None:
        super().__init__()
        self.setWindowTitle("SIMPLEPLAYER")
        icon_path = Path(__file__).resolve().parent / "resources" / "icon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(760, 460)

        self.registry = BackendRegistry()
        self.engine: AudioEngine | None = None
        self.audio = RealtimeAudioOutput()
        self._restore_audio_device()
        self.tracks: list[TrackInfo] = []
        self.single_instance_server: SingleInstanceServer | None = None

        self.drop_panel = DropPanel(self.open_files)
        self.status = QLabel("Loading emulated backend registry...")
        self.now_playing = QLabel("No file loaded")
        self.now_playing.setObjectName("nowPlaying")
        self.track_combo = QComboBox()
        self.track_combo.currentIndexChanged.connect(self.change_track)

        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.toggle_playback)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_playback)

        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(100)
        self.volume.valueChanged.connect(self.change_volume)

        self.seek_bar = QSlider(Qt.Orientation.Horizontal)
        self.seek_bar.setRange(0, 1000)
        self.seek_bar.sliderPressed.connect(self.user_seeking_started)
        self.seek_bar.sliderReleased.connect(self.seek_finished)
        self._is_seeking = False

        self.voices = QListWidget()
        self.voices.itemChanged.connect(self.change_voice_mute)

        controls = QHBoxLayout()
        controls.addWidget(self.play_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(QLabel("Track"))
        controls.addWidget(self.track_combo, 1)
        controls.addWidget(QLabel("Volume"))
        controls.addWidget(self.volume)

        layout = QVBoxLayout()
        layout.addWidget(self.drop_panel)
        layout.addWidget(self.now_playing)
        layout.addWidget(self.seek_bar)
        layout.addLayout(controls)
        layout.addWidget(QLabel("Voices / channels"))
        layout.addWidget(self.voices)
        layout.addWidget(self.status)

        root = QWidget()
        root.setLayout(layout)
        self.setCentralWidget(root)
        self._build_menu()
        self._apply_style()

        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.refresh_position)
        self.timer.start()

        self._boot_engine()

        if startup_files:
            QTimer.singleShot(0, lambda: self.open_files(startup_files))

    def closeEvent(self, event) -> None:
        self.audio.stop()
        if self.single_instance_server:
            self.single_instance_server.stop()
        if self.engine:
            self.engine.close()
        super().closeEvent(event)

    def enable_single_instance_server(self) -> None:
        server = SingleInstanceServer(self.open_files)
        if server.start():
            self.single_instance_server = server
        else:
            self.status.setText("Single-instance listener unavailable; Explorer opens may create new windows.")

    def _build_menu(self) -> None:
        open_action = QAction("Open...", self)
        open_action.triggered.connect(self.pick_file)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        menu = self.menuBar().addMenu("File")
        menu.addAction(open_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        self.audio_menu = self.menuBar().addMenu("Audio")
        self.audio_menu.aboutToShow.connect(self._populate_audio_menu)

        backend_action = QAction("Backends...", self)
        backend_action.triggered.connect(self.show_backends)
        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction(backend_action)

    def _boot_engine(self) -> None:
        installed = [spec.name for spec in self.registry.specs if spec.available]
        planned = [spec.name for spec in self.registry.specs if not spec.available]
        self.status.setText(
            f"Installed: {', '.join(installed)} | Planned isolated slots: {len(planned)}"
        )

    def pick_file(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open emulated music",
            "",
            "Emulated music (*.ay *.gbs *.gym *.hes *.kss *.nsf *.nsfe *.sap *.spc *.vgm *.vgz);;All files (*.*)",
        )
        if file_name:
            self.open_files([Path(file_name)])

    def show_backends(self) -> None:
        QMessageBox.information(self, "Emulated Backends", "\n".join(self.registry.describe()))

    def open_files(self, files: list[Path]) -> None:
        path = next((file for file in files if self.registry.find(file)), None)
        if not path:
            self.status.setText("No supported emulated music file found in drop.")
            return

        try:
            self.audio.playing = False
            if self.engine:
                self.engine.close()
            self.engine = self.registry.create_for(path)
            self.audio.set_engine(self.engine)
            self._ensure_audio_started()
            self.tracks = self.engine.open(path)
            self._populate_tracks()
            self._populate_voices()
            self.now_playing.setText(path.name)
            backend_name = getattr(self.engine, "display_name", type(self.engine).__name__)
            self.status.setText(f"Loaded {path.name} with {backend_name} and {len(self.tracks)} track(s)")
            self.audio.playing = True
            self.play_button.setText("Pause")
        except EngineError as exc:
            QMessageBox.warning(self, "Could not open file", str(exc))
            self.status.setText(str(exc))

    def _populate_tracks(self) -> None:
        self.track_combo.blockSignals(True)
        self.track_combo.clear()
        for track in self.tracks:
            detail = " - ".join(part for part in (track.title, track.author, _format_ms(track.play_length_ms)) if part)
            self.track_combo.addItem(f"{track.index + 1}. {detail}", track.index)
        self.track_combo.blockSignals(False)

    def _populate_voices(self) -> None:
        self.voices.blockSignals(True)
        self.voices.clear()
        if not self.engine:
            return
        for index, name in enumerate(self.engine.voice_names()):
            item_text = f"{index + 1}. {name}"
            self.voices.addItem(item_text)
            item = self.voices.item(index)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
        self.voices.blockSignals(False)

    def change_track(self, combo_index: int) -> None:
        if combo_index < 0 or not self.engine:
            return
        track_index = int(self.track_combo.itemData(combo_index))
        try:
            self.engine.start_track(track_index)
            self._populate_voices()
        except EngineError as exc:
            self.status.setText(str(exc))

    def toggle_playback(self) -> None:
        try:
            self._ensure_audio_started()
        except Exception as exc:
            QMessageBox.warning(self, "Audio output unavailable", str(exc))
            self.status.setText(str(exc))
            return
        self.audio.playing = not self.audio.playing
        self.play_button.setText("Pause" if self.audio.playing else "Play")

    def _ensure_audio_started(self) -> None:
        self.audio.start()

    def stop_playback(self) -> None:
        if self.audio:
            self.audio.playing = False
            self.play_button.setText("Play")
        if self.engine:
            self.engine.seek_ms(0)

    def change_volume(self, value: int) -> None:
        if self.audio:
            self.audio.volume = value / 100

    def user_seeking_started(self) -> None:
        self._is_seeking = True

    def seek_finished(self) -> None:
        if not self.engine:
            self._is_seeking = False
            return
        track = self.tracks[self.engine.current_track] if self.tracks else None
        if track and track.play_length_ms > 0:
            target_ms = int((self.seek_bar.value() / 1000) * track.play_length_ms)
            self.engine.seek_ms(target_ms)
        self._is_seeking = False

    def change_voice_mute(self, item) -> None:
        if not self.engine:
            return
        index = self.voices.row(item)
        muted = item.checkState() != Qt.CheckState.Checked
        self.engine.mute_voice(index, muted)

    def refresh_position(self) -> None:
        if not self.engine or not self.engine.path:
            return
        current_ms = self.engine.tell_ms()
        pos = _format_ms(current_ms)
        track = self.tracks[self.engine.current_track] if self.tracks else None
        duration = _format_ms(track.play_length_ms) if track else "--:--"
        backend_name = getattr(self.engine, "display_name", type(self.engine).__name__)
        self.status.setText(
            f"{self.engine.path.name} | {backend_name} | Track {self.engine.current_track + 1} | {pos} / {duration}"
        )

        if track and track.play_length_ms > 0 and getattr(self, "_is_seeking", False) is False:
            ratio = min(1.0, current_ms / track.play_length_ms)
            self.seek_bar.blockSignals(True)
            self.seek_bar.setValue(int(ratio * 1000))
            self.seek_bar.blockSignals(False)

    def _restore_audio_device(self) -> None:
        settings = QSettings("SimplePlayer", "SimplePlayer")
        saved_name = settings.value("audio/device_name", "")
        saved_hostapi = settings.value("audio/device_hostapi", "")
        if saved_name and saved_hostapi:
            try:
                devices = sd.query_devices()
                hostapis = sd.query_hostapis()
                for idx, dev in enumerate(devices):
                    if dev['max_output_channels'] > 0:
                        hostapi_name = hostapis[dev['hostapi']]['name']
                        if dev['name'] == saved_name and hostapi_name == saved_hostapi:
                            self.audio.device_id = idx
                            break
            except Exception:
                pass

    def _populate_audio_menu(self) -> None:
        self.audio_menu.clear()

        # Default Device option
        default_action = QAction("Default Device", self)
        default_action.setCheckable(True)
        default_action.setChecked(self.audio.device_id is None)
        default_action.triggered.connect(lambda checked=False: self.select_audio_device(None))
        self.audio_menu.addAction(default_action)
        self.audio_menu.addSeparator()

        try:
            devices = sd.query_devices()
            hostapis = sd.query_hostapis()
        except Exception as e:
            error_action = QAction(f"Error querying devices: {e}", self)
            error_action.setEnabled(False)
            self.audio_menu.addAction(error_action)
            return

        for idx, dev in enumerate(devices):
            if dev['max_output_channels'] > 0:
                hostapi_name = hostapis[dev['hostapi']]['name']
                name = f"{dev['name']} ({hostapi_name})"
                action = QAction(name, self)
                action.setCheckable(True)
                action.setChecked(self.audio.device_id == idx)
                action.triggered.connect(lambda checked=False, i=idx: self.select_audio_device(i))
                self.audio_menu.addAction(action)

    def select_audio_device(self, device_id: int | None) -> None:
        try:
            self.audio.set_device(device_id)
            settings = QSettings("SimplePlayer", "SimplePlayer")
            if device_id is None:
                settings.setValue("audio/device_name", "")
                settings.setValue("audio/device_hostapi", "")
            else:
                try:
                    dev = sd.query_devices(device_id)
                    hostapis = sd.query_hostapis()
                    hostapi_name = hostapis[dev['hostapi']]['name']
                    settings.setValue("audio/device_name", dev['name'])
                    settings.setValue("audio/device_hostapi", hostapi_name)
                except Exception:
                    pass
        except Exception as exc:
            QMessageBox.warning(self, "Could not set audio device", str(exc))

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #111713;
                color: #edf4e8;
                font-family: "Segoe UI", "Verdana";
                font-size: 14px;
            }
            #dropPanel {
                border: 2px dashed #a8d16d;
                border-radius: 24px;
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
                    stop: 0 #18281c, stop: 0.55 #15251f, stop: 1 #293018);
                min-height: 150px;
            }
            #dropTitle {
                font-size: 22px;
                font-weight: 700;
                color: #f7ffd8;
            }
            #dropSubtitle, QLabel {
                color: #bfd2b8;
            }
            #nowPlaying {
                color: #ffffff;
                font-size: 18px;
                font-weight: 600;
            }
            QPushButton, QComboBox {
                background: #d2f277;
                color: #152012;
                border: 0;
                border-radius: 10px;
                padding: 8px 12px;
                font-weight: 700;
            }
            QPushButton:hover, QComboBox:hover {
                background: #ecff9c;
            }
            QListWidget {
                background: #0c100e;
                border: 1px solid #2e3b2e;
                border-radius: 14px;
                padding: 8px;
            }
            QSlider::groove:horizontal {
                height: 7px;
                background: #2d3b2c;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #eaff92;
                width: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }
            """
        )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    startup_files = [Path(arg) for arg in argv[1:] if not arg.startswith("-")]

    if startup_files and send_to_running_instance(startup_files):
        return 0

    app = QApplication(argv)
    window = MainWindow(startup_files=startup_files)
    window.enable_single_instance_server()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
