"""
theme.py — Chiptune Palace Global Theme
Tetris Classic Palace aesthetic: deep navy/indigo bricks, hot-pink accents,
electric-lime highlights, phosphor-green text, CRT scanline feel.
"""

# ── Palette ──────────────────────────────────────────────────────────────────
C_BG            = "rgba(13, 13, 26, 230)"   # Semi-transparent navy
C_BRICK1        = "rgba(22, 33, 62, 180)"   # Translucent dark blue
C_BRICK2        = "rgba(15, 52, 96, 200)"   # Translucent deeper blue
C_ACCENT        = "#e94560"   # Hot-pink — primary CTA, selected items
C_ACCENT2       = "#ff6b6b"   # Coral-pink — hover tint
C_LIME          = "#39ff14"   # Electric lime — track name text / "lit" indicator
C_GREEN         = "#00ff41"   # Phosphor green — library text
C_CYAN          = "#00d4ff"   # Neon cyan — playback position / progress chunk
C_YELLOW        = "#ffd700"   # Gold — starred / volume icon
C_TEXT          = "#e8e8e8"   # Off-white — general labels
C_MUTED         = "#6a7080"   # Muted blue-grey — disabled / placeholder
C_BORDER        = "#2a2a4a"   # Subtle border separators
C_SCROLLBAR     = "#1e1e3a"   # Scrollbar track

# ── Typography ───────────────────────────────────────────────────────────────
FONT_PIXEL  = "Press Start 2P"
FONT_TITLE  = "Press Start 2P"

# ── Sizes ────────────────────────────────────────────────────────────────────
BORDER_RADIUS = "4px"
BTN_PADDING   = "6px 14px"
INPUT_PADDING = "6px 10px"

# ── Global QSS ───────────────────────────────────────────────────────────────
GLOBAL_STYLE = f"""
/* === Base === */
QMainWindow, QDialog {{
    background-color: {C_BG};
}}
QWidget {{
    background-color: transparent;
    color: {C_TEXT};
    font-family: '{FONT_PIXEL}';
    font-size: 7px;
}}

/* Main Containers */
#centralWidget, #sidebar, #mainContent, #playbackBar {{
    background-color: {C_BG};
}}

/* === Scanline Overlay === */
#scanlineOverlay {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(0,0,0,0),
        stop:0.5 rgba(0,0,0,0.05),
        stop:1 rgba(0,0,0,0)
    );
    background-size: 100% 4px;
}}

/* === Labels === */
QLabel {{
    color: {C_TEXT};
    background: transparent;
}}
.titleLabel {{
    color: {C_ACCENT};
    font-size: 11px;
    font-weight: bold;
}}
.nowPlayingLabel {{
    color: {C_LIME};
    font-size: 8px;
}}

/* === LineEdit / Search === */
QLineEdit {{
    background-color: {C_BRICK1};
    color: {C_GREEN};
    border: 2px solid {C_ACCENT};
    border-radius: {BORDER_RADIUS};
    padding: {INPUT_PADDING};
}}
QLineEdit:focus {{
    border-color: {C_CYAN};
}}

/* === Buttons === */
QPushButton {{
    background-color: {C_BRICK2};
    color: {C_TEXT};
    border: 2px solid {C_ACCENT};
    border-radius: {BORDER_RADIUS};
    padding: {BTN_PADDING};
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: {C_ACCENT};
    color: #ffffff;
}}
QPushButton#playBtn {{
    border-radius: 20px;
    min-width: 40px;
    min-height: 40px;
    font-size: 9px;
}}

/* === Table & Tree & List Widgets === */
QTreeView, QTableWidget, QListWidget {{
    background-color: {C_BRICK1};
    alternate-background-color: {C_BRICK2};
    border: 1px solid {C_BORDER};
    gridline-color: {C_BORDER};
    color: {C_TEXT};
    selection-background-color: {C_ACCENT};
    selection-color: #ffffff;
    outline: none;
}}
QHeaderView::section {{
    background-color: {C_BRICK2};
    color: {C_CYAN};
    padding: 6px;
    border: 1px solid {C_BORDER};
    font-weight: bold;
}}

/* === Sliders === */
QSlider::groove:horizontal {{
    border: 1px solid {C_BORDER};
    height: 6px;
    background: {C_BRICK2};
    margin: 2px 0;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {C_ACCENT};
    border: 1px solid {C_TEXT};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{
    background: {C_CYAN};
    border-radius: 3px;
}}

/* === Progress Bars === */
QProgressBar {{
    background: {C_BRICK2};
    border: 1px solid {C_ACCENT};
    border-radius: {BORDER_RADIUS};
    color: {C_TEXT};
    text-align: center;
    font-size: 6px;
    height: 14px;
}}
QProgressBar::chunk {{
    background: {C_ACCENT};
}}

/* === Scrollbars === */
QScrollBar:vertical {{
    background: {C_BG};
    width: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {C_ACCENT};
    border-radius: 5px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {C_ACCENT2};
}}

/* === Splitter === */
QSplitter::handle {{
    background: {C_BORDER};
}}
"""
