import sys
import os
import requests
import re
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QListWidget, QListWidgetItem, QLabel, QStatusBar, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QSlider, QSplitter, QProgressBar, QFileDialog, QDialog,
    QFormLayout, QDialogButtonBox, QMessageBox, QTabWidget, QComboBox, QMenu,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QUrl, QTimer, QSize, QRectF
from PySide6.QtGui import QFont, QPalette, QColor, QIcon, QPixmap, QAction, QTextDocument, QFontDatabase

def load_nes_font():
    # Dynamically load the authentic Press Start 2P pixel font
    import os
    _font_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
        "assets", "PressStart2P-Regular.ttf"
    )
    if os.path.exists(_font_path):
        from PySide6.QtGui import QFontDatabase
        QFontDatabase.addApplicationFont(_font_path)


# Custom QFont subclass that redirects 'Courier New' and other monospace requests
# to 'Press Start 2P', and scales down sizes to preserve beautiful 8-bit aspect layout
_original_qfont = QFont
class QFontWrapper(_original_qfont):
    def __init__(self, *args, **kwargs):
        if args:
            args = list(args)
            family = args[0]
            if isinstance(family, str) and (family in ("Courier New", "Courier", "monospace")):
                args[0] = "Press Start 2P"
            
            # Scale down the font size since NES pixel font is wide and bold
            if len(args) > 1 and isinstance(args[1], (int, float)):
                size = args[1]
                if size >= 24:
                    args[1] = 13
                elif size >= 16:
                    args[1] = 10
                elif size >= 14:
                    args[1] = 9
                elif size >= 11:
                    args[1] = 8
                elif size >= 9:
                    args[1] = 7
                else:
                    args[1] = max(5, int(size * 0.65))
            args = tuple(args)
        super().__init__(*args, **kwargs)

# Inject QFont override
QFont = QFontWrapper

from chiptunepalace.gui.theme import GLOBAL_STYLE
from chiptunepalace.services.audio_engine import AudioEngine, PlaybackState
from chiptunepalace.services.track_service import TrackService, SUPPORTED_EXTS
from chiptunepalace.services.queue_manager import QueueManager
from chiptunepalace.services.download_service import DownloadService
from chiptunepalace.services.web_scraper_service import WebScraperService, ScraperThread, RandomizerThread
from chiptunepalace.services.config_service import ConfigService
from chiptunepalace.services.hotkey_service import HotkeyService
from chiptunepalace.gui.shortcuts import KeyboardShortcutModule


class ImageLoaderThread(QThread):
    """Asynchronous loader for Libretro artwork and screenshots."""
    loaded = Signal(str, QPixmap)  # (type: "boxart"|"screenshot", QPixmap)

    def __init__(self, img_type, url):
        super().__init__()
        self.img_type = img_type
        self.url = url

    def run(self):
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(self.url, headers=headers, timeout=10)
            if response.status_code == 200:
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                self.loaded.emit(self.img_type, pixmap)
            else:
                self.loaded.emit(self.img_type, QPixmap())
        except Exception:
            self.loaded.emit(self.img_type, QPixmap())


class DecoderInstallerThread(QThread):
    """Asynchronous installer for high-fidelity emulation CLI transcoders (vgmstream)."""
    progress = Signal(str)
    finished = Signal(bool, str)

    def run(self):
        import urllib.request
        import zipfile
        import shutil
        
        vendor_bin_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            "vendor", "bin"
        )
        os.makedirs(vendor_bin_dir, exist_ok=True)
        
        url = "https://github.com/bnnm/vgmstream-builds/raw/master/bin/vgmstream-latest-test-u.zip"
        zip_path = os.path.join(vendor_bin_dir, "vgmstream_temp.zip")
        
        try:
            self.progress.emit("Downloading high-fidelity retro decoders...")
            import ssl
            ssl_context = ssl._create_unverified_context()
            
            req = urllib.request.Request(
                url, 
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, context=ssl_context, timeout=20) as response, open(zip_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
            
            self.progress.emit("Extracting decoder packages...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(vendor_bin_dir)
                
            if os.path.exists(zip_path):
                os.remove(zip_path)
                
            exe_path = os.path.join(vendor_bin_dir, "vgmstream-cli.exe")
            if os.path.exists(exe_path):
                self.finished.emit(True, "Decoders installed successfully! PlayStation (PSF) and all other chiptunes will now play with high-fidelity native quality.")
            else:
                self.finished.emit(False, "Extraction completed, but vgmstream-cli.exe was not found. Please check your internet connection or install manually.")
        except Exception as e:
            self.finished.emit(False, f"Installation failed: {e}")
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except:
                    pass


class RichTextDelegate(QStyledItemDelegate):
    """Custom delegate that renders HTML/RichText text inside QTreeWidgetItems."""
    def paint(self, painter, option, index):
        options = QStyleOptionViewItem(option)
        self.initStyleOption(options, index)
        
        painter.save()
        
        doc = QTextDocument()
        doc.setDefaultFont(options.font)
        
        # Load the HTML markup content of the item
        html_text = options.text
        if option.state & QStyle.State_MouseOver:
            html_text = f"<span style='text-decoration: underline;'>{html_text}</span>"
        doc.setHtml(html_text)
        
        # Clear base text so standard delegate doesn't double-draw it
        options.text = ""
        
        # Paint item background and standard interactive states (focus, hover, select, etc)
        style = options.widget.style() if options.widget else QApplication.style()
        style.drawControl(QStyle.CE_ItemViewItem, options, painter, options.widget)
        
        # Clip painting inside tree row
        painter.translate(options.rect.left() + 5, options.rect.top())
        clip = QRectF(0, 0, options.rect.width() - 5, options.rect.height())
        doc.setTextWidth(clip.width())
        
        # Center the parsed HTML vertically within the row cell bounds
        text_height = doc.size().height()
        offset_y = (options.rect.height() - text_height) / 2
        if offset_y > 0:
            painter.translate(0, offset_y)
            
        doc.drawContents(painter, clip)
        
        painter.restore()


class ShortcutsHelpDialog(QDialog):
    """Sleek retro pop-up dialog showing keyboard shortcut hotkeys."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("HOTKEY MANUAL")
        self.setFixedWidth(420)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        
        # Style with dark translucent theme and bright neon border
        self.setStyleSheet(
            "QDialog {"
            "  background-color: rgb(15, 15, 25);"
            "  border: 2px solid #ff00ff;"
            "  border-radius: 8px;"
            "}"
            "QLabel {"
            "  color: #00d4ff;"
            "  font-family: 'Press Start 2P';"
            "  font-size: 7px;"
            "}"
        )
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("⌨ CHIPTUNE HOTKEYS")
        title.setFont(QFont("Courier New", 14, QFont.Bold))
        title.setStyleSheet("color: #ff00ff; letter-spacing: 1px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Divider line
        divider = QWidget()
        divider.setStyleSheet("background-color: #2a2a4a; min-height: 1px; max-height: 1px;")
        layout.addWidget(divider)
        
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setContentsMargins(0, 10, 0, 10)
        
        shortcuts = [
            ("Space / Media Play", "Play / Pause"),
            ("Right Arrow", "Seek Forward 5s"),
            ("Left Arrow", "Seek Backward 5s"),
            ("Up Arrow", "Volume Up 5%"),
            ("Down Arrow", "Volume Down 5%"),
            ("Ctrl + Right / Media Next", "Next Track"),
            ("Ctrl + Left / Media Prev", "Prev Track"),
            ("Ctrl + S", "Toggle Shuffle"),
            ("Ctrl + R", "Toggle Repeat One"),
            ("Ctrl + F", "Focus Local Filter"),
            ("Ctrl + Shift + F", "Focus Online Search"),
            ("Esc", "Clear Search & Focus"),
            ("Ctrl + ,", "Open Settings Dialog"),
        ]
        
        for key, desc in shortcuts:
            lbl_key = QLabel(key)
            lbl_key.setFont(QFont("Courier New", 10, QFont.Bold))
            lbl_key.setStyleSheet("color: #ffd700;") # Gold keys
            
            lbl_desc = QLabel(desc)
            lbl_desc.setFont(QFont("Courier New", 10))
            lbl_desc.setStyleSheet("color: #ffffff;")
            
            form_layout.addRow(lbl_key, lbl_desc)
            
        layout.addLayout(form_layout)
        
        # OK Button
        btn_ok = QPushButton("ACKNOWLEDGE")
        btn_ok.setFont(QFont("Courier New", 10, QFont.Bold))
        btn_ok.setStyleSheet(
            "QPushButton {"
            "  color: #39ff14; border: 1px solid #39ff14; border-radius: 4px; padding: 8px;"
            "  background-color: transparent;"
            "}"
            "QPushButton:hover {"
            "  background-color: rgba(57, 255, 20, 0.1);"
            "}"
        )
        btn_ok.clicked.connect(self.accept)
        layout.addWidget(btn_ok)


class CustomTitleBar(QWidget):
    """Retro themed titlebar replacing standard OS decoration."""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(15, 8, 15, 8)
        
        # --- LEFT SIDE UTILITIES (gorgeous intuitive buttons) ---
        # 1. Folder Quick Browse
        self.btn_title_browse = QPushButton("📂")
        self.btn_title_browse.setFixedSize(30, 30)
        self.btn_title_browse.setStyleSheet(
            "QPushButton {"
            "  color: #ffd700; border: 1px solid #ffd700; border-radius: 4px; font-size: 16px; background: rgba(0,0,0,0.2);"
            "}"
            "QPushButton:hover {"
            "  background: rgba(255, 215, 0, 0.15);"
            "}"
        )
        self.btn_title_browse.setToolTip("Quickly index and open local game music folders.")
        
        # 2. Keyboard Hotkey Guide
        self.btn_shortcuts_help = QPushButton("⌨")
        self.btn_shortcuts_help.setFixedSize(30, 30)
        self.btn_shortcuts_help.setStyleSheet(
            "QPushButton {"
            "  color: #ff00ff; border: 1px solid #ff00ff; border-radius: 4px; font-size: 16px; background: rgba(0,0,0,0.2);"
            "}"
            "QPushButton:hover {"
            "  background: rgba(255, 0, 255, 0.15);"
            "}"
        )
        self.btn_shortcuts_help.setToolTip("Show application keyboard shortcuts and media keys manual.")
        
        # 3. App settings & decoder installer
        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setFixedSize(30, 30)
        self.btn_settings.setStyleSheet(
            "QPushButton {"
            "  color: #00d4ff; border: 1px solid #00d4ff; border-radius: 4px; font-size: 16px; background: rgba(0,0,0,0.2);"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 212, 255, 0.15);"
            "}"
        )
        self.btn_settings.setToolTip("Open audio settings and install high-fidelity decoders.")
        
        self.layout.addWidget(self.btn_title_browse)
        self.layout.addWidget(self.btn_shortcuts_help)
        self.layout.addWidget(self.btn_settings)
        
        self.layout.addStretch()
        
        # Pixel-style Centered Title Label
        self.title_label = QLabel("CHIPTUNEPALACE")
        self.title_label.setFont(QFont("Courier New", 15, QFont.Bold))
        self.title_label.setStyleSheet("color: #e94560; letter-spacing: 2px;") # Hot pink
        self.title_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.title_label)
        
        self.layout.addStretch()
        
        # --- RIGHT SIDE WINDOW CONTROLS ---
        # Minimize Icon
        self.btn_min = QPushButton("─")
        self.btn_min.setFixedSize(30, 30)
        self.btn_min.setStyleSheet(
            "QPushButton {"
            "  color: #39ff14; border: 1px solid #39ff14; border-radius: 4px; font-weight: bold; background: rgba(0,0,0,0.2);"
            "}"
            "QPushButton:hover {"
            "  background: rgba(57, 255, 20, 0.15);"
            "}"
        )
        self.btn_min.setToolTip("Minimize Window")
        
        # Maximize/Restore Icon
        self.btn_max = QPushButton("▢")
        self.btn_max.setFixedSize(30, 30)
        self.btn_max.setStyleSheet(
            "QPushButton {"
            "  color: #ffd700; border: 1px solid #ffd700; border-radius: 4px; font-weight: bold; background: rgba(0,0,0,0.2);"
            "}"
            "QPushButton:hover {"
            "  background: rgba(255, 215, 0, 0.15);"
            "}"
        )
        self.btn_max.setToolTip("Toggle Maximize / Restore")
        
        # Close Icon
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(30, 30)
        self.btn_close.setStyleSheet(
            "QPushButton {"
            "  color: #e94560; border: 1px solid #e94560; border-radius: 4px; font-weight: bold; background: rgba(0,0,0,0.2);"
            "}"
            "QPushButton:hover {"
            "  background: rgba(233, 69, 96, 0.15);"
            "}"
        )
        self.btn_close.setToolTip("Close Application")
        
        self.layout.addWidget(self.btn_min)
        self.layout.addWidget(self.btn_max)
        self.layout.addWidget(self.btn_close)
        
        # Connect Actions
        self.btn_title_browse.clicked.connect(self.parent.scan_local_folder)
        self.btn_shortcuts_help.clicked.connect(self.parent.show_shortcuts_help)
        self.btn_settings.clicked.connect(self.parent.show_settings_dialog)
        self.btn_min.clicked.connect(self.parent.showMinimized)
        self.btn_max.clicked.connect(self.parent.toggle_maximize)
        self.btn_close.clicked.connect(self.parent.close)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.parent._drag_pos = event.globalPosition().toPoint() - self.parent.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and hasattr(self.parent, '_drag_pos'):
            self.parent.move(event.globalPosition().toPoint() - self.parent._drag_pos)
            event.accept()


class SettingsDialog(QDialog):
    """Allows configuration of download directory and other preferences."""
    def __init__(self, config_service, parent=None):
        super().__init__(parent)
        self.config_service = config_service
        self.setWindowTitle("SETTINGS")
        self.setMinimumSize(420, 290)
        self.setStyleSheet(GLOBAL_STYLE)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        form_layout = QFormLayout()
        
        self.lbl_dir = QLabel("Download Folder:")
        self.lbl_dir.setFont(QFont("Courier New", 11, QFont.Bold))
        self.txt_dir = QLineEdit()
        self.txt_dir.setText(self.config_service.get("download_dir"))
        
        self.btn_browse = QPushButton("BROWSE")
        self.btn_browse.setStyleSheet("padding: 4px 10px; font-size: 11px;")
        self.btn_browse.clicked.connect(self.browse_directory)
        
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.txt_dir)
        dir_layout.addWidget(self.btn_browse)
        
        form_layout.addRow(self.lbl_dir, dir_layout)
        layout.addLayout(form_layout)
        layout.addSpacing(10)
        
        # Decoders installation section
        self.lbl_decoders_title = QLabel("Sound Engine Decoders:")
        self.lbl_decoders_title.setFont(QFont("Courier New", 11, QFont.Bold))
        self.lbl_decoders_title.setStyleSheet("color: #00d4ff;")
        
        self.btn_install_decoders = QPushButton("INSTALL HIGH-FIDELITY DECODERS")
        self.btn_install_decoders.setStyleSheet("""
            QPushButton {
                background-color: #00d4ff;
                color: #0d0d1a;
                font-family: 'Press Start 2P';
                font-size: 7px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background-color: #00e5ff;
            }
            QPushButton:disabled {
                background-color: #4a4a5a;
                color: #8a8a9a;
            }
        """)
        self.btn_install_decoders.clicked.connect(self.install_decoders)
        
        self.lbl_decoder_status = QLabel("")
        self.lbl_decoder_status.setFont(QFont("Courier New", 10))
        self.lbl_decoder_status.setStyleSheet("color: #ff9f00;")
        self.lbl_decoder_status.setWordWrap(True)
        
        # Check if already installed
        vendor_bin_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
            "vendor", "bin"
        )
        if os.path.exists(os.path.join(vendor_bin_dir, "vgmstream-cli.exe")):
            self.lbl_decoder_status.setText("Status: High-fidelity decoders are already installed and active!")
            self.lbl_decoder_status.setStyleSheet("color: #39ff14;")
            self.btn_install_decoders.setText("REINSTALL HIGH-FIDELITY DECODERS")
            
        layout.addWidget(self.lbl_decoders_title)
        layout.addWidget(self.btn_install_decoders)
        layout.addWidget(self.lbl_decoder_status)
        layout.addSpacing(15)
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.setStyleSheet("QPushButton { min-width: 80px; }")
        self.button_box.accepted.connect(self.save_settings)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        
    def install_decoders(self):
        self.btn_install_decoders.setEnabled(False)
        self.lbl_decoder_status.setStyleSheet("color: #ff9f00;")
        self.lbl_decoder_status.setText("Status: Initializing installer...")
        
        self.installer_thread = DecoderInstallerThread(self)
        self.installer_thread.progress.connect(self.on_installer_progress)
        self.installer_thread.finished.connect(self.on_installer_finished)
        self.installer_thread.start()
        
    def on_installer_progress(self, msg):
        self.lbl_decoder_status.setText(f"Status: {msg}")
        
    def on_installer_finished(self, success, msg):
        self.btn_install_decoders.setEnabled(True)
        if success:
            self.lbl_decoder_status.setText(f"Success: {msg}")
            self.lbl_decoder_status.setStyleSheet("color: #39ff14;")
            self.btn_install_decoders.setText("REINSTALL HIGH-FIDELITY DECODERS")
            
            # Show a friendly popup to the user
            from PySide6.QtWidgets import QMessageBox
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("INSTALL SUCCESS")
            msg_box.setText("Decoders Installed Successfully!")
            msg_box.setInformativeText(msg)
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #1a1a2e;
                    border: 2px solid #39ff14;
                    border-radius: 10px;
                }
                QLabel {
                    color: #ffffff;
                    font-family: 'Press Start 2P';
                    font-size: 8px;
                }
                QPushButton {
                    background-color: #39ff14;
                    color: #0d0d1a;
                    font-family: 'Press Start 2P';
                    font-size: 7px;
                    font-weight: bold;
                    border: none;
                    border-radius: 5px;
                    padding: 8px 16px;
                    min-width: 70px;
                }
                QPushButton:hover {
                    background-color: #55ff55;
                }
            """)
            msg_box.exec()
        else:
            self.lbl_decoder_status.setText(f"Error: {msg}")
            self.lbl_decoder_status.setStyleSheet("color: #ff007f;")
        
    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "SELECT DOWNLOAD FOLDER", self.txt_dir.text())
        if directory:
            self.txt_dir.setText(os.path.abspath(directory))
            
    def save_settings(self):
        self.config_service.set("download_dir", self.txt_dir.text())
        self.accept()


