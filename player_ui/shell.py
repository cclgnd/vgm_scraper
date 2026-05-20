from __future__ import annotations

import math
import random
import sys
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QLinearGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from player_ui.api_client import PlayerApiClient, PlayerApiError


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"


class Palette:
    cyan = QColor("#00d4ff")
    magenta = QColor("#ff00df")
    green = QColor("#39ff14")
    yellow = QColor("#ffe45e")
    red = QColor("#ff4268")
    text = QColor("#f5f7ff")
    muted = QColor("#aab2d4")
    panel = QColor(7, 12, 26, 92)
    panel_dark = QColor(2, 4, 13, 118)


def load_fonts() -> tuple[str, str]:
    font_path = ASSETS / "PressStart2P-Regular.ttf"
    pixel_font = "Consolas"
    if font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            pixel_font = families[0]
            
    ui_font = "Segoe UI"
    return ui_font, pixel_font


def choose_logo_font() -> str:
    preferred = (
        "Playstation",
        "PlayStation",
        "PlayStation 2",
        "PS2P",
        "Arial Black",
        "Segoe UI Black",
        "Segoe UI",
    )
    families = {family.lower(): family for family in QFontDatabase.families()}
    for name in preferred:
        found = families.get(name.lower())
        if found:
            return found
    return "Arial"


