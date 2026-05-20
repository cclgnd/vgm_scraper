"""
Logging system for VGM Scraper.

- Daily log file: one file per day, appends all activity
- Error log: separate file per day, only errors for review
- Console output: optional mirror to stdout
"""

import os
import logging
import datetime
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)


class VGMSLogger:
    """Manages daily log files and error-only logs."""

    def __init__(self, log_dir: str = LOG_DIR, verbose: bool = False):
        self.log_dir = log_dir
        self.verbose = verbose
        self._today = None
        self._daily_logger = None
        self._error_logger = None
        self._setup_loggers()

    def _get_date_str(self) -> str:
        return datetime.datetime.now().strftime("%Y-%m-%d")

    def _setup_loggers(self):
        today = self._get_date_str()

        # Daily log (all activity)
        daily_path = os.path.join(self.log_dir, f"scraper_{today}.log")
        self._daily_logger = logging.getLogger("vgm_scraper.daily")
        self._daily_logger.setLevel(logging.DEBUG)
        if not self._daily_logger.handlers:
            handler = logging.FileHandler(daily_path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
            self._daily_logger.addHandler(handler)

        # Error-only log (only errors and warnings)
        error_path = os.path.join(self.log_dir, f"errors_{today}.log")
        self._error_logger = logging.getLogger("vgm_scraper.errors")
        self._error_logger.setLevel(logging.WARNING)
        if not self._error_logger.handlers:
            handler = logging.FileHandler(error_path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
            self._error_logger.addHandler(handler)

        # Root logger for console output (optional)
        if self.verbose:
            root = logging.getLogger("vgm_scraper")
            root.setLevel(logging.DEBUG)
            if not root.handlers:
                console = logging.StreamHandler()
                console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
                root.addHandler(console)

    def _check_rotate(self):
        """Rotate to new day's files if date changed."""
        today = self._get_date_str()
        if today != self._today:
            self._today = today
            self._setup_loggers()

    def info(self, message: str, source: str = "system"):
        self._check_rotate()
        self._daily_logger.info(f"[{source}] {message}")

    def warning(self, message: str, source: str = "system"):
        self._check_rotate()
        self._daily_logger.warning(f"[{source}] {message}")
        self._error_logger.warning(f"[{source}] {message}")

    def error(self, message: str, source: str = "system", exc_info: bool = False):
        self._check_rotate()
        self._daily_logger.error(f"[{source}] {message}", exc_info=exc_info)
        self._error_logger.error(f"[{source}] {message}", exc_info=exc_info)

    def debug(self, message: str, source: str = "system"):
        self._check_rotate()
        self._daily_logger.debug(f"[{source}] {message}")

    def get_daily_log_path(self) -> str:
        return os.path.join(self.log_dir, f"scraper_{self._get_date_str()}.log")

    def get_error_log_path(self) -> str:
        return os.path.join(self.log_dir, f"errors_{self._get_date_str()}.log")

    def get_log_files(self) -> list[str]:
        """List all log files, sorted by date."""
        if not os.path.exists(self.log_dir):
            return []
        files = []
        for f in os.listdir(self.log_dir):
            if f.endswith(".log"):
                files.append(os.path.join(self.log_dir, f))
        return sorted(files)

    def read_log(self, filename: str, max_lines: int = 500) -> str:
        """Read a log file, returning last N lines."""
        filepath = os.path.join(self.log_dir, filename)
        if not os.path.exists(filepath):
            return ""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
                return "".join(lines[-max_lines:])
        except Exception:
            return ""


# Global logger instance
_logger = None


def get_logger() -> VGMSLogger:
    global _logger
    if _logger is None:
        _logger = VGMSLogger()
    return _logger
