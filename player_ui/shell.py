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
    panel = QColor(7, 12, 26, 168)
    panel_dark = QColor(2, 4, 13, 190)


def load_fonts() -> str:
    font_path = ASSETS / "PressStart2P-Regular.ttf"
    if font_path.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            return families[0]
    return "Consolas"


def make_blurred_pixmap(source: QPixmap, size, radius: int = 22) -> QPixmap:
    """Render a QGraphicsBlurEffect into a reusable pixmap."""
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
        self._bg_source = QPixmap(str(ASSETS / "cyberpunk_bg.jpg"))
        self._bg_blurred = QPixmap()
        self._last_bg_size = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if not self._bg_source.isNull():
            if self._last_bg_size != self.size():
                self._bg_blurred = make_blurred_pixmap(self._bg_source, self.size())
                self._last_bg_size = self.size()
            painter.drawPixmap(self.rect(), self._bg_blurred)
        painter.fillRect(self.rect(), QColor(2, 3, 12, 136))
        border = QPen(Palette.magenta, 1.4)
        painter.setPen(border)
        painter.setBrush(QColor(1, 4, 16, 80))
        painter.drawRect(self.rect().adjusted(6, 6, -7, -7))
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
        painter.setPen(QPen(self.accent, 1.15))
        painter.drawRoundedRect(r, 7, 7)
        painter.setPen(QPen(QColor(self.accent.red(), self.accent.green(), self.accent.blue(), 60), 1))
        painter.drawRoundedRect(r.adjusted(4, 4, -4, -4), 5, 5)
        super().paintEvent(event)


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
        painter.setBrush(QColor(5, 9, 24, bg_alpha))
        painter.setPen(QPen(self.accent, 1.5))
        painter.drawRoundedRect(r, 8, 8)
        painter.setPen(QPen(QColor(self.accent.red(), self.accent.green(), self.accent.blue(), 80), 1))
        painter.drawRoundedRect(r.adjusted(4, 4, -4, -4), 5, 5)
        self._draw_icon(painter, r.center())

    def _draw_icon(self, painter: QPainter, center):
        pen = QPen(self.accent, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        cx, cy = center.x(), center.y()
        name = self.icon_name
        if name == "play":
            path = QPainterPath()
            path.moveTo(cx - 6, cy - 9)
            path.lineTo(cx + 8, cy)
            path.lineTo(cx - 6, cy + 9)
            path.closeSubpath()
            painter.setBrush(self.accent)
            painter.drawPath(path)
        elif name == "pause":
            painter.fillRect(QRectF(cx - 8, cy - 9, 5, 18), self.accent)
            painter.fillRect(QRectF(cx + 3, cy - 9, 5, 18), self.accent)
        elif name == "stop":
            painter.setBrush(self.accent)
            painter.drawRoundedRect(QRectF(cx - 8, cy - 8, 16, 16), 2, 2)
        elif name == "prev":
            painter.drawLine(QPointF(cx - 10, cy - 9), QPointF(cx - 10, cy + 9))
            self._triangle(painter, cx + 2, cy, -1)
            self._triangle(painter, cx + 11, cy, -1)
        elif name == "next":
            painter.drawLine(QPointF(cx + 10, cy - 9), QPointF(cx + 10, cy + 9))
            self._triangle(painter, cx - 2, cy, 1)
            self._triangle(painter, cx - 11, cy, 1)
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
            self._triangle(painter, cx + 9, cy - 8, 1)

    def _triangle(self, painter, cx, cy, direction):
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
        painter.setBrush(self.accent)
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
        painter.setBrush(QColor(5, 9, 24, 178 if self.underMouse() else 140))
        painter.setPen(QPen(self.accent, 1.5))
        painter.drawRoundedRect(r, 8, 8)
        icon_rect = QRectF(r.left() + 14, r.center().y() - 10, 20, 20)
        IconButton(self.icon_name, "", self.accent)._draw_icon(painter, icon_rect.center())
        painter.setPen(self.accent)
        painter.drawText(r.adjusted(44, 0, -8, 0), Qt.AlignVCenter | Qt.AlignLeft, self.text())


class LufsMeter(QWidget):
    """LUFS-style loudness meter.

    The current shell uses simulated values. The audio engine can later feed
    integrated/short-term LUFS and peak values through set_levels().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.short_lufs = -42.0
        self.integrated_lufs = -24.0
        self.peak_db = -12.0
        self.setMinimumHeight(42)

    def set_levels(self, short_lufs: float, integrated_lufs: float, peak_db: float):
        self.short_lufs = float(short_lufs)
        self.integrated_lufs = float(integrated_lufs)
        self.peak_db = float(peak_db)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 4, -2, -4)
        painter.setPen(QPen(Palette.cyan, 1))
        painter.setBrush(QColor(2, 4, 13, 185))
        painter.drawRoundedRect(r, 6, 6)
        label_w = 98
        meter = r.adjusted(label_w, 9, -72, -9)
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
        self.font_family = load_fonts()
        self.setWindowTitle("Chiptune Palace")
        self.resize(1240, 850)
        self.setMinimumSize(980, 680)
        if (ASSETS / "icon.png").exists():
            self.setWindowIcon(QIcon(str(ASSETS / "icon.png")))
        self._drag_pos = None
        self._build()
        self._start_meter_demo()

    def _font(self, size: int) -> QFont:
        f = QFont(self.font_family, size)
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
        divider.setStyleSheet(f"background: rgba({Palette.cyan.red()}, {Palette.cyan.green()}, {Palette.cyan.blue()}, 120);")
        content_layout.addWidget(divider)
        content_layout.addWidget(right, 1)
        outer.addWidget(content, 1)

        self.setStyleSheet(f"""
            QWidget {{
                color: {Palette.text.name()};
                font-family: "{self.font_family}";
                font-size: 8px;
                background: transparent;
            }}
            QLineEdit {{
                color: {Palette.text.name()};
                background: rgba(6, 8, 20, 150);
                border: 1px solid {Palette.magenta.name()};
                border-radius: 6px;
                padding: 8px 10px;
                selection-background-color: {Palette.magenta.name()};
            }}
            QTreeWidget, QListWidget {{
                background: rgba(4, 8, 20, 86);
                border: 0;
                color: {Palette.text.name()};
                outline: 0;
            }}
            QTreeWidget::item, QListWidget::item {{
                min-height: 25px;
            }}
            QTreeWidget::item:selected, QListWidget::item:selected {{
                background: rgba(0, 212, 255, 42);
            }}
            QSplitter::handle {{
                background: rgba(0, 212, 255, 100);
            }}
        """)

    def _build_header(self) -> QWidget:
        panel = GlassPanel(Palette.magenta)
        panel.setFixedHeight(66)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(18, 8, 8, 8)
        layout.setSpacing(12)

        title = QLabel("CHIPTUNE PALACE")
        title.setFont(self._font(17))
        title.setStyleSheet(f"color: {Palette.cyan.name()};")
        layout.addWidget(title)

        search = QLineEdit()
        search.setPlaceholderText("Search consoles, games, files...")
        search.setFont(self._font(8))
        layout.addWidget(search, 1)

        status = QLabel("BACKEND ONLINE")
        status.setFont(self._font(8))
        status.setStyleSheet(f"color: {Palette.green.name()};")
        layout.addWidget(status)

        cfg = IconButton("gear", "Settings", Palette.yellow)
        cfg.setFixedWidth(54)
        layout.addWidget(cfg)

        minimize = IconButton("min", "Minimize", Palette.green)
        minimize.setFixedWidth(48)
        minimize.clicked.connect(self.showMinimized)
        layout.addWidget(minimize)

        maximize = IconButton("max", "Maximize / restore", Palette.yellow)
        maximize.setFixedWidth(48)
        maximize.clicked.connect(self._toggle_maximized)
        layout.addWidget(maximize)

        close = IconButton("close", "Close", Palette.red)
        close.setFixedWidth(48)
        close.clicked.connect(self.close)
        layout.addWidget(close)
        return panel

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
        title.setFont(self._font(8))
        title.setStyleSheet(f"color: {Palette.cyan.name()};")
        browser_layout.addWidget(title)
        tree = QTreeWidget()
        tree.setMinimumWidth(0)
        tree.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        tree.setHeaderHidden(True)
        tree.setIndentation(20)
        tree.setFont(self._font(8))
        self._populate_browser(tree)
        browser_layout.addWidget(tree, 1)
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
        action_layout.addWidget(play_game)
        action_layout.addWidget(open_game)
        action_layout.addWidget(retry_failed)
        layout.addWidget(actions)

        queue = GlassPanel(Palette.magenta)
        queue.setMinimumWidth(0)
        queue_layout = QVBoxLayout(queue)
        queue_layout.setContentsMargins(12, 10, 12, 12)
        qtitle = QLabel("PLAYLIST QUEUE")
        qtitle.setFont(self._font(8))
        qtitle.setStyleSheet(f"color: {Palette.magenta.name()};")
        queue_layout.addWidget(qtitle)
        qlist = QListWidget()
        qlist.setMinimumWidth(0)
        qlist.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        qlist.setFont(self._font(8))
        for track in ["01 Opening", "02 Metal Man", "03 Bubble Man", "04 Air Man", "05 Quick Man", "06 Dr. Wily Stage 1", "moved to sfx"]:
            qlist.addItem(QListWidgetItem(track))
        queue_layout.addWidget(qlist, 1)
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
        game = QLabel("MEGA MAN 2")
        game.setFont(self._font(14))
        game.setStyleSheet(f"color: {Palette.yellow.name()};")
        meta = QLabel("NES / Capcom / 1988\nLibretro metadata ready. Box art and title screen available.\nSource: verified archive resource, best candidate selected.")
        meta.setFont(self._font(8))
        meta.setStyleSheet(f"color: {Palette.muted.name()};")
        meta.setWordWrap(True)
        meta.setMinimumHeight(52)
        ready = QLabel("LOCAL READY")
        ready.setAlignment(Qt.AlignCenter)
        ready.setFont(self._font(8))
        ready.setStyleSheet(f"color: {Palette.green.name()}; border: 1px solid {Palette.green.name()}; border-radius: 6px; padding: 10px;")
        ready.setFixedWidth(172)
        grid.addWidget(game, 0, 0)
        grid.addWidget(meta, 1, 0)
        grid.addWidget(ready, 0, 1, 2, 1)
        layout.addWidget(info)

        art_panel = GlassPanel(Palette.magenta)
        art_panel.setMinimumWidth(0)
        art_layout = QVBoxLayout(art_panel)
        art_layout.setContentsMargins(14, 14, 14, 14)
        art = QLabel()
        pix = QPixmap(str(ASSETS / "cyberpunk_art_2.png"))
        art.setPixmap(pix)
        art.setScaledContents(True)
        art.setMinimumWidth(0)
        art.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        art.setMinimumHeight(250)
        art_layout.addWidget(art)
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
        now_title = QLabel("02 Metal Man")
        now_title.setFont(self._font(9))
        now_title.setStyleSheet(f"color: {Palette.text.name()};")
        now_meta = QLabel("Local / VGZ / 01:12")
        now_meta.setFont(self._font(8))
        now_meta.setStyleSheet(f"color: {Palette.muted.name()};")
        provenance = QLabel("Provenance: archive member verified after game open.")
        provenance.setFont(self._font(8))
        provenance.setWordWrap(True)
        provenance.setStyleSheet(f"color: {Palette.muted.name()};")
        file_text_layout.addWidget(now_title)
        file_text_layout.addWidget(now_meta)
        file_text_layout.addWidget(provenance)
        file_layout.addWidget(file_text, 1)
        local = QLabel("LOCAL")
        local.setAlignment(Qt.AlignCenter)
        local.setFont(self._font(8))
        local.setStyleSheet(f"color: {Palette.green.name()}; border: 1px solid {Palette.green.name()}; border-radius: 6px; padding: 10px;")
        file_layout.addWidget(local)
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
        self.meter = LufsMeter()
        player_layout.addWidget(self.meter, 1)
        layout.addWidget(player)
        return col

    def _populate_browser(self, tree: QTreeWidget):
        data = {
            "NINTENDO": {
                "Nintendo Entertainment System": {
                    "Mega Man 2": ["01 Opening    00:43 VGM", "02 Metal Man  01:12 VGZ", "03 Bubble Man Obtaining file"],
                    "Super Mario World": [],
                },
                "Super Nintendo": {"Chrono Trigger": []},
            },
            "SEGA": {
                "Mega Drive / Genesis": {
                    "Streets of Rage 2": ["01 Go Straight 02:18 VGZ", "02 In The Bar Failed"],
                    "Sonic the Hedgehog 2": [],
                }
            },
            "SONY": {"PlayStation": {"Ridge Racer Type 4": []}},
        }
        for maker, consoles in data.items():
            maker_item = QTreeWidgetItem([maker])
            maker_item.setForeground(0, Palette.magenta)
            tree.addTopLevelItem(maker_item)
            maker_item.setExpanded(True)
            for console, games in consoles.items():
                console_item = QTreeWidgetItem([console])
                console_item.setForeground(0, Palette.cyan)
                maker_item.addChild(console_item)
                console_item.setExpanded(True)
                for game, tracks in games.items():
                    game_item = QTreeWidgetItem([game])
                    game_item.setForeground(0, Palette.yellow)
                    console_item.addChild(game_item)
                    game_item.setExpanded(True)
                    for track in tracks:
                        track_item = QTreeWidgetItem([track])
                        if "Failed" in track:
                            track_item.setForeground(0, Palette.red)
                        elif "Obtaining" in track:
                            track_item.setForeground(0, Palette.cyan)
                        else:
                            track_item.setForeground(0, Palette.green)
                        game_item.addChild(track_item)

    def _start_meter_demo(self):
        self._meter_phase = 0.0
        self._meter_timer = QTimer(self)
        self._meter_timer.timeout.connect(self._tick_meter)
        self._meter_timer.start(70)

    def _tick_meter(self):
        self._meter_phase += 0.17
        wave = math.sin(self._meter_phase) * 8 + math.sin(self._meter_phase * 2.7) * 3
        noise = random.uniform(-2.2, 1.2)
        short = max(-60.0, min(-5.0, -22.0 + wave + noise))
        integrated = -21.0
        peak = short + 8
        self.meter.set_levels(short, integrated, peak)

    def _toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() < 76:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton and not self.isMaximized():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


def main():
    app = QApplication(sys.argv)
    window = PlayerShell()
    window.show()
    sys.exit(app.exec())