def make_blurred_pixmap(source: QPixmap, size, radius: int = 22) -> QPixmap:
    from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene

    scaled = source.scaled(size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = max(0, (scaled.width() - size.width()) // 2)
    y = max(0, (scaled.height() - size.height()) // 2)
    scaled = scaled.copy(x, y, size.width(), size.height())

    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(scaled)
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(radius)
    item.setGraphicsEffect(effect)
    scene.addItem(item)

    result = QPixmap(size)
    result.fill(Qt.transparent)
    painter = QPainter(result)
    scene.render(painter, QRectF(result.rect()), QRectF(scaled.rect()))
    painter.end()
    return result


class BackgroundWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._bg_source = QPixmap(str(ASSETS / "cyberpunk_bg.jpg"))
        self._bg_blurred = QPixmap()
        self._last_bg_size = None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self._bg_source.isNull():
            if self._last_bg_size != self.size():
                self._bg_blurred = make_blurred_pixmap(self._bg_source, self.size(), 30)
                self._last_bg_size = self.size()
            painter.drawPixmap(self.rect(), self._bg_blurred)
        
        painter.fillRect(self.rect(), QColor(2, 3, 12, 96))
        super().paintEvent(event)


class GlassPanel(QFrame):
    def __init__(self, accent: QColor = Palette.cyan, parent=None):
        super().__init__(parent)
        self.accent = accent
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setObjectName("glassPanel")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        
        painter.setBrush(Palette.panel)
        painter.setPen(QPen(QColor(255, 255, 255, 15), 1.0))
        painter.drawRoundedRect(r, 8, 8)
        
        painter.setPen(QPen(QColor(255, 255, 255, 35), 1.0))
        painter.drawPath(self._top_edge_path(r, 8))
        
        painter.setPen(QPen(QColor(self.accent.red(), self.accent.green(), self.accent.blue(), 200), 2.0))
        painter.drawLine(r.topLeft() + QPointF(12, 0), r.topRight() - QPointF(12, 0))

    def _top_edge_path(self, r: QRectF, radius: float) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(r.left(), r.top() + radius)
        path.arcTo(r.left(), r.top(), radius * 2, radius * 2, 180, -90)
        path.lineTo(r.right() - radius, r.top())
        path.arcTo(r.right() - radius * 2, r.top(), radius * 2, radius * 2, 90, -90)
        return path


class IconButton(QPushButton):
    def __init__(self, icon_name: str, tooltip: str, accent: QColor = Palette.cyan, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.accent = accent
        self.setToolTip(tooltip)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        self.setMinimumWidth(48)
        self.setText("")
        self.setFocusPolicy(Qt.NoFocus)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        hovered = self.underMouse()
        pressed = self.isDown()
        bg_alpha = 210 if pressed else (185 if hovered else 145)
        painter.setBrush(QColor(5, 9, 24, min(bg_alpha, 118)))
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1.0))
        painter.drawRoundedRect(r, 8, 8)
        if hovered:
            painter.setPen(QPen(self.accent, 1.0))
            painter.drawRoundedRect(r, 8, 8)
        self._draw_icon(painter, r.center(), hovered)

    def _draw_icon(self, painter: QPainter, center, hovered: bool):
        color = self.accent if hovered else Palette.text
        pen = QPen(color, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        cx, cy = center.x(), center.y()
        name = self.icon_name
        if name == "play":
            path = QPainterPath()
            path.moveTo(cx - 5, cy - 8)
            path.lineTo(cx + 7, cy)
            path.lineTo(cx - 5, cy + 8)
            path.closeSubpath()
            painter.setBrush(color)
            painter.drawPath(path)
        elif name == "pause":
            painter.fillRect(QRectF(cx - 7, cy - 8, 4, 16), color)
            painter.fillRect(QRectF(cx + 3, cy - 8, 4, 16), color)
        elif name == "stop":
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(cx - 7, cy - 7, 14, 14), 2, 2)
        elif name == "prev":
            painter.drawLine(QPointF(cx - 10, cy - 9), QPointF(cx - 10, cy + 9))
            self._triangle(painter, cx + 2, cy, -1, color)
            self._triangle(painter, cx + 11, cy, -1, color)
        elif name == "next":
            painter.drawLine(QPointF(cx + 10, cy - 9), QPointF(cx + 10, cy + 9))
            self._triangle(painter, cx - 2, cy, 1, color)
            self._triangle(painter, cx - 11, cy, 1, color)
        elif name == "min":
            painter.drawLine(QPointF(cx - 10, cy + 6), QPointF(cx + 10, cy + 6))
        elif name == "max":
            painter.drawRoundedRect(QRectF(cx - 9, cy - 9, 18, 18), 2, 2)
        elif name == "close":
            painter.drawLine(QPointF(cx - 8, cy - 8), QPointF(cx + 8, cy + 8))
            painter.drawLine(QPointF(cx + 8, cy - 8), QPointF(cx - 8, cy + 8))
        elif name == "gear":
            painter.drawEllipse(QPointF(cx, cy), 8, 8)
            painter.drawEllipse(QPointF(cx, cy), 2.8, 2.8)
            for i in range(8):
                a = i * math.pi / 4
                painter.drawLine(
                    QPointF(cx + math.cos(a) * 10, cy + math.sin(a) * 10),
                    QPointF(cx + math.cos(a) * 13, cy + math.sin(a) * 13),
                )
        elif name == "folder":
            painter.drawRoundedRect(QRectF(cx - 13, cy - 4, 26, 16), 3, 3)
            painter.drawLine(QPointF(cx - 12, cy - 4), QPointF(cx - 5, cy - 10))
            painter.drawLine(QPointF(cx - 5, cy - 10), QPointF(cx + 2, cy - 10))
        elif name == "retry":
            painter.drawArc(QRectF(cx - 11, cy - 11, 22, 22), 40 * 16, 275 * 16)
            self._triangle(painter, cx + 9, cy - 8, 1, color)
        elif name == "heart":
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            path = QPainterPath()
            path.moveTo(cx, cy + 5)
            path.cubicTo(cx - 10, cy - 5, cx - 5, cy - 10, cx, cy - 3)
            path.cubicTo(cx + 5, cy - 10, cx + 10, cy - 5, cx, cy + 5)
            painter.drawPath(path)

    def _triangle(self, painter, cx, cy, direction, color):
        path = QPainterPath()
        if direction > 0:
            path.moveTo(cx - 6, cy - 8)
            path.lineTo(cx + 5, cy)
            path.lineTo(cx - 6, cy + 8)
        else:
            path.moveTo(cx + 6, cy - 8)
            path.lineTo(cx - 5, cy)
            path.lineTo(cx + 6, cy + 8)
        path.closeSubpath()
        painter.setBrush(color)
        painter.drawPath(path)
        painter.setBrush(Qt.NoBrush)

class NeonCommandButton(QPushButton):
    def __init__(self, text: str, icon_name: str, accent: QColor = Palette.cyan, parent=None):
        super().__init__(text, parent)
        self.icon_name = icon_name
        self.accent = accent
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(44)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip(text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        hovered = self.underMouse()
        painter.setBrush(QColor(5, 9, 24, 118 if hovered else 82))
        painter.setPen(QPen(self.accent if hovered else QColor(255, 255, 255, 30), 1.5))
        painter.drawRoundedRect(r, 8, 8)
        icon_rect = QRectF(r.left() + 14, r.center().y() - 10, 20, 20)
        IconButton(self.icon_name, "", self.accent)._draw_icon(painter, icon_rect.center(), hovered)
        painter.setPen(Palette.text)
        painter.drawText(r.adjusted(44, 0, -8, 0), Qt.AlignVCenter | Qt.AlignLeft, self.text())


class LufsMeter(QWidget):
    """LUFS-style loudness meter."""
    def __init__(self, pixel_font: str, parent=None):
        super().__init__(parent)
        self.pixel_font = pixel_font
        self.short_lufs = -42.0
        self.integrated_lufs = -24.0
        self.peak_db = -12.0
        self.setMinimumHeight(38)

    def set_levels(self, short_lufs: float, integrated_lufs: float, peak_db: float):
        self.short_lufs = float(short_lufs)
        self.integrated_lufs = float(integrated_lufs)
        self.peak_db = float(peak_db)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 4, -2, -4)
        
        painter.setPen(QPen(QColor(255, 255, 255, 20), 1))
        painter.setBrush(QColor(2, 4, 13, 96))
        painter.drawRoundedRect(r, 6, 6)
        label_w = 98
        meter = r.adjusted(label_w, 9, -72, -9)
        
        painter.setFont(QFont(self.pixel_font, 6))
        painter.setPen(Palette.muted)
        painter.drawText(QRectF(r.left() + 10, r.top(), label_w - 16, r.height()), Qt.AlignVCenter, "LUFS")

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 212, 255, 38))
        painter.drawRoundedRect(meter, 3, 3)
        width = max(0.0, min(1.0, (self.short_lufs + 60.0) / 60.0)) * meter.width()
        hot = QColor(Palette.green)
        if self.short_lufs > -14:
            hot = Palette.yellow
        if self.short_lufs > -8:
            hot = Palette.red
        painter.setBrush(hot)
        painter.drawRoundedRect(QRectF(meter.left(), meter.top(), width, meter.height()), 3, 3)
        target_x = meter.left() + ((-16 + 60) / 60) * meter.width()
        painter.setPen(QPen(Palette.magenta, 1.4))
        painter.drawLine(QPointF(target_x, meter.top() - 4), QPointF(target_x, meter.bottom() + 4))
        painter.setPen(Palette.cyan)
        painter.drawText(QRectF(r.right() - 66, r.top(), 64, r.height()), Qt.AlignVCenter | Qt.AlignRight, f"{self.short_lufs:0.1f}")


