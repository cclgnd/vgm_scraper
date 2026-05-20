"""
VGM Scraper GUI - Tabbed interface with auto-start scraping and daily logs.
"""

import os
import json
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk, scrolledtext, messagebox, filedialog

from vgm_scraper.config import DEFAULT_DOWNLOAD_DIR, DEFAULT_DB_PATH
from vgm_scraper.core import ScraperSession
from vgm_scraper.db.manager import DatabaseManager
from vgm_scraper.catalog.library import LibraryManager
from vgm_scraper.acquisition.crawler import WebCrawler
from vgm_scraper.acquisition.local_scanner import LocalScanner
from vgm_scraper.acquisition.retrieval import RetrievalManager
from vgm_scraper.acquisition.discovery import DiscoveryEngine
from vgm_scraper.acquisition.sources import get_source, get_all_static_sources, get_dynamic_sources
from vgm_scraper.app_logging import get_logger

CHECKED = "\u2611"
UNCHECKED = "\u2610"
GUI_SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui_settings.json")

# Dark mode palette: dark/grey/olive
COLORS = {
    "bg_primary": "#1a1d1e",
    "bg_secondary": "#24282a",
    "bg_tertiary": "#2d3235",
    "bg_hover": "#3a3f42",
    "bg_active": "#4a5054",
    "fg_primary": "#c8cec8",
    "fg_secondary": "#8a948a",
    "fg_muted": "#5a645a",
    "olive_accent": "#7a8a5e",
    "olive_light": "#94a878",
    "olive_dark": "#5a6a48",
    "olive_pale": "#b8c8a0",
    "border": "#3a4042",
    "border_light": "#4a5054",
    "selection_bg": "#3a4a32",
    "selection_fg": "#d0d8c0",
    "success": "#6a8a5e",
    "warning": "#a89858",
    "error": "#a85858",
}


def _apply_dark_theme(root):
    """Apply dark theme to root and all ttk widgets."""
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".",
                      background=COLORS["bg_primary"],
                      foreground=COLORS["fg_primary"],
                      fieldbackground=COLORS["bg_secondary"],
                      bordercolor=COLORS["border"],
                      darkcolor=COLORS["border"],
                      lightcolor=COLORS["border_light"],
                      troughcolor=COLORS["bg_tertiary"],
                      focuscolor=COLORS["olive_accent"],
                      selectbackground=COLORS["selection_bg"],
                      selectforeground=COLORS["selection_fg"],
                      insertcolor=COLORS["olive_light"],
                      font=("", 9))

    style.configure("TFrame", background=COLORS["bg_primary"])
    style.configure("TLabel", background=COLORS["bg_primary"], foreground=COLORS["fg_primary"])
    style.configure("TButton",
                    background=COLORS["bg_tertiary"],
                    foreground=COLORS["fg_primary"],
                    bordercolor=COLORS["border"],
                    focuscolor=COLORS["olive_accent"],
                    padding=(8, 3))
    style.map("TButton",
              background=[("active", COLORS["bg_hover"]), ("pressed", COLORS["bg_active"])],
              foreground=[("active", COLORS["olive_pale"])])

    style.configure("TLabelframe",
                    background=COLORS["bg_secondary"],
                    bordercolor=COLORS["border"],
                    foreground=COLORS["olive_light"])
    style.configure("TLabelframe.Label",
                    background=COLORS["bg_secondary"],
                    foreground=COLORS["olive_light"],
                    font=("", 9, "bold"))

    style.configure("TEntry",
                    fieldbackground=COLORS["bg_secondary"],
                    foreground=COLORS["fg_primary"],
                    bordercolor=COLORS["border"],
                    insertcolor=COLORS["olive_light"])

    style.configure("TCheckbutton",
                    background=COLORS["bg_primary"],
                    foreground=COLORS["fg_primary"])

    style.configure("TPanedwindow", background=COLORS["border"])

    style.configure("Treeview",
                    background=COLORS["bg_secondary"],
                    foreground=COLORS["fg_primary"],
                    fieldbackground=COLORS["bg_secondary"],
                    bordercolor=COLORS["border"],
                    rowheight=22)
    style.map("Treeview",
              background=[("selected", COLORS["selection_bg"])],
              foreground=[("selected", COLORS["selection_fg"])])
    style.configure("Treeview.Heading",
                    background=COLORS["bg_tertiary"],
                    foreground=COLORS["fg_secondary"],
                    bordercolor=COLORS["border"],
                    font=("", 9, "bold"))
    style.map("Treeview.Heading",
              background=[("active", COLORS["bg_hover"])])

    style.configure("TNotebook",
                    background=COLORS["bg_primary"],
                    bordercolor=COLORS["border"],
                    tabmargins=(0, 0, 0, 0))
    style.configure("TNotebook.Tab",
                    background=COLORS["bg_tertiary"],
                    foreground=COLORS["fg_secondary"],
                    bordercolor=COLORS["border"],
                    padding=(12, 4),
                    font=("", 9))
    style.map("TNotebook.Tab",
              background=[("selected", COLORS["bg_active"])],
              foreground=[("selected", COLORS["olive_light"])],
              expand=[("selected", (0, 0, 0, 2))])

    style.configure("TScrollbar",
                    background=COLORS["bg_tertiary"],
                    troughcolor=COLORS["bg_secondary"],
                    bordercolor=COLORS["border"],
                    darkcolor=COLORS["border"],
                    lightcolor=COLORS["border_light"])
    style.map("TScrollbar",
              background=[("active", COLORS["bg_hover"]), ("pressed", COLORS["olive_dark"])])

    style.configure("TProgressbar",
                    background=COLORS["olive_accent"],
                    troughcolor=COLORS["bg_tertiary"],
                    bordercolor=COLORS["border"])

    style.configure("TMenu",
                    background=COLORS["bg_secondary"],
                    foreground=COLORS["fg_primary"])

    style.configure("TMenubutton",
                    background=COLORS["bg_tertiary"],
                    foreground=COLORS["fg_primary"],
                    bordercolor=COLORS["border"])
    style.map("TMenubutton",
              background=[("active", COLORS["bg_hover"])])


class VGMScraperGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("VGM Scraper")
        self.root.geometry("1200x800")
        self.root.minsize(800, 550)

        _apply_dark_theme(root)

        self.db = DatabaseManager(DEFAULT_DB_PATH)
        self.session = ScraperSession()
        self.library = LibraryManager(self.db)
        self.retrieval = RetrievalManager(self.db, DEFAULT_DOWNLOAD_DIR)
        self.logger = get_logger()

        self.checked_items = set()
        self.item_cache = {}
        self.discovery_engine = None
        self._scraping_running = False
        self._catalog_loading = False
        self.gui_settings = self._load_gui_settings()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._apply_text_widget_theme()
        self._bind_tree_clicks()
        self.root.after(100, self._refresh_tree)
        self.root.after(1000, self._start_scraping)

    def _on_close(self):
        """Clean up background threads and close properly."""
        self._save_tree_column_widths()
        self._append_log("Shutting down...")
        self._scraping_running = False
        if self.discovery_engine:
            self.discovery_engine.stop_continuous()
        self.root.destroy()

    def _load_gui_settings(self) -> dict:
        try:
            with open(GUI_SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_gui_settings(self):
        try:
            with open(GUI_SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self.gui_settings, f, indent=2)
        except Exception as e:
            self._append_log(f"[SETTINGS] Could not save GUI settings: {e}")

    def _apply_text_widget_theme(self):
        """Apply dark theme to tk.Text and tk.Listbox widgets (not controlled by ttk.Style)."""
        text_opts = {
            "bg": COLORS["bg_secondary"],
            "fg": COLORS["fg_primary"],
            "insertbackground": COLORS["olive_light"],
            "selectbackground": COLORS["selection_bg"],
            "selectforeground": COLORS["selection_fg"],
            "highlightbackground": COLORS["border"],
            "highlightcolor": COLORS["olive_accent"],
            "highlightthickness": 1,
            "font": ("Consolas", 8),
            "relief": tk.FLAT,
        }
        listbox_opts = {
            "bg": COLORS["bg_secondary"],
            "fg": COLORS["fg_primary"],
            "selectbackground": COLORS["selection_bg"],
            "selectforeground": COLORS["selection_fg"],
            "highlightbackground": COLORS["border"],
            "highlightcolor": COLORS["olive_accent"],
            "highlightthickness": 1,
            "font": ("Consolas", 9),
            "relief": tk.FLAT,
        }
        # ScrolledText widgets
        for w in [self.scraping_log, self.log_viewer, self.catalog_log]:
            if hasattr(w, "text"):
                w.text.configure(**text_opts)
            else:
                w.configure(**text_opts)
        # Listbox
        if hasattr(self, "log_listbox"):
            self.log_listbox.configure(**listbox_opts)

        # Root window background
        self.root.configure(bg=COLORS["bg_primary"])

        # Treeview tag colors for status
        self.tree.tag_configure("downloaded", background=COLORS["olive_dark"], foreground=COLORS["olive_pale"])
        self.tree.tag_configure("pending", foreground=COLORS["fg_muted"])
        self.tree.tag_configure("needs_audition", foreground=COLORS["olive_light"])
        self.tree.tag_configure("manual_passed", background=COLORS["olive_dark"], foreground=COLORS["olive_pale"])
        self.tree.tag_configure("manual_failed", foreground="#d28b8b")
        self.tree.tag_configure("empty_extract", foreground="#d2b48c")
        self.tree.tag_configure("failed", foreground="#d28b8b")

        # Queue tree tags
        if hasattr(self, "queue_tree"):
            self.queue_tree.tag_configure("downloaded", background=COLORS["olive_dark"], foreground=COLORS["olive_pale"])
            self.queue_tree.tag_configure("needs_audition", foreground=COLORS["olive_light"])
            self.queue_tree.tag_configure("manual_passed", background=COLORS["olive_dark"], foreground=COLORS["olive_pale"])
            self.queue_tree.tag_configure("manual_failed", foreground="#d28b8b")
            self.queue_tree.tag_configure("empty_extract", foreground="#d2b48c")
            self.queue_tree.tag_configure("failed", foreground="#d28b8b")

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=6)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Download dir:").pack(side=tk.LEFT)
        self.dir_var = tk.StringVar(value=DEFAULT_DOWNLOAD_DIR)
        ttk.Entry(top, textvariable=self.dir_var, width=50).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Browse", command=self._browse_dir).pack(side=tk.LEFT)

        # Notebook tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        self._build_catalog_tab()
        self._build_scraping_tab()
        self._build_queue_tab()
        self._build_logs_tab()

        # Bottom status bar
        bottom = ttk.Frame(self.root, padding=(6, 0, 6, 6))
        bottom.pack(fill=tk.X)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(bottom, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(side=tk.RIGHT, padx=8, fill=tk.X, expand=True)
        self.progress_label = ttk.Label(bottom, text="")
        self.progress_label.pack(side=tk.RIGHT, padx=4)

    # ============================================
    # CATALOG TAB
    # ============================================

    def _build_catalog_tab(self):
        tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab, text="Catalog")

        btns = ttk.Frame(tab)
        btns.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(btns, text="Load Catalog", command=self._load_catalog).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Download Checked", command=self._download_checked_games).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Check All", command=self._check_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Uncheck All", command=self._uncheck_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Expand All", command=self._expand_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Collapse All", command=self._collapse_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Reset DB", command=self._reset_database).pack(side=tk.RIGHT, padx=2)

        # Split pane: tree (left) + live log (right)
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left: tree view
        tree_frame = ttk.Frame(paned)
        paned.add(tree_frame, weight=3)

        columns = ("size", "status", "url", "download")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="tree headings", selectmode="none")
        self.tree.heading("#0", text="Name", anchor=tk.W)
        self.tree.heading("size", text="Size (MB)", anchor=tk.E)
        self.tree.heading("status", text="Status", anchor=tk.W)
        self.tree.heading("url", text="Page URL", anchor=tk.W)
        self.tree.heading("download", text="Download URL", anchor=tk.W)

        self.tree.column("#0", width=420, minwidth=200, stretch=False)
        self.tree.column("size", width=90, minwidth=70, anchor=tk.E, stretch=False)
        self.tree.column("status", width=100, minwidth=80, anchor=tk.W, stretch=False)
        self.tree.column("url", width=330, minwidth=200, stretch=False)
        self.tree.column("download", width=380, minwidth=220, stretch=False)
        self._restore_tree_column_widths()
        self.root.after(50, self._restore_tree_column_widths)
        self.tree.bind("<ButtonRelease-1>", self._on_tree_column_resize, add="+")

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        # Right: live scraper log
        log_frame = ttk.Frame(paned)
        paned.add(log_frame, weight=1)

        log_header = ttk.Frame(log_frame)
        log_header.pack(fill=tk.X)

        ttk.Label(log_header, text="Scraper Activity Log").pack(side=tk.LEFT, padx=4)

        # Date selector for previous logs
        self.log_date_var = tk.StringVar(value="Today (live)")
        self.log_date_menu = ttk.OptionMenu(log_header, self.log_date_var, "Today (live)", command=self._on_log_date_select)
        self.log_date_menu.pack(side=tk.RIGHT, padx=4)
        self._refresh_log_dates()

        self.catalog_log = scrolledtext.ScrolledText(log_frame, state=tk.DISABLED, font=("Consolas", 8), width=40)
        self.catalog_log.pack(fill=tk.BOTH, expand=True, padx=(4, 0))

        self._load_today_log()

    # ============================================
    # SCRAPING TAB
    # ============================================

    def _build_scraping_tab(self):
        tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab, text="Scraping")

        # Static sources
        sf = ttk.LabelFrame(tab, text="Static Sources", padding=6)
        sf.pack(fill=tk.X, pady=4)

        self.source_vars = {}
        static_sources = get_all_static_sources(self.session, self.db)
        for i, src in enumerate(static_sources):
            v = tk.BooleanVar(value=True)
            self.source_vars[src.name] = v
            ttk.Checkbutton(sf, text=src.name, variable=v).grid(row=i // 3, column=i % 3, sticky=tk.W, padx=8, pady=2)

        # Discovery settings
        df = ttk.LabelFrame(tab, text="Autonomous Discovery", padding=6)
        df.pack(fill=tk.X, pady=4)

        self.discovery_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(df, text="Enable autonomous discovery (finds new VGM sites automatically)",
                        variable=self.discovery_var).pack(anchor=tk.W, pady=2)

        ttk.Label(df, text="Discovery interval (seconds):").pack(anchor=tk.W)
        self.discovery_interval = ttk.Entry(df, width=10)
        self.discovery_interval.insert(0, "3600")
        self.discovery_interval.pack(anchor=tk.W, pady=2)

        ttk.Label(df, text="Max sites per pass:").pack(anchor=tk.W)
        self.discovery_max = ttk.Entry(df, width=10)
        self.discovery_max.insert(0, "10")
        self.discovery_max.pack(anchor=tk.W, pady=2)

        # Crawl settings
        cf = ttk.LabelFrame(tab, text="Crawl Settings", padding=6)
        cf.pack(fill=tk.X, pady=4)

        ttk.Label(cf, text="Max depth (pages per console):").pack(anchor=tk.W)
        self.crawl_depth = ttk.Entry(cf, width=10)
        self.crawl_depth.insert(0, "3")
        self.crawl_depth.pack(anchor=tk.W, pady=2)

        ttk.Label(cf, text="Request delay (seconds):").pack(anchor=tk.W)
        self.request_delay = ttk.Entry(cf, width=10)
        self.request_delay.insert(0, "1.0")
        self.request_delay.pack(anchor=tk.W, pady=2)

        # Controls
        ctrl = ttk.Frame(tab)
        ctrl.pack(fill=tk.X, pady=6)
        ttk.Button(ctrl, text="Crawl Now", command=self._crawl_sources).pack(side=tk.LEFT, padx=4)
        ttk.Button(ctrl, text="Scan Local Folder", command=self._scan_local).pack(side=tk.LEFT, padx=4)
        self.start_scraping_btn = ttk.Button(ctrl, text="Start Scraping", command=self._start_scraping_manual)
        self.start_scraping_btn.pack(side=tk.LEFT, padx=4)
        self.stop_scraping_btn = ttk.Button(ctrl, text="Stop Scraping", command=self._stop_scraping)
        self.stop_scraping_btn.pack(side=tk.LEFT, padx=4)
        self._update_scraping_buttons()

        # Scraping log
        self.scraping_log = scrolledtext.ScrolledText(tab, height=18, state=tk.DISABLED, font=("Consolas", 8))
        self.scraping_log.pack(fill=tk.BOTH, expand=True)

    # ============================================
    # QUEUE TAB
    # ============================================

    def _build_queue_tab(self):
        tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab, text="Queue")

        ttk.Label(tab, text="Downloaded games appear here with their discovered tracks.",
                  font=("", 9)).pack(anchor=tk.W, pady=8)

        self.queue_count = ttk.Label(tab, text="0 games downloaded")
        self.queue_count.pack(anchor=tk.W, pady=4)

        columns = ("qtracks", "qstatus", "qpath", "_game_id")
        self.queue_tree = ttk.Treeview(tab, columns=columns, show="tree headings", selectmode="browse")
        self.queue_tree.heading("#0", text="Game")
        self.queue_tree.heading("qtracks", text="Tracks")
        self.queue_tree.heading("qstatus", text="Audition")
        self.queue_tree.heading("qpath", text="Local Path")
        self.queue_tree.heading("_game_id", text="")
        self.queue_tree.column("#0", width=250)
        self.queue_tree.column("qtracks", width=80, anchor=tk.E)
        self.queue_tree.column("qstatus", width=120, anchor=tk.W)
        self.queue_tree.column("qpath", width=300)
        self.queue_tree.column("_game_id", width=0, minwidth=0, stretch=False)
        self.queue_tree.pack(fill=tk.BOTH, expand=True)

        audition_btns = ttk.Frame(tab)
        audition_btns.pack(fill=tk.X, pady=4)
        ttk.Button(audition_btns, text="Mark Passed", command=lambda: self._mark_selected_game_audition("manual_passed")).pack(side=tk.LEFT, padx=2)
        ttk.Button(audition_btns, text="Mark Failed", command=lambda: self._mark_selected_game_audition("manual_failed")).pack(side=tk.LEFT, padx=2)
        ttk.Button(audition_btns, text="Needs Audition", command=lambda: self._mark_selected_game_audition("needs_audition")).pack(side=tk.LEFT, padx=2)
        ttk.Button(audition_btns, text="Refresh", command=self._refresh_queue_view).pack(side=tk.LEFT, padx=2)
        self._refresh_queue_view()

    def _refresh_queue_view(self):
        for child in self.queue_tree.get_children():
            self.queue_tree.delete(child)

        with self.db.connect() as conn:
            rows = conn.execute("""
                SELECT g.title, g.id, COUNT(t.id) as track_count, MIN(lf.file_path) as local_path
                FROM games g
                LEFT JOIN collections c ON c.game_id = g.id
                LEFT JOIN tracks t ON t.collection_id = c.id
                LEFT JOIN local_files lf ON lf.track_id = t.id AND lf.is_available = 1
                GROUP BY g.id
                HAVING track_count > 0
                ORDER BY g.title
            """).fetchall()

        for row in rows:
            audition_status = self.db.get_game_audition_status(row["id"])
            self.queue_tree.insert("", "end", text=row["title"],
                                   values=(row["track_count"], audition_status, row["local_path"] or "—", row["id"]),
                                   tags=(audition_status if audition_status != "pending" else "downloaded",))

        self.queue_count.configure(text=f"{len(rows)} games downloaded")

    def _mark_selected_game_audition(self, status: str):
        selected = self.queue_tree.selection()
        if not selected:
            messagebox.showinfo("No selection", "Select a downloaded game first.")
            return

        iid = selected[0]
        game_id = self.queue_tree.set(iid, "_game_id")
        if not game_id:
            messagebox.showinfo("No game", "Could not resolve the selected game.")
            return

        self.db.add_audition_event(
            game_id=int(game_id),
            event_type="manual_audition",
            status=status,
            details={"source": "gui_queue"},
        )
        title = self.queue_tree.item(iid, "text")
        self._append_log(f"[AUDITION] {title}: {status}")
        self._refresh_queue_view()
        self._update_tree_incremental()

    # ============================================
    # LOGS TAB
    # ============================================

    def _build_logs_tab(self):
        tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tab, text="Logs")

        lbtns = ttk.Frame(tab)
        lbtns.pack(fill=tk.X, pady=4)
        ttk.Button(lbtns, text="Refresh File List", command=self._refresh_log_files).pack(side=tk.LEFT, padx=2)
        ttk.Button(lbtns, text="Open Log Folder", command=self._open_log_folder).pack(side=tk.LEFT, padx=2)

        ttk.Label(tab, text="Log files:").pack(anchor=tk.W, pady=(4, 2))
        self.log_listbox = tk.Listbox(tab, height=8, font=("Consolas", 9))
        self.log_listbox.pack(fill=tk.X, pady=2)
        self.log_listbox.bind("<<ListboxSelect>>", self._on_log_select)

        self.log_viewer = scrolledtext.ScrolledText(tab, height=20, state=tk.DISABLED, font=("Consolas", 8))
        self.log_viewer.pack(fill=tk.BOTH, expand=True)

        self._refresh_log_files()

    # ============================================
    # TREE CLICK HANDLING
    # ============================================

    def _bind_tree_clicks(self):
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-Button-1>", self._on_tree_double_click)
        self.tree.bind("<Button-3>", self._on_tree_right_click)

        # Context menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Open page", command=self._open_page_url)
        self.context_menu.add_command(label="Open download", command=self._open_download_url)
        self.context_menu.add_command(label="Copy page URL", command=lambda: self._copy_url("source_url"))
        self.context_menu.add_command(label="Copy download URL", command=lambda: self._copy_url("download_url"))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Show full path", command=self._show_full_path)

    def _restore_tree_column_widths(self):
        widths = self.gui_settings.get("catalog_tree_column_widths", {})
        for column, width in widths.items():
            if column in ("#0", "size", "status", "url", "download"):
                try:
                    self.tree.column(column, width=int(width))
                except Exception:
                    pass

    def _save_tree_column_widths(self):
        if not hasattr(self, "tree"):
            return
        widths = {}
        for column in ("#0", "size", "status", "url", "download"):
            try:
                widths[column] = int(self.tree.column(column, "width"))
            except Exception:
                pass
        self.gui_settings["catalog_tree_column_widths"] = widths
        self._save_gui_settings()

    def _on_tree_column_resize(self, event=None):
        self.root.after_idle(self._save_tree_column_widths)

    def _on_tree_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item or item not in self.item_cache:
            return
        self.tree.selection_set(item)
        self.context_menu.tk_popup(event.x_root, event.y_root)

    def _get_item_url(self, key: str = "source_url"):
        """Get URL for the currently selected item."""
        sel = self.tree.selection()
        if not sel:
            return ""
        iid = sel[0]
        cached = self.item_cache.get(iid)
        if not cached:
            return ""
        if cached["type"] == "game":
            return cached.get(key, "")
        if cached["type"] == "console":
            # Get first game's URL as representative
            for child in self.tree.get_children(iid):
                child_cached = self.item_cache.get(child)
                if child_cached and child_cached.get(key):
                    return child_cached[key]
        return ""

    def _get_item_path(self):
        """Get the full tree path for the selected item."""
        sel = self.tree.selection()
        if not sel:
            return ""
        iid = sel[0]
        parts = []
        current = iid
        while current:
            text = self.tree.item(current, "text")
            if text.startswith(CHECKED) or text.startswith(UNCHECKED):
                text = text[2:]
            parts.insert(0, text.strip())
            current = self.tree.parent(current)
        return " > ".join(parts)

    def _open_page_url(self):
        url = self._get_item_url("source_url")
        if url:
            webbrowser.open(url)
            self._append_log(f"[BROWSER] Opened: {url}")

    def _open_download_url(self):
        url = self._get_item_url("download_url")
        if url:
            webbrowser.open(url)
            self._append_log(f"[BROWSER] Opened download: {url}")

    def _copy_url(self, key: str = "source_url"):
        url = self._get_item_url(key)
        if url:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self._append_log(f"[CLIPBOARD] Copied: {url}")

    def _show_full_path(self):
        path = self._get_item_path()
        url = self._get_item_url("source_url")
        download_url = self._get_item_url("download_url")
        display = f"Path: {path}"
        if url:
            display += f"\nPage URL: {url}"
        if download_url:
            display += f"\nDownload URL: {download_url}"
        messagebox.showinfo("Full Path", display)

    def _on_tree_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item or item not in self.item_cache:
            return
        region = self.tree.identify_region(event.x, event.y)
        if region == "tree":
            cached = self.item_cache[item]
            if cached["type"] == "console":
                self._toggle_console_check(item)
            else:
                self._toggle_check(item)

    def _on_tree_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item or item not in self.item_cache:
            return
        cached = self.item_cache[item]
        if cached["type"] == "console":
            self._queue_console_games(item)

    def _toggle_check(self, iid):
        if iid in self.checked_items:
            self.checked_items.discard(iid)
            self._set_check_state(iid, False)
        else:
            self.checked_items.add(iid)
            self._set_check_state(iid, True)

    def _toggle_console_check(self, con_iid):
        """Check/uncheck all games under a console."""
        children = list(self.tree.get_children(con_iid))
        all_checked = all(c in self.checked_items for c in children if c in self.item_cache)
        for child in children:
            if child in self.item_cache:
                if all_checked:
                    self.checked_items.discard(child)
                    self._set_check_state(child, False)
                else:
                    self.checked_items.add(child)
                    self._set_check_state(child, True)
        # Update console checkbox
        self._set_check_state(con_iid, not all_checked)

    def _queue_console_games(self, con_iid):
        """Queue all games under a console for download."""
        count = 0
        for child in self.tree.get_children(con_iid):
            if child in self.item_cache and child not in self.checked_items:
                self.checked_items.add(child)
                self._set_check_state(child, True)
                count += 1
        self._set_check_state(con_iid, True)
        self._append_log(f"Queued {count} games from {self.tree.item(con_iid, 'text')}")

    def _set_check_state(self, iid, checked):
        current_text = self.tree.item(iid, "text")
        if current_text.startswith(CHECKED) or current_text.startswith(UNCHECKED):
            current_text = current_text[2:]
        prefix = CHECKED if checked else UNCHECKED
        self.tree.item(iid, text=f"{prefix} {current_text}")

    # ============================================
    # LOGGING
    # ============================================

    def _append_log(self, text):
        self.scraping_log.configure(state=tk.NORMAL)
        self.scraping_log.insert(tk.END, text + "\n")
        # No auto-scroll: preserves view position during updates
        self.scraping_log.configure(state=tk.DISABLED)
        self.logger.info(text, source="gui")

        # Also append to catalog-side live log
        self.catalog_log.configure(state=tk.NORMAL)
        self.catalog_log.insert(tk.END, text + "\n")
        self.catalog_log.see(tk.END)
        self.catalog_log.configure(state=tk.DISABLED)

    def _refresh_log_dates(self):
        """Populate the date selector menu with available log files."""
        files = self.logger.get_log_files()
        dates = ["Today (live)"]
        for f in files:
            basename = os.path.basename(f)
            if basename.startswith("scraper_") and basename.endswith(".log"):
                date_part = basename.replace("scraper_", "").replace(".log", "")
                dates.append(date_part)
        menu = self.log_date_menu["menu"]
        menu.delete(0, "end")
        for d in dates:
            menu.add_command(label=d, command=lambda val=d: self.log_date_var.set(val))
        if len(dates) > 1:
            self.log_date_var.set(dates[-1])

    def _on_log_date_select(self, value):
        """Handle date selection from the log menu."""
        if value == "Today (live)":
            self._load_today_log()
        else:
            self._load_historical_log(value)

    def _load_today_log(self):
        """Load today's log file and enable live updates."""
        self.catalog_log.configure(state=tk.NORMAL)
        self.catalog_log.delete("1.0", tk.END)
        today = self.logger._get_date_str()
        content = self.logger.read_log(f"scraper_{today}.log", max_lines=1000)
        self.catalog_log.insert(tk.END, content)
        self.catalog_log.see(tk.END)
        self.catalog_log.configure(state=tk.DISABLED)

    def _load_historical_log(self, date_str):
        """Load a historical log file (read-only, no live updates)."""
        self.catalog_log.configure(state=tk.NORMAL)
        self.catalog_log.delete("1.0", tk.END)
        content = self.logger.read_log(f"scraper_{date_str}.log", max_lines=2000)
        if content:
            self.catalog_log.insert(tk.END, f"=== Historical log: {date_str} ===\n\n")
            self.catalog_log.insert(tk.END, content)
        else:
            self.catalog_log.insert(tk.END, f"No log found for {date_str}")
        self.catalog_log.configure(state=tk.DISABLED)

    def _refresh_log_files(self):
        self.log_listbox.delete(0, tk.END)
        files = self.logger.get_log_files()
        for f in files:
            self.log_listbox.insert(tk.END, os.path.basename(f))
        self._refresh_log_dates()

    def _on_log_select(self, event):
        sel = self.log_listbox.curselection()
        if not sel:
            return
        filename = self.log_listbox.get(sel[0])
        content = self.logger.read_log(filename)
        self.log_viewer.configure(state=tk.NORMAL)
        self.log_viewer.delete("1.0", tk.END)
        self.log_viewer.insert(tk.END, content)
        self.log_viewer.configure(state=tk.DISABLED)

    def _open_log_folder(self):
        import subprocess
        subprocess.Popen(["explorer", self.logger.log_dir])

    # ============================================
    # TREE OPERATIONS
    # ============================================

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self.dir_var.get())
        if d:
            self.dir_var.set(d)

    def _refresh_tree(self):
        if self._catalog_loading:
            return
        self._catalog_loading = True
        self.status_var.set("Loading catalog...")

        def run():
            try:
                tree = self.db.get_gui_catalog_summary()
                self.root.after(0, lambda: self._populate_tree(tree))
            except Exception as e:
                self.root.after(0, lambda: self._append_log(f"[CATALOG] Load failed: {e}"))
                self.root.after(0, lambda: self.status_var.set("Catalog load failed."))
                self.root.after(0, lambda: setattr(self, "_catalog_loading", False))

        threading.Thread(target=run, daemon=True).start()

    def _populate_tree(self, tree: list[dict]):
        for child in self.tree.get_children():
            self.tree.delete(child)
        self.item_cache.clear()
        self.checked_items.clear()

        total_games_all = 0
        for console in tree:
            total_games = len(console.get("games", []))
            total_games_all += total_games
            downloaded = self._count_console_downloaded(console)
            con_label = f"{console['display_name']} ({downloaded}/{total_games})"
            con_iid = self.tree.insert("", "end", text=f"{UNCHECKED} {con_label}", open=total_games > 0)
            self.item_cache[con_iid] = {"type": "console", "id": console.get("id"),
                                        "display_name": console["display_name"],
                                        "total": total_games, "downloaded": downloaded}

            for game in console.get("games", []):
                track_count = game.get("track_count", 0)
                status = self._display_game_status(game, game.get("has_files", False))

                source_url = game.get("source_url", "")
                download_url = game.get("download_url", "")

                game_text = f"{UNCHECKED} {game['title']}"
                iid = self.tree.insert(con_iid, "end", text=game_text,
                                       values=(track_count, status, source_url, download_url),
                                       tags=(status,))
                self.item_cache[iid] = {"type": "game", "id": game["id"], "title": game["title"],
                                        "console": console["display_name"], "source_url": source_url,
                                        "download_url": download_url, "resource_id": game.get("resource_id")}
        self._catalog_loading = False
        self.status_var.set(f"Catalog loaded: {total_games_all} games.")
        self._append_log(f"[CATALOG] Loaded {total_games_all} games.")

    def _update_tree_incremental(self):
        self._refresh_tree()
        return
        tree = self.db.get_gui_catalog_summary()
        existing_top = {self.tree.item(c, "text"): c for c in self.tree.get_children()}

        for console in tree:
            total_games = len(console.get("games", []))
            downloaded = self._count_console_downloaded(console)
            con_label = f"{console['display_name']} ({downloaded}/{total_games})"
            con_text = f"{UNCHECKED} {con_label}"
            con_checked = f"{CHECKED} {con_label}"

            # Find existing console node by either checked or unchecked variant
            con_iid = existing_top.get(con_text) or existing_top.get(con_checked)
            if con_iid:
                # Update label if counts changed
                current = self.tree.item(con_iid, "text")
                if current not in (con_text, con_checked):
                    is_checked = current.startswith(CHECKED)
                    self.tree.item(con_iid, text=f"{CHECKED if is_checked else UNCHECKED} {con_label}")
            else:
                con_iid = self.tree.insert("", "end", text=con_text)

            self.item_cache[con_iid] = {"type": "console", "id": console.get("id"),
                                        "display_name": console["display_name"],
                                        "total": total_games, "downloaded": downloaded}

            existing_games = {self.tree.item(c, "text"): c for c in self.tree.get_children(con_iid)}
            for game in console.get("games", []):
                track_count = game.get("track_count", 0)
                status = self._display_game_status(game, game.get("has_files", False))

                source_url = game.get("source_url", "")
                download_url = game.get("download_url", "")
                game_text = f"{UNCHECKED} {game['title']}"
                if game_text in existing_games:
                    iid = existing_games[game_text]
                    current_vals = self.tree.item(iid, "values")
                    if current_vals[1] != status or current_vals[2] != source_url or current_vals[3] != download_url:
                        self.tree.item(iid, values=(track_count, status, source_url, download_url), tags=(status,))
                else:
                    iid = self.tree.insert(con_iid, "end", text=game_text,
                                           values=(track_count, status, source_url, download_url),
                                           tags=(status,))
                    self.item_cache[iid] = {"type": "game", "id": game["id"], "title": game["title"],
                                            "console": console["display_name"], "source_url": source_url,
                                            "download_url": download_url, "resource_id": game.get("resource_id")}

    def _count_console_downloaded(self, console: dict) -> int:
        """Count how many games in a console have local files."""
        return sum(1 for game in console.get("games", []) if game.get("has_files"))

    @staticmethod
    def _display_game_status(game: dict, has_files: bool) -> str:
        audition_status = game.get("audition_status") or "pending"
        if audition_status != "pending":
            return audition_status
        return "downloaded" if has_files else "pending"

    def _get_game_source_url(self, game_id: int) -> str:
        """Get the source URL for a game from resource_nodes."""
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT rn.url FROM resource_nodes rn "
                "JOIN provenance_events pe ON pe.resource_id = rn.id "
                "WHERE pe.details LIKE ? LIMIT 1",
                (f"%game_id={game_id}%",)
            ).fetchone()
            if row:
                return row["url"]
            # Fallback: try matching by title
            game = conn.execute("SELECT title FROM games WHERE id = ?", (game_id,)).fetchone()
            if game:
                row = conn.execute(
                    "SELECT url FROM resource_nodes WHERE node_type = 'pack' AND title = ? LIMIT 1",
                    (game["title"],)
                ).fetchone()
                if row:
                    return row["url"]
        return ""

    def _load_catalog(self):
        self._refresh_tree()
        self._append_log("Catalog tree refreshed from database.")

    def _reset_database(self):
        confirmed = messagebox.askyesno(
            "Reset database",
            "This will delete all catalog, acquisition, provenance, retrieval, local-file, audition, and discovery records.\n\n"
            "Downloaded files on disk will not be deleted.\n\n"
            "Reset the database now?",
            icon=messagebox.WARNING,
        )
        if not confirmed:
            return

        self._scraping_running = False
        if self.discovery_engine:
            self.discovery_engine.stop_continuous()

        try:
            stats = self.db.reset_database()
            self.checked_items.clear()
            self.item_cache.clear()
            self._refresh_tree()
            self._refresh_queue_view()
            self.status_var.set("Database reset.")
            self._append_log("[RESET] Database reset; downloaded files were left untouched.")
            messagebox.showinfo("Database reset", "Database reset complete. Downloaded files were not deleted.")
        except Exception as e:
            self._append_log(f"[RESET] Failed: {e}")
            messagebox.showerror("Reset failed", str(e))

    # ============================================
    # SCRAPING
    # ============================================

    def _start_scraping(self):
        """Auto-start scraping and discovery on GUI launch."""
        if self._scraping_running:
            return
        self._scraping_running = True
        self._update_scraping_buttons()
        self._append_log("Auto-starting scraping engine...")

        # Start autonomous discovery
        if self.discovery_var.get():
            try:
                interval = int(self.discovery_interval.get() or 3600)
                max_sites = int(self.discovery_max.get() or 10)
                self.discovery_engine = DiscoveryEngine(self.db, self.session)
                self.discovery_engine.start_continuous(interval=interval, max_sites=max_sites)
                self._append_log(f"Autonomous discovery started (interval: {interval}s, max sites: {max_sites})")
                self.logger.info(f"Discovery started: interval={interval}s, max_sites={max_sites}", source="discovery")
            except Exception as e:
                self._append_log(f"Discovery start error: {e}")
                self.logger.error(f"Discovery start failed: {e}", source="discovery")

        # Start initial crawl of enabled sources
        self._crawl_sources()

    def _start_scraping_manual(self):
        if self._scraping_running:
            return
        self._append_log("Scraping started.")
        self.logger.info("Scraping started by user", source="gui")
        self._start_scraping()

    def _stop_scraping(self):
        if not self._scraping_running:
            return
        self._scraping_running = False
        if self.discovery_engine:
            self.discovery_engine.stop_continuous()
        self._update_scraping_buttons()
        self._append_log("Scraping stopped.")
        self.logger.info("Scraping stopped by user", source="gui")

    def _update_scraping_buttons(self):
        if not hasattr(self, "start_scraping_btn") or not hasattr(self, "stop_scraping_btn"):
            return
        if self._scraping_running:
            self.start_scraping_btn.configure(state=tk.DISABLED)
            self.stop_scraping_btn.configure(state=tk.NORMAL)
        else:
            self.start_scraping_btn.configure(state=tk.NORMAL)
            self.stop_scraping_btn.configure(state=tk.DISABLED)

    def _crawl_sources(self):
        selected = [n for n, v in self.source_vars.items() if v.get()]
        if not selected:
            self._append_log("No sources selected for crawl.")
            return

        self.status_var.set("Crawling...")
        self._append_log(f"Starting crawl: {', '.join(selected)}")

        def run():
            crawler = WebCrawler(self.db, self.session)
            total = 0
            for name in selected:
                if not self._scraping_running:
                    self.root.after(0, lambda: self._append_log("Crawl stopped before next source."))
                    break
                try:
                    src = get_source(name, self.session, self.db)
                    self.root.after(0, lambda n=name: self._append_log(f"  Crawling {n}..."))
                    count = crawler.crawl_source(src, max_depth=3)
                    total += count
                    self.root.after(0, lambda n=name, c=count: self._append_log(f"  {n}: {c} resources"))
                    self.root.after(0, self._update_tree_incremental)
                except Exception as e:
                    self.root.after(0, lambda n=name, e=e: self._append_log(f"  {n} error: {e}"))
                    self.logger.error(f"Crawl failed for {name}: {e}", source=name)

            self.root.after(0, lambda: self.status_var.set(f"Crawl complete. {total} resources."))
            self.root.after(0, lambda: self._append_log(f"Crawl complete. {total} resources."))
            self.root.after(0, self._update_tree_incremental)

        threading.Thread(target=run, daemon=True).start()

    def _scan_local(self):
        d = filedialog.askdirectory(initialdir=self.dir_var.get())
        if not d:
            return

        self.status_var.set("Scanning...")
        self._append_log(f"Scanning {d}...")

        def run():
            scanner = LocalScanner(self.db)
            results = scanner.scan_directory(d)
            self.root.after(0, lambda: self._append_log(f"Found {len(results)} folders."))
            for r in results:
                self.root.after(0, lambda p=r['path'], c=r['confidence']: self._append_log(f"  {p} ({c:.2f})"))
            self.root.after(0, lambda: self.status_var.set("Scan complete."))
            self.root.after(0, self._update_tree_incremental)

        threading.Thread(target=run, daemon=True).start()

    # ============================================
    # QUEUE
    # ============================================

    def _download_checked_games(self):
        checked_games = []
        for iid in self.checked_items:
            item = self.item_cache.get(iid)
            if item and item["type"] == "game":
                checked_games.append(item)

        if not checked_games:
            messagebox.showinfo("No selection", "Check games in the tree to download.")
            return

        # Pause background scraping for download priority
        was_scraping = self._scraping_running
        if was_scraping:
            self._append_log("[PRIORITY] Pausing background scraping for downloads...")
            self._scraping_running = False
            if self.discovery_engine:
                self.discovery_engine.stop_continuous()

        self.status_var.set(f"[PRIORITY] Downloading {len(checked_games)} games...")
        self._append_log(f"[PRIORITY] Starting download of {len(checked_games)} games...")

        def run():
            from vgm_scraper.acquisition.downloader import Downloader
            downloader = Downloader(DEFAULT_DOWNLOAD_DIR)

            for i, game in enumerate(checked_games):
                self.root.after(0, lambda idx=i, t=len(checked_games): self.progress.configure(maximum=t, value=idx + 1))
                self.root.after(0, lambda g=game: self._append_log(f"  [PRIORITY] Downloading: {g['title']}"))

                resource = self._find_download_resource(game)

                if not resource:
                    self.root.after(0, lambda g=game: self._append_log(f"  SKIP: {g['title']} - no download URL found"))
                    continue

                dl_url = self._resolve_download_url_for_resource(resource)
                result = downloader.download_and_extract(
                    url=resource["url"],
                    download_url=dl_url,
                    title=game["title"],
                    console=game["console"],
                )

                if result["success"]:
                    # Extract and create tracks from actual files
                    track_count = 0
                    extracted_files = result.get("files", [])
                    coll_id = self.db.get_or_create_collection(
                        game_id=game["id"],
                        title=game["title"],
                        source_url=resource["url"],
                    )

                    self.db.add_audition_event(
                        resource_id=resource["id"],
                        game_id=game["id"],
                        event_type="download_verified",
                        status="needs_audition",
                        details={
                            "pack_dir": result["pack_dir"],
                            "archive_path": result.get("archive_path"),
                            "archive_member_count": result.get("archive_member_count", 0),
                            "extracted_file_count": len(extracted_files),
                            "skipped_file_count": len(result.get("skipped_files", [])),
                        },
                    )

                    for track_number, filepath in enumerate(extracted_files, 1):
                        if os.path.exists(filepath):
                            filename = os.path.basename(filepath)
                            title = os.path.splitext(filename)[0]
                            fmt = os.path.splitext(filename)[1].lower()
                            size = os.path.getsize(filepath)
                            member = os.path.relpath(filepath, result["pack_dir"])

                            track_id = self.db.get_or_create_track(
                                title=title,
                                collection_id=coll_id,
                                game_id=game["id"],
                                track_number=track_number,
                                format_hint=fmt,
                            )

                            # Register local file
                            fp = downloader.fingerprint_file(filepath)
                            self.db.add_local_file(track_id, filepath, size, fp)
                            self.db.link_resource_to_track(resource["id"], track_id, is_primary=1)
                            self.db.add_provenance_event(
                                resource_id=resource["id"],
                                track_id=track_id,
                                event_type="track_extracted",
                                details=f"Archive member: {member}",
                            )
                            self.db.add_audition_event(
                                resource_id=resource["id"],
                                game_id=game["id"],
                                track_id=track_id,
                                event_type="track_extracted",
                                status="needs_audition",
                                details={
                                    "archive_member": member,
                                    "file_path": filepath,
                                    "size_bytes": size,
                                    "format": fmt,
                                },
                            )
                            track_count += 1

                    self.root.after(0, lambda g=game, c=track_count: self._append_log(f"  OK: {g['title']} ({c} tracks)"))
                    # Immediately refresh queue and tree so player sees files
                    self.root.after(0, self._update_tree_incremental)
                    self.root.after(0, self._refresh_queue_view)
                else:
                    skipped_count = len(result.get("skipped_files", []))
                    member_count = result.get("archive_member_count", 0)
                    self.db.add_provenance_event(
                        resource_id=resource["id"],
                        event_type="download_failed",
                        details=(
                            f"{result.get('error')}; archive_members={member_count}; "
                            f"skipped_files={skipped_count}; archive={result.get('archive_path')}"
                        ),
                    )
                    self.db.add_audition_event(
                        resource_id=resource["id"],
                        game_id=game["id"],
                        event_type="download_failed",
                        status="empty_extract" if member_count else "failed",
                        details={
                            "error": result.get("error"),
                            "archive_path": result.get("archive_path"),
                            "archive_member_count": member_count,
                            "skipped_files": result.get("skipped_files", []),
                        },
                    )
                    self.root.after(
                        0,
                        lambda g=game, e=result.get("error"), m=member_count, s=skipped_count:
                            self._append_log(f"  FAIL: {g['title']} - {e} ({m} members, {s} skipped)")
                    )

            # Resume background scraping if it was running
            if was_scraping:
                self.root.after(0, lambda: self._append_log("[PRIORITY] Downloads complete. Resuming background scraping..."))
                self.root.after(0, lambda: self._resume_scraping())
            else:
                self.root.after(0, lambda: self.status_var.set("Download complete."))
                self.root.after(0, self._update_tree_incremental)
                self.root.after(0, self._refresh_queue_view)

        threading.Thread(target=run, daemon=True).start()

    def _find_download_resource(self, game: dict):
        """Prefer the selected source URL, then fall back to title matching."""
        from vgm_scraper.acquisition.console_classifier import classify_console

        with self.db.connect() as conn:
            if game.get("resource_id"):
                row = conn.execute(
                    """SELECT id, title, url, download_url FROM resource_nodes
                       WHERE id = ?
                       LIMIT 1""",
                    (game["resource_id"],),
                ).fetchone()
                if row:
                    return row

            if game.get("download_url"):
                row = conn.execute(
                    """SELECT id, title, url, download_url FROM resource_nodes
                       WHERE node_type = 'pack' AND download_url = ?
                       LIMIT 1""",
                    (game["download_url"],),
                ).fetchone()
                if row:
                    return row

            if game.get("source_url"):
                row = conn.execute(
                    """SELECT id, title, url, download_url FROM resource_nodes
                       WHERE node_type = 'pack' AND url = ?
                       LIMIT 1""",
                    (game["source_url"],),
                ).fetchone()
                if row:
                    return row

            rows = conn.execute(
                """SELECT id, title, url, download_url FROM resource_nodes
                   WHERE node_type = 'pack' AND title = ?
                   ORDER BY download_url DESC, discovered_at DESC
                   LIMIT 25""",
                (game["title"],),
            ).fetchall()

            expected = classify_console(game.get("console", ""))
            for row in rows:
                actual = classify_console(row["download_url"], row["url"], row["title"])
                if expected.is_known and actual.slug == expected.slug:
                    return row

            if rows:
                self._append_log(
                    f"  SKIP: {game['title']} - title matched resources, but none matched {game.get('console')}"
                )
            return None

    def _resolve_download_url_for_resource(self, resource):
        """Resolve detail-page URLs to real downloadable files when needed."""
        download_url = resource["download_url"] or ""
        page_url = resource["url"] or ""
        candidate = download_url or page_url

        if self._looks_like_download_url(candidate):
            return candidate

        if "zophar.net/music/" in page_url:
            try:
                from vgm_scraper.acquisition.sources.zophar import ZopharSource
                resolved = ZopharSource(self.session, self.db).resolve_original_download_url(page_url)
                if resolved:
                    with self.db.connect() as conn:
                        conn.execute(
                            "UPDATE resource_nodes SET download_url = ? WHERE id = ?",
                            (resolved, resource["id"]),
                        )
                    self._append_log(f"  Resolved Zophar download: {resolved}")
                    return resolved
            except Exception as e:
                self._append_log(f"  Zophar download resolver failed: {e}")

        return candidate

    @staticmethod
    def _looks_like_download_url(url: str) -> bool:
        lowered = (url or "").lower().split("?")[0]
        return lowered.endswith((".zip", ".7z", ".rar", ".vgm", ".vgz", ".nsf", ".spc", ".gsf", ".gbs", ".usf", ".psf", ".ssf", ".dsf"))

    def _resume_scraping(self):
        """Resume background scraping after priority downloads complete."""
        self._scraping_running = True
        self._update_scraping_buttons()
        try:
            interval = int(self.discovery_interval.get() or 3600)
            max_sites = int(self.discovery_max.get() or 10)
            self.discovery_engine = DiscoveryEngine(self.db, self.session)
            self.discovery_engine.start_continuous(interval=interval, max_sites=max_sites)
        except Exception as e:
            self._append_log(f"Discovery resume error: {e}")
        self._crawl_sources()

    def _process_jobs(self):
        self.status_var.set("Processing jobs...")
        self._append_log("Processing pending retrieval jobs...")

        def run():
            results = self.retrieval.process_pending_jobs()
            for r in results:
                self.root.after(0, lambda j=r['job_id'], s=r['status']: self._append_log(f"  Job {j}: {s}"))
            self.root.after(0, lambda: self.status_var.set("Jobs processed."))
            self.root.after(0, self._update_tree_incremental)
            self.root.after(0, self._refresh_queue_view)

        threading.Thread(target=run, daemon=True).start()

    def _clear_queue(self):
        for child in self.queue_tree.get_children():
            self.queue_tree.delete(child)
        self.queue_count.configure(text="0 items")
        self._append_log("Queue cleared.")

    # ============================================
    # TREE HELPERS
    # ============================================

    def _check_all(self):
        for iid in self.item_cache:
            self.checked_items.add(iid)
            self._set_check_state(iid, True)

    def _uncheck_all(self):
        self.checked_items.clear()
        for iid in self.item_cache:
            self._set_check_state(iid, False)

    def _expand_all(self):
        def _expand(iid):
            self.tree.item(iid, open=True)
            for child in self.tree.get_children(iid):
                _expand(child)
        for child in self.tree.get_children():
            _expand(child)

    def _collapse_all(self):
        for child in self.tree.get_children():
            self.tree.item(child, open=False)


def main():
    root = tk.Tk()
    root.lift()
    root.attributes('-topmost', True)
    root.after(200, lambda: root.attributes('-topmost', False))
    try:
        app = VGMScraperGUI(root)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"GUI startup error: {e}\n{tb}")
        messagebox.showerror("Startup Error", f"{e}\n\n{tb}")
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
