import sys
import os
import requests
import re
import traceback
import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QListWidget, QListWidgetItem, QLabel, QStatusBar, QTreeWidget, QTreeWidgetItem, QTreeView, QFrame,
    QLineEdit, QSlider, QSplitter, QProgressBar, QFileDialog, QDialog, QScrollArea,
    QFormLayout, QDialogButtonBox, QMessageBox, QTabWidget, QComboBox, QMenu, QTextEdit,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal, QUrl, QTimer, QSize, QRectF
from PySide6.QtGui import QFont, QPalette, QColor, QIcon, QPixmap, QAction, QTextDocument, QFontDatabase, QFontMetrics, QPainter

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
        style_to_set = None
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
                    
            # Intercept QFont.Style passed in third positional argument to prevent PySide6 TypeError.
            # PySide6's QFont C++ constructor signature accepts (family, pointSize, weight, italic) but
            # does not accept (family, pointSize, Style) positional arguments.
            if len(args) > 2:
                from PySide6.QtGui import QFont as _qf
                if hasattr(_qf, 'Style') and isinstance(args[2], _qf.Style):
                    style_to_set = args[2]
                    args[2] = -1  # Set default weight parameter (valid integer)
            args = tuple(args)
        super().__init__(*args, **kwargs)
        if style_to_set is not None:
            self.setStyle(style_to_set)

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
        doc.setDocumentMargin(0.0)
        doc.setDefaultFont(options.font)
        
        # Load the HTML markup content of the item
        html_text = options.text
        # Strip local and online attributes from display to show clean real file names
        for prefix in ("[LOCAL] ", "[ONLINE] ", "[local] ", "[online] ", "[LOCAL]", "[ONLINE]", "[local]", "[online]"):
            html_text = html_text.replace(prefix, "")
            
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
        # doc.setTextWidth(clip.width()) -- Disable wrapping to prevent vertical text clipping
        
        # Center the parsed HTML vertically within the row cell bounds
        text_height = doc.size().height()
        offset_y = (options.rect.height() - text_height) / 2
        if offset_y > 0:
            painter.translate(0, offset_y)
            
        doc.drawContents(painter, clip)
        
        painter.restore()

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        
        # Load font dynamically for size estimation
        font = index.data(Qt.FontRole)
        if not font or not isinstance(font, QFont):
            font = option.font
            
        # Parse exact display text using QTextDocument to bypass font-metrics fallback bugs on Windows
        doc = QTextDocument()
        doc.setDocumentMargin(0.0)
        doc.setDefaultFont(font)
        
        html_text = index.data(Qt.DisplayRole)
        if not html_text:
            html_text = ""
            
        for prefix in ("[LOCAL] ", "[ONLINE] ", "[local] ", "[online] ", "[LOCAL]", "[ONLINE]", "[local]", "[online]"):
            html_text = html_text.replace(prefix, "")
            
        doc.setHtml(html_text)
        text_height = int(doc.size().height())
        
        # Dynamic 10% spacing rule
        spacing = int(text_height * 0.10)
        if spacing < 2:
            spacing = 2
            
        # Enforce retro arcade minimum row height of 24 pixels to completely prevent compression overlaps
        row_height = max(text_height + spacing, 24)
        size.setHeight(row_height)
        return size