class PlayerShell(BackgroundWindow):
    def __init__(self):
        super().__init__()
        self.ui_font, self.pixel_font = load_fonts()
        self.logo_font = choose_logo_font()
        self.api = PlayerApiClient()
        self.selected_game_id = None
        self.selected_game_title = ""
        self._drag_pos = None
        self._was_dragging = False
        self.setWindowTitle("Chiptune Palace")
        self.resize(1240, 850)
        self.setMinimumSize(720, 520)
        if (ASSETS / "icon.png").exists():
            self.setWindowIcon(QIcon(str(ASSETS / "icon.png")))
        self._build()
        self._start_meter_demo()
        QTimer.singleShot(0, self._load_catalog_tree)
        self._start_backend_stats_poll()

    def _font(self, size: int, bold=False) -> QFont:
        f = QFont(self.ui_font, size)
        if bold:
            f.setBold(True)
        return f

    def _pixel_font(self, size: int) -> QFont:
        f = QFont(self.pixel_font, size)
        f.setLetterSpacing(QFont.PercentageSpacing, 100)
        return f

    def _build(self):
        root = QWidget(self)
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)

        header = self._build_header()
        outer.addWidget(header)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        left = self._build_left_column()
        right = self._build_right_column()
        content_layout.addWidget(left, 1)
        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setStyleSheet(f"background: rgba(255, 255, 255, 20);")
        content_layout.addWidget(divider)
        content_layout.addWidget(right, 1)
        outer.addWidget(content, 1)

        self.setStyleSheet(f"""
            QWidget {{
                color: {Palette.text.name()};
                font-family: "{self.ui_font}";
                font-size: 13px;
                background: transparent;
            }}
            QLineEdit {{
                color: {Palette.text.name()};
                background: rgba(6, 8, 20, 82);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 6px;
                padding: 8px 12px;
                selection-background-color: {Palette.magenta.name()};
            }}
            QLineEdit:focus {{
                border: 1px solid {Palette.cyan.name()};
            }}
            QTreeWidget, QListWidget {{
                background: transparent;
                border: 0;
                color: {Palette.text.name()};
                outline: 0;
            }}
            QTreeWidget::item, QListWidget::item {{
                min-height: 32px;
                padding: 4px;
                border-radius: 4px;
            }}
            QTreeWidget::item:hover, QListWidget::item:hover {{
                background: rgba(255, 255, 255, 10);
            }}
            QTreeWidget::item:selected, QListWidget::item:selected {{
                background: rgba(0, 212, 255, 42);
                color: {Palette.cyan.name()};
            }}
            QSplitter::handle {{
                background: transparent;
            }}
            QScrollBar:vertical {{
                border: none;
                background: rgba(0,0,0,0);
                width: 6px;
                margin: 0px 0px 0px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,30);
                min-height: 20px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(255,255,255,60);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
            }}
        """)

    def _build_header(self) -> QWidget:
        panel = GlassPanel(Palette.magenta)
        panel.setFixedHeight(66)
        
        # 3-section layout to keep logo perfectly centered
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(0)

        # Left Section (Search)
        left_container = QWidget()
        left_layout = QHBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        search = QLineEdit()
        search.setPlaceholderText("Search consoles, games, files...")
        left_layout.addWidget(search, 1)
        layout.addWidget(left_container, 1)

        # Center Section (Logo)
        center_container = QWidget()
        center_layout = QHBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(10)
        center_layout.setAlignment(Qt.AlignCenter)
        
        class AnimatedLogo(QWidget):
            def __init__(self, logo_font_name):
                super().__init__()
                self.logo_font_name = logo_font_name
                self.setFixedSize(500, 60)
                self.phase = 0.0
                self.frame_count = 0
                
                # 8-bit star particles
                self.stars = []
                for _ in range(35):
                    self.stars.append({
                        'x': random.uniform(0, 500),
                        'y': random.uniform(0, 60),
                        'speed': random.uniform(0.2, 0.8),
                        'size': random.choice([2, 3, 4]),
                        'type': random.choice(['4pt', '5pt', 'sparkle']),
                        'twinkle_offset': random.uniform(0, math.pi * 2)
                    })
                
                # SMW floating star
                self.smw_star = None
                self.smw_trail = []
                self.smw_spawn_counter = 0
                self.SMW_SPAWN_INTERVAL = 1800  # ~60 seconds at 30fps
                
                # Quiet equalizer strip behind the title.
                self.eq_bars = []
                for i in range(44):
                    self.eq_bars.append({
                        'height': random.uniform(4, 18),
                        'target': random.uniform(4, 20),
                        'speed': random.uniform(0.035, 0.11)
                    })
                
                self.timer = QTimer(self)
                self.timer.timeout.connect(self.animate)
                self.timer.start(33)

            def animate(self):
                self.phase += 0.04
                self.frame_count += 1
                
                # Update EQ bars
                for bar in self.eq_bars:
                    bar['height'] += (bar['target'] - bar['height']) * bar['speed']
                    if abs(bar['height'] - bar['target']) < 0.5:
                        bar['target'] = random.uniform(4, 22)
                
                # SMW star logic
                self.smw_spawn_counter += 1
                if self.smw_spawn_counter >= self.SMW_SPAWN_INTERVAL and self.smw_star is None:
                    self.smw_star = {'x': -20, 'y': random.uniform(10, 50), 'size': 8}
                    self.smw_trail = []
                    self.smw_spawn_counter = 0
                
                if self.smw_star:
                    self.smw_star['x'] += 1.5
                    if self.frame_count % 3 == 0:
                        self.smw_trail.append({
                            'x': self.smw_star['x'],
                            'y': self.smw_star['y'],
                            'life': 1.0
                        })
                    for t in self.smw_trail:
                        t['life'] -= 0.02
                    self.smw_trail = [t for t in self.smw_trail if t['life'] > 0]
                    
                    if self.smw_star['x'] > 500:
                        self.smw_star = None
                        self.smw_trail = []

                self.update()

            def _draw_8bit_star(self, painter, x, y, size, star_type, alpha=255):
                color = QColor(255, 255, 200, alpha)
                painter.setBrush(color)
                painter.setPen(Qt.NoPen)
                
                if star_type == '4pt':
                    s = size
                    points = [
                        QPointF(x, y - s),
                        QPointF(x + s*0.3, y - s*0.3),
                        QPointF(x + s, y),
                        QPointF(x + s*0.3, y + s*0.3),
                        QPointF(x, y + s),
                        QPointF(x - s*0.3, y + s*0.3),
                        QPointF(x - s, y),
                        QPointF(x - s*0.3, y - s*0.3)
                    ]
                    painter.drawPolygon(points)
                elif star_type == '5pt':
                    s = size
                    points = []
                    for i in range(5):
                        angle = math.radians(i * 72 - 90)
                        points.append(QPointF(x + math.cos(angle) * s, y + math.sin(angle) * s))
                        angle = math.radians(i * 72 - 90 + 36)
                        points.append(QPointF(x + math.cos(angle) * s * 0.4, y + math.sin(angle) * s * 0.4))
                    painter.drawPolygon(points)
                else:
                    painter.fillRect(QRectF(x - size//2, y - 1, size, 2), color)
                    painter.fillRect(QRectF(x - 1, y - size//2, 2, size), color)

            def _draw_smw_star(self, painter, x, y, size):
                yellow = QColor(255, 220, 50)
                painter.setBrush(yellow)
                painter.setPen(QColor(200, 170, 30))
                
                points = []
                for i in range(5):
                    angle = math.radians(i * 72 - 90)
                    points.append(QPointF(x + math.cos(angle) * size, y + math.sin(angle) * size))
                    angle = math.radians(i * 72 - 90 + 36)
                    points.append(QPointF(x + math.cos(angle) * size * 0.45, y + math.sin(angle) * size * 0.45))
                painter.drawPolygon(points)
                
                painter.setBrush(QColor(0, 0, 0))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPointF(x - 2, y - 1), 1.5, 1.5)
                painter.drawEllipse(QPointF(x + 2, y - 1), 1.5, 1.5)

            def _draw_equalizer_strip(self, painter, w, h):
                bar_width = 5
                bar_spacing = 5
                total_width = len(self.eq_bars) * bar_width + (len(self.eq_bars) - 1) * bar_spacing
                start_x = (w - total_width) / 2
                base_y = h - 6

                glow = QLinearGradient(0, 0, w, 0)
                glow.setColorAt(0.0, QColor(0, 0, 0, 0))
                glow.setColorAt(0.5, QColor(57, 255, 20, 16))
                glow.setColorAt(1.0, QColor(0, 0, 0, 0))
                painter.fillRect(QRectF(0, base_y - 30, w, 30), glow)

                for i, bar in enumerate(self.eq_bars):
                    x = start_x + i * (bar_width + bar_spacing)
                    bar_h = bar['height']
                    zone = i / max(1, len(self.eq_bars) - 1)
                    if zone < 0.54:
                        color = QColor(57, 255, 20, 52)
                    elif zone < 0.78:
                        color = QColor(255, 228, 94, 56)
                    else:
                        color = QColor(255, 66, 104, 60)

                    painter.setBrush(color)
                    painter.setPen(Qt.NoPen)
                    painter.drawRoundedRect(QRectF(x, base_y - bar_h, bar_width, bar_h), 1.5, 1.5)

            def paintEvent(self, e):
                p = QPainter(self)
                p.setRenderHint(QPainter.Antialiasing)
                w, h = self.width(), self.height()
                
                # 1. Background glow
                bg_grad = QLinearGradient(0, h/2, w, h/2)
                bg_grad.setColorAt(0, QColor(0, 0, 0, 0))
                bg_grad.setColorAt(0.5, QColor(0, 212, 255, 15))
                bg_grad.setColorAt(1, QColor(0, 0, 0, 0))
                p.fillRect(self.rect(), bg_grad)
                
                # 2. 8-bit Star Particles
                for star in self.stars:
                    star['x'] += star['speed']
                    if star['x'] > w + 10:
                        star['x'] = -10
                        star['y'] = random.uniform(0, h)
                    
                    twinkle = int(120 + math.sin(self.phase * 2 + star['twinkle_offset']) * 80)
                    self._draw_8bit_star(p, star['x'], star['y'], star['size'], star['type'], twinkle)
                
                # 3. SMW Star & Trail
                if self.smw_star:
                    for t in self.smw_trail:
                        alpha = int(t['life'] * 180)
                        p.setBrush(QColor(255, 220, 100, alpha))
                        p.setPen(Qt.NoPen)
                        p.drawEllipse(QPointF(t['x'], t['y']), t['life'] * 3, t['life'] * 3)
                    
                    self._draw_smw_star(p, self.smw_star['x'], self.smw_star['y'], self.smw_star['size'])
                
                # 4. Quiet equalizer strip
                self._draw_equalizer_strip(p, w, h)
                
                # 5. Text
                font = QFont(self.logo_font_name, 24, QFont.Black)
                font.setLetterSpacing(QFont.PercentageSpacing, 100)
                font.setItalic(False)
                
                text_path = QPainterPath()
                text_path.addText(0, 0, font, "CHIPTUNE PALACE")
                br = text_path.boundingRect()
                
                p.translate(w/2 - br.width()/2, h/2 + br.height()/3)
                
                p.translate(2, 2)
                p.setBrush(QColor(0, 0, 0, 180))
                p.setPen(Qt.NoPen)
                p.drawPath(text_path)
                p.translate(-2, -2)
                
                text_grad = QLinearGradient(0, -br.height(), 0, 0)
                text_grad.setColorAt(0, QColor(255, 255, 255))
                text_grad.setColorAt(0.5, QColor(0, 180, 220))
                text_grad.setColorAt(1, QColor(0, 60, 120))
                
                p.setBrush(text_grad)
                p.setPen(QPen(QColor(255, 255, 255, 100), 0.8))
                p.drawPath(text_path)
                
                p.setClipPath(text_path)
                p.setBrush(QColor(0, 0, 0, 40))
                for y in range(int(-br.height()), 10, 3):
                    p.drawRect(0, y, br.width(), 2)
                p.setClipping(False)
                
        logo_icon = AnimatedLogo(self.logo_font)
        center_layout.addWidget(logo_icon)
        
        layout.addWidget(center_container, 1)

        # Right Section (Status & Config)
        right_container = QWidget()
        right_layout = QHBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addStretch(1)
        
        status = QLabel("BACKEND ONLINE")
        status.setFont(self._pixel_font(7))
        status.setStyleSheet(f"color: {Palette.green.name()};")
        right_layout.addWidget(status)

        cfg = IconButton("gear", "Settings", Palette.yellow)
        cfg.setFixedWidth(42)
        right_layout.addWidget(cfg)

        minimize = IconButton("min", "Minimize", Palette.cyan)
        minimize.setFixedWidth(42)
        minimize.clicked.connect(self.showMinimized)
        right_layout.addWidget(minimize)

        maximize = IconButton("max", "Maximize / restore", Palette.cyan)
        maximize.setFixedWidth(42)
        maximize.clicked.connect(self._toggle_maximized)
        right_layout.addWidget(maximize)

        close = IconButton("close", "Close", Palette.red)
        close.setFixedWidth(42)
        close.clicked.connect(self.close)
        right_layout.addWidget(close)

        layout.addWidget(right_container, 1)

        return panel

    def _toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() <= 78:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._was_dragging = False
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton and not self.isMaximized():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            self._was_dragging = True
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_pos is not None and self._was_dragging and not self.isMaximized():
            self._snap_to_half_screen(event.globalPosition().toPoint())
        self._drag_pos = None
        self._was_dragging = False
        super().mouseReleaseEvent(event)

    def _snap_to_half_screen(self, global_pos):
        screen = QApplication.screenAt(global_pos) or self.screen()
        if screen is None:
            return
        area = screen.availableGeometry()
        threshold = 24
        half_width = max(self.minimumWidth(), area.width() // 2)
        if global_pos.x() <= area.left() + threshold:
            self.setGeometry(area.left(), area.top(), half_width, area.height())
        elif global_pos.x() >= area.right() - threshold:
            self.setGeometry(area.right() - half_width + 1, area.top(), half_width, area.height())

    def _build_left_column(self) -> QWidget:
        col = QWidget()
        col.setMinimumWidth(0)
        col.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        browser = GlassPanel(Palette.cyan)
        browser.setMinimumWidth(0)
        browser_layout = QVBoxLayout(browser)
        browser_layout.setContentsMargins(12, 10, 12, 12)
        title = QLabel("FILE BROWSER")
        title.setFont(self._pixel_font(7))
        title.setStyleSheet(f"color: {Palette.cyan.name()}; letter-spacing: 1px;")
        browser_layout.addWidget(title)
        self.browser_tree = QTreeWidget()
        self.browser_tree.setMinimumWidth(0)
        self.browser_tree.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.browser_tree.setHeaderHidden(True)
        self.browser_tree.setIndentation(20)
        self.browser_tree.itemSelectionChanged.connect(self._on_browser_selection_changed)
        self.browser_tree.itemDoubleClicked.connect(self._on_browser_item_opened)
        self._populate_browser_placeholder("Backend not loaded")
        browser_layout.addWidget(self.browser_tree, 1)
        layout.addWidget(browser, 3)

        actions = QWidget()
        actions.setMinimumWidth(0)
        action_layout = QHBoxLayout(actions)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(10)
        play_game = NeonCommandButton("Play Game", "play", Palette.green)
        play_game.setToolTip("Play selected game")
        open_game = NeonCommandButton("Open", "folder", Palette.cyan)
        open_game.setToolTip("Open selected game and verify availability")
        retry_failed = NeonCommandButton("Retry", "retry", Palette.yellow)
        retry_failed.setToolTip("Retry failed selected game or file")
        open_game.clicked.connect(self._open_selected_game)
        retry_failed.clicked.connect(self._retry_selected_game)
        action_layout.addWidget(play_game)
        action_layout.addWidget(open_game)
        action_layout.addWidget(retry_failed)
        layout.addWidget(actions)

        queue = GlassPanel(Palette.magenta)
        queue.setMinimumWidth(0)
        queue_layout = QVBoxLayout(queue)
        queue_layout.setContentsMargins(12, 10, 12, 12)
        qtitle = QLabel("PLAYLIST QUEUE")
        qtitle.setFont(self._pixel_font(7))
        qtitle.setStyleSheet(f"color: {Palette.magenta.name()}; letter-spacing: 1px;")
        queue_layout.addWidget(qtitle)
        self.queue_list = QListWidget()
        self.queue_list.setMinimumWidth(0)
        self.queue_list.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        queue_layout.addWidget(self.queue_list, 1)
        layout.addWidget(queue, 1)
        return col

    def _build_right_column(self) -> QWidget:
        col = QWidget()
        col.setMinimumWidth(0)
        col.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        layout = QVBoxLayout(col)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        info = GlassPanel(Palette.cyan)
        info.setMinimumWidth(0)
        info.setFixedHeight(142)
        grid = QGridLayout(info)
        grid.setContentsMargins(16, 14, 16, 14)
        self.game_title_label = QLabel("NO GAME SELECTED")
        self.game_title_label.setFont(self._font(20, bold=True))
        self.game_title_label.setStyleSheet(f"color: {Palette.yellow.name()};")
        self.game_meta_label = QLabel("Load backend catalog, then open a game to verify file availability.")
        self.game_meta_label.setStyleSheet(f"color: {Palette.muted.name()};")
        self.game_meta_label.setWordWrap(True)
        self.game_meta_label.setMinimumHeight(52)
        self.game_status_label = QLabel("WAITING")
        self.game_status_label.setAlignment(Qt.AlignCenter)
        self.game_status_label.setFont(self._pixel_font(7))
        self.game_status_label.setStyleSheet(f"color: {Palette.cyan.name()}; border: 1px solid rgba(0, 212, 255, 50); background: rgba(0, 212, 255, 18); border-radius: 6px; padding: 10px;")
        self.game_status_label.setFixedWidth(172)
        grid.addWidget(self.game_title_label, 0, 0)
        grid.addWidget(self.game_meta_label, 1, 0)
        grid.addWidget(self.game_status_label, 0, 1, 2, 1)
        layout.addWidget(info)

        art_panel = GlassPanel(Palette.magenta)
        art_panel.setMinimumWidth(0)
        art_layout = QVBoxLayout(art_panel)
        art_layout.setContentsMargins(14, 14, 14, 14)
        art = QLabel()
        pix = QPixmap(str(ASSETS / "cyberpunk_art_2.png"))
        if not pix.isNull():
            art.setPixmap(pix.scaledToHeight(250, Qt.SmoothTransformation))
        art.setAlignment(Qt.AlignCenter)
        art_layout.addWidget(art, 0, Qt.AlignCenter)
        layout.addWidget(art_panel, 1)

        file_info = GlassPanel(Palette.cyan)
        file_info.setMinimumWidth(0)
        file_info.setFixedHeight(122)
        file_layout = QHBoxLayout(file_info)
        file_layout.setContentsMargins(16, 12, 16, 12)
        file_text = QWidget()
        file_text_layout = QVBoxLayout(file_text)
        file_text_layout.setContentsMargins(0, 0, 0, 0)
        file_text_layout.setSpacing(7)
        self.now_title_label = QLabel("No file selected")
        self.now_title_label.setFont(self._font(14, bold=True))
        self.now_title_label.setStyleSheet(f"color: {Palette.text.name()};")
        self.now_meta_label = QLabel("")
        self.now_meta_label.setStyleSheet(f"color: {Palette.muted.name()};")
        self.provenance_label = QLabel("File availability appears after game open.")
        self.provenance_label.setWordWrap(True)
        self.provenance_label.setStyleSheet(f"color: {Palette.muted.name()};")
        file_text_layout.addWidget(self.now_title_label)
        file_text_layout.addWidget(self.now_meta_label)
        file_text_layout.addWidget(self.provenance_label)
        file_layout.addWidget(file_text, 1)
        self.file_status_label = QLabel("")
        self.file_status_label.setAlignment(Qt.AlignCenter)
        self.file_status_label.setFont(self._pixel_font(7))
        self.file_status_label.setStyleSheet(f"color: {Palette.cyan.name()}; border: 1px solid rgba(0, 212, 255, 50); background: rgba(0, 212, 255, 18); border-radius: 6px; padding: 10px;")
        file_layout.addWidget(self.file_status_label)
        layout.addWidget(file_info)

        player = GlassPanel(Palette.cyan)
        player.setMinimumWidth(0)
        player.setFixedHeight(112)
        player_layout = QHBoxLayout(player)
        player_layout.setContentsMargins(14, 12, 14, 12)
        player_layout.setSpacing(10)
        player_layout.addWidget(IconButton("prev", "Previous", Palette.cyan))
        player_layout.addWidget(IconButton("play", "Play / pause", Palette.magenta))
        player_layout.addWidget(IconButton("stop", "Stop", Palette.red))
        player_layout.addWidget(IconButton("next", "Next", Palette.cyan))
        self.meter = LufsMeter(self.pixel_font)
        player_layout.addWidget(self.meter, 1)
        self.job_status_label = QLabel("JOBS --")
        self.job_status_label.setAlignment(Qt.AlignCenter)
        self.job_status_label.setFont(self._pixel_font(6))
        self.job_status_label.setStyleSheet(f"color: {Palette.muted.name()};")
        self.job_status_label.setMinimumWidth(220)
        player_layout.addWidget(self.job_status_label)
        layout.addWidget(player)
        return col

    def _populate_browser_placeholder(self, text: str):
        self.browser_tree.clear()
        item = QTreeWidgetItem([text])
        item.setForeground(0, Palette.muted)
        item.setData(0, Qt.UserRole, {"type": "status"})
        self.browser_tree.addTopLevelItem(item)

    def _load_catalog_tree(self):
        try:
            tree = self.api.tree()
        except PlayerApiError as exc:
            self._populate_browser_placeholder("Backend offline")
            self._set_game_status("OFFLINE", Palette.red)
            self.game_meta_label.setText(str(exc))
            return

        self._populate_catalog_tree(tree)
        self._set_game_status("READY", Palette.green)
        self.game_meta_label.setText("Catalog loaded. Select a game, then open it to verify files.")

    def _populate_catalog_tree(self, consoles: list[dict]):
        self.browser_tree.clear()
        makers: dict[str, list[dict]] = {}
        for console in consoles:
            maker = (console.get("maker") or "Unknown Maker").upper()
            makers.setdefault(maker, []).append(console)

        if not makers:
            self._populate_browser_placeholder("No catalog entries")
            return

        for maker in sorted(makers):
            maker_item = QTreeWidgetItem([maker])
            maker_item.setForeground(0, Palette.magenta)
            maker_item.setData(0, Qt.UserRole, {"type": "maker"})
            self.browser_tree.addTopLevelItem(maker_item)
            maker_item.setExpanded(True)

            for console in sorted(makers[maker], key=lambda row: row.get("display_name") or ""):
                console_item = QTreeWidgetItem([console.get("display_name") or "Unknown Console"])
                console_item.setForeground(0, Palette.cyan)
                console_item.setData(0, Qt.UserRole, {"type": "console", "data": console})
                maker_item.addChild(console_item)
                console_item.setExpanded(True)

                for game in sorted(console.get("games", []), key=lambda row: row.get("title") or ""):
                    game_item = QTreeWidgetItem([game.get("title") or "Unknown Game"])
                    game_item.setForeground(0, Palette.yellow)
                    game_item.setData(0, Qt.UserRole, {"type": "game", "data": game})
                    console_item.addChild(game_item)

    def _on_browser_selection_changed(self):
        item = self.browser_tree.currentItem()
        payload = item.data(0, Qt.UserRole) if item else {}
        payload_type = payload.get("type") if isinstance(payload, dict) else ""
        if payload_type == "game":
            game = payload["data"]
            self.selected_game_id = game.get("id")
            self.selected_game_title = game.get("title") or ""
            self.game_title_label.setText(self.selected_game_title.upper())
            self.game_meta_label.setText("Open game to verify online files.")
            self._set_game_status("ONLINE", Palette.cyan)
        elif payload_type == "track":
            self._show_file_info(payload["data"])

    def _on_browser_item_opened(self, item: QTreeWidgetItem):
        payload = item.data(0, Qt.UserRole) if item else {}
        if isinstance(payload, dict) and payload.get("type") == "game":
            self._open_game_item(item, retry_failed=False)

    def _open_selected_game(self):
        item = self._selected_game_item()
        if item is not None:
            self._open_game_item(item, retry_failed=False)

    def _retry_selected_game(self):
        item = self._selected_game_item()
        if item is not None:
            self._open_game_item(item, retry_failed=True)

    def _selected_game_item(self) -> QTreeWidgetItem | None:
        item = self.browser_tree.currentItem()
        while item is not None:
            payload = item.data(0, Qt.UserRole)
            if isinstance(payload, dict) and payload.get("type") == "game":
                return item
            item = item.parent()
        return None

    def _open_game_item(self, game_item: QTreeWidgetItem, retry_failed: bool):
        payload = game_item.data(0, Qt.UserRole)
        game = payload.get("data", {}) if isinstance(payload, dict) else {}
        game_id = game.get("id")
        if game_id is None:
            return

        self.selected_game_id = game_id
        self.selected_game_title = game.get("title") or ""
        self.game_title_label.setText(self.selected_game_title.upper())
        self._set_game_status("OBTAINING", Palette.cyan)
        self.game_meta_label.setText("Verifying file availability...")

        try:
            result = self.api.retry_game(game_id) if retry_failed else self.api.game_files(game_id)
        except PlayerApiError as exc:
            self._set_game_status("FAILED", Palette.red)
            self.game_meta_label.setText(str(exc))
            return

        self._replace_game_files(game_item, result.get("files", []))
        status = result.get("status", "unknown")
        color = Palette.green if status in {"already_listed", "obtaining_file"} else Palette.red
        self._set_game_status(status.replace("_", " ").upper(), color)
        hidden = result.get("hidden_short_file_count", 0)
        suffix = f" Hidden SFX: {hidden}." if hidden else ""
        self.game_meta_label.setText(f"{len(result.get('files', []))} verified file rows exposed.{suffix}")
        game_item.setExpanded(True)

    def _replace_game_files(self, game_item: QTreeWidgetItem, files: list[dict]):
        while game_item.childCount():
            game_item.removeChild(game_item.child(0))

        self.queue_list.clear()
        for file_row in files:
            text = self._file_row_text(file_row)
            track_item = QTreeWidgetItem([text])
            track_item.setForeground(0, self._status_color(file_row.get("availability_status")))
            track_item.setData(0, Qt.UserRole, {"type": "track", "data": file_row})
            game_item.addChild(track_item)
            self.queue_list.addItem(QListWidgetItem(text))

        if files:
            self._show_file_info(files[0])
        else:
            self.now_title_label.setText("No verified files")
            self.now_meta_label.setText("")
            self.provenance_label.setText("No compatible file rows exposed for this game.")
            self.file_status_label.setText("")

    def _show_file_info(self, file_row: dict):
        self.now_title_label.setText(file_row.get("title") or "Unknown file")
        duration = self._format_duration(file_row.get("duration_seconds"))
        fmt = (file_row.get("format_hint") or "").lstrip(".").upper()
        status = (file_row.get("availability_status") or "").replace("_", " ").title()
        parts = [part for part in (status, fmt, duration) if part]
        self.now_meta_label.setText(" / ".join(parts))
        self.provenance_label.setText("Availability verified by scraper API after game open.")
        self.file_status_label.setText((file_row.get("availability_status") or "").replace("_", " ").upper())
        self.file_status_label.setStyleSheet(self._badge_style(self._status_color(file_row.get("availability_status"))))

    def _file_row_text(self, file_row: dict) -> str:
        number = file_row.get("track_number")
        prefix = f"{number:02d} " if isinstance(number, int) else ""
        duration = self._format_duration(file_row.get("duration_seconds"))
        fmt = (file_row.get("format_hint") or "").lstrip(".").upper()
        status = (file_row.get("availability_status") or "").replace("_", " ").title()
        tail = " ".join(part for part in (duration, fmt, status) if part)
        return f"{prefix}{file_row.get('title') or 'Unknown'} {tail}".strip()

    @staticmethod
    def _format_duration(value) -> str:
        if value is None:
            return ""
        seconds = max(0, int(round(float(value))))
        hours, rem = divmod(seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _status_color(status: str | None) -> QColor:
        if status == "local":
            return Palette.green
        if status == "failed":
            return Palette.red
        if status == "obtaining_file":
            return Palette.cyan
        return Palette.text

    def _set_game_status(self, text: str, color: QColor):
        self.game_status_label.setText(text)
        self.game_status_label.setStyleSheet(self._badge_style(color))

    @staticmethod
    def _badge_style(color: QColor) -> str:
        return (
            f"color: {color.name()}; "
            f"border: 1px solid rgba({color.red()}, {color.green()}, {color.blue()}, 50); "
            f"background: rgba({color.red()}, {color.green()}, {color.blue()}, 18); "
            "border-radius: 6px; padding: 10px;"
        )

    def _start_meter_demo(self):
        self._meter_phase = 0.0
        self._meter_timer = QTimer(self)
        self._meter_timer.timeout.connect(self._tick_meter)
        self._meter_timer.start(70)

    def _start_backend_stats_poll(self):
        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._refresh_backend_stats)
        self._stats_timer.start(4000)
        QTimer.singleShot(250, self._refresh_backend_stats)

    def _refresh_backend_stats(self):
        try:
            stats = self.api.stats()
        except PlayerApiError:
            self.job_status_label.setText("JOBS OFFLINE")
            self.job_status_label.setStyleSheet(f"color: {Palette.red.name()};")
            return

        crawl_active = stats.get("crawl_jobs_running", 0)
        crawl_done = stats.get("crawl_jobs_completed", 0)
        crawl_failed = stats.get("crawl_jobs_failed", 0)
        retrieval_active = stats.get("retrieval_jobs_pending", 0) + stats.get("retrieval_jobs_downloading", 0)
        retrieval_done = stats.get("retrieval_jobs_completed", 0)
        retrieval_failed = stats.get("retrieval_jobs_failed", 0)
        resources = stats.get("resource_nodes", 0)
        games = stats.get("games", 0)

        self.job_status_label.setText(
            f"JOBS C{crawl_active}/{crawl_done}/{crawl_failed} "
            f"R{retrieval_active}/{retrieval_done}/{retrieval_failed} "
            f"G{games} RES{resources}"
        )
        color = Palette.red if crawl_failed or retrieval_failed else Palette.green
        self.job_status_label.setStyleSheet(f"color: {color.name()};")

    def _tick_meter(self):
        self._meter_phase += 0.17
        wave = math.sin(self._meter_phase) * 8 + math.sin(self._meter_phase * 2.7) * 3
        noise = random.uniform(-2.2, 1.2)
        short = max(-60.0, min(-5.0, -22.0 + wave + noise))
        integrated = -21.0
        peak = short + 8
        self.meter.set_levels(short, integrated, peak)


def main():
    app = QApplication(sys.argv)
    window = PlayerShell()
    window.show()
    sys.exit(app.exec())