class QComboBoxDialog(QDialog):
    """Combobox dialog allowing users to pick elements like ZIP members."""
    def __init__(self, title, label_text, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(380)
        self.setStyleSheet(GLOBAL_STYLE)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        lbl = QLabel(label_text)
        lbl.setFont(QFont("Courier New", 11, QFont.Bold))
        layout.addWidget(lbl)
        
        self.combo = QComboBox()
        self.combo.addItems(items)
        layout.addWidget(self.combo)
        
        layout.addSpacing(15)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    @staticmethod
    def get_selection(parent, title, label_text, items):
        dialog = QComboBoxDialog(title, label_text, items, parent)
        result = dialog.exec()
        return dialog.combo.currentText(), result == QDialog.Accepted


class MainWindow(QMainWindow):
    def __init__(self):
        load_nes_font()
        super().__init__()
        
        self._initialized = False
        
        # Initialize Logging and DebugService first
        from chiptunepalace.services.debug_service import DebugService
        self.debug_service = DebugService()
        self.debug_service.install_excepthook()
        self.debug_service.log_info("--- Chiptune Palace Application Startup ---")
        
        self.setWindowTitle("CHIPTUNEPALACE")
        self.setMinimumSize(1000, 700)
        
        # Enable frameless transparent look
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # Initialize Backend Services
        self.config_service = ConfigService()
        self.track_service = TrackService()
        self.audio_engine = AudioEngine()
        
        # Inject custom download directory from ConfigService
        download_dir = self.config_service.get("download_dir")
        self.download_service = DownloadService(download_dir=download_dir)
        
        self.queue_manager = QueueManager(self.track_service, self.audio_engine)
        self.scraper = WebScraperService()
        self.hotkey_service = HotkeyService(self.audio_engine, self.queue_manager)
        
        self._is_dragging_slider = False
        self._is_maximized = False
        self._normal_geometry = None
        self._image_threads = []
        self._current_track = None
        
        # State tracking
        self.is_repeat_one = False
        self.is_randomizer_active = False
        self.randomizer_thread = None
        self._play_first_track_of_expanded_item = None
        self._error_dialog_active = False
        
        self.init_ui()
        self.apply_theme()
        
        # Initialize keyboard shortcuts manager
        self.shortcuts = KeyboardShortcutModule(self)
        
        # Load local library tree on startup
        self.load_online_consoles()
        
        # Hook VLC audio events
        self.audio_engine.playback_state_changed.connect(self.on_playback_state_changed)
        self.audio_engine.position_changed.connect(self.on_playback_position_changed)
        self.audio_engine.duration_changed.connect(self.on_playback_duration_changed)
        self.audio_engine.error_occurred.connect(self.on_playback_error)
        self.audio_engine.warning_occurred.connect(self.on_playback_warning)
        self.audio_engine.track_finished.disconnect(self.queue_manager.advance_to_next_track) # disconnect base loop to support repeat one
        self.audio_engine.track_finished.connect(self.on_track_finished)
        
        # Set default volume
        default_volume = self.config_service.get("volume")
        self.audio_engine.set_volume(default_volume)
        self.volume_slider.setValue(default_volume)
        
        self._initialized = True
        
    def init_ui(self):
        # Master Translucent Central Widget
        self.central_widget = QWidget()
        self.central_widget.setObjectName("centralWidget")
        self.setCentralWidget(self.central_widget)
        
        master_layout = QVBoxLayout(self.central_widget)
        master_layout.setContentsMargins(2, 2, 2, 2)
        master_layout.setSpacing(0)
        
        # 1. Custom Title Bar
        self.title_bar = CustomTitleBar(self)
        master_layout.addWidget(self.title_bar)
        
        # Scanline Glow CRT overlay
        self.scanline_overlay = QWidget(self.central_widget)
        self.scanline_overlay.setObjectName("scanlineOverlay")
        self.scanline_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        # 2. Main Content Area Splitter
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setHandleWidth(2)
        
        # --- LEFT PANEL (Library tree & Search Scraper) ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(10, 10, 10, 10)
        
        self.nav_tabs = QTabWidget()
        
        # Tab 1: Library Tree
        self.tab_library = QWidget()
        lib_layout = QVBoxLayout(self.tab_library)
        lib_layout.setContentsMargins(0, 5, 0, 0)
        
        # Library Filter Search Bar
        filter_layout = QHBoxLayout()
        self.txt_lib_filter = QLineEdit()
        self.txt_lib_filter.setPlaceholderText("🔍 Filter Consoles & Games...")
        self.txt_lib_filter.setFont(QFont("Courier New", 10))
        self.txt_lib_filter.setStyleSheet(
            "QLineEdit {"
            "  color: #ffffff; background-color: rgba(20, 20, 20, 0.6); "
            "  border: 1px solid #ff00ff; border-radius: 4px; padding: 5px;"
            "}"
            "QLineEdit:focus {"
            "  border: 1px solid #39ff14;"
            "}"
        )
        self.txt_lib_filter.textChanged.connect(self.filter_library_tree)
        filter_layout.addWidget(self.txt_lib_filter)
        lib_layout.addLayout(filter_layout)
        
        self.library_tree = QTreeWidget()
        self.library_tree.setItemDelegate(RichTextDelegate(self.library_tree))
        self.library_tree.setHeaderLabel("Retro Archive Explorer")
        self.library_tree.setFont(QFont("Courier New", 11))
        self.library_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.library_tree.customContextMenuRequested.connect(self.show_library_context_menu)
        self.library_tree.itemDoubleClicked.connect(self.on_library_item_double_clicked)
        self.library_tree.itemClicked.connect(self.on_library_item_clicked)
        self.library_tree.itemExpanded.connect(self.on_tree_item_expanded)
        self.library_tree.setMouseTracking(True)
        self.library_tree.entered.connect(lambda index: self.library_tree.viewport().update())
        self.library_tree.currentItemChanged.connect(self.on_library_current_item_changed)
        lib_layout.addWidget(self.library_tree)
        
        lib_buttons_layout = QHBoxLayout()
        
        self.btn_open_file = QPushButton("OPEN FILE")
        self.btn_open_file.clicked.connect(self.open_and_play_file)
        self.btn_open_file.setStyleSheet("color: #00d4ff; border-color: #00d4ff;")
        
        self.btn_scan_folder = QPushButton("SCAN FOLDER")
        self.btn_scan_folder.clicked.connect(self.scan_local_folder)
        self.btn_scan_folder.setStyleSheet("color: #ffd700; border-color: #ffd700;")
        
        self.btn_refresh_lib = QPushButton("REFRESH")
        self.btn_refresh_lib.clicked.connect(self.refresh_library_tree)
        
        lib_buttons_layout.addWidget(self.btn_open_file)
        lib_buttons_layout.addWidget(self.btn_scan_folder)
        lib_buttons_layout.addWidget(self.btn_refresh_lib)
        
        lib_layout.addLayout(lib_buttons_layout)
        
        # Tab 2: Online Search & Scraper
        self.tab_scraper = QWidget()
        scrap_layout = QVBoxLayout(self.tab_scraper)
        scrap_layout.setContentsMargins(0, 5, 0, 0)
        
        search_row = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search Retro Music...")
        self.txt_search.returnPressed.connect(self.trigger_online_search)
        
        self.btn_search = QPushButton("SEARCH")
        self.btn_search.clicked.connect(self.trigger_online_search)
        
        search_row.addWidget(self.txt_search)
        search_row.addWidget(self.btn_search)
        scrap_layout.addLayout(search_row)
        
        # Scraper Results List
        self.search_results = QListWidget()
        self.search_results.setFont(QFont("Courier New", 11))
        self.search_results.itemClicked.connect(self.on_search_result_clicked)
        self.search_results.itemDoubleClicked.connect(self.on_search_result_double_clicked)
        scrap_layout.addWidget(self.search_results)
        
        self.btn_download_pack = QPushButton("DOWNLOAD & STREAM PACK")
        self.btn_download_pack.setEnabled(False)
        self.btn_download_pack.clicked.connect(self.download_selected_online_pack)
        scrap_layout.addWidget(self.btn_download_pack)
        
        self.nav_tabs.addTab(self.tab_library, "LOCAL LIBRARY")
        self.nav_tabs.addTab(self.tab_scraper, "ONLINE SCRAPER")
        
        left_layout.addWidget(self.nav_tabs)
        main_splitter.addWidget(left_widget)
        
        # --- RIGHT PANEL (Artwork display & details) ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 10, 10, 10)
        
        # Title Metadata Panel
        self.metadata_panel = QWidget()
        meta_layout = QVBoxLayout(self.metadata_panel)
        meta_layout.setContentsMargins(0, 0, 0, 10)
        
        self.lbl_now_playing_title = QLabel("NO TUNE PLAYING")
        self.lbl_now_playing_title.setFont(QFont("Courier New", 16, QFont.Bold))
        self.lbl_now_playing_title.setStyleSheet("color: #39ff14;") # Lime text
        self.lbl_now_playing_title.setWordWrap(True)
        self.lbl_now_playing_title.setAlignment(Qt.AlignCenter)
        self.lbl_now_playing_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        
        self.lbl_now_playing_desc = QLabel("Select a retro game or query the online database to begin.")
        self.lbl_now_playing_desc.setFont(QFont("Courier New", 11))
        self.lbl_now_playing_desc.setWordWrap(True)
        self.lbl_now_playing_desc.setAlignment(Qt.AlignCenter)
        self.lbl_now_playing_desc.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        
        meta_layout.addWidget(self.lbl_now_playing_title)
        meta_layout.addWidget(self.lbl_now_playing_desc)
        right_layout.addWidget(self.metadata_panel)
        
        # Dual Artwork Panels (Cover box art & Gameplay snap)
        art_layout = QHBoxLayout()
        
        # Box Art Box
        boxart_widget = QWidget()
        boxart_widget.setStyleSheet("border: 2px solid #2a2a4a; background: rgba(0,0,0,0.2);")
        boxart_widget_layout = QVBoxLayout(boxart_widget)
        boxart_widget_layout.setContentsMargins(5, 5, 5, 5)
        
        lbl_boxart_title = QLabel("BOX ART")
        lbl_boxart_title.setFont(QFont("Courier New", 9, QFont.Bold))
        lbl_boxart_title.setAlignment(Qt.AlignCenter)
        lbl_boxart_title.setStyleSheet("color: #ffd700; border: none; background: transparent;")
        
        self.lbl_boxart = QLabel()
        self.lbl_boxart.setFixedSize(220, 260)
        self.lbl_boxart.setAlignment(Qt.AlignCenter)
        self.lbl_boxart.setStyleSheet("border: none; background: transparent;")
        self.lbl_boxart.setText("[ NO BOX ART ]")
        
        boxart_widget_layout.addWidget(lbl_boxart_title)
        boxart_widget_layout.addWidget(self.lbl_boxart)
        art_layout.addWidget(boxart_widget)
        
        # Screenshot Box
        snap_widget = QWidget()
        snap_widget.setStyleSheet("border: 2px solid #2a2a4a; background: rgba(0,0,0,0.2);")
        snap_widget_layout = QVBoxLayout(snap_widget)
        snap_widget_layout.setContentsMargins(5, 5, 5, 5)
        
        lbl_snap_title = QLabel("GAMEPLAY SCREENSHOT")
        lbl_snap_title.setFont(QFont("Courier New", 9, QFont.Bold))
        lbl_snap_title.setAlignment(Qt.AlignCenter)
        lbl_snap_title.setStyleSheet("color: #00d4ff; border: none; background: transparent;")
        
        self.lbl_screenshot = QLabel()
        self.lbl_screenshot.setFixedSize(220, 260)
        self.lbl_screenshot.setAlignment(Qt.AlignCenter)
        self.lbl_screenshot.setStyleSheet("border: none; background: transparent;")
        self.lbl_screenshot.setText("[ NO SCREENSHOT ]")
        
        snap_widget_layout.addWidget(lbl_snap_title)
        snap_widget_layout.addWidget(self.lbl_screenshot)
        art_layout.addWidget(snap_widget)
        
        right_layout.addLayout(art_layout)
        right_layout.addStretch()
        
        main_splitter.addWidget(right_widget)
        
        # Set Splitter ratio
        main_splitter.setSizes([450, 550])
        master_layout.addWidget(main_splitter)
        
        # 3. Bottom Playback Controls Bar
        self.playback_bar = QWidget()
        self.playback_bar.setObjectName("playbackBar")
        playback_layout = QVBoxLayout(self.playback_bar)
        playback_layout.setContentsMargins(15, 10, 15, 10)
        
        # Seek row
        seek_layout = QHBoxLayout()
        self.lbl_time_current = QLabel("00:00")
        self.lbl_time_current.setFont(QFont("Courier New", 10))
        self.lbl_time_current.setMinimumWidth(45)
        
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 100)
        self.seek_slider.setValue(0)
        self.seek_slider.sliderPressed.connect(self.on_seek_slider_pressed)
        self.seek_slider.sliderReleased.connect(self.on_seek_slider_released)
        
        self.lbl_time_total = QLabel("00:00")
        self.lbl_time_total.setFont(QFont("Courier New", 10))
        self.lbl_time_total.setMinimumWidth(45)
        
        seek_layout.addWidget(self.lbl_time_current)
        seek_layout.addWidget(self.seek_slider)
        seek_layout.addWidget(self.lbl_time_total)
        playback_layout.addLayout(seek_layout)
        
        # Audio Control row
        control_row = QHBoxLayout()
        
        # Volume Box
        volume_layout = QHBoxLayout()
        lbl_vol_icon = QLabel("🔊")
        lbl_vol_icon.setStyleSheet("color: #ffd700; font-size: 14px;")
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        
        volume_layout.addWidget(lbl_vol_icon)
        volume_layout.addWidget(self.volume_slider)
        control_row.addLayout(volume_layout)
        
        control_row.addStretch()
        
        # Neon classic player buttons
        self.btn_prev = QPushButton("⏮")
        self.btn_prev.setFixedSize(36, 36)
        self.btn_prev.clicked.connect(self.play_previous_track)
        self.btn_prev.setStyleSheet(
            "QPushButton {"
            "  color: #00d4ff; border: 1px solid #00d4ff; border-radius: 4px; font-size: 16px; background: rgba(0,0,0,0.2);"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 212, 255, 0.15);"
            "}"
        )
        self.btn_prev.setToolTip("Previous Track (Ctrl+Left)")
        
        self.btn_stop = QPushButton("⏹")
        self.btn_stop.setFixedSize(36, 36)
        self.btn_stop.clicked.connect(self.stop_playback)
        self.btn_stop.setStyleSheet(
            "QPushButton {"
            "  color: #e94560; border: 1px solid #e94560; border-radius: 4px; font-size: 16px; background: rgba(0,0,0,0.2);"
            "}"
            "QPushButton:hover {"
            "  background: rgba(233, 69, 96, 0.15);"
            "}"
        )
        self.btn_stop.setToolTip("Stop Playback")
        
        self.btn_play = QPushButton("▶")
        self.btn_play.setObjectName("playBtn")
        self.btn_play.setFixedSize(46, 46)
        self.btn_play.clicked.connect(self.toggle_play_pause)
        self.btn_play.setToolTip("Play / Pause (Space)")
        
        self.btn_next = QPushButton("⏭")
        self.btn_next.setFixedSize(36, 36)
        self.btn_next.clicked.connect(self.play_next_track)
        self.btn_next.setStyleSheet(
            "QPushButton {"
            "  color: #00d4ff; border: 1px solid #00d4ff; border-radius: 4px; font-size: 16px; background: rgba(0,0,0,0.2);"
            "}"
            "QPushButton:hover {"
            "  background: rgba(0, 212, 255, 0.15);"
            "}"
        )
        self.btn_next.setToolTip("Next Track (Ctrl+Right)")
        
        control_row.addWidget(self.btn_prev)
        control_row.addWidget(self.btn_stop)
        control_row.addWidget(self.btn_play)
        control_row.addWidget(self.btn_next)
        
        control_row.addStretch()
        
        # Toggle Modes (Repeat, Shuffle and Randomizer)
        mode_layout = QHBoxLayout()
        self.btn_shuffle = QPushButton("SHUFFLE: OFF")
        self.btn_shuffle.setFixedWidth(110)
        self.btn_shuffle.setStyleSheet("color: #ffd700; border-color: #ffd700;") # Gold theme
        self.btn_shuffle.clicked.connect(self.toggle_shuffle)
        self.btn_shuffle.setToolTip("Toggle Shuffle Playback Mode (Ctrl+S)")
        
        self.btn_repeat = QPushButton("REPEAT: OFF")
        self.btn_repeat.setFixedWidth(110)
        self.btn_repeat.setStyleSheet("color: #ff6b6b; border-color: #ff6b6b;") # Pink-red theme
        self.btn_repeat.clicked.connect(self.toggle_repeat)
        self.btn_repeat.setToolTip("Toggle Repeat Track Mode (Ctrl+R)")
        
        self.btn_randomizer = QPushButton("👾 RADAR: OFF")
        self.btn_randomizer.setFixedWidth(120)
        self.btn_randomizer.setStyleSheet("color: #ff00ff; border-color: #ff00ff;") # Cyberpunk magenta theme!
        self.btn_randomizer.clicked.connect(self.toggle_randomizer)
        self.btn_randomizer.setToolTip("Toggle Cyber-Radar: auto-discovers and loops random internet retro tracks")
        
        mode_layout.addWidget(self.btn_shuffle)
        mode_layout.addWidget(self.btn_repeat)
        mode_layout.addWidget(self.btn_randomizer)
        control_row.addLayout(mode_layout)
        
        playback_layout.addLayout(control_row)
        master_layout.addWidget(self.playback_bar)
        
        # 4. Downloads Progress Panel (at very bottom)
        self.downloads_panel = QWidget()
        self.downloads_panel.setFixedHeight(40)
        self.downloads_panel.setStyleSheet("background: rgba(0,0,0,0.3); border-top: 1px solid #2a2a4a;")
        dl_layout = QHBoxLayout(self.downloads_panel)
        dl_layout.setContentsMargins(15, 2, 15, 2)
        
        self.lbl_dl_status = QLabel("NO LIVE DOWNLOADS")
        self.lbl_dl_status.setFont(QFont("Courier New", 10, QFont.Bold))
        self.lbl_dl_status.setStyleSheet("color: #6a7080; border: none;")
        
        self.dl_progress = QProgressBar()
        self.dl_progress.setRange(0, 100)
        self.dl_progress.setValue(0)
        self.dl_progress.setVisible(False)
        self.dl_progress.setStyleSheet("border-color: #00d4ff;") # Neon cyan border
        
        dl_layout.addWidget(self.lbl_dl_status)
        dl_layout.addWidget(self.dl_progress, stretch=1)
        master_layout.addWidget(self.downloads_panel)
        
        # 5. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Retro Arcade Core Initialized.")
        self.status_bar.setStyleSheet("QStatusBar { background: rgba(13, 13, 26, 255); color: #6a7080; font-family: 'Press Start 2P'; font-size: 6px; }")

    def apply_theme(self):
        self.setStyleSheet(GLOBAL_STYLE)

    # --- Title Bar & Frameless Window Commands ---
    def toggle_maximize(self):
        if self._is_maximized:
            self.showNormal()
            self._is_maximized = False
            self.title_bar.btn_max.setText("▢")
        else:
            self._normal_geometry = self.geometry()
            self.showMaximized()
            self._is_maximized = True
            self.title_bar.btn_max.setText("⧉")

    def show_settings_dialog(self):
        dialog = SettingsDialog(self.config_service, self)
        if dialog.exec() == QDialog.Accepted:
            # Re-inject new download service if path changed
            new_dir = self.config_service.get("download_dir")
            self.download_service.download_dir = new_dir
            self.status_bar.showMessage(f"Download directory updated to {new_dir}", 4000)
            self.refresh_library_tree()

    def show_shortcuts_help(self):
        dialog = ShortcutsHelpDialog(self)
        dialog.exec()

    # --- Local Library & Online Catalog Explorer Operations ---
    def refresh_library_tree(self):
        """Refreshes the catalog explorer (reloads online systems)."""
        self.load_online_consoles()

    def load_online_consoles(self):
        self.status_bar.showMessage("Connecting to retro music archives...")
        self.library_tree.clear()
        
        # Add a loading placeholder
        loading_item = QTreeWidgetItem(self.library_tree)
        loading_item.setText(0, "Loading Retro Systems Catalog...")
        loading_item.setFont(0, QFont("Courier New", 11, QFont.Bold))
        loading_item.setForeground(0, QColor("#ffd700"))
        loading_item.setData(0, Qt.UserRole, "loading")
        
        self.console_thread = ScraperThread(self.scraper.get_consoles)
        self.console_thread.task_finished.connect(self.on_consoles_loaded)
        self.console_thread.error.connect(self.on_consoles_error)
        self.console_thread.start()
        self._image_threads.append(self.console_thread)

    def on_consoles_loaded(self, consoles):
        self.library_tree.clear()
        if not consoles:
            self.status_bar.showMessage("Failed to connect online. Loading local library fallback.")
            self.refresh_local_only_tree()
            return
            
        self.status_bar.showMessage("Retro systems catalog loaded.", 4000)
        
        # Sort console name folders by name alphabetically
        sorted_consoles = sorted(consoles, key=lambda x: x.get("name", "").lower())
        for c in sorted_consoles:
            c_item = QTreeWidgetItem(self.library_tree)
            c_item.setText(0, c["name"].upper())
            c_item.setFont(0, QFont("Courier New", 12, QFont.Bold))
            c_item.setForeground(0, QColor("#00d4ff")) # Neon Cyan
            
            # Save metadata
            c_item.setData(0, Qt.UserRole, "console")
            c_item.setData(1, Qt.UserRole, c["url"])
            c_item.setData(2, Qt.UserRole, c["name"])
            
            # Add dummy child so it shows expand arrow
            dummy = QTreeWidgetItem(c_item)
            dummy.setText(0, "Loading Packs...")
            dummy.setData(0, Qt.UserRole, "dummy")

    def on_consoles_error(self, err):
        self.library_tree.clear()
        self.status_bar.showMessage(f"Catalog connection failed: {err[:50]}. Loading local fallback.", 6000)
        self.refresh_local_only_tree()

    def on_tree_item_expanded(self, item):
        node_type = item.data(0, Qt.UserRole)
        
        if node_type == "console":
            # Check if it has a dummy child (needs loading)
            if item.childCount() == 1 and item.child(0).data(0, Qt.UserRole) == "dummy":
                url = item.data(1, Qt.UserRole)
                console_name = item.data(2, Qt.UserRole)
                
                # Start background thread to load packs
                thread = ScraperThread(self.scraper.get_packs_by_console, url)
                thread.task_finished.connect(lambda packs, i=item, c=console_name: self.on_packs_loaded(i, c, packs))
                thread.error.connect(lambda err: self.status_bar.showMessage(f"Error loading packs: {err}", 5000))
                thread.start()
                self._image_threads.append(thread)
                
        elif node_type == "game":
            # Check if it has a dummy child
            if item.childCount() == 1 and item.child(0).data(0, Qt.UserRole) == "dummy":
                url = item.data(1, Qt.UserRole)
                game_name = item.data(2, Qt.UserRole)
                console_name = item.parent().data(2, Qt.UserRole)
                source = item.data(3, Qt.UserRole)
                
                # Check local database first!
                local_tracks = self.track_service.get_tracks_by_console_and_game(console_name, game_name)
                if local_tracks:
                    item.removeChild(item.child(0)) # Remove dummy
                    for t in local_tracks:
                        t_item = QTreeWidgetItem(item)
                        ext = ""
                        if t.get('member_name'):
                            ext = os.path.splitext(t['member_name'])[1].lower()
                        elif t.get('file_path'):
                            ext = os.path.splitext(t['file_path'])[1].lower()
                        elif t.get('format'):
                            ext = f".{t['format'].lower()}"
                        t_item.setText(0, f"[LOCAL] {t['title']}{ext}")
                        t_item.setFont(0, QFont("Courier New", 11))
                        t_item.setForeground(0, QColor("#00ff41")) # Retro Green
                        t_item.setData(0, Qt.UserRole, "track")
                        t_item.setData(1, Qt.UserRole, t['id'])
                    return
                
                if source == "ModArchive":
                    # ModArchive tracks are single songs (the pack is the song itself)
                    item.removeChild(item.child(0)) # Remove dummy
                    t_item = QTreeWidgetItem(item)
                    
                    ext = ".mod"
                    if url:
                        url_ext = os.path.splitext(url.split('?')[0])[1].lower()
                        if url_ext:
                            ext = url_ext
                    t_item.setText(0, f"[ONLINE] Play Module{ext}")
                    t_item.setFont(0, QFont("Courier New", 11))
                    t_item.setForeground(0, QColor("#00ffff")) # Cyan online
                    t_item.setData(0, Qt.UserRole, "online_track")
                    t_item.setData(1, Qt.UserRole, url) # The direct download URL
                    t_item.setData(2, Qt.UserRole, game_name)
                    t_item.setData(3, Qt.UserRole, source)
                else:
                    # Scrape VGMRips track listing online
                    thread = ScraperThread(self.scraper.get_tracks_in_pack, url)
                    thread.task_finished.connect(lambda tracks, i=item, g=game_name, u=url, s=source: self.on_tracks_loaded(i, g, u, s, tracks))
                    thread.error.connect(lambda err: self.status_bar.showMessage(f"Error loading tracks: {err}", 5000))
                    thread.start()
                    self._image_threads.append(thread)

    def on_packs_loaded(self, item, console_name, packs):
        # Remove dummy child
        if item.childCount() > 0:
            item.removeChild(item.child(0))
            
        if not packs:
            no_packs = QTreeWidgetItem(item)
            no_packs.setText(0, "[ No Packs Available ]")
            no_packs.setFont(0, QFont("Courier New", 11, QFont.StyleItalic))
            no_packs.setForeground(0, QColor("#6a7080"))
            return
            
        for p in packs:
            p_item = QTreeWidgetItem(item)
            p_item.setText(0, p["title"])
            p_item.setFont(0, QFont("Courier New", 11, QFont.Bold))
            p_item.setForeground(0, QColor("#ffd700")) # Gold
            
            # Check if this pack is already local
            local_tracks = self.track_service.get_tracks_by_console_and_game(console_name, p["title"])
            if local_tracks:
                p_item.setText(0, f"★ {p['title']}") # Star indicator for local downloaded packs
                p_item.setForeground(0, QColor("#39ff14")) # Bright lime
                
            p_item.setData(0, Qt.UserRole, "game")
            p_item.setData(1, Qt.UserRole, p["url"])
            p_item.setData(2, Qt.UserRole, p["title"])
            p_item.setData(3, Qt.UserRole, p.get("source", "VGMRips"))
            p_item.setData(4, Qt.UserRole, p.get("download_url", p["url"])) # Store ZIP download URL in role 4
            
            # Add dummy child so it shows expand arrow
            dummy = QTreeWidgetItem(p_item)
            dummy.setText(0, "Loading Tracks...")
            dummy.setData(0, Qt.UserRole, "dummy")

        # Re-apply active search filter if one is present
        filter_text = self.txt_lib_filter.text()
        if filter_text.strip():
            self.filter_library_tree(filter_text)

    def _find_matching_local_track(self, scraped_title, local_tracks):
        if not scraped_title or not local_tracks:
            return None
            
        # Normalize scraped title: remove punctuation, lowercase
        norm_scraped = re.sub(r'[^a-zA-Z0-9]', '', scraped_title).lower()
        
        # Try exact match or substring matches
        for t in local_tracks:
            # Strip number prefixes (e.g. "01 ", "01-", "01_") and extension
            local_title = t['title']
            local_title = os.path.splitext(local_title)[0]
            local_title = re.sub(r'^\d+[\s\-_]*', '', local_title)
            
            norm_local = re.sub(r'[^a-zA-Z0-9]', '', local_title).lower()
            
            if norm_scraped in norm_local or norm_local in norm_scraped:
                return t
                
        # Fallback: try checking if the local title contains the first few words of the scraped title
        words_scraped = [w for w in re.findall(r'\w+', scraped_title.lower()) if len(w) > 2]
        if words_scraped:
            for t in local_tracks:
                local_title = os.path.splitext(t['title'])[0].lower()
                if all(word in local_title for word in words_scraped[:2]):
                    return t
                    
        return None

    def on_tracks_loaded(self, item, game_name, pack_url, source, tracks):
        # Remove dummy
        if item.childCount() > 0:
            item.removeChild(item.child(0))
            
        if not tracks:
            # Fallback: if we couldn't scrape tracks list but have the zip link,
            # allow playing the direct ZIP archive as a single option
            t_item = QTreeWidgetItem(item)
            t_item.setText(0, "[ONLINE] Stream Pack.zip")
            t_item.setFont(0, QFont("Courier New", 11))
            t_item.setForeground(0, QColor("#00ffff"))
            t_item.setData(0, Qt.UserRole, "online_track")
            t_item.setData(1, Qt.UserRole, pack_url)
            t_item.setData(2, Qt.UserRole, game_name)
            t_item.setData(3, Qt.UserRole, source)
            return
            
        console_name = item.parent().data(2, Qt.UserRole)
        # Fetch local tracks for this console/game if any
        local_tracks = self.track_service.get_tracks_by_console_and_game(console_name, game_name)
        
        for t in tracks:
            t_item = QTreeWidgetItem(item)
            
            # Try to find a local match
            matched_local = None
            if local_tracks:
                matched_local = self._find_matching_local_track(t['title'], local_tracks)
                
            if matched_local:
                ext = ""
                if matched_local.get('member_name'):
                    ext = os.path.splitext(matched_local['member_name'])[1].lower()
                elif matched_local.get('file_path'):
                    ext = os.path.splitext(matched_local['file_path'])[1].lower()
                elif matched_local.get('format'):
                    ext = f".{matched_local['format'].lower()}"
                t_item.setText(0, f"[LOCAL] {t['title']}{ext}")
                t_item.setFont(0, QFont("Courier New", 11))
                t_item.setForeground(0, QColor("#00ff41")) # Lime local
                t_item.setData(0, Qt.UserRole, "track")
                t_item.setData(1, Qt.UserRole, matched_local['id'])
            else:
                ext = self.get_console_default_extension(console_name)
                t_item.setText(0, f"[ONLINE] {t['title']}{ext}")
                t_item.setFont(0, QFont("Courier New", 11))
                t_item.setForeground(0, QColor("#00ffff")) # Cyan online
                t_item.setData(0, Qt.UserRole, "online_track")
                t_item.setData(1, Qt.UserRole, pack_url) # Parent pack URL
                
            t_item.setData(2, Qt.UserRole, t['title']) # Track title
            t_item.setData(3, Qt.UserRole, source)

        # Check if this item is flagged to play its first track upon loading
        flagged_item = getattr(self, "_play_first_track_of_expanded_item", None)
        if flagged_item == item:
            self._play_first_track_of_expanded_item = None
            if item.childCount() > 0:
                first_child = item.child(0)
                if first_child.data(0, Qt.UserRole) in ("track", "online_track"):
                    self.library_tree.setCurrentItem(first_child)
                    self.on_library_item_double_clicked(first_child, 0)

    def get_console_default_extension(self, console_name):
        """Dynamically returns the primary retro music format extension for a given console."""
        c_lower = str(console_name).lower()
        if "snes" in c_lower or "super nintendo" in c_lower:
            return ".spc"
        elif "genesis" in c_lower or "mega drive" in c_lower:
            return ".vgm"
        elif "nes" == c_lower or " nes" in c_lower or "nes " in c_lower or "nintendo entertainment" in c_lower:
            return ".nsf"
        elif "game boy advance" in c_lower or "gba" in c_lower:
            return ".gsf"
        elif "game boy" in c_lower or "gbc" in c_lower or "gb " in c_lower:
            return ".gbs"
        elif "nintendo ds" in c_lower or "nds" in c_lower:
            return ".2sf"
        elif "nintendo 64" in c_lower or "n64" in c_lower:
            return ".usf"
        elif "master system" in c_lower or "game gear" in c_lower:
            return ".sgc"
        elif "saturn" in c_lower:
            return ".ssf"
        elif "dreamcast" in c_lower:
            return ".dsf"
        elif "playstation 2" in c_lower or "ps2" in c_lower:
            return ".psf2"
        elif "playstation" in c_lower or "ps1" in c_lower or "psx" in c_lower:
            return ".psf"
        elif "atari st" in c_lower or "cpc" in c_lower or "spectrum" in c_lower:
            return ".ym"
        elif "commodore 64" in c_lower or "c64" in c_lower or "sid" in c_lower:
            return ".sid"
        elif "amiga" in c_lower:
            return ".mod"
        return ".vgm"

    def refresh_local_only_tree(self):
        self.library_tree.clear()
        catalog = self.track_service.get_library_hierarchy()
        
        if not catalog:
            welcome = QTreeWidgetItem(self.library_tree)
            welcome.setText(0, "LOCAL LIBRARY IS EMPTY")
            welcome.setFont(0, QFont("Courier New", 11, QFont.Bold))
            welcome.setForeground(0, QColor("#6a7080"))
            
            hint = QTreeWidgetItem(welcome)
            hint.setText(0, "Use ONLINE SCRAPER or click SCAN FOLDER.")
            hint.setFont(0, QFont("Courier New", 10))
            return
            
        # Sort console name folders alphabetically by name
        for console, games in sorted(catalog.items(), key=lambda x: x[0].lower()):
            console_item = QTreeWidgetItem(self.library_tree)
            console_item.setText(0, console.upper())
            console_item.setFont(0, QFont("Courier New", 12, QFont.Bold))
            console_item.setForeground(0, QColor("#00d4ff")) # Cyan
            console_item.setData(0, Qt.UserRole, "console_local")
            
            for game, tracks in games.items():
                game_item = QTreeWidgetItem(console_item)
                game_item.setText(0, f"★ {game}")
                game_item.setFont(0, QFont("Courier New", 11, QFont.Bold))
                game_item.setForeground(0, QColor("#39ff14")) # Lime local
                game_item.setData(0, Qt.UserRole, "game_local")
                
                for t in tracks:
                    track_item = QTreeWidgetItem(game_item)
                    ext = ""
                    if t.get('member_name'):
                        ext = os.path.splitext(t['member_name'])[1].lower()
                    elif t.get('file_path'):
                        ext = os.path.splitext(t['file_path'])[1].lower()
                    elif t.get('format'):
                        ext = f".{t['format'].lower()}"
                    track_item.setText(0, f"[LOCAL] {t['title']}{ext}")
                    track_item.setFont(0, QFont("Courier New", 11))
                    track_item.setForeground(0, QColor("#00ff41")) # Retro green
                    track_item.setData(0, Qt.UserRole, "track")
                    track_item.setData(1, Qt.UserRole, t['id'])
                    
        self.library_tree.expandAll()

    def on_library_current_item_changed(self, current, previous):
        """Dynamically transforms the 'SCAN FOLDER' button to 'PLAY FOLDER CONTENT' when a folder is selected."""
        if current:
            node_type = current.data(0, Qt.UserRole)
            if node_type in ("game", "game_local", "console", "console_local"):
                self.btn_scan_folder.setText("PLAY FOLDER CONTENT")
                self.btn_scan_folder.setStyleSheet("color: #ff00ff; border-color: #ff00ff; font-weight: bold;") # Cyberpunk magenta theme!
                return
                
        self.btn_scan_folder.setText("SCAN FOLDER")
        self.btn_scan_folder.setStyleSheet("color: #ffd700; border-color: #ffd700; font-weight: bold;") # Gold theme

    def on_library_item_clicked(self, item, column):
        node_type = item.data(0, Qt.UserRole)
        
        if node_type == "track":
            track_id = item.data(1, Qt.UserRole)
            if track_id is not None:
                track = self.track_service.get_track_by_id(track_id)
                if track:
                    self.update_track_metadata_display(track)
            self.on_library_item_double_clicked(item, column)
                    
        elif node_type in ("game", "game_local"):
            game_name = item.data(2, Qt.UserRole) or item.text(0) or ""
            if game_name.startswith("★ "):
                game_name = game_name[2:]
            
            parent = item.parent()
            console_name = (parent.data(2, Qt.UserRole) or parent.text(0) or "Unknown") if parent else "Unknown"
            if console_name.startswith("★ "):
                console_name = console_name[2:]
            
            fake_track = {
                'title': game_name,
                'artist': 'Various',
                'console': console_name,
                'game': game_name
            }
            self.update_track_metadata_display(fake_track)
            item.setExpanded(not item.isExpanded())
            
        elif node_type == "online_track":
            track_title = item.data(2, Qt.UserRole) or ""
            game_name = item.parent().data(2, Qt.UserRole) if item.parent() else ""
            console_name = item.parent().parent().data(2, Qt.UserRole) if (item.parent() and item.parent().parent()) else ""
            
            fake_track = {
                'title': track_title,
                'artist': 'Various',
                'console': console_name,
                'game': game_name
            }
            self.update_track_metadata_display(fake_track)
            self.on_library_item_double_clicked(item, column)
            
        elif node_type in ("console", "console_local"):
            item.setExpanded(not item.isExpanded())

    def on_library_item_double_clicked(self, item, column):
        node_type = item.data(0, Qt.UserRole)
        self.debug_service.log_interaction("Library item double-clicked", f"Type: {node_type}, Text: '{item.text(0)}'")
        self.disable_randomizer_if_active()
        
        if node_type == "track":
            track_id = item.data(1, Qt.UserRole)
            if track_id is not None:
                parent_game = item.parent()
                track_ids = []
                if parent_game:
                    for i in range(parent_game.childCount()):
                        child = parent_game.child(i)
                        tid = child.data(1, Qt.UserRole)
                        if child.data(0, Qt.UserRole) == "track" and tid is not None:
                            track_ids.append(tid)
                
                if not track_ids:
                    track_ids = [track_id]
                    
                self.queue_manager.load_playlist(track_ids)
                self.queue_manager.start_playback(track_id)
                
        elif node_type == "online_track":
            pack_url = item.data(1, Qt.UserRole)
            track_title = item.data(2, Qt.UserRole)
            source = item.data(3, Qt.UserRole)
            game_name = item.parent().data(2, Qt.UserRole)
            console_name = item.parent().parent().data(2, Qt.UserRole)
            
            self.lbl_dl_status.setText(f"STREAMING: {track_title.upper()[:25]}...")
            self.lbl_dl_status.setStyleSheet("color: #00d4ff; border: none;")
            self.dl_progress.setValue(0)
            self.dl_progress.setVisible(True)
            
            self._active_downloading_item = item.parent()
            self._active_playing_title = track_title
            
            # Retrieve direct ZIP download URL from role 4 (falls back to pack_url for ModArchive)
            download_url = item.parent().data(4, Qt.UserRole) or pack_url
            if "zophar.net" in download_url:
                download_url = self.scraper.get_resolved_zophar_download_url(download_url)
                
            self.download_service.download_pack(
                url=download_url,
                pack_name=game_name,
                extract=False,
                on_progress=self.on_download_progress,
                on_status=self.on_download_status,
                on_zip_ready=lambda path, job_id, c=console_name, g=game_name, u=download_url: self.on_online_track_downloaded(path, c, g, u),
                on_error=self.on_download_error
            )

    def on_online_track_downloaded(self, zip_path, console, game, source_url):
        self.dl_progress.setVisible(False)
        self.lbl_dl_status.setText("DOWNLOAD COMPLETED")
        self.lbl_dl_status.setStyleSheet("color: #00ff41; border: none;")
        
        # Index downloaded ZIP
        indexed_ids = self.track_service.index_zip_pack(
            zip_path=zip_path,
            console_name=console,
            game_name=game,
            source_url=source_url
        )
        
        parent_item = getattr(self, "_active_downloading_item", None)
        target_title = getattr(self, "_active_playing_title", "")
        
        if parent_item:
            parent_item.setText(0, f"★ {game}")
            parent_item.setForeground(0, QColor("#39ff14")) # Bright Lime
            
            # Fetch the updated local tracks from the database
            local_tracks = self.track_service.get_tracks_by_console_and_game(console, game)
            
            play_track_id = None
            track_ids = []
            
            # Update children in-place to avoid breaking the full scraped tracklist!
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                node_type = child.data(0, Qt.UserRole)
                scraped_title = child.data(2, Qt.UserRole)
                
                # If it's online, convert it to local
                if node_type == "online_track" and scraped_title:
                    matched_local = self._find_matching_local_track(scraped_title, local_tracks)
                    if matched_local:
                        child.setText(0, f"[LOCAL] {scraped_title}")
                        child.setForeground(0, QColor("#00ff41")) # Retro Green
                        child.setData(0, Qt.UserRole, "track")
                        child.setData(1, Qt.UserRole, matched_local['id'])
                        
                # Gather all local track IDs for the playlist queue!
                if child.data(0, Qt.UserRole) == "track":
                    tid = child.data(1, Qt.UserRole)
                    if tid is not None:
                        track_ids.append(tid)
                        # If this child matches the double-clicked target title, set it as the play target
                        if scraped_title == target_title:
                            play_track_id = tid
                            
            parent_item.setExpanded(True)
            
            # Fallback for playing the target track if not matched directly in the loop
            if play_track_id is None and target_title:
                matched_local = self._find_matching_local_track(target_title, local_tracks)
                if matched_local:
                    play_track_id = matched_local['id']
            
            # Fallback to the first available track if still None
            if play_track_id is None and track_ids:
                play_track_id = track_ids[0]
                
            # If no track_ids are matched, fall back to the newly indexed database IDs
            if not track_ids and indexed_ids:
                track_ids = indexed_ids
                play_track_id = indexed_ids[0]
                
            if track_ids:
                self.queue_manager.load_playlist(track_ids)
                self.queue_manager.start_playback(play_track_id)
        else:
            self.refresh_library_tree()
            if indexed_ids:
                self.queue_manager.load_playlist(indexed_ids)
                self.queue_manager.start_playback(indexed_ids[0])

    def show_library_context_menu(self, pos):
        item = self.library_tree.itemAt(pos)
        if not item:
            return
            
        node_type = item.data(0, Qt.UserRole)
        file_path = None
        
        if node_type == "track":
            track_id = item.data(1, Qt.UserRole)
            if track_id is not None:
                track = self.track_service.get_track_by_id(track_id)
                if track and track.get('file_path'):
                    file_path = track['file_path']
        elif node_type in ("game", "game_local"):
            # Try to find a local child track to locate the game folder/zip file path
            for i in range(item.childCount()):
                child = item.child(i)
                if child.data(0, Qt.UserRole) == "track":
                    track_id = child.data(1, Qt.UserRole)
                    if track_id is not None:
                        track = self.track_service.get_track_by_id(track_id)
                        if track and track.get('file_path'):
                            file_path = track['file_path']
                            break
                            
        if file_path and os.path.exists(file_path):
            menu = QMenu(self)
            menu.setStyleSheet("""
                QMenu {
                    background-color: #121620;
                    color: #ffffff;
                    border: 2px solid #00d4ff;
                    font-family: 'Press Start 2P';
                    font-size: 7px;
                }
                QMenu::item {
                    padding: 6px 20px;
                }
                QMenu::item:selected {
                    background-color: #00d4ff;
                    color: #121620;
                }
            """)
            
            open_action = QAction("📂 Show in Explorer", self)
            open_action.triggered.connect(lambda: self.open_track_folder(file_path))
            menu.addAction(open_action)
            
            menu.exec(self.library_tree.mapToGlobal(pos))

    def open_track_folder(self, file_path):
        import subprocess
        try:
            norm_path = os.path.normpath(file_path)
            subprocess.run(['explorer', '/select,', norm_path])
        except Exception as e:
            self.status_bar.showMessage(f"Failed to open explorer: {e}", 4000)

    # --- Online Scraper & Search Operations ---
    def trigger_online_search(self):
        query = self.txt_search.text().strip()
        self.debug_service.log_interaction("Online search triggered", f"Query: '{query}'")
        if not query:
            return
        
        self.btn_search.setEnabled(False)
        self.txt_search.setEnabled(False)
        self.search_results.clear()
        self.status_bar.showMessage(f"Scraping online chiptunes for '{query}'...")
        
        self.search_thread = ScraperThread(self.scraper.search_online, query)
        self.search_thread.task_finished.connect(self.on_search_finished)
        self.search_thread.error.connect(self.on_search_error)
        self.search_thread.start()

    def on_search_finished(self, results):
        self.btn_search.setEnabled(True)
        self.txt_search.setEnabled(True)
        
        if not results:
            self.status_bar.showMessage("Search finished: 0 matching packs found.", 5000)
            self.search_results.addItem("No retro albums found online matching query.")
            return
            
        self.status_bar.showMessage(f"Search finished: Found {len(results)} matches.", 5000)
        
        for r in results:
            item = QListWidgetItem()
            # Mark clearly if from VGMRips, ModArchive, etc.
            source = r.get("source", "Web")
            artist = r.get("artist", "Unknown")
            title = r.get("title", "Unknown pack")
            
            item.setText(f"[{source.upper()}] {title} — ({artist})")
            item.setData(Qt.UserRole, r)
            self.search_results.addItem(item)

    def on_search_error(self, err_msg):
        self.btn_search.setEnabled(True)
        self.txt_search.setEnabled(True)
        self.status_bar.showMessage(f"Scraper thread failed: {err_msg[:50]}", 6000)
        QMessageBox.warning(self, "SCRAPE ERROR", f"Failed to fetch tracks online:\n{err_msg}")

    def on_search_result_clicked(self, item):
        res = item.data(Qt.UserRole)
        if not res:
            self.btn_download_pack.setEnabled(False)
            return
            
        self.btn_download_pack.setEnabled(True)
        # Update metadata display preview
        fake_track = {
            'title': res.get('title'),
            'artist': res.get('artist', 'Various'),
            'console': res.get('source', 'Online Scrape'),
            'game': res.get('title')
        }
        self.update_track_metadata_display(fake_track)

    def on_search_result_double_clicked(self, item):
        self.download_selected_online_pack()

    def download_selected_online_pack(self):
        selected = self.search_results.currentItem()
        if not selected:
            return
        res = selected.data(Qt.UserRole)
        if not res:
            return
            
        url = res.get("url")
        if url and "zophar.net" in url:
            url = self.scraper.get_resolved_zophar_download_url(url)
            
        pack_title = res.get("title")
        source = res.get("source", "VGMRips")
        
        # Deduce systems based on source or titles
        console = "Various"
        if "SEGA" in pack_title.upper() or "GENESIS" in pack_title.upper():
            console = "GENESIS"
        elif "SNES" in pack_title.upper() or "SUPER NINTENDO" in pack_title.upper():
            console = "SNES"
        elif "NES" in pack_title.upper() or "NINTENDO" in pack_title.upper():
            console = "NES"
        elif "MODARCHIVE" in source.upper():
            console = "MODARCHIVE"
            
        self.btn_download_pack.setEnabled(False)
        self.lbl_dl_status.setText(f"DOWNLOADING: {pack_title.upper()[:25]}...")
        self.lbl_dl_status.setStyleSheet("color: #00d4ff; border: none;") # Cyan active
        self.dl_progress.setValue(0)
        self.dl_progress.setVisible(True)
        
        # Trigger background download using our QThread DownloadService (no full extract for ZIP streaming!)
        self.download_service.download_pack(
            url=url,
            pack_name=pack_title,
            extract=False, # We use ZIP streaming! Save the ZIP intact.
            on_progress=self.on_download_progress,
            on_status=self.on_download_status,
            on_zip_ready=lambda path, job_id, c=console, g=pack_title, u=url: self.on_download_zip_ready(path, c, g, u),
            on_error=self.on_download_error
        )

    # --- Background Download Signals ---
    def on_download_progress(self, job_id, percent):
        self.dl_progress.setValue(percent)

    def on_download_status(self, job_id, text):
        self.status_bar.showMessage(f"Download {job_id} Status: {text}", 2000)

    def on_download_zip_ready(self, zip_path, console, game, source_url):
        self.dl_progress.setVisible(False)
        self.lbl_dl_status.setText("DOWNLOAD COMPLETED")
        self.lbl_dl_status.setStyleSheet("color: #00ff41; border: none;") # Green finished
        
        # 1. Index downloaded ZIP archive in database
        indexed_ids = self.track_service.index_zip_pack(
            zip_path=zip_path,
            console_name=console,
            game_name=game,
            source_url=source_url
        )
        
        # 2. Refresh local hierarchy
        self.refresh_library_tree()
        
        # 3. Immediately trigger playback of first track in indexed list
        if indexed_ids:
            self.queue_manager.load_playlist(indexed_ids)
            self.queue_manager.start_playback(indexed_ids[0])
            self.btn_download_pack.setEnabled(True)
        else:
            QMessageBox.information(self, "ZIP INDEXING", "Download finished, but no playable chiptune tracks (.vgm/.vgz) were found inside the ZIP.")
            self.btn_download_pack.setEnabled(True)

    def on_download_error(self, err_msg, job_id):
        self.dl_progress.setVisible(False)
        self.lbl_dl_status.setText("DOWNLOAD FAILED")
        self.lbl_dl_status.setStyleSheet("color: #e94560; border: none;") # Red failed
        self.btn_download_pack.setEnabled(True)
        QMessageBox.warning(self, "DOWNLOAD ERROR", f"Background download failed:\n{err_msg}")

    # --- Artwork & Metadata Dynamic Loaders ---
    def update_track_metadata_display(self, track):
        self._current_track = track
        title = track.get('title', 'Unknown Track')
        artist = track.get('artist', 'Various')
        console = track.get('console', 'Unknown Console')
        game = track.get('game', 'Unknown Game')
        
        self.lbl_now_playing_title.setText(title.upper())
        self.lbl_now_playing_desc.setText(f"System: {console.upper()} | Game: {game}\nComposer: {artist}")
        
        # Clear old image threads
        for t in self._image_threads:
            t.terminate()
        self._image_threads.clear()
        
        # Load placeholders first
        self.lbl_boxart.setText("[ LOADING... ]")
        self.lbl_screenshot.setText("[ LOADING... ]")
        
        # Ask WebScraperService for Libretro links
        art_links = self.scraper.get_artwork(console, game)
        
        # Load Boxart
        box_thread = ImageLoaderThread("boxart", art_links["boxart"])
        box_thread.loaded.connect(self.on_image_loaded)
        self._image_threads.append(box_thread)
        box_thread.start()
        
        # Load Screenshot
        snap_thread = ImageLoaderThread("screenshot", art_links["screenshot"])
        snap_thread.loaded.connect(self.on_image_loaded)
        self._image_threads.append(snap_thread)
        snap_thread.start()

    def on_image_loaded(self, img_type, pixmap):
        label = self.lbl_boxart if img_type == "boxart" else self.lbl_screenshot
        default_txt = "[ NO BOX ART ]" if img_type == "boxart" else "[ NO SCREENSHOT ]"
        
        if not pixmap or pixmap.isNull():
            label.setPixmap(QPixmap())
            label.setText(default_txt)
        else:
            # Scale beautifully to fit standard frame
            scaled = pixmap.scaled(label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            label.setPixmap(scaled)

    # --- Bottom Playback Controls Actions ---
    def get_all_tracks_under_item(self, item):
        """Recursively collects all child items representing playable tracks."""
        tracks = []
        node_type = item.data(0, Qt.UserRole)
        if node_type in ("track", "online_track"):
            tracks.append(item)
        else:
            for i in range(item.childCount()):
                child = item.child(i)
                tracks.extend(self.get_all_tracks_under_item(child))
        return tracks

    def toggle_play_pause(self):
        self.debug_service.log_interaction("Play/Pause button clicked")
        selected = self.library_tree.currentItem()
        
        # If an item is selected in the library tree, prioritize playing/pausing it or loading it!
        if selected:
            node_type = selected.data(0, Qt.UserRole)
            
            # If it's a folder or game node
            if node_type in ("game", "game_local", "console", "console_local"):
                self.disable_randomizer_if_active()
                tracks = self.get_all_tracks_under_item(selected)
                if tracks:
                    first_track = tracks[0]
                    first_type = first_track.data(0, Qt.UserRole)
                    
                    if first_type == "track":
                        track_ids = []
                        for child in tracks:
                            tid = child.data(1, Qt.UserRole)
                            if child.data(0, Qt.UserRole) == "track" and tid is not None:
                                track_ids.append(tid)
                        
                        if track_ids:
                            self.queue_manager.load_playlist(track_ids)
                            self.queue_manager.start_playback(track_ids[0])
                            self.status_bar.showMessage(f"PLAYING PLAYLIST FROM FOLDER: {selected.text(0).upper()}", 4000)
                    elif first_type == "online_track":
                        # Trigger streaming download for the first online track under this node
                        self.on_library_item_double_clicked(first_track, 0)
                else:
                    self.status_bar.showMessage("Folder is empty or loading children...", 3000)
                return
                
            # If it's a single track
            elif node_type == "track":
                track_id = selected.data(1, Qt.UserRole)
                if track_id is not None:
                    # If this selected track is already the active/loaded track, toggle play/pause!
                    active_id = self.queue_manager.get_current_track_id()
                    if active_id == track_id:
                        state = self.audio_engine.state
                        if state == PlaybackState.PLAYING:
                            self.audio_engine.pause()
                        else:
                            self.audio_engine.play()
                    else:
                        # Otherwise play the track and its siblings!
                        self.disable_randomizer_if_active()
                        parent_game = selected.parent()
                        track_ids = []
                        if parent_game:
                            for i in range(parent_game.childCount()):
                                child = parent_game.child(i)
                                tid = child.data(1, Qt.UserRole)
                                if child.data(0, Qt.UserRole) == "track" and tid is not None:
                                    track_ids.append(tid)
                        if not track_ids:
                            track_ids = [track_id]
                        self.queue_manager.load_playlist(track_ids)
                        self.queue_manager.start_playback(track_id)
                return
                
            elif node_type == "online_track":
                # Trigger streaming/download for online track
                self.on_library_item_double_clicked(selected, 0)
                return

        # Fallback: standard play/pause on the audio engine (no selected item or unplayable type)
        state = self.audio_engine.state
        if state == PlaybackState.PLAYING:
            self.audio_engine.pause()
        elif state == PlaybackState.PAUSED:
            self.audio_engine.play()
        else:
            self.status_bar.showMessage("No track selected or active queue.", 3000)

    def stop_playback(self):
        self.debug_service.log_interaction("Stop button clicked")
        self.audio_engine.stop()

    def play_next_track(self):
        self.debug_service.log_interaction("Next track button clicked")
        self.queue_manager.advance_to_next_track()

    def play_previous_track(self):
        self.debug_service.log_interaction("Previous track button clicked")
        self.queue_manager.previous_track()

    def toggle_shuffle(self):
        self.debug_service.log_interaction("Shuffle button clicked")
        self.queue_manager.toggle_shuffle()
        if self.queue_manager.is_shuffling:
            self.btn_shuffle.setText("SHUFFLE: ON")
            self.btn_shuffle.setStyleSheet("color: #39ff14; border-color: #39ff14;") # Lime active
        else:
            self.btn_shuffle.setText("SHUFFLE: OFF")
            self.btn_shuffle.setStyleSheet("color: #ffd700; border-color: #ffd700;") # Gold

    def toggle_repeat(self):
        self.debug_service.log_interaction("Repeat button clicked")
        self.is_repeat_one = not self.is_repeat_one
        if self.is_repeat_one:
            self.btn_repeat.setText("REPEAT: ONE")
            self.btn_repeat.setStyleSheet("color: #39ff14; border-color: #39ff14;") # Lime active
        else:
            self.btn_repeat.setText("REPEAT: OFF")
            self.btn_repeat.setStyleSheet("color: #ff6b6b; border-color: #ff6b6b;") # Red-pink

    def disable_randomizer_if_active(self):
        """Disables the randomizer function and stops any active randomizer threads/playback."""
        if self.is_randomizer_active:
            self.is_randomizer_active = False
            self.btn_randomizer.setText("👾 RADAR: OFF")
            self.btn_randomizer.setStyleSheet("color: #ff00ff; border-color: #ff00ff;") # Magenta inactive
            self.audio_engine.stop()
            if self.randomizer_thread and self.randomizer_thread.isRunning():
                self.randomizer_thread.terminate()
                self.randomizer_thread.wait()
            self.status_bar.showMessage("Randomizer deactivated by manual play. Playback stopped.", 4000)

    def toggle_randomizer(self):
        self.is_randomizer_active = not self.is_randomizer_active
        if self.is_randomizer_active:
            self.btn_randomizer.setText("👾 RADAR: ON")
            self.btn_randomizer.setStyleSheet("color: #39ff14; border-color: #39ff14;") # Lime active
            self.status_bar.showMessage("👾 Randomizer mode active! Spinning the retro radar...", 4000)
            self.play_next_random_track()
        else:
            self.btn_randomizer.setText("👾 RADAR: OFF")
            self.btn_randomizer.setStyleSheet("color: #ff00ff; border-color: #ff00ff;") # Magenta inactive
            self.audio_engine.stop()  # Stop playback completely when turning randomizer off
            if self.randomizer_thread and self.randomizer_thread.isRunning():
                self.randomizer_thread.terminate()
                self.randomizer_thread.wait()
            self.status_bar.showMessage("Randomizer mode deactivated. Playback stopped.", 4000)

    def play_next_random_track(self):
        # Stop any running randomizer threads to avoid collisions
        if self.randomizer_thread and self.randomizer_thread.isRunning():
            self.randomizer_thread.terminate()
            self.randomizer_thread.wait()
            
        self.status_bar.showMessage("📡 Radar scanning retro galaxy...", 5000)
        self.randomizer_thread = RandomizerThread(self.scraper, self.track_service)
        self.randomizer_thread.task_finished.connect(self.on_random_track_selected)
        self.randomizer_thread.error.connect(self.on_randomizer_error)
        self.randomizer_thread.start()

    def on_random_track_selected(self, track_info):
        if not self.is_randomizer_active:
            return
            
        t_type = track_info["type"]
        title = track_info["title"]
        console = track_info["console"]
        game = track_info["game"]
        
        self.status_bar.showMessage(f"🎯 Target Locked: {title} ({console} / {game})", 6000)
        
        if t_type == "local":
            track_id = track_info["track_id"]
            track_data = self.track_service.get_track_by_id(track_id)
            if track_data:
                self.update_track_metadata_display(track_data)
            self.queue_manager.load_playlist([track_id])
            self.queue_manager.start_playback(track_id)
        else:
            pack_url = track_info["pack_url"]
            download_url = track_info["download_url"]
            source = track_info["source"]
            
            if download_url and "zophar.net" in download_url:
                download_url = self.scraper.get_resolved_zophar_download_url(download_url)
                
            self.lbl_dl_status.setText(f"DOWNLOADING {game.upper()}...")
            self.lbl_dl_status.setStyleSheet("color: #ffd700; border: none;")
            self.dl_progress.setValue(0)
            self.dl_progress.setVisible(True)
            
            self._active_downloading_item = None
            self._active_playing_title = title
            
            self.download_service.download_pack(
                url=download_url,
                pack_name=game,
                extract=False,
                on_progress=self.on_download_progress,
                on_status=self.on_download_status,
                on_zip_ready=lambda path, job_id, c=console, g=game, u=download_url: self.on_random_online_downloaded(path, c, g, u, title),
                on_error=self.on_download_error
            )

    def on_random_online_downloaded(self, zip_path, console, game, download_url, target_title):
        self.dl_progress.setVisible(False)
        self.lbl_dl_status.setText("DOWNLOAD COMPLETED")
        self.lbl_dl_status.setStyleSheet("color: #00ff41; border: none;")
        
        indexed_ids = self.track_service.index_zip_pack(
            zip_path=zip_path,
            console_name=console,
            game_name=game,
            source_url=download_url
        )
        
        if not self.is_randomizer_active:
            return
            
        local_tracks = self.track_service.get_tracks_by_console_and_game(console, game)
        play_track_id = None
        
        if local_tracks:
            matched = self._find_matching_local_track(target_title, local_tracks)
            if matched:
                play_track_id = matched["id"]
            else:
                play_track_id = local_tracks[0]["id"]
                
        if play_track_id is None and indexed_ids:
            play_track_id = indexed_ids[0]
            
        if play_track_id is not None:
            track_data = self.track_service.get_track_by_id(play_track_id)
            if track_data:
                self.update_track_metadata_display(track_data)
            self.queue_manager.load_playlist([play_track_id])
            self.queue_manager.start_playback(play_track_id)
        else:
            self.play_next_random_track()

    def on_randomizer_error(self, err_msg):
        self.status_bar.showMessage(f"Radar Search Failed: {err_msg[:40]}", 4000)
        if self.is_randomizer_active:
            self.play_next_random_track()


    def on_volume_changed(self, value):
        if hasattr(self, "_initialized") and self._initialized:
            self.debug_service.log_interaction("Volume changed", f"Value: {value}%")
        self.audio_engine.set_volume(value)
        self.config_service.set("volume", value)

    # --- Keyboard Shortcut Action Handlers ---
    def volume_up_step(self):
        new_val = min(100, self.volume_slider.value() + 5)
        self.volume_slider.setValue(new_val)
        self.status_bar.showMessage(f"Volume: {new_val}%", 1500)
        
    def volume_down_step(self):
        new_val = max(0, self.volume_slider.value() - 5)
        self.volume_slider.setValue(new_val)
        self.status_bar.showMessage(f"Volume: {new_val}%", 1500)

    def seek_forward_step(self):
        cur = self.seek_slider.value()
        max_limit = self.seek_slider.maximum()
        new_val = min(max_limit, cur + 5)
        self.seek_slider.setValue(new_val)
        self.audio_engine.set_time(new_val)
        m, s = divmod(new_val, 60)
        self.status_bar.showMessage(f"Seek: {m:02d}:{s:02d}", 1500)

    def seek_backward_step(self):
        cur = self.seek_slider.value()
        new_val = max(0, cur - 5)
        self.seek_slider.setValue(new_val)
        self.audio_engine.set_time(new_val)
        m, s = divmod(new_val, 60)
        self.status_bar.showMessage(f"Seek: {m:02d}:{s:02d}", 1500)

    def focus_local_filter(self):
        self.nav_tabs.setCurrentIndex(0) # Switch to Local Library tab
        self.txt_lib_filter.setFocus()
        self.txt_lib_filter.selectAll()
        self.status_bar.showMessage("Search: Filter focused", 1500)

    def focus_online_search(self):
        self.nav_tabs.setCurrentIndex(1) # Switch to Online Search tab
        self.txt_search.setFocus()
        self.txt_search.selectAll()
        self.status_bar.showMessage("Search: Online query focused", 1500)

    def clear_search_and_focus(self):
        if self.txt_lib_filter.hasFocus():
            self.txt_lib_filter.clear()
            self.library_tree.setFocus()
            self.status_bar.showMessage("Filter cleared", 1500)
        elif self.txt_search.hasFocus():
            self.txt_search.clear()
            self.search_results.setFocus()
            self.status_bar.showMessage("Search cleared", 1500)
        else:
            self.txt_lib_filter.clear()
            self.txt_search.clear()
            self.library_tree.setFocus()

    # --- Seek Slider Protection ---
    def on_seek_slider_pressed(self):
        self._is_dragging_slider = True

    def on_seek_slider_released(self):
        self._is_dragging_slider = False
        val_sec = self.seek_slider.value()
        self.audio_engine.set_time(val_sec)

    # --- Audio Engine Signal Listeners ---
    def on_playback_state_changed(self, state):
        self.status_bar.showMessage(f"Audio Engine State: {state}")
        if state == PlaybackState.PLAYING:
            self.btn_play.setText("⏸")
            # Update now playing display if we played from hotkeys/next
            current_id = self.queue_manager.get_current_track_id()
            if current_id:
                track = self.track_service.get_track_by_id(current_id)
                if track and self._current_track != track:
                    self.update_track_metadata_display(track)
        else:
            self.btn_play.setText("▶")

    def on_playback_position_changed(self, seconds):
        if not self._is_dragging_slider:
            self.seek_slider.setValue(int(seconds))
            
        m, s = divmod(int(seconds), 60)
        self.lbl_time_current.setText(f"{m:02d}:{s:02d}")

    def on_playback_duration_changed(self, seconds):
        self.seek_slider.setRange(0, int(seconds))
        m, s = divmod(int(seconds), 60)
        self.lbl_time_total.setText(f"{m:02d}:{s:02d}")

    def on_playback_error(self, err_msg):
        self.debug_service.log_error(f"Playback error: {err_msg}")
        self.status_bar.showMessage(f"Playback Error: {err_msg}", 5000)
        
        # Guard against nested event queue triggers generating infinite dialog loops
        if getattr(self, "_error_dialog_active", False):
            return
            
        self._error_dialog_active = True
        try:
            # Pop up a highly visible custom-styled QMessageBox error dialog
            from PySide6.QtWidgets import QMessageBox
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("PLAYBACK ERROR")
            msg.setText("Unable to play selected track.")
            msg.setInformativeText(f"{err_msg}\n\nPlease check if this audio format is supported by VLC or if the file is corrupted.")
            
            # Consistent Neon Retro Styling
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #1a1a2e;
                    border: 2px solid #ff007f;
                    border-radius: 10px;
                }
                QLabel {
                    color: #ffffff;
                    font-family: 'Press Start 2P';
                    font-size: 8px;
                }
                QPushButton {
                    background-color: #ff007f;
                    color: #ffffff;
                    font-family: 'Press Start 2P';
                    font-size: 7px;
                    font-weight: bold;
                    border: none;
                    border-radius: 5px;
                    padding: 8px 16px;
                    min-width: 70px;
                }
                QPushButton:hover {
                    background-color: #ff00a0;
                }
            """)
            msg.exec()
        finally:
            self._error_dialog_active = False

    def on_playback_warning(self, warn_msg):
        """Displays non-blocking vibrant warnings on status bar when using audio synth fallbacks."""
        self.debug_service.log_warning(f"Playback warning: {warn_msg}")
        # Use bright neon orange/amber styling for non-blocking status notifications
        self.status_bar.setStyleSheet("QStatusBar { background: #2a1b0a; color: #ff9f00; font-family: 'Press Start 2P'; font-size: 6px; border-top: 1px solid #ff9f00; }")
        self.status_bar.showMessage(f"⚠️ {warn_msg}", 10000)
        
        # Reset back to default style after 10 seconds
        QTimer.singleShot(10000, lambda: self.status_bar.setStyleSheet(
            "QStatusBar { background: rgba(13, 13, 26, 255); color: #6a7080; font-family: 'Press Start 2P'; font-size: 6px; }"
        ))
        
    def on_track_finished(self):
        if self.is_randomizer_active:
            self.play_next_random_track()
        elif self.is_repeat_one and self._current_track:
            # Replay same track
            current_id = self.queue_manager.get_current_track_id()
            if current_id:
                self.queue_manager._play_track_by_id(current_id)
        else:
            # Random state is off! Find next contiguous tree track
            played_contiguous = False
            current_id = self.queue_manager.get_current_track_id()
            current_title = self._current_track.get('title') if self._current_track else None
            
            current_item = self.find_tree_item_by_track_id_or_title(current_id, current_title)
            if current_item:
                next_item = self.get_next_contiguous_tree_track(current_item)
                if next_item:
                    self.library_tree.setCurrentItem(next_item)
                    self.on_library_item_double_clicked(next_item, 0)
                    played_contiguous = True
                    
            if not played_contiguous:
                self.queue_manager.advance_to_next_track()

    def find_tree_item_by_track_id_or_title(self, track_id, title=None):
        def search_node(item):
            node_type = item.data(0, Qt.UserRole)
            if node_type in ("track", "online_track"):
                if track_id is not None and item.data(1, Qt.UserRole) == track_id:
                    return item
                if title and item.data(2, Qt.UserRole) == title:
                    return item
            for i in range(item.childCount()):
                res = search_node(item.child(i))
                if res:
                    return res
            return None
            
        for i in range(self.library_tree.topLevelItemCount()):
            res = search_node(self.library_tree.topLevelItem(i))
            if res:
                return res
        return None

    def get_next_contiguous_tree_track(self, current_item):
        if not current_item:
            return None
            
        parent = current_item.parent()
        if not parent:
            return None
            
        # 1. Look for a next sibling under the same parent
        index = parent.indexOfChild(current_item)
        if index != -1 and index < parent.childCount() - 1:
            next_sibling = parent.child(index + 1)
            if next_sibling.data(0, Qt.UserRole) in ("track", "online_track"):
                return next_sibling
                
        # 2. Last track in folder finished! Go to next sibling of the game parent
        grandparent = parent.parent()
        if grandparent:
            parent_index = grandparent.indexOfChild(parent)
            if parent_index != -1 and parent_index < grandparent.childCount() - 1:
                next_game = grandparent.child(parent_index + 1)
                
                # Expand next game to trigger loading if lazy-loaded!
                next_game.setExpanded(True)
                
                # Check if it has child tracks already
                if next_game.childCount() > 0:
                    first_child = next_game.child(0)
                    if first_child.data(0, Qt.UserRole) in ("track", "online_track"):
                        return first_child
                    elif first_child.data(0, Qt.UserRole) == "dummy":
                        self._play_first_track_of_expanded_item = next_game
                        self.status_bar.showMessage(f"Lazy loading next contiguous game: {next_game.text(0)}...", 4000)
                        return None
                        
            # 3. No next game in this console! Try next console folder top level item
            else:
                top_index = self.library_tree.indexOfTopLevelItem(grandparent)
                if top_index != -1 and top_index < self.library_tree.topLevelItemCount() - 1:
                    next_console = self.library_tree.topLevelItem(top_index + 1)
                    next_console.setExpanded(True)
                    
                    if next_console.childCount() > 0:
                        first_game = next_console.child(0)
                        first_game.setExpanded(True)
                        
                        if first_game.childCount() > 0:
                            first_child = first_game.child(0)
                            if first_child.data(0, Qt.UserRole) in ("track", "online_track"):
                                return first_child
                            elif first_child.data(0, Qt.UserRole) == "dummy":
                                self._play_first_track_of_expanded_item = first_game
                                return None
                                
        return None

    def open_and_play_file(self):
        """Allows playing any local standalone chiptune or ZIP file directly."""
        self.disable_randomizer_if_active()
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "OPEN RETRO MUSIC FILE", 
            self.config_service.get("download_dir"),
            "Chiptunes (*.vgm *.vgz *.spc *.nsf *.nsfe *.gbs *.gsf *.minigsf *.2sf *.mini2sf *.usf *.miniusf *.gym *.sgc *.ssf *.minissf *.dsf *.minipsf *.hes *.ym *.vtx *.sid *.mod *.xm *.it *.s3m *.zip);;All Files (*)"
        )
        if not file_path:
            return
            
        file_path = os.path.abspath(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        
        # If it is a ZIP archive, let user pick which member to play or scan it
        if ext == ".zip":
            import zipfile
            try:
                with zipfile.ZipFile(file_path, 'r') as zf:
                    members = [m for m in zf.namelist() if os.path.splitext(m)[1].lower() in SUPPORTED_EXTS]
                if not members:
                    QMessageBox.warning(self, "EMPTY ZIP", "No playable chiptunes found inside the ZIP.")
                    return
                
                # Show selection combobox dialog
                member, ok = QComboBoxDialog.get_selection(self, "SELECT ZIP TRACK", "Choose track from ZIP:", members)
                if ok and member:
                    # Parse title
                    title = os.path.splitext(os.path.basename(member))[0]
                    title = re.sub(r'^\d+[\s\-_]*', '', title).replace('_', ' ').strip()
                    
                    fake_track = {
                        'title': title,
                        'artist': 'Various',
                        'console': 'Local Archive',
                        'game': os.path.splitext(os.path.basename(file_path))[0],
                        'file_path': file_path,
                        'member_name': member
                    }
                    self.update_track_metadata_display(fake_track)
                    self.audio_engine.load_track(file_path, member_name=member)
                    self.audio_engine.play()
                    self.status_bar.showMessage(f"Streaming from ZIP: {title}")
            except Exception as e:
                QMessageBox.critical(self, "ZIP ERROR", f"Failed to read ZIP:\n{e}")
        else:
            # Standalone flat file
            # Validate extension
            if ext not in SUPPORTED_EXTS:
                from PySide6.QtWidgets import QMessageBox
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Warning)
                msg.setWindowTitle("UNSUPPORTED FORMAT")
                msg.setText("Unsupported file extension!")
                msg.setInformativeText(
                    f"The file extension '{ext}' is not supported by Chiptune Palace.\n\n"
                    "Supported formats include:\n"
                    f"{', '.join(sorted(SUPPORTED_EXTS))}"
                )
                msg.setStyleSheet("""
                    QMessageBox {
                        background-color: #1a1a2e;
                        border: 2px solid #ff0055;
                        border-radius: 10px;
                    }
                    QLabel {
                        color: #ffffff;
                        font-family: 'Press Start 2P';
                        font-size: 8px;
                    }
                    QPushButton {
                        background-color: #ff0055;
                        color: #ffffff;
                        font-family: 'Press Start 2P';
                        font-size: 7px;
                        font-weight: bold;
                        border: none;
                        border-radius: 5px;
                        padding: 8px 16px;
                        min-width: 70px;
                    }
                    QPushButton:hover {
                        background-color: #ff3377;
                    }
                """)
                msg.exec()
                return

            title = os.path.splitext(os.path.basename(file_path))[0]
            title = re.sub(r'^\d+[\s\-_]*', '', title).replace('_', ' ').strip()
            
            console = "Local System"
            game = "Standalone Audio"
            artist = "Unknown"
            
            # Attempt to deduce console/game from path/filename
            if "GENESIS" in file_path.upper() or "SEGA" in file_path.upper():
                console = "GENESIS"
            elif "SNES" in file_path.upper():
                console = "SNES"
            elif "NES" in file_path.upper():
                console = "NES"
                
            fake_track = {
                'title': title,
                'artist': artist,
                'console': console,
                'game': game,
                'file_path': file_path,
                'member_name': None
            }
            self.update_track_metadata_display(fake_track)
            self.audio_engine.load_track(file_path)
            self.audio_engine.play()
            self.status_bar.showMessage(f"Playing direct file: {title}")

    def scan_local_folder(self):
        """Recursively scans a folder to automatically index files and ZIPs into the local database,
        OR if a folder in the tree is selected, compiles a playlist and starts playback."""
        selected = self.library_tree.currentItem()
        if selected:
            node_type = selected.data(0, Qt.UserRole)
            if node_type in ("game", "game_local", "console", "console_local"):
                # Interpret as a call for playlist creation and instant playback
                tracks = self.get_all_tracks_under_item(selected)
                if not tracks:
                    self.status_bar.showMessage("No playable tracks found in folder.")
                    return
                    
                # Collect track IDs (local) or stream details (online)
                track_ids = []
                first_track = None
                for t_item in tracks:
                    t_type = t_item.data(0, Qt.UserRole)
                    if t_type == "track":
                        tid = t_item.data(1, Qt.UserRole)
                        if tid is not None:
                            track_ids.append(tid)
                            if first_track is None:
                                first_track = t_item
                                
                if track_ids:
                    # Instant playback of the folder's files in proper order
                    self.queue_manager.load_playlist(track_ids)
                    first_id = first_track.data(1, Qt.UserRole)
                    self.queue_manager.start_playback(first_id)
                    self.status_bar.showMessage(f"Playing folder content: {len(track_ids)} tracks loaded.")
                else:
                    # If they are online tracks, trigger single-click streaming for the first track
                    if tracks:
                        self.on_library_item_clicked(tracks[0], 0)
                return

        directory = QFileDialog.getExistingDirectory(self, "SELECT FOLDER TO SCAN FOR MUSIC", self.config_service.get("download_dir"))
        if not directory:
            return
            
        directory = os.path.abspath(directory)
        self.status_bar.showMessage(f"Scanning folder recursively: {directory}...")
        
        supported_exts = SUPPORTED_EXTS
        
        indexed_count = 0
        zip_count = 0
        standalone_count = 0
        
        # Set cursor to busy
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for root, dirs, files in os.walk(directory):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    full_path = os.path.join(root, f)
                    
                    if ext == ".zip":
                        # Deduce console and game from folder/zip structure
                        console = os.path.basename(os.path.dirname(full_path))
                        game = os.path.splitext(f)[0]
                        if console.upper() in {"DOWNLOADS", "CHIPTUNEPALACE"}:
                            console = "Local System"
                            
                        indexed_ids = self.track_service.index_zip_pack(
                            zip_path=full_path,
                            console_name=console,
                            game_name=game
                        )
                        if indexed_ids:
                            zip_count += 1
                            indexed_count += len(indexed_ids)
                    elif ext in supported_exts:
                        # STANDALONE FILE
                        # Deduce console and game from folders
                        game = os.path.basename(root)
                        console = os.path.basename(os.path.dirname(root))
                        if game.upper() in {"DOWNLOADS", "CHIPTUNEPALACE"}:
                            game = "Local Audio"
                        if console.upper() in {"DOWNLOADS", "CHIPTUNEPALACE"}:
                            console = "Local System"
                            
                        title = os.path.splitext(f)[0]
                        # Clean leading number tags
                        title = re.sub(r'^\d+[\s\-_]*', '', title).replace('_', ' ').strip()
                        
                        fingerprint = self.track_service.db_manager.get_fingerprint(full_path)
                        
                        self.track_service.add_track(
                            title=title,
                            artist="Unknown",
                            console=console,
                            game=game,
                            file_path=full_path,
                            fingerprint=fingerprint,
                            format=ext[1:].upper()
                        )
                        standalone_count += 1
                        indexed_count += 1
        finally:
            QApplication.restoreOverrideCursor()
            
        self.refresh_library_tree()
        self.status_bar.showMessage(f"Scan finished! Indexed {indexed_count} tracks ({zip_count} ZIPs, {standalone_count} files).", 8000)
        QMessageBox.information(
            self, 
            "SCAN COMPLETE", 
            f"Successfully scanned folder!\n\nIndexed ZIPs: {zip_count}\nIndexed standalone tracks: {standalone_count}\nTotal tracks now playable: {indexed_count}"
        )

    def highlight_search_text(self, text, query, highlight_color="#ff007f"):
        """Case-insensitively wraps matching substrings of query in text with colored spans."""
        if not query:
            return text
            
        safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        try:
            pattern = re.compile(re.escape(query), re.IGNORECASE)
            # Wrap all occurrences with inline CSS styling for high-contrast neon highlights
            return pattern.sub(f'<span style="color: {highlight_color}; font-weight: bold; text-shadow: 0 0 3px {highlight_color};">\\g<0></span>', safe_text)
        except Exception:
            return safe_text

    def update_item_display_text(self, item, query):
        """Dynamically applies high-contrast HTML highlighting to a QTreeWidgetItem's label."""
        node_type = item.data(0, Qt.UserRole)
        original_name = item.data(2, Qt.UserRole) or item.text(0) or ""
        
        # Strip temporary tags or prefixes in case of dirty fallback
        original_name = re.sub('<[^<]+?>', '', original_name)
        if original_name.startswith("★ "):
            original_name = original_name[2:]
            
        # Map item category to its matching neon design palette color
        if node_type == "console" or node_type == "console_local":
            base_color = "#00d4ff"  # Neon Cyan
            display_name = original_name.upper()
            prefix = ""
        elif node_type == "game" or node_type == "game_local":
            source = item.data(3, Qt.UserRole)
            if source == "Local" or node_type == "game_local":
                base_color = "#39ff14"  # Bright Lime local
            else:
                base_color = "#ffd700"  # Gold online
            display_name = original_name
            prefix = "★ "
        else:
            is_local = original_name.startswith("[LOCAL]") or original_name.startswith("[local]")
            is_online = original_name.startswith("[ONLINE]") or original_name.startswith("[online]")
            
            clean_name = original_name
            if is_local:
                clean_name = clean_name[7:].strip()
            elif is_online:
                clean_name = clean_name[8:].strip()
                
            if node_type == "track":
                base_color = "#00ff41" # Neon green
            elif node_type == "online_track":
                base_color = "#00ffff" # Neon cyan
            else:
                base_color = "#ffd700" # Neon gold
                
            display_name = clean_name
            prefix = "[LOCAL] " if is_local else ("[ONLINE] " if is_online else "")
            
        # Wrap matching letters with electric hot pink highlight color (#ff007f)
        # This contrasts spectacularly against cyan, green, and gold alike!
        highlighted = self.highlight_search_text(display_name, query, highlight_color="#ff007f")
        
        # Build standard inline span wrapper
        html_str = f"<span style='color: {base_color};'>{prefix}{highlighted}</span>"
        item.setText(0, html_str)

    def filter_library_tree(self, text):
        query = text.strip().lower()
        
        def matches(item):
            item_text = item.data(2, Qt.UserRole) or item.text(0) or ""
            item_text = re.sub('<[^<]+?>', '', item_text).lower()
            if item_text.startswith("★ "):
                item_text = item_text[2:]
            if item_text.startswith("[local] "):
                item_text = item_text[8:]
            if item_text.startswith("[online] "):
                item_text = item_text[9:]
            return query in item_text

        if not query:
            # Restore all consoles, games and tracks to standard visible state
            for i in range(self.library_tree.topLevelItemCount()):
                console_item = self.library_tree.topLevelItem(i)
                console_item.setHidden(False)
                
                # Restore plain console text
                c_name = console_item.data(2, Qt.UserRole) or console_item.text(0) or ""
                c_name = re.sub('<[^<]+?>', '', c_name)
                if c_name.startswith("★ "):
                    c_name = c_name[2:]
                console_item.setText(0, c_name.upper())
                console_item.setForeground(0, QColor("#00d4ff"))
                
                for j in range(console_item.childCount()):
                    game_item = console_item.child(j)
                    game_item.setHidden(False)
                    
                    # Restore plain game text
                    g_name = game_item.data(2, Qt.UserRole) or game_item.text(0) or ""
                    g_name = re.sub('<[^<]+?>', '', g_name)
                    if g_name.startswith("★ "):
                        g_name = g_name[2:]
                        
                    node_type = game_item.data(0, Qt.UserRole)
                    source = game_item.data(3, Qt.UserRole)
                    if source == "Local" or node_type == "game_local":
                        game_item.setText(0, f"★ {g_name}")
                        game_item.setForeground(0, QColor("#39ff14"))
                    else:
                        game_item.setText(0, g_name)
                        game_item.setForeground(0, QColor("#ffd700"))
                        
                    # Restore plain tracks text
                    for k in range(game_item.childCount()):
                        track_item = game_item.child(k)
                        track_item.setHidden(False)
                        t_name = track_item.data(2, Qt.UserRole) or track_item.text(0) or ""
                        t_name = re.sub('<[^<]+?>', '', t_name)
                        track_item.setText(0, t_name)
                        
                        t_node_type = track_item.data(0, Qt.UserRole)
                        if t_node_type == "track":
                            track_item.setForeground(0, QColor("#00ff41"))
                        elif t_node_type == "online_track":
                            track_item.setForeground(0, QColor("#00ffff"))
            return

        # Dynamically pre-populate matching consoles with games from the local database
        try:
            all_tracks = self.track_service.get_all_tracks()
            matching_tracks = []
            for t in all_tracks:
                t_game = t.get('game') or ""
                t_title = t.get('title') or ""
                if query in t_game.lower() or query in t_title.lower():
                    matching_tracks.append(t)
            
            # Map of console_name (lowercase) -> set of game names
            matching_db_map = {}
            for t in matching_tracks:
                c = t.get('console') or ""
                g = t.get('game') or ""
                if c and g:
                    c_key = c.lower()
                    if c_key not in matching_db_map:
                        matching_db_map[c_key] = set()
                    matching_db_map[c_key].add(g)
                    
            # Populate matching consoles
            for i in range(self.library_tree.topLevelItemCount()):
                console_item = self.library_tree.topLevelItem(i)
                c_name = console_item.data(2, Qt.UserRole) or console_item.text(0) or ""
                c_name = re.sub('<[^<]+?>', '', c_name)
                c_key = c_name.lower()
                if c_key.startswith("★ "):
                    c_key = c_key[2:]
                
                # Check if this tree console matches any console in our database map
                for db_console, db_games in matching_db_map.items():
                    if db_console in c_key or c_key in db_console:
                        # Build a set of existing game names in this console's tree node
                        existing_games = set()
                        for j in range(console_item.childCount()):
                            child = console_item.child(j)
                            gname = child.data(2, Qt.UserRole) or child.text(0) or ""
                            if gname:
                                gname = re.sub('<[^<]+?>', '', gname)
                                if gname.startswith("★ "):
                                    gname = gname[2:]
                                existing_games.add(gname.lower())
                                
                        # If this console has a dummy child, remove it
                        if console_item.childCount() == 1 and console_item.child(0).data(0, Qt.UserRole) == "dummy":
                            console_item.removeChild(console_item.child(0))
                            
                        # Add any matching local games that aren't already present in the tree
                        for gname in sorted(db_games):
                            if gname.lower() not in existing_games:
                                g_item = QTreeWidgetItem(console_item)
                                g_item.setText(0, f"★ {gname}")
                                g_item.setFont(0, QFont("Courier New", 11, QFont.Bold))
                                g_item.setForeground(0, QColor("#39ff14")) # Bright Lime local
                                g_item.setData(0, Qt.UserRole, "game_local")  # Correctly set to game_local!
                                g_item.setData(1, Qt.UserRole, "") # Empty online URL
                                g_item.setData(2, Qt.UserRole, gname)
                                g_item.setData(3, Qt.UserRole, "Local")
                                
                                # Add dummy child so tracks can load on expansion
                                dummy = QTreeWidgetItem(g_item)
                                dummy.setText(0, "Loading Tracks...")
                                dummy.setData(0, Qt.UserRole, "dummy")
                                
                                existing_games.add(gname.lower())
        except Exception as e:
            print(f"Error during search filter DB pre-population: {e}")

        # Update visibility and highlight matching consoles, games, and tracks
        for i in range(self.library_tree.topLevelItemCount()):
            console_item = self.library_tree.topLevelItem(i)
            console_matches = matches(console_item)
            
            any_game_matches = False
            for j in range(console_item.childCount()):
                game_item = console_item.child(j)
                game_matches = matches(game_item)
                
                any_track_matches = False
                for k in range(game_item.childCount()):
                    track_item = game_item.child(k)
                    track_matches = matches(track_item)
                    
                    if console_matches or game_matches or track_matches:
                        track_item.setHidden(False)
                        if track_matches:
                            self.update_item_display_text(track_item, query)
                            any_track_matches = True
                        else:
                            # Restore standard track text
                            t_name = track_item.data(2, Qt.UserRole) or track_item.text(0) or ""
                            t_name = re.sub('<[^<]+?>', '', t_name)
                            track_item.setText(0, t_name)
                    else:
                        track_item.setHidden(True)
                
                # Highlight and update game display text
                self.update_item_display_text(game_item, query)
                
                if console_matches or game_matches or any_track_matches:
                    game_item.setHidden(False)
                    any_game_matches = True
                    if any_track_matches:
                        game_item.setExpanded(True)
                else:
                    game_item.setHidden(True)
            
            # Highlight and update console display text
            self.update_item_display_text(console_item, query)
            
            if console_matches or any_game_matches:
                console_item.setHidden(False)
                if any_game_matches:
                    console_item.setExpanded(True)
            else:
                console_item.setHidden(True)

    # --- Cleanup ---
    def closeEvent(self, event):
        self.hotkey_service.cleanup()
        self.audio_engine.stop()
        event.accept()


# Standard Main method to support run_app.py
def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