class BackgroundWidget(QWidget):
    """Custom widget that draws our premium cyberpunk background as a holographic screen viewport portal."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.bg_pixmap = None
        self.full_screen_bg = None
        self.overlay_opacity = 0.30 # Default to 30% overlay opacity (70% transparency!)
        self.blur_radius = 30.0 # 30px default blur radius (matching 70% transparency)
        self.layout_mode = "PORTAL" # Default layout mode
        
        # Load the background image
        bg_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "assets", "cyberpunk_bg.jpg"
        )
        if os.path.exists(bg_path):
            self.bg_pixmap = QPixmap(bg_path)
            self.regenerate_full_screen_bg()
            
        # Apply graphics blur effect
        from PySide6.QtWidgets import QGraphicsBlurEffect
        self.blur_effect = QGraphicsBlurEffect(self)
        self.blur_effect.setBlurRadius(self.blur_radius)
        self.blur_effect.setBlurHints(QGraphicsBlurEffect.PerformanceHint)
        self.setGraphicsEffect(self.blur_effect)

    def regenerate_full_screen_bg(self):
        if not self.bg_pixmap or self.bg_pixmap.isNull():
            return
            
        # Get primary screen size
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            screen_geom = screen.geometry()
            w = screen_geom.width()
            h = screen_geom.height()
        else:
            w, h = 1920, 1080 # Fallback
            
        # Scale background pixmap to stretch to the exact desktop screen dimensions
        self.full_screen_bg = self.bg_pixmap.scaled(
            w, h,
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation
        )

    def set_blur_radius(self, radius):
        self.blur_radius = max(0.0, float(radius))
        self.blur_effect.setBlurRadius(self.blur_radius)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        has_image = self.bg_pixmap and not self.bg_pixmap.isNull()
        
        if has_image:
            if self.layout_mode == "PORTAL":
                if self.full_screen_bg and not self.full_screen_bg.isNull():
                    from PySide6.QtCore import QPoint, QRect
                    # Map top-left (0,0) of this widget to absolute screen coordinates
                    global_pos = self.mapToGlobal(QPoint(0, 0))
                    
                    # Draw the portion of full_screen_bg matching our absolute desktop viewport
                    painter.drawPixmap(
                        self.rect(),
                        self.full_screen_bg,
                        QRect(global_pos.x(), global_pos.y(), self.width(), self.height())
                    )
                else:
                    painter.drawPixmap(self.rect(), self.bg_pixmap)
            elif self.layout_mode == "STRETCH":
                # Stretched perfectly to fill the widget frame (fully visible image!)
                painter.drawPixmap(self.rect(), self.bg_pixmap)
            elif self.layout_mode == "CENTER":
                # Aspect-fit and centered inside the widget frame
                scaled = self.bg_pixmap.scaled(
                    self.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                x = (self.width() - scaled.width()) // 2
                y = (self.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
        else:
            # Fallback color if image is missing
            painter.fillRect(self.rect(), QColor(13, 13, 26))
            
        # Draw dark overlay on top with dynamic opacity (adjustable)
        alpha = int(self.overlay_opacity * 255)
        overlay_color = QColor(13, 13, 26, alpha)
        painter.fillRect(self.rect(), overlay_color)


class DoubleClickableLabel(QLabel):
    double_clicked = Signal()

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


class ScraperLogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SCRAPER LIVE LOG")
        self.resize(860, 520)
        self.setModal(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.lbl_url = QLabel("Current URL: [idle]")
        self.lbl_url.setFont(QFont("Courier New", 9, QFont.Bold))
        self.lbl_url.setStyleSheet("color: #00d4ff;")
        self.lbl_url.setWordWrap(True)
        layout.addWidget(self.lbl_url)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setFont(QFont("Courier New", 9))
        self.txt_log.setStyleSheet(
            "QTextEdit {"
            "  color: #e8e8e8; background-color: rgba(12, 18, 32, 0.92);"
            "  border: 1px solid #00d4ff; border-radius: 6px;"
            "}"
        )
        layout.addWidget(self.txt_log, 1)

    def update_current_url(self, url: str):
        self.lbl_url.setText(f"Current URL: {url or '[idle]'}")

    def append_line(self, line: str):
        self.txt_log.append(line)
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())


class DescriptionBar(QWidget):
    """
    Translucent bar at the lower-right corner of the window.
    Expands smoothly to pop up the active track/game description,
    independent transparency/blur sliders, and background layout options.
    """
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setObjectName("descriptionBar")
        
        # Sleek vertical layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 8, 10, 8)
        self.layout.setSpacing(5)
        
        # Top row: Info icon + text
        self.top_widget = QWidget(self)
        self.top_widget.setStyleSheet("background: transparent;")
        top_layout = QHBoxLayout(self.top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)
        
        # Info icon
        self.lbl_icon = QLabel("ℹ️")
        self.lbl_icon.setStyleSheet("color: #00d4ff; font-family: 'Press Start 2P'; font-size: 8px; background: transparent;")
        top_layout.addWidget(self.lbl_icon)
        
        # The actual description tag label
        self.lbl_text = QLabel("NO TRACK PLAYING")
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setStyleSheet("color: #e8e8e8; font-family: 'Courier New'; font-size: 9px; background: transparent;")
        top_layout.addWidget(self.lbl_text, 1)
        
        self.layout.addWidget(self.top_widget)
        
        # 1. Opacity row: Opacity/transparency slider (only visible when expanded)
        self.slider_widget = QWidget(self)
        self.slider_widget.setStyleSheet("background: transparent;")
        slider_layout = QHBoxLayout(self.slider_widget)
        slider_layout.setContentsMargins(0, 2, 0, 0)
        slider_layout.setSpacing(6)
        
        self.lbl_slider = QLabel("🔆")
        self.lbl_slider.setStyleSheet("color: #39ff14; font-size: 10px; background: transparent;")
        slider_layout.addWidget(self.lbl_slider)
        
        # Sleek transparency slider
        self.trans_slider = QSlider(Qt.Horizontal, self)
        self.trans_slider.setRange(0, 100)
        self.trans_slider.setValue(30) # Default: 30% overlay opacity (70% transparency!)
        self.trans_slider.setStyleSheet(
            "QSlider::groove:horizontal {"
            "  height: 4px;"
            "  background: rgba(255, 255, 255, 0.1);"
            "  border-radius: 2px;"
            "}"
            "QSlider::handle:horizontal {"
            "  background: #39ff14;"
            "  width: 10px;"
            "  margin-top: -3px;"
            "  margin-bottom: -3px;"
            "  border-radius: 5px;"
            "}"
            "QSlider::sub-page:horizontal {"
            "  background: #39ff14;"
            "  border-radius: 2px;"
            "}"
        )
        self.trans_slider.valueChanged.connect(self.on_slider_changed)
        slider_layout.addWidget(self.trans_slider, 1)
        
        self.lbl_val = QLabel("30%")
        self.lbl_val.setStyleSheet("color: #39ff14; font-family: 'Courier New'; font-size: 8px; font-weight: bold; background: transparent;")
        slider_layout.addWidget(self.lbl_val)
        
        self.layout.addWidget(self.slider_widget)

        # 2. Dedicated Blur Level row (only visible when expanded)
        self.blur_widget = QWidget(self)
        self.blur_widget.setStyleSheet("background: transparent;")
        blur_layout = QHBoxLayout(self.blur_widget)
        blur_layout.setContentsMargins(0, 2, 0, 0)
        blur_layout.setSpacing(6)
        
        self.lbl_blur_icon = QLabel("💧")
        self.lbl_blur_icon.setStyleSheet("color: #00d4ff; font-size: 10px; background: transparent;")
        blur_layout.addWidget(self.lbl_blur_icon)
        
        self.blur_slider = QSlider(Qt.Horizontal, self)
        self.blur_slider.setRange(0, 50)
        self.blur_slider.setValue(30) # Default blur radius: 30px
        self.blur_slider.setStyleSheet(
            "QSlider::groove:horizontal {"
            "  height: 4px;"
            "  background: rgba(255, 255, 255, 0.1);"
            "  border-radius: 2px;"
            "}"
            "QSlider::handle:horizontal {"
            "  background: #00d4ff;"
            "  width: 10px;"
            "  margin-top: -3px;"
            "  margin-bottom: -3px;"
            "  border-radius: 5px;"
            "}"
            "QSlider::sub-page:horizontal {"
            "  background: #00d4ff;"
            "  border-radius: 2px;"
            "}"
        )
        self.blur_slider.valueChanged.connect(self.on_blur_changed)
        blur_layout.addWidget(self.blur_slider, 1)
        
        self.lbl_blur_val = QLabel("30px")
        self.lbl_blur_val.setStyleSheet("color: #00d4ff; font-family: 'Courier New'; font-size: 8px; font-weight: bold; background: transparent;")
        blur_layout.addWidget(self.lbl_blur_val)
        
        self.layout.addWidget(self.blur_widget)

        # 3. Dynamic Background Layout Buttons (only visible when expanded)
        self.buttons_widget = QWidget(self)
        self.buttons_widget.setStyleSheet("background: transparent;")
        buttons_layout = QHBoxLayout(self.buttons_widget)
        buttons_layout.setContentsMargins(0, 2, 0, 0)
        buttons_layout.setSpacing(6)
        
        self.lbl_layout_icon = QLabel("🖼️")
        self.lbl_layout_icon.setStyleSheet("color: #e94560; font-size: 10px; background: transparent;")
        buttons_layout.addWidget(self.lbl_layout_icon)
        
        self.btn_portal = QPushButton("PORTAL")
        self.btn_portal.clicked.connect(lambda: self.change_layout_mode("PORTAL"))
        buttons_layout.addWidget(self.btn_portal)
        
        self.btn_stretch = QPushButton("STRETCH")
        self.btn_stretch.clicked.connect(lambda: self.change_layout_mode("STRETCH"))
        buttons_layout.addWidget(self.btn_stretch)
        
        self.btn_center = QPushButton("CENTER")
        self.btn_center.clicked.connect(lambda: self.change_layout_mode("CENTER"))
        buttons_layout.addWidget(self.btn_center)
        
        self.layout.addWidget(self.buttons_widget)
        
        # Glassmorphic cyber styling
        self.setStyleSheet(
            "QWidget#descriptionBar {"
            "  background-color: rgba(22, 33, 62, 0.75);" # Translucent navy/blue
            "  border: 1px solid #00d4ff;"                 # Electric neon cyan border
            "  border-radius: 6px;"
            "}"
        )
        
        # Set default size and state
        self.expanded = False
        self.lbl_text.setVisible(False)
        self.slider_widget.setVisible(False)
        self.blur_widget.setVisible(False)
        self.buttons_widget.setVisible(False)
        self.setCursor(Qt.PointingHandCursor)
        
        self.adjust_size_and_position()
        self.set_active_layout_button("PORTAL")
        
    def on_slider_changed(self, val):
        self.lbl_val.setText(f"{val}%")
        if self.main_window and hasattr(self.main_window, "bg_widget"):
            self.main_window.bg_widget.overlay_opacity = val / 100.0
            self.main_window.bg_widget.update()

    def on_blur_changed(self, val):
        self.lbl_blur_val.setText(f"{val}px")
        if self.main_window and hasattr(self.main_window, "bg_widget"):
            self.main_window.bg_widget.set_blur_radius(val)
            self.main_window.bg_widget.update()

    def change_layout_mode(self, mode):
        if self.main_window and hasattr(self.main_window, "bg_widget"):
            self.main_window.bg_widget.layout_mode = mode
            self.main_window.bg_widget.update()
            self.set_active_layout_button(mode)

    def set_active_layout_button(self, mode):
        btn_style_normal = (
            "QPushButton {"
            "  color: #39ff14; background-color: rgba(20, 20, 20, 0.6);"
            "  border: 1px solid #39ff14; border-radius: 3px;"
            "  font-family: 'Press Start 2P'; font-size: 6px; padding: 3px 6px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #39ff14; color: #121620;"
            "}"
        )
        btn_style_active = (
            "QPushButton {"
            "  color: #ffffff; background-color: #e94560;"
            "  border: 1px solid #ffffff; border-radius: 3px;"
            "  font-family: 'Press Start 2P'; font-size: 6px; padding: 3px 6px; font-weight: bold;"
            "}"
        )
        
        self.btn_portal.setStyleSheet(btn_style_active if mode == "PORTAL" else btn_style_normal)
        self.btn_stretch.setStyleSheet(btn_style_active if mode == "STRETCH" else btn_style_normal)
        self.btn_center.setStyleSheet(btn_style_active if mode == "CENTER" else btn_style_normal)
            
    def adjust_size_and_position(self):
        if not self.main_window:
            return
            
        parent_width = self.main_window.width()
        parent_height = self.main_window.height()
        
        # Dimensions based on expansion state
        if self.expanded:
            width = 320
            height = 150 # Expanded height to fit all sliders & buttons perfectly!
        else:
            width = 32
            height = 24
            
        # Place at bottom right with 20px margin from bottom and right
        x = parent_width - width - 20
        y = parent_height - height - 40
        
        self.setGeometry(x, y, width, height)
        self.raise_()
        
    def enterEvent(self, event):
        if not self.expanded:
            self.expanded = True
            self.lbl_text.setVisible(True)
            self.slider_widget.setVisible(True)
            self.blur_widget.setVisible(True)
            self.buttons_widget.setVisible(True)
            self.adjust_size_and_position()
            
    def leaveEvent(self, event):
        if self.expanded:
            self.expanded = False
            self.lbl_text.setVisible(False)
            self.slider_widget.setVisible(False)
            self.blur_widget.setVisible(False)
            self.buttons_widget.setVisible(False)
            self.adjust_size_and_position()
            
    def update_description(self, desc_text):
        if not desc_text:
            self.lbl_text.setText("Select a retro game or query the online database to begin.")
        else:
            self.lbl_text.setText(desc_text.replace("\n", " | "))


class SmoothScrollArea(QScrollArea):
    """Horizontal scroll area supporting smooth mouse-wheel animations."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("background: transparent; border: none;")
        self.animation = None
        
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.angleDelta().x()
            
        bar = self.horizontalScrollBar()
        current_val = bar.value()
        # Down scroll goes right, up scroll goes left (standard mousewheel feel)
        target_val = current_val - (delta / 120) * 80
        target_val = max(bar.minimum(), min(bar.maximum(), target_val))
        
        if current_val == target_val:
            event.accept()
            return
            
        from PySide6.QtCore import QVariantAnimation, QEasingCurve
        if self.animation and self.animation.state() == QVariantAnimation.Running:
            start_val = bar.value()
            self.animation.stop()
        else:
            start_val = current_val
            
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(250) # Smooth 250ms visual transition
        self.animation.setStartValue(start_val)
        self.animation.setEndValue(int(target_val))
        self.animation.setEasingCurve(QEasingCurve.OutQuad)
        self.animation.valueChanged.connect(bar.setValue)
        self.animation.start()
        
        event.accept()


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
        self.btn_title_browse = QPushButton("BROWSE")
        self.btn_title_browse.setFixedSize(90, 30)
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
        self.btn_shortcuts_help = QPushButton("HOTKEYS")
        self.btn_shortcuts_help.setFixedSize(90, 30)
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
        self.btn_settings = QPushButton("SETTINGS")
        self.btn_settings.setFixedSize(90, 30)
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
        # Centered Glowing Neon Logo in Title Bar!
        self.title_logo = QLabel()
        self.title_logo.setAlignment(Qt.AlignCenter)
        from PySide6.QtGui import QPixmap
        logo_pixmap = QPixmap("D:\\CHIPTUNEPALACE\\assets\\chiptune_palace_logo.png")
        if not logo_pixmap.isNull():
            self.title_logo.setPixmap(logo_pixmap.scaledToHeight(28, Qt.SmoothTransformation))
        else:
            self.title_logo.setText("CHIPTUNE PALACE")
            self.title_logo.setFont(QFont("Press Start 2P", 9, QFont.Bold))
            self.title_logo.setStyleSheet("color: #e94560;")
        self.layout.addWidget(self.title_logo)
        
        self.layout.addStretch()
        
        # --- RIGHT SIDE WINDOW CONTROLS ---
        # Minimize Icon
        self.btn_min = QPushButton("MIN")
        self.btn_min.setFixedSize(62, 30)
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
        self.btn_max = QPushButton("MAX")
        self.btn_max.setFixedSize(82, 30)
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
        self.btn_close = QPushButton("CLOSE")
        self.btn_close.setFixedSize(82, 30)
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


class IntegratedVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("integratedVisualizer")
        self.setMinimumSize(240, 180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Main Layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Borderless, glowing container frame
        self.container = QFrame()
        self.container.setObjectName("visContainer")
        self.container.setStyleSheet(
            "#visContainer {"
            "  background-color: rgba(30, 30, 30, 0.85);"
            "  border: 2px solid #ff00ff;"
            "  border-radius: 8px;"
            "}"
        )
        
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(6, 6, 6, 6)
        container_layout.setSpacing(0)
        
        # Artwork Label
        self.lbl_art = QLabel()
        self.lbl_art.setAlignment(Qt.AlignCenter)
        self.lbl_art.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.lbl_art.setScaledContents(True)
        container_layout.addWidget(self.lbl_art)
        
        layout.addWidget(self.container)
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        parent = self.parentWidget()
        if parent and hasattr(parent, 'update_center_artwork'):
            parent.update_center_artwork()


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
        self.setMinimumSize(680, 754)
        self.resize(720, 780)
        
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
        self.scraper_log_dialog = None
        self.scraper_log_lines = []
        self.scraper_current_url = ""
        self.scraper_log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "logs",
            "scraper"
        )
        os.makedirs(self.scraper_log_dir, exist_ok=True)
        
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
        
        # Integrated CRT visualizer replaces the old box art / screenshot area.
        self.visualizer_window = IntegratedVisualizer(self)
        
        self.init_ui()
        self.apply_theme()
        self._load_persistent_scraper_log()
        
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
        from PySide6.QtWidgets import QFrame
        
        # Master Translucent Central Widget
        self.central_widget = QWidget(self)
        self.central_widget.setObjectName("centralWidget")
        self.setCentralWidget(self.central_widget)
        self.setMouseTracking(True)
        self.central_widget.setMouseTracking(True)
        
        # Instantiate separate background widget layers underneath
        self.bg_widget = BackgroundWidget(self.central_widget)
        self.bg_widget.lower() # Sits at the bottom of the stack
        self.bg_widget.setGeometry(self.central_widget.rect())
        
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
        
        # Keep carousel variables for backward-compatible event hooks
        self.carousel_tiles = []
        self.current_selected_console = None
        
        # === PRE-INITIALIZE PLAYBACK CONTROLS BAR & QUEUE LIST ===
        self.queue_list = QListWidget()
        self.queue_list.setObjectName("queueList")
        self.queue_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.queue_list.setSelectionMode(QListWidget.SingleSelection)
        self.queue_list.itemDoubleClicked.connect(self.on_queue_item_double_clicked)

        # Compact 2-Row Media Playback Controls Bar
        self.playback_bar = QWidget()
        self.playback_bar.setObjectName("playbackBar")
        
        playback_vertical = QVBoxLayout(self.playback_bar)
        playback_vertical.setContentsMargins(10, 6, 10, 6)
        playback_vertical.setSpacing(6)
        
        # Row 1: Seek Screen (Dynamic Seek Slider & time/track labels)
        seek_center_layout = QVBoxLayout()
        seek_center_layout.setSpacing(2)
        seek_center_layout.setContentsMargins(0, 0, 0, 0)
        
        info_row = QHBoxLayout()
        info_row.setContentsMargins(0, 0, 0, 0)
        self.lbl_time_current = QLabel("00:00")
        self.lbl_time_current.setFont(QFont("Courier New", 9))
        self.lbl_time_current.setStyleSheet("color: #00d4ff;")
        self.lbl_time_current.setMinimumWidth(38)
        
        self.lbl_playback_tracker = QLabel("[ READY FOR TRANSMISSION ]")
        self.lbl_playback_tracker.setFont(QFont("Press Start 2P", 7))
        self.lbl_playback_tracker.setStyleSheet("color: #39ff14;")
        self.lbl_playback_tracker.setAlignment(Qt.AlignCenter)
        
        self.lbl_time_total = QLabel("00:00")
        self.lbl_time_total.setFont(QFont("Courier New", 9))
        self.lbl_time_total.setStyleSheet("color: #00d4ff;")
        self.lbl_time_total.setMinimumWidth(38)
        self.lbl_time_total.setAlignment(Qt.AlignRight)
        
        info_row.addWidget(self.lbl_time_current)
        info_row.addWidget(self.lbl_playback_tracker, stretch=1)
        info_row.addWidget(self.lbl_time_total)
        seek_center_layout.addLayout(info_row)
        
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 100)
        self.seek_slider.setValue(0)
        self.seek_slider.sliderPressed.connect(self.on_seek_slider_pressed)
        self.seek_slider.sliderReleased.connect(self.on_seek_slider_released)
        seek_center_layout.addWidget(self.seek_slider)
        
        playback_vertical.addLayout(seek_center_layout)
        
        # Row 2: Transport controls
        transport_row = QHBoxLayout()
        transport_row.setSpacing(8)
        transport_row.setContentsMargins(0, 0, 0, 0)
        
        # Left Group: Controls
        self.btn_prev = QPushButton("PREV")
        self.btn_prev.setFixedSize(62, 30)
        self.btn_prev.clicked.connect(self.play_previous_track)
        self.btn_prev.setStyleSheet(
            "QPushButton { color: #00d4ff; border: 1px solid #00d4ff; border-radius: 4px; font-size: 12px; background: rgba(0,0,0,0.2); }"
            "QPushButton:hover { background: rgba(0, 212, 255, 0.15); }"
        )
        self.btn_prev.setToolTip("Previous Track (Ctrl+Left)")
        
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setFixedSize(62, 30)
        self.btn_stop.clicked.connect(self.stop_playback)
        self.btn_stop.setStyleSheet(
            "QPushButton { color: #e94560; border: 1px solid #e94560; border-radius: 4px; font-size: 12px; background: rgba(0,0,0,0.2); }"
            "QPushButton:hover { background: rgba(233, 69, 96, 0.15); }"
        )
        self.btn_stop.setToolTip("Stop Playback")
        
        self.btn_play = QPushButton("PLAY")
        self.btn_play.setObjectName("playBtn")
        self.btn_play.setFixedSize(72, 32)
        self.btn_play.clicked.connect(self.toggle_play_pause)
        self.btn_play.setToolTip("Play / Pause (Space)")
        
        self.btn_next = QPushButton("NEXT")
        self.btn_next.setFixedSize(62, 30)
        self.btn_next.clicked.connect(self.play_next_track)
        self.btn_next.setStyleSheet(
            "QPushButton { color: #00d4ff; border: 1px solid #00d4ff; border-radius: 4px; font-size: 12px; background: rgba(0,0,0,0.2); }"
            "QPushButton:hover { background: rgba(0, 212, 255, 0.15); }"
        )
        self.btn_next.setToolTip("Next Track (Ctrl+Right)")
        
        transport_row.addStretch()
        transport_row.addWidget(self.btn_prev)
        transport_row.addWidget(self.btn_stop)
        transport_row.addWidget(self.btn_play)
        transport_row.addWidget(self.btn_next)
        transport_row.addStretch()
        playback_vertical.addLayout(transport_row)

        # Row 3: playback modes
        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        mode_row.setContentsMargins(0, 0, 0, 0)

        self.btn_shuffle = QPushButton("SHUFFLE: OFF")
        self.btn_shuffle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_shuffle.setFixedHeight(24)
        self.btn_shuffle.setStyleSheet("color: #ffd700; border-color: #ffd700; padding: 2px; font-size: 6px;")
        self.btn_shuffle.clicked.connect(self.toggle_shuffle)
        self.btn_shuffle.setToolTip("Toggle Shuffle Playback Mode (Ctrl+S)")
        
        self.btn_repeat = QPushButton("REPEAT: OFF")
        self.btn_repeat.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_repeat.setFixedHeight(24)
        self.btn_repeat.setStyleSheet("color: #ff6b6b; border-color: #ff6b6b; padding: 2px; font-size: 6px;")
        self.btn_repeat.clicked.connect(self.toggle_repeat)
        self.btn_repeat.setToolTip("Toggle Repeat Track Mode (Ctrl+R)")
        
        self.btn_randomizer = QPushButton("RADAR: OFF")
        self.btn_randomizer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_randomizer.setFixedHeight(24)
        self.btn_randomizer.setStyleSheet("color: #ff00ff; border-color: #ff00ff; padding: 2px; font-size: 6px;")
        self.btn_randomizer.clicked.connect(self.toggle_randomizer)
        self.btn_randomizer.setToolTip("Toggle Cyber-Radar: auto-discovers and loops random internet retro tracks")
        
        mode_row.addWidget(self.btn_shuffle)
        mode_row.addWidget(self.btn_repeat)
        mode_row.addWidget(self.btn_randomizer)
        playback_vertical.addLayout(mode_row)

        # Row 4: Volume control
        volume_layout = QHBoxLayout()
        volume_layout.setSpacing(8)
        volume_layout.setContentsMargins(0, 0, 0, 0)
        lbl_vol_icon = QLabel("VOLUME")
        lbl_vol_icon.setMinimumWidth(60)
        lbl_vol_icon.setStyleSheet("color: #ffd700; font-size: 9px;")
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.volume_slider.valueChanged.connect(self.on_volume_changed)
        
        volume_layout.addWidget(lbl_vol_icon)
        volume_layout.addWidget(self.volume_slider)
        playback_vertical.addLayout(volume_layout)

        # === 2-COLUMN MAIN WORKSPACE SPLITTER ===
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setHandleWidth(3)
        main_splitter.setObjectName("mainSplitter")
        
        # --- LEFT COLUMN (Library Navigation & Playback Queue) ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(5)
        
        self.nav_tabs = QTabWidget()
        
        # Tab 1: Library Tree
        self.tab_library = QWidget()
        lib_layout = QVBoxLayout(self.tab_library)
        lib_layout.setContentsMargins(0, 5, 0, 0)
        
        # Library Filter Search Bar with Consolidated Icon Action Buttons
        filter_layout = QHBoxLayout()
        self.txt_lib_filter = QLineEdit()
        self.txt_lib_filter.setPlaceholderText("Filter Consoles & Games...")
        self.txt_lib_filter.setFont(QFont("Press Start 2P", 7))
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
        
        # Compact Icon-Based "Open File" button
        self.btn_open_file = QPushButton("OPEN")
        self.btn_open_file.setFixedSize(82, 28)
        self.btn_open_file.setToolTip("Open Local Chiptune File")
        self.btn_open_file.clicked.connect(self.open_and_play_file)
        self.btn_open_file.setStyleSheet(
            "QPushButton {"
            "  color: #00d4ff; background-color: rgba(20, 20, 20, 0.6); "
            "  border: 1px solid #00d4ff; border-radius: 4px; font-family: 'Press Start 2P'; font-size: 8px; padding: 0px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #00d4ff; color: #121620;"
            "}"
        )
        filter_layout.addWidget(self.btn_open_file)
        
        # Compact Icon-Based "Refresh" button
        self.btn_refresh_lib = QPushButton("REFRESH")
        self.btn_refresh_lib.setFixedSize(90, 28)
        self.btn_refresh_lib.setToolTip("Refresh Local Library Tree")
        self.btn_refresh_lib.clicked.connect(self.refresh_library_tree)
        self.btn_refresh_lib.setStyleSheet(
            "QPushButton {"
            "  color: #39ff14; background-color: rgba(20, 20, 20, 0.6); "
            "  border: 1px solid #39ff14; border-radius: 4px; font-family: 'Press Start 2P'; font-size: 8px; padding: 0px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #39ff14; color: #121620;"
            "}"
        )
        filter_layout.addWidget(self.btn_refresh_lib)
        
        lib_layout.addLayout(filter_layout)
        
        # Main Retro Archive Tree
        from chiptunepalace.gui.main_window import RichTextDelegate
        self.library_tree = QTreeWidget()
        self.library_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.library_tree.setIndentation(10)
        self.library_tree.setItemDelegate(RichTextDelegate(self.library_tree))
        self.library_tree.setHeaderLabel("Retro Archive Explorer")
        self.library_tree.setFont(QFont("Press Start 2P", 8))
        self.library_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.library_tree.customContextMenuRequested.connect(self.show_library_context_menu)
        self.library_tree.itemDoubleClicked.connect(self.on_library_item_double_clicked)
        self.library_tree.itemClicked.connect(self.on_library_item_clicked)
        self.library_tree.itemExpanded.connect(self.on_tree_item_expanded)
        self.library_tree.setMouseTracking(True)
        self.library_tree.entered.connect(lambda index: self.library_tree.viewport().update())
        self.library_tree.currentItemChanged.connect(self.on_library_current_item_changed)
        lib_layout.addWidget(self.library_tree)
        
        # Single Full-Width Contextual Scan / Play Action Button
        lib_buttons_layout = QHBoxLayout()
        self.btn_scan_folder = QPushButton("SCAN FOLDER")
        self.btn_scan_folder.clicked.connect(self.scan_local_folder)
        self.btn_scan_folder.setStyleSheet(
            "QPushButton {"
            "  color: #ffd700; background-color: rgba(20, 20, 20, 0.6); "
            "  border: 1px solid #ffd700; border-radius: 4px; "
            "  font-family: 'Press Start 2P'; font-size: 7px; font-weight: bold; padding: 6px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #ffd700; color: #121620;"
            "}"
        )
        lib_buttons_layout.addWidget(self.btn_scan_folder)
        lib_layout.addLayout(lib_buttons_layout)
        
        # Tab 2: Online Search & Scraper
        self.tab_scraper = QWidget()
        scrap_layout = QVBoxLayout(self.tab_scraper)
        scrap_layout.setContentsMargins(0, 5, 0, 0)
        
        search_row = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search Retro Music...")
        self.txt_search.setFont(QFont("Press Start 2P", 7))
        self.txt_search.setStyleSheet(
            "QLineEdit {"
            "  color: #ffffff; background-color: rgba(20, 20, 20, 0.6); "
            "  border: 1px solid #00d4ff; border-radius: 4px; padding: 5px;"
            "}"
            "QLineEdit:focus {"
            "  border: 1px solid #ff00ff;"
            "}"
        )
        self.txt_search.returnPressed.connect(self.trigger_online_search)
        
        self.btn_search = QPushButton("SEARCH")
        self.btn_search.clicked.connect(self.trigger_online_search)
        self.btn_search.setFont(QFont("Press Start 2P", 7))
        self.btn_search.setFixedWidth(110)
        self.btn_search.setFixedHeight(26)
        
        search_row.addWidget(self.txt_search)
        search_row.addWidget(self.btn_search)
        scrap_layout.addLayout(search_row)
        
        # Scraper Results List
        self.search_results = QListWidget()
        self.search_results.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.search_results.setFont(QFont("Courier New", 11))
        self.search_results.itemClicked.connect(self.on_search_result_clicked)
        self.search_results.itemDoubleClicked.connect(self.on_search_result_double_clicked)
        scrap_layout.addWidget(self.search_results)
        
        self.btn_download_pack = QPushButton("DOWNLOAD & STREAM PACK")
        self.btn_download_pack.setEnabled(False)
        self.btn_download_pack.clicked.connect(self.download_selected_online_pack)
        self.btn_download_pack.setFont(QFont("Press Start 2P", 7))
        self.btn_download_pack.setFixedHeight(30)
        scrap_layout.addWidget(self.btn_download_pack)
        
        self.nav_tabs.addTab(self.tab_library, "LOCAL LIBRARY")
        self.nav_tabs.addTab(self.tab_scraper, "ONLINE SCRAPER")
        
        left_layout.addWidget(self.nav_tabs, stretch=5)
        
        # Add Playback Queue Separator/Header
        lbl_queue_header = QLabel("PLAYBACK QUEUE")
        lbl_queue_header.setFont(QFont("Press Start 2P", 7))
        lbl_queue_header.setStyleSheet("color: #00d4ff; text-transform: uppercase; margin-top: 8px; margin-bottom: 2px;")
        lbl_queue_header.setAlignment(Qt.AlignLeft)
        left_layout.addWidget(lbl_queue_header)
        
        # Add Playback Queue List
        left_layout.addWidget(self.queue_list, stretch=3)
        
        main_splitter.addWidget(left_widget)
        
        # --- RIGHT COLUMN (Visual Gameplay Screen & Control Deck) ---
        self.cyberpunk_images = [
            "D:\\CHIPTUNEPALACE\\assets\\cyberpunk_art_1.png",
            "D:\\CHIPTUNEPALACE\\assets\\cyberpunk_art_2.png",
            "D:\\CHIPTUNEPALACE\\assets\\cyberpunk_art_3.png"
        ]
        self.current_art_index = 0
        
        # Aliases for high-fidelity backwards compatibility
        self.lbl_center_art = self.visualizer_window.lbl_art
        self.center_art_frame = self.visualizer_window.container
        
        self.update_center_artwork()
        
        # Start QTimer for alternating centerpiece artwork
        self.art_carousel_timer = QTimer(self)
        self.art_carousel_timer.timeout.connect(self.cycle_center_artwork)
        self.art_carousel_timer.start(8000)
        
        # Title Metadata Panel
        self.metadata_panel = QWidget()
        meta_layout = QVBoxLayout(self.metadata_panel)
        meta_layout.setContentsMargins(10, 10, 10, 10)
        meta_layout.setSpacing(6)
        
        lbl_meta_header = QLabel("CYBER RECEIVER")
        lbl_meta_header.setFont(QFont("Press Start 2P", 7))
        lbl_meta_header.setStyleSheet("color: #ff00ff; text-transform: uppercase;")
        lbl_meta_header.setAlignment(Qt.AlignCenter)
        meta_layout.addWidget(lbl_meta_header)
        
        self.lbl_now_playing_title = QLabel("NO TUNE PLAYING")
        self.lbl_now_playing_title.setFont(QFont("Press Start 2P", 9, QFont.Bold))
        self.lbl_now_playing_title.setStyleSheet("color: #39ff14;") # Lime text
        self.lbl_now_playing_title.setWordWrap(True)
        self.lbl_now_playing_title.setAlignment(Qt.AlignCenter)
        self.lbl_now_playing_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        meta_layout.addWidget(self.lbl_now_playing_title)
        
        self.lbl_now_playing_desc = QLabel("Select a retro game or query the online database to begin.")
        self.lbl_now_playing_desc.setFont(QFont("Courier New", 10))
        self.lbl_now_playing_desc.setWordWrap(True)
        self.lbl_now_playing_desc.setAlignment(Qt.AlignCenter)
        self.lbl_now_playing_desc.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        meta_layout.addWidget(self.lbl_now_playing_desc)
        
        # Integrated CRT screen control.
        self.btn_toggle_vis = QPushButton("NEXT VISUAL")
        self.btn_toggle_vis.setObjectName("toggleVisBtn")
        self.btn_toggle_vis.setFixedHeight(32)
        self.btn_toggle_vis.setFont(QFont("Press Start 2P", 7))
        self.btn_toggle_vis.setStyleSheet(
            "QPushButton {"
            "  color: #ff00ff; background-color: rgba(20, 20, 20, 0.6); "
            "  border: 1px solid #ff00ff; border-radius: 4px; "
            "  font-family: 'Press Start 2P'; font-size: 7px; font-weight: bold; padding: 6px; margin-top: 5px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #ff00ff; color: #121620;"
            "}"
        )
        self.btn_toggle_vis.clicked.connect(self.cycle_center_artwork)
        meta_layout.addWidget(self.btn_toggle_vis)

        # Right Pane container stacking elements vertically
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 5, 5, 5)
        right_layout.setSpacing(6)
        
        right_layout.addWidget(self.metadata_panel)
        right_layout.addWidget(self.visualizer_window, stretch=1)
        right_layout.addWidget(self.playback_bar)
        
        main_splitter.addWidget(right_widget)
        
        # Set Splitter ratio & stretch behavior for high-fidelity 2-column resizing
        left_widget.setMinimumWidth(320)
        right_widget.setMinimumWidth(320)
        main_splitter.setSizes([350, 370])
        main_splitter.setStretchFactor(0, 1)  # Make left library panel grow/stretch
        main_splitter.setStretchFactor(1, 2)  # Make right console/artwork panel stretch double
        master_layout.addWidget(main_splitter)
        
        # 5. Downloads Progress Panel (at very bottom)
        self.downloads_panel = QWidget()
        self.downloads_panel.setFixedHeight(40)
        self.downloads_panel.setStyleSheet("background: rgba(0,0,0,0.3); border-top: 1px solid #2a2a4a;")
        dl_layout = QHBoxLayout(self.downloads_panel)
        dl_layout.setContentsMargins(15, 2, 15, 2)
        
        self.lbl_dl_status = DoubleClickableLabel("NO LIVE DOWNLOADS")
        self.lbl_dl_status.setFont(QFont("Courier New", 10, QFont.Bold))
        self.lbl_dl_status.setStyleSheet("color: #6a7080; border: none;")
        self.lbl_dl_status.setToolTip("Double-click to open scraper live log")
        self.lbl_dl_status.double_clicked.connect(self.show_scraper_log_dialog)
        
        self.dl_progress = QProgressBar()
        self.dl_progress.setRange(0, 100)
        self.dl_progress.setValue(0)
        self.dl_progress.setVisible(False)
        self.dl_progress.setStyleSheet("border-color: #00d4ff;") # Neon cyan border
        dl_layout.addWidget(self.lbl_dl_status)
        dl_layout.addWidget(self.dl_progress, stretch=1)
        master_layout.addWidget(self.downloads_panel)
        
        # 6. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Retro Arcade Core Initialized.")
        self.status_bar.setStyleSheet("QStatusBar { background: rgba(13, 13, 26, 255); color: #6a7080; font-family: 'Press Start 2P'; font-size: 6px; }")
        
        # 7. Floating glassmorphic description bar at the bottom-right corner
        self.description_bar = DescriptionBar(self)

    def on_carousel_tile_clicked(self, name, filter_text, button):
        if self.current_selected_console == name:
            self.current_selected_console = None
            button.setProperty("selected", "false")
            button.style().unpolish(button)
            button.style().polish(button)
            self.txt_lib_filter.setText("")
            self.status_bar.showMessage("Carousel filter cleared.", 3000)
        else:
            for btn in self.carousel_tiles:
                btn.setProperty("selected", "false")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                
            self.current_selected_console = name
            button.setProperty("selected", "true")
            button.style().unpolish(button)
            button.style().polish(button)
            
            self.txt_lib_filter.setText(filter_text)
            self.status_bar.showMessage(f"Displaying {filter_text} games catalog.", 4000)

    def update_center_artwork(self):
        if not hasattr(self, 'lbl_center_art') or not self.lbl_center_art:
            return
        art_path = self.cyberpunk_images[self.current_art_index]
        pixmap = QPixmap(art_path)
        lbl = self.lbl_center_art
        if not pixmap.isNull():
            w = lbl.width()
            h = lbl.height()
            if w < 100 or h < 100:
                w, h = 360, 240
            lbl.setPixmap(pixmap.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            lbl.setText(f"[ CYBERPUNK VIEW {self.current_art_index + 1} ]")
            lbl.setFont(QFont("Press Start 2P", 10))
            lbl.setStyleSheet("color: #00d4ff;")

    def cycle_center_artwork(self):
        self.current_art_index = (self.current_art_index + 1) % len(self.cyberpunk_images)
        self.update_center_artwork()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "bg_widget") and self.bg_widget:
            self.bg_widget.setGeometry(self.central_widget.rect())
        if hasattr(self, "description_bar") and self.description_bar:
            self.description_bar.adjust_size_and_position()

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, "bg_widget") and self.bg_widget:
            self.bg_widget.update()

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, 'lbl_center_art') and self.lbl_center_art:
            self.update_center_artwork()

    def toggle_visualizer(self):
        self.cycle_center_artwork()

    # --- Frameless Window Drag Resizing Border Methods ---
    _resize_border = 6
    _resize_edge = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
            self._resize_edge = self._get_resize_edge(local_pos)
            if self._resize_edge:
                self._resize_start_geometry = self.geometry()
                self._resize_start_global_pos = event.globalPosition().toPoint()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        local_pos = self.mapFromGlobal(event.globalPosition().toPoint())
        if event.buttons() == Qt.NoButton:
            edge = self._get_resize_edge(local_pos)
            if edge in ("left", "right"):
                self.setCursor(Qt.SizeHorCursor)
            elif edge in ("top", "bottom"):
                self.setCursor(Qt.SizeVerCursor)
            elif edge in ("top-left", "bottom-right"):
                self.setCursor(Qt.SizeFDiagCursor)
            elif edge in ("top-right", "bottom-left"):
                self.setCursor(Qt.SizeBDiagCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
        elif event.buttons() == Qt.LeftButton and hasattr(self, "_resize_edge") and self._resize_edge:
            from PySide6.QtCore import QRect
            delta = event.globalPosition().toPoint() - self._resize_start_global_pos
            geom = QRect(self._resize_start_geometry)
            min_w = self.minimumWidth()
            min_h = self.minimumHeight()
            
            if "right" in self._resize_edge:
                geom.setWidth(max(min_w, self._resize_start_geometry.width() + delta.x()))
            elif "left" in self._resize_edge:
                new_w = max(min_w, self._resize_start_geometry.width() - delta.x())
                geom.setLeft(self._resize_start_geometry.right() - new_w)
                
            if "bottom" in self._resize_edge:
                geom.setHeight(max(min_h, self._resize_start_geometry.height() + delta.y()))
            elif "top" in self._resize_edge:
                new_h = max(min_h, self._resize_start_geometry.height() - delta.y())
                geom.setTop(self._resize_start_geometry.bottom() - new_h)
                
            self.setGeometry(geom)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._resize_edge = None
        self.setCursor(Qt.ArrowCursor)
        super().mouseReleaseEvent(event)

    def _get_resize_edge(self, pos):
        if self._is_maximized:
            return None
        w = self.width()
        h = self.height()
        margin = self._resize_border
        
        on_left = pos.x() <= margin
        on_right = pos.x() >= w - margin
        on_top = pos.y() <= margin
        on_bottom = pos.y() >= h - margin
        
        if on_top and on_left: return "top-left"
        if on_top and on_right: return "top-right"
        if on_bottom and on_left: return "bottom-left"
        if on_bottom and on_right: return "bottom-right"
        if on_left: return "left"
        if on_right: return "right"
        if on_top: return "top"
        if on_bottom: return "bottom"
        return None

    def apply_theme(self):
        self.setStyleSheet(GLOBAL_STYLE)

    # --- Title Bar & Frameless Window Commands ---
    def toggle_maximize(self):
        if self._is_maximized:
            self.showNormal()
            self._is_maximized = False
            self.title_bar.btn_max.setText("MAX")
        else:
            self._normal_geometry = self.geometry()
            self.showMaximized()
            self._is_maximized = True
            self.title_bar.btn_max.setText("RESTORE")

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

    def show_scraper_log_dialog(self):
        if self.scraper_log_dialog is None:
            self.scraper_log_dialog = ScraperLogDialog(self)
            for line in self.scraper_log_lines:
                self.scraper_log_dialog.append_line(line)
            self.scraper_log_dialog.update_current_url(self.scraper_current_url)
        self.scraper_log_dialog.show()
        self.scraper_log_dialog.raise_()
        self.scraper_log_dialog.activateWindow()

    def append_scraper_log(self, message: str, url: str = ""):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        self.scraper_log_lines.append(line)
        if len(self.scraper_log_lines) > 2000:
            self.scraper_log_lines = self.scraper_log_lines[-2000:]

        if url:
            self.scraper_current_url = url

        self._write_scraper_log_line(line, url=url)

        if self.scraper_log_dialog is not None:
            self.scraper_log_dialog.append_line(line)
            self.scraper_log_dialog.update_current_url(self.scraper_current_url)

    def _today_scraper_log_path(self) -> str:
        day = datetime.datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.scraper_log_dir, f"scraper_{day}.log")

    def _write_scraper_log_line(self, line: str, url: str = ""):
        try:
            log_path = self._today_scraper_log_path()
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
                if url:
                    f.write(f"    URL: {url}\n")
        except Exception as e:
            self.debug_service.log_error(f"Failed to persist scraper log line: {e}")

    def _load_persistent_scraper_log(self):
        """
        Loads today's persistent scraper log into memory so the live log window
        remains incremental across app restarts.
        """
        path = self._today_scraper_log_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = [ln.rstrip("\n") for ln in f.readlines()]
            # Keep memory bounded while preserving recent context
            self.scraper_log_lines = lines[-2000:]
        except Exception as e:
            self.debug_service.log_error(f"Failed loading persistent scraper log: {e}")

    # --- Local Library & Online Catalog Explorer Operations ---
    def refresh_library_tree(self):
        """Refreshes the catalog explorer (reloads online systems)."""
        self.load_online_consoles()

    def load_online_consoles(self):
        self.status_bar.showMessage("Connecting to retro music archives...")
        self.append_scraper_log("Starting console catalog refresh.", "https://vgmrips.net/packs/systems")
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
            self.append_scraper_log("Console catalog request returned no data.")
            self.status_bar.showMessage("Failed to connect online. Loading local library fallback.")
            self.refresh_local_only_tree()
            return
             
        self.append_scraper_log(f"Loaded {len(consoles)} console entries.")
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
        self.append_scraper_log(f"Console catalog error: {err}")
        self.status_bar.showMessage(f"Catalog connection failed: {err[:50]}. Loading local fallback.", 6000)
        self.refresh_local_only_tree()

    def on_tree_item_expanded(self, item):
        """Loads console/game children lazily and shields UI from malformed data or callback races."""
        try:
            node_type = item.data(0, Qt.UserRole)

            if node_type == "console":
                if item.childCount() == 1 and item.child(0).data(0, Qt.UserRole) == "dummy":
                    url = item.data(1, Qt.UserRole)
                    console_name = item.data(2, Qt.UserRole)
                    self.append_scraper_log(f"Loading packs for console '{console_name}'.", url)

                    cached_packs = self.track_service.db_manager.get_cached_packs(console_name)
                    if cached_packs:
                        self.on_packs_loaded(item, console_name, cached_packs)
                        thread = ScraperThread(self.scraper.get_packs_by_console, url)
                        thread.task_finished.connect(lambda packs, i=item, c=console_name: self.on_background_packs_updated(i, c, packs))
                        thread.start()
                        self._image_threads.append(thread)
                    else:
                        thread = ScraperThread(self.scraper.get_packs_by_console, url)
                        thread.task_finished.connect(lambda packs, i=item, c=console_name: self.on_packs_loaded(i, c, packs))
                        thread.error.connect(lambda err: self.status_bar.showMessage(f"Error loading packs: {err}", 5000))
                        thread.start()
                        self._image_threads.append(thread)

            elif node_type in ("game", "game_local"):
                if item.childCount() == 1 and item.child(0).data(0, Qt.UserRole) == "dummy":
                    url = item.data(1, Qt.UserRole)
                    game_name = item.data(2, Qt.UserRole)
                    parent_item = item.parent()
                    console_name = parent_item.data(2, Qt.UserRole) if parent_item else "Unknown"
                    if not console_name and parent_item:
                        console_name = parent_item.text(0)
                    source = item.data(3, Qt.UserRole) or ("Local" if node_type == "game_local" else "")
                    self.append_scraper_log(
                        f"Loading tracks for game '{game_name}' ({console_name}) from source '{source}'.",
                        url
                    )

                    if self.populate_local_tracks_for_game_item(item, console_name, game_name):
                        return

                    if node_type == "game_local":
                        item.removeChild(item.child(0))
                        no_tracks = QTreeWidgetItem(item)
                        no_tracks.setText(0, "[ No local files indexed ]")
                        italic_font = QFont("Courier New", 11)
                        italic_font.setItalic(True)
                        no_tracks.setFont(0, italic_font)
                        no_tracks.setForeground(0, QColor("#6a7080"))
                        return

                    if source == "ModArchive":
                        item.removeChild(item.child(0))
                        t_item = QTreeWidgetItem(item)

                        ext = ".mod"
                        if url:
                            url_ext = os.path.splitext(url.split('?')[0])[1].lower()
                            if url_ext:
                                ext = url_ext
                        t_item.setText(0, f"[ONLINE] Play Module{ext}")
                        t_item.setFont(0, QFont("Courier New", 11))
                        t_item.setForeground(0, QColor("#00ffff"))
                        t_item.setData(0, Qt.UserRole, "online_track")
                        t_item.setData(1, Qt.UserRole, url)
                        t_item.setData(2, Qt.UserRole, game_name)
                        t_item.setData(3, Qt.UserRole, source)
                    else:
                        thread = ScraperThread(self.scraper.get_tracks_in_pack, url)
                        thread.task_finished.connect(lambda tracks, i=item, g=game_name, u=url, s=source: self.on_tracks_loaded(i, g, u, s, tracks))
                        thread.error.connect(lambda err: self.status_bar.showMessage(f"Error loading tracks: {err}", 5000))
                        thread.start()
                        self._image_threads.append(thread)
        except Exception as e:
            self.debug_service.log_error(f"MainWindow: Explorer expansion failed: {e}")
            self.debug_service.log_error(traceback.format_exc())
            self.status_bar.showMessage("Explorer failed to load this folder. See debug log for details.", 5000)

    def populate_local_tracks_for_game_item(self, item, console_name, game_name):
        """Synchronously fills a game node with indexed local tracks when available."""
        local_tracks = self.track_service.get_tracks_by_console_and_game(console_name, game_name)
        if not local_tracks:
            return False

        item.takeChildren()
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
            t_item.setForeground(0, QColor("#00ff41"))
            t_item.setData(0, Qt.UserRole, "track")
            t_item.setData(1, Qt.UserRole, t['id'])
            t_item.setData(2, Qt.UserRole, t.get('title') or "")
        return True

    def on_packs_loaded(self, item, console_name, packs, cache_to_db=True):
        if item is None:
            return

        if not isinstance(packs, list):
            packs = []

        # Cache packs in local database
        if cache_to_db and packs and hasattr(self, "track_service") and self.track_service.db_manager:
            self.track_service.db_manager.cache_packs(console_name, packs)

        # Remove dummy child
        if item.childCount() > 0:
            item.removeChild(item.child(0))

        if not packs:
            self.append_scraper_log(f"No packs found for console '{console_name}'.")
            no_packs = QTreeWidgetItem(item)
            no_packs.setText(0, "[ No Packs Available ]")
            italic_font = QFont("Courier New", 11)
            italic_font.setItalic(True)
            no_packs.setFont(0, italic_font)
            no_packs.setForeground(0, QColor("#6a7080"))
            return

        self.append_scraper_log(f"Retrieved {len(packs)} packs for console '{console_name}'.")
        for p in packs:
            if not isinstance(p, dict):
                continue

            title = (p.get("title") or "").strip()
            if not title:
                continue

            pack_url = p.get("url", "")
            download_url = p.get("download_url", pack_url)

            p_item = QTreeWidgetItem(item)
            p_item.setText(0, title)
            p_item.setFont(0, QFont("Courier New", 11, QFont.Bold))
            p_item.setForeground(0, QColor("#ffd700"))

            # Check if this pack is already local
            local_tracks = self.track_service.get_tracks_by_console_and_game(console_name, title)
            if local_tracks:
                p_item.setText(0, f"[LOCAL] {title}")
                p_item.setForeground(0, QColor("#39ff14"))

            p_item.setData(0, Qt.UserRole, "game")
            p_item.setData(1, Qt.UserRole, pack_url)
            p_item.setData(2, Qt.UserRole, title)
            p_item.setData(3, Qt.UserRole, p.get("source", "VGMRips"))
            p_item.setData(4, Qt.UserRole, download_url)

            # Add dummy child so it shows expand arrow
            dummy = QTreeWidgetItem(p_item)
            dummy.setText(0, "Loading Tracks...")
            dummy.setData(0, Qt.UserRole, "dummy")

        # Re-apply active search filter if one is present
        filter_text = self.txt_lib_filter.text()
        if filter_text.strip():
            self.filter_library_tree(filter_text)

    def on_background_packs_updated(self, item, console_name, packs):
        if not packs:
            return
            
        # 1. Update the database cache with fresh scrape
        if hasattr(self, "track_service") and self.track_service.db_manager:
            self.track_service.db_manager.cache_packs(console_name, packs)
            
        # 2. Check if we need to update the UI
        ui_packs_count = 0
        for idx in range(item.childCount()):
            child = item.child(idx)
            if child.data(0, Qt.UserRole) == "game":
                ui_packs_count += 1
                
        if ui_packs_count != len(packs):
            self.status_bar.showMessage(f"Discovered {len(packs) - ui_packs_count} new games for {console_name}! Catalog updated.", 4000)
            
            # Save expanded state of existing children
            expanded_games = set()
            for idx in range(item.childCount()):
                child = item.child(idx)
                if child.data(0, Qt.UserRole) == "game" and child.isExpanded():
                    expanded_games.add(child.data(2, Qt.UserRole))
                    
            # Refresh node
            item.takeChildren()
            self.on_packs_loaded(item, console_name, packs)
            
            # Restore expanded state
            for idx in range(item.childCount()):
                child = item.child(idx)
                if child.data(0, Qt.UserRole) == "game" and child.data(2, Qt.UserRole) in expanded_games:
                    child.setExpanded(True)

    def _find_matching_local_track(self, scraped_title, local_tracks):
        if not scraped_title or not local_tracks:
            return None
            
        # Clean HTML highlight markup tags if present (e.g. from dynamic search tags)
        scraped_title_clean = re.sub(r'<[^<]+?>', '', scraped_title)
        
        # Strip common track duration suffixes like " 2:21" or " 03:45" at the end of the track name
        scraped_title_clean = re.sub(r'\s*\d+:\d+\s*$', '', scraped_title_clean)
        
        # Strip other potential surrounding whitespace
        scraped_title_clean = scraped_title_clean.strip()
            
        # Normalize scraped title: remove punctuation, lowercase
        norm_scraped = re.sub(r'[^a-zA-Z0-9]', '', scraped_title_clean).lower()
        
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
        words_scraped = [w for w in re.findall(r'\w+', scraped_title_clean.lower()) if len(w) > 2]
        if words_scraped:
            for t in local_tracks:
                local_title = os.path.splitext(t['title'])[0].lower()
                if all(word in local_title for word in words_scraped[:2]):
                    return t
                    
        return None

    def on_tracks_loaded(self, item, game_name, pack_url, source, tracks):
        if item is None:
            return

        if not isinstance(tracks, list):
            tracks = []

        # Remove dummy
        if item.childCount() > 0:
            item.removeChild(item.child(0))

        if not tracks:
            self.append_scraper_log(
                f"No track list scraped for '{game_name}'. Archive contents are not inspected yet.",
                pack_url
            )
            # This is an availability placeholder, not proof that the game has
            # only one file. Double-click downloads and indexes the archive.
            t_item = QTreeWidgetItem(item)
            t_item.setText(0, "[ONLINE] Inspect archive files")
            t_item.setFont(0, QFont("Courier New", 11))
            t_item.setForeground(0, QColor("#00ffff"))
            t_item.setData(0, Qt.UserRole, "online_track")
            t_item.setData(1, Qt.UserRole, pack_url)
            t_item.setData(2, Qt.UserRole, game_name)
            t_item.setData(3, Qt.UserRole, source)
            return

        self.append_scraper_log(f"Retrieved {len(tracks)} track entries for game '{game_name}'.", pack_url)
        parent_item = item.parent()
        console_name = parent_item.data(2, Qt.UserRole) if parent_item else "Unknown"
        local_tracks = self.track_service.get_tracks_by_console_and_game(console_name, game_name)

        for t in tracks:
            if not isinstance(t, dict):
                continue

            track_title = (t.get("title") or "").strip()
            if not track_title:
                continue

            t_item = QTreeWidgetItem(item)

            matched_local = None
            if local_tracks:
                matched_local = self._find_matching_local_track(track_title, local_tracks)

            if matched_local:
                ext = ""
                if matched_local.get('member_name'):
                    ext = os.path.splitext(matched_local['member_name'])[1].lower()
                elif matched_local.get('file_path'):
                    ext = os.path.splitext(matched_local['file_path'])[1].lower()
                elif matched_local.get('format'):
                    ext = f".{matched_local['format'].lower()}"
                t_item.setText(0, f"[LOCAL] {track_title}{ext}")
                t_item.setFont(0, QFont("Courier New", 11))
                t_item.setForeground(0, QColor("#00ff41"))
                t_item.setData(0, Qt.UserRole, "track")
                t_item.setData(1, Qt.UserRole, matched_local['id'])
            else:
                ext = self.get_console_default_extension(console_name)
                t_item.setText(0, f"[ONLINE] {track_title}{ext}")
                t_item.setFont(0, QFont("Courier New", 11))
                t_item.setForeground(0, QColor("#00ffff"))
                t_item.setData(0, Qt.UserRole, "online_track")
                t_item.setData(1, Qt.UserRole, pack_url)

            t_item.setData(2, Qt.UserRole, track_title)
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
            console_item.setData(2, Qt.UserRole, console)
            
            for game, tracks in games.items():
                game_item = QTreeWidgetItem(console_item)
                game_item.setText(0, f"★ {game}")
                game_item.setFont(0, QFont("Courier New", 11, QFont.Bold))
                game_item.setForeground(0, QColor("#39ff14")) # Lime local
                game_item.setData(0, Qt.UserRole, "game_local")
                game_item.setData(2, Qt.UserRole, game)
                game_item.setData(3, Qt.UserRole, "Local")
                
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
                    track_item.setData(2, Qt.UserRole, t.get('title') or "")
                    

    def on_library_current_item_changed(self, current, previous):
        """Dynamically transforms the 'SCAN FOLDER' button to 'PLAY FOLDER CONTENT' when a folder is selected."""
        if current:
            node_type = current.data(0, Qt.UserRole)
            if node_type in ("game", "game_local", "console", "console_local"):
                self.btn_scan_folder.setText("PLAY FOLDER CONTENT")
                self.btn_scan_folder.setStyleSheet(
                    "QPushButton {"
                    "  color: #ff00ff; background-color: rgba(20, 20, 20, 0.6); "
                    "  border: 1px solid #ff00ff; border-radius: 4px; "
                    "  font-family: 'Press Start 2P'; font-size: 7px; font-weight: bold; padding: 6px;"
                    "}"
                    "QPushButton:hover {"
                    "  background-color: #ff00ff; color: #121620;"
                    "}"
                )
                return
                
        self.btn_scan_folder.setText("SCAN FOLDER")
        self.btn_scan_folder.setStyleSheet(
            "QPushButton {"
            "  color: #ffd700; background-color: rgba(20, 20, 20, 0.6); "
            "  border: 1px solid #ffd700; border-radius: 4px; "
            "  font-family: 'Press Start 2P'; font-size: 7px; font-weight: bold; padding: 6px;"
            "}"
            "QPushButton:hover {"
            "  background-color: #ffd700; color: #121620;"
            "}"
        )

    def on_library_item_clicked(self, item, column):
        if item is None:
            self.debug_service.log_warning("Ignoring library click because item is null.")
            return

        node_type = item.data(0, Qt.UserRole)
        
        if node_type == "track":
            track_id = item.data(1, Qt.UserRole)
            if track_id is not None:
                track = self.track_service.get_track_by_id(track_id)
                if track:
                    self.update_track_metadata_display(track)
                    
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
            game_item = item.parent()
            console_item = game_item.parent() if game_item else None
            game_name = game_item.data(2, Qt.UserRole) if game_item else ""
            console_name = console_item.data(2, Qt.UserRole) if console_item else ""
            
            fake_track = {
                'title': track_title,
                'artist': 'Various',
                'console': console_name,
                'game': game_name
            }
            self.update_track_metadata_display(fake_track)
            
        elif node_type in ("console", "console_local"):
            item.setExpanded(not item.isExpanded())

    def on_library_item_double_clicked(self, item, column):
        if item is None:
            self.debug_service.log_warning("Ignoring library double-click because item is null.")
            return

        node_type = item.data(0, Qt.UserRole)
        self.debug_service.log_interaction("Library item double-clicked", f"Type: {node_type}, Text: '{item.text(0)}'")
        self.disable_randomizer_if_active()
        
        if node_type == "track":
            track_id = item.data(1, Qt.UserRole)
            if track_id is not None:
                track_details = self.track_service.get_track_by_id(track_id)
                
                # Check if the local file exists on disk
                file_exists = False
                if track_details and track_details.get('file_path'):
                    file_exists = os.path.exists(track_details['file_path'])
                    
                if not file_exists:
                    # Dynamic online fallback streaming!
                    self.debug_service.log_info(f"Local track file missing: {track_details.get('file_path') if track_details else 'None'}. Querying fallback source URL.")
                    source_url = None
                    if track_details:
                        source_url = track_details.get('source_url')
                        
                    # Query scraped_packs database cache for the game's download URL
                    if not source_url and track_details:
                        game_name = track_details.get('game')
                        console_name = track_details.get('console')
                        if game_name and console_name:
                            scraped_pack = self.track_service.db_manager.get_scraped_pack_by_name(console_name, game_name)
                            if scraped_pack:
                                source_url = scraped_pack.get('download_url') or scraped_pack.get('url')
                                
                    if source_url:
                        # Convert to online track and trigger dynamic streaming!
                        cleaned_title = track_details.get('title') if track_details else re.sub(r'^\[LOCAL\]\s*', '', item.text(0))
                        item.setData(0, Qt.UserRole, "online_track")
                        item.setData(1, Qt.UserRole, source_url)
                        item.setData(2, Qt.UserRole, cleaned_title)
                        item.setData(3, Qt.UserRole, "Online Repository")
                        
                        parent_game = item.parent()
                        if parent_game:
                            parent_game.setData(4, Qt.UserRole, source_url)
                            
                        self.status_bar.showMessage("Local file missing on disk. Falling back to online repository...", 6000)
                        self.on_library_item_double_clicked(item, column)
                        return
                
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
            game_item = item.parent()
            console_item = game_item.parent() if game_item else None
            game_name = game_item.data(2, Qt.UserRole) if game_item else ""
            console_name = console_item.data(2, Qt.UserRole) if console_item else ""

            if not game_item:
                self.debug_service.log_warning(
                    f"Online stream aborted: missing game parent for track '{track_title}'."
                )
                self.status_bar.showMessage("Unable to stream track: missing game context.", 5000)
                return
            
            self.lbl_dl_status.setText(f"STREAMING: {track_title.upper()[:25]}...")
            self.lbl_dl_status.setStyleSheet("color: #00d4ff; border: none;")
            self.dl_progress.setValue(0)
            self.dl_progress.setVisible(True)
            
            self._active_downloading_item = game_item
            self._active_playing_title = track_title
            
            # Retrieve direct ZIP download URL from role 4 (falls back to pack_url for ModArchive)
            download_url = game_item.data(4, Qt.UserRole) or pack_url
            if not download_url:
                self.debug_service.log_error(
                    f"Online stream aborted: no URL for track='{track_title}', game='{game_name}', source='{source}'."
                )
                self.status_bar.showMessage("Unable to stream track: missing source URL.", 5000)
                self.dl_progress.setVisible(False)
                self.lbl_dl_status.setText("STREAM FAILED")
                self.lbl_dl_status.setStyleSheet("color: #ff5555; border: none;")
                return

            if "zophar.net" in download_url:
                resolved = self.scraper.get_resolved_zophar_download_url(download_url)
                if resolved:
                    download_url = resolved
                else:
                    self.debug_service.log_warning(
                        f"Zophar URL resolver returned empty URL, continuing with original: {download_url}"
                    )
                
            self.download_service.download_pack(
                url=download_url,
                pack_name=game_name,
                extract=False,
                on_progress=self.on_download_progress,
                on_status=self.on_download_status,
                on_zip_ready=lambda path, job_id, c=console_name, g=game_name, u=download_url: self._safe_on_online_track_downloaded(path, c, g, u),
                on_error=self.on_download_error
            )

    def _safe_on_online_track_downloaded(self, zip_path, console, game, source_url):
        try:
            self.on_online_track_downloaded(zip_path, console, game, source_url)
        except Exception as e:
            self.debug_service.log_error(f"Streaming callback failed: {e}")
            self.status_bar.showMessage(f"Streaming failed: {str(e)[:80]}", 6000)
            self.dl_progress.setVisible(False)
            self.lbl_dl_status.setText("STREAM FAILED")
            self.lbl_dl_status.setStyleSheet("color: #ff5555; border: none;")
            self.append_scraper_log(f"Streaming failure for '{game}': {e}", source_url or "")

    def on_online_track_downloaded(self, zip_path, console, game, source_url):
        if not zip_path or not os.path.exists(zip_path):
            raise FileNotFoundError(f"ZIP not found after download: {zip_path}")

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
        self.append_scraper_log(f"Search started for query '{query}'.", f"https://vgmrips.net/packs/search?q={query}")
        
        self.search_thread = ScraperThread(self.scraper.search_online, query)
        self.search_thread.task_finished.connect(self.on_search_finished)
        self.search_thread.error.connect(self.on_search_error)
        self.search_thread.start()

    def on_search_finished(self, results):
        self.btn_search.setEnabled(True)
        self.txt_search.setEnabled(True)
        
        if not results:
            self.append_scraper_log("Search finished with 0 results.")
            self.status_bar.showMessage("Search finished: 0 matching packs found.", 5000)
            self.search_results.addItem("No retro albums found online matching query.")
            return
             
        self.append_scraper_log(f"Search finished with {len(results)} results.")
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
            
        self.integrate_search_results_to_explorer(results)

    def integrate_search_results_to_explorer(self, results):
        """
        Dynamically enriches the Retro Archive Explorer with games discovered via search.
        Spawns missing console category folders on-the-fly and updates local SQLite caches.
        """
        if not results:
            return
            
        # We want to deduplicate by console_name to refresh nodes efficiently
        consoles_to_refresh = set()
        
        # Mapping system names to VGMRips standard formatting
        maker_map = {
            "sega": "Sega",
            "nintendo": "Nintendo",
            "nec": "NEC",
            "sharp": "Sharp",
            "ibm": "IBM",
            "snk": "SNK",
            "capcom": "Capcom",
            "atari": "Atari",
            "commodore": "Commodore",
            "sinclair": "Sinclair",
            "apple": "Apple",
            "microsoft": "Microsoft",
            "sony": "Sony",
            "bandai": "Bandai",
            "konami": "Konami",
            "namco": "Namco",
            "taito": "Taito",
            "toaplan": "Toaplan",
            "hudson": "Hudson",
            "fujitsu": "Fujitsu",
            "seibu": "Seibu",
            "cave": "Cave"
        }
        
        for r in results:
            raw_console = r.get("console_name")
            if not raw_console:
                continue
                
            # Normalize raw console name to "Maker Console" if needed (standardize with list_consoles format)
            console_name = raw_console
            for maker_slug, maker_name in maker_map.items():
                if maker_name.lower() in raw_console.lower():
                    # Already formatted
                    break
            else:
                # If console starts with a known maker slug in its URL, normalize it
                console_url = r.get("console_url", "")
                if "/packs/system/" in console_url:
                    import re
                    match = re.search(r'/packs/system/([^/]+)/', console_url)
                    if match:
                        maker_slug = match.group(1).lower()
                        if maker_slug in maker_map:
                            console_name = f"{maker_map[maker_slug]} {raw_console}"
            
            title = r.get("title")
            url = r.get("url")
            download_url = r.get("download_url", r.get("url")) # Fallback
            source = r.get("source", "VGMRips")
            
            # 1. Update SQLite database cache permanently!
            if hasattr(self, "track_service") and self.track_service.db_manager:
                self.track_service.db_manager.add_single_cached_pack(
                    console_name=console_name,
                    title=title,
                    url=url,
                    download_url=download_url,
                    source=source
                )
                
            # 2. Check if this console is already represented in our QTreeWidget
            root = self.library_tree.invisibleRootItem()
            console_node = None
            for i in range(root.childCount()):
                child = root.child(i)
                if child.data(2, Qt.UserRole) == console_name or child.text(0) == console_name.upper():
                    console_node = child
                    break
                    
            # 3. If console is missing in Explorer list, dynamically create its category folder!
            if not console_node:
                console_node = QTreeWidgetItem(self.library_tree)
                console_node.setText(0, console_name.upper())
                console_node.setFont(0, QFont("Courier New", 12, QFont.Bold))
                console_node.setForeground(0, QColor("#00d4ff")) # Neon Cyan
                
                # Save metadata
                console_node.setData(0, Qt.UserRole, "console")
                console_node.setData(1, Qt.UserRole, r.get("console_url", ""))
                console_node.setData(2, Qt.UserRole, console_name)
                
                # Add dummy child so it shows expand arrow
                dummy = QTreeWidgetItem(console_node)
                dummy.setText(0, "Loading Packs...")
                dummy.setData(0, Qt.UserRole, "dummy")
                
                self.debug_service.log_info(f"MainController: Dynamically spawned new console folder: {console_name}")
                
            consoles_to_refresh.add((console_node, console_name))
            
        # 4. For each affected console, if it's already expanded, refresh it dynamically
        # to immediately show the new games without collapsing/expanding!
        for node, c_name in consoles_to_refresh:
            if node.isExpanded():
                node.takeChildren() # Clear existing
                cached_packs = self.track_service.db_manager.get_cached_packs(c_name)
                self.on_packs_loaded(node, c_name, cached_packs, cache_to_db=False)

    def on_search_error(self, err_msg):
        self.btn_search.setEnabled(True)
        self.txt_search.setEnabled(True)
        self.append_scraper_log(f"Search error: {err_msg}")
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
        self.append_scraper_log(f"Preparing download for pack '{pack_title}' from source '{source}'.", url)
        
        # Align scraped console name with actual library tree system names
        scraped_console = res.get("console_name") or "Various"
        console = scraped_console
        
        # 1. First, try dynamic item matching from the existing tree category names
        matched_tree_console = None
        for idx in range(self.library_tree.topLevelItemCount()):
            item_text = self.library_tree.topLevelItem(idx).data(2, Qt.UserRole) or ""
            item_text_clean = re.sub('<[^<]+?>', '', item_text).strip()
            if item_text_clean and scraped_console:
                it_lower = item_text_clean.lower()
                sc_lower = scraped_console.lower()
                if sc_lower in it_lower or it_lower in sc_lower:
                    matched_tree_console = item_text_clean
                    break
                    
        if matched_tree_console:
            console = matched_tree_console
        else:
            # 2. Fall back to standard robust console name normalization mappings
            c_upper = scraped_console.upper()
            if "MODARCHIVE" in c_upper or "MODARCHIVE" in source.upper():
                console = "MODARCHIVE: CHIPTUNE"
            elif "GENESIS" in c_upper or "MEGA DRIVE" in c_upper or "MEGA-DRIVE" in c_upper or "SEGA GENESIS" in c_upper:
                console = "Sega Mega Drive"
            elif "SUPER NINTENDO" in c_upper or "SNES" in c_upper or "SUPER FAMICOM" in c_upper or "SUPER NES" in c_upper:
                console = "Nintendo Super NES"
            elif "NES" in c_upper or "NINTENDO ENTERTAINMENT" in c_upper or "FAMICOM" in c_upper:
                if "SUPER" not in c_upper:
                    console = "Nintendo NES"
            elif "NINTENDO 64" in c_upper or "N64" in c_upper:
                console = "Nintendo 64 (ZOPHAR)"
            elif "SATURN" in c_upper:
                console = "Sega Saturn (ZOPHAR)"
            elif "DREAMCAST" in c_upper:
                console = "Sega Dreamcast (ZOPHAR)"
            elif "PLAYSTATION" in c_upper or "PSF" in c_upper or "PS1" in c_upper or "PSX" in c_upper:
                if "2" not in c_upper:
                    console = "Sony PlayStation (ZOPHAR)"
                else:
                    console = "Sony PlayStation 2"
            elif "GAME BOY ADVANCE" in c_upper or "GBA" in c_upper:
                console = "Nintendo Game Boy Advance"
            elif "GAME BOY" in c_upper or "GB" in c_upper or "GBC" in c_upper:
                if "ADVANCE" not in c_upper:
                    console = "Nintendo Game Boy"
            
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
        self.append_scraper_log(f"Download {job_id}: {text}")
        self.status_bar.showMessage(f"Download {job_id} Status: {text}", 2000)

    def on_download_zip_ready(self, zip_path, console, game, source_url):
        self.append_scraper_log(f"Download finished for '{game}'. Indexing archive now.", source_url)
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
        self.append_scraper_log(f"Download {job_id} failed: {err_msg}")
        self.dl_progress.setVisible(False)
        self.lbl_dl_status.setText("DOWNLOAD FAILED")
        self.lbl_dl_status.setStyleSheet("color: #e94560; border: none;") # Red failed
        self.btn_download_pack.setEnabled(True)
        QMessageBox.warning(self, "DOWNLOAD ERROR", f"Background download failed:\n{err_msg}")

    # --- Artwork & Metadata Dynamic Loaders ---
    def update_track_metadata_display(self, track):
        if not isinstance(track, dict):
            self.debug_service.log_warning(f"Ignoring metadata update for invalid track payload: {track!r}")
            return

        self._current_track = track
        title = track.get('title', 'Unknown Track')
        artist = track.get('artist', 'Various')
        console = track.get('console', 'Unknown Console')
        game = track.get('game', 'Unknown Game')
        
        self.lbl_now_playing_title.setText(title.upper())
        desc_text = f"System: {console.upper()} | Game: {game}\nComposer: {artist}"
        self.lbl_now_playing_desc.setText(desc_text)
        if hasattr(self, "description_bar") and self.description_bar:
            self.description_bar.update_description(desc_text)
        if hasattr(self, "lbl_playback_tracker"):
            self.lbl_playback_tracker.setText(f"⚡ {title.upper()} - TRANSMITTING")
        
        # Clear any legacy image threads safely by disconnecting their slots.
        for t in self._image_threads:
            try:
                t.disconnect()
            except Exception:
                pass
        self._image_threads.clear()
        self.update_center_artwork()
        
        # Update the live playback queue list!
        self.update_queue_list_display()

    def on_image_loaded(self, img_type, pixmap):
        # Legacy artwork loading is intentionally disabled: the integrated CRT
        # visualizer now owns the right-side media slot.
        return

    def update_queue_list_display(self):
        if not hasattr(self, "queue_list"):
            return
        self.queue_list.clear()
        
        # Read the current order from the queue manager
        queue_ids = self.queue_manager.current_queue
        current_active_id = self.queue_manager.get_current_track_id()
        
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtGui import QColor, QFont
        from PySide6.QtCore import Qt
        
        for index, tid in enumerate(queue_ids):
            track_details = self.track_service.get_track_by_id(tid)
            title = track_details.get("title", f"Track #{tid}") if track_details else f"Track #{tid}"
            game = track_details.get("game", "") if track_details else ""
            
            display_text = f"{index+1:02d}. {title.upper()}"
            if game:
                display_text += f" ({game.upper()})"
                
            item = QListWidgetItem(display_text)
            # Store the track ID in the item's custom user role data for quick lookup
            item.setData(Qt.UserRole, tid)
            
            # If this is the currently playing track, style it beautifully in neon green!
            if tid == current_active_id:
                item.setForeground(QColor("#39ff14")) # lime green
                item.setFont(QFont("Press Start 2P", 7, QFont.Bold))
                item.setText(f"▶ {display_text}")
            else:
                item.setForeground(QColor("#00d4ff")) # retro cyan
                item.setFont(QFont("Courier New", 9))
                
            self.queue_list.addItem(item)

    def on_queue_item_double_clicked(self, item):
        from PySide6.QtCore import Qt
        tid = item.data(Qt.UserRole)
        if tid is not None:
            self.queue_manager.start_playback(tid)
            self.update_queue_list_display()

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

    def item_has_pending_dummy_child(self, item):
        return (
            item is not None
            and item.childCount() == 1
            and item.child(0).data(0, Qt.UserRole) == "dummy"
        )

    def ensure_explorer_children_loaded(self, item):
        """
        Triggers lazy population before folder playback scans children.
        Local folders load synchronously; online folders may start a background scrape.
        """
        if item is None:
            return False

        triggered_load = False
        node_type = item.data(0, Qt.UserRole)
        if node_type in ("console", "game", "game_local") and self.item_has_pending_dummy_child(item):
            self.on_tree_item_expanded(item)
            item.setExpanded(True)
            triggered_load = True

        for i in range(item.childCount()):
            child = item.child(i)
            child_type = child.data(0, Qt.UserRole)
            if child_type in ("game", "game_local") and self.item_has_pending_dummy_child(child):
                self.on_tree_item_expanded(child)
                child.setExpanded(True)
                triggered_load = True
        return triggered_load

    def toggle_play_pause(self):
        self.debug_service.log_interaction("Play/Pause button clicked")
        selected = self.library_tree.currentItem()
        
        # If an item is selected in the library tree, prioritize playing/pausing it or loading it!
        if selected:
            node_type = selected.data(0, Qt.UserRole)
            
            # If it's a folder or game node
            if node_type in ("game", "game_local", "console", "console_local"):
                self.disable_randomizer_if_active()
                triggered_load = self.ensure_explorer_children_loaded(selected)
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
                    if triggered_load:
                        self.status_bar.showMessage("Loading folder contents. Try play again when entries appear.", 4000)
                    else:
                        self.status_bar.showMessage("Folder has no playable indexed tracks yet.", 4000)
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
        self.update_queue_list_display()

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
            self.btn_randomizer.setText("RADAR: OFF")
            self.btn_randomizer.setStyleSheet("color: #ff00ff; border-color: #ff00ff;") # Magenta inactive
            self.audio_engine.stop()
            if self.randomizer_thread:
                try:
                    self.randomizer_thread.disconnect()
                except Exception:
                    pass
            self.status_bar.showMessage("Randomizer deactivated by manual play. Playback stopped.", 4000)

    def toggle_randomizer(self):
        self.is_randomizer_active = not self.is_randomizer_active
        if self.is_randomizer_active:
            self.btn_randomizer.setText("RADAR: ON")
            self.btn_randomizer.setStyleSheet("color: #39ff14; border-color: #39ff14;") # Lime active
            self.status_bar.showMessage("👾 Randomizer mode active! Spinning the retro radar...", 4000)
            self.play_next_random_track()
        else:
            self.btn_randomizer.setText("RADAR: OFF")
            self.btn_randomizer.setStyleSheet("color: #ff00ff; border-color: #ff00ff;") # Magenta inactive
            self.audio_engine.stop()  # Stop playback completely when turning randomizer off
            if self.randomizer_thread:
                try:
                    self.randomizer_thread.disconnect()
                except Exception:
                    pass
            self.status_bar.showMessage("Randomizer mode deactivated. Playback stopped.", 4000)

    def play_next_random_track(self):
        # Stop any running randomizer threads to avoid collisions
        if self.randomizer_thread:
            try:
                self.randomizer_thread.disconnect()
            except Exception:
                pass
            
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
            self.btn_play.setText("PAUSE")
            if hasattr(self, "btn_prominent_play"):
                self.btn_prominent_play.setText("PAUSE")
            # Update now playing display if we played from hotkeys/next
            current_id = self.queue_manager.get_current_track_id()
            if current_id:
                track = self.track_service.get_track_by_id(current_id)
                if track and self._current_track != track:
                    self.update_track_metadata_display(track)
        else:
            self.btn_play.setText("PLAY")
            if hasattr(self, "btn_prominent_play"):
                self.btn_prominent_play.setText("PLAY NOW ⚡")

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
                triggered_load = self.ensure_explorer_children_loaded(selected)
                tracks = self.get_all_tracks_under_item(selected)
                if not tracks:
                    if triggered_load:
                        self.status_bar.showMessage("Loading folder contents. Try play again when entries appear.", 4000)
                    else:
                        self.status_bar.showMessage("No playable indexed tracks found in folder.", 4000)
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
                    # If they are online tracks, trigger streaming for the first track.
                    if tracks:
                        self.on_library_item_double_clicked(tracks[0], 0)
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
