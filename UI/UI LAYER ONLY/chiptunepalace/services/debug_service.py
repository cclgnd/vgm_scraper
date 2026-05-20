import os
import sys
import logging
import traceback
from datetime import datetime

class DebugService:
    """
    Centralized logging and debugging service for Chiptune Palace.
    Handles user interaction logging, system warning/error logging, and global unhandled exception tracking.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DebugService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        # Get project root folder
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.log_filepath = os.path.join(root_dir, "chiptunepalace_debug.log")
        
        # Configure standard Logger
        self.logger = logging.getLogger("ChiptunePalace")
        self.logger.setLevel(logging.INFO)
        
        # Avoid duplicate handlers if re-initialized
        if not self.logger.handlers:
            # File Handler
            try:
                fh = logging.FileHandler(self.log_filepath, encoding="utf-8")
                fh.setLevel(logging.INFO)
                formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s')
                fh.setFormatter(formatter)
                self.logger.addHandler(fh)
            except Exception as e:
                print(f"DebugService: Failed to open log file {self.log_filepath}: {e}", file=sys.stderr)
                
            # Stream Handler (Stdout)
            sh = logging.StreamHandler(sys.stdout)
            sh.setLevel(logging.INFO)
            formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s')
            sh.setFormatter(formatter)
            self.logger.addHandler(sh)
            
        self._initialized = True
        self.log_info("DebugService initialized. Log file path: " + self.log_filepath)

    def log_interaction(self, action: str, details: str = None):
        """Logs user interactions like button clicks, volume changes, and menu selection."""
        msg = f"[INTERACTION] User triggered: {action}"
        if details:
            msg += f" ({details})"
        self.logger.info(msg)

    def log_info(self, message: str):
        """Logs informational system states."""
        self.logger.info(message)

    def log_warning(self, message: str):
        """Logs standard warning alerts."""
        self.logger.warning(message)

    def log_error(self, message: str, exc_info=None):
        """Logs errors and optional exception stack traces."""
        self.logger.error(message, exc_info=exc_info)

    def install_excepthook(self):
        """Installs global exception hook to capture any uncaught thread or main loop crashes."""
        sys.excepthook = self.sys_exception_hook
        self.log_info("Global unhandled exception hook installed successfully.")

    def sys_exception_hook(self, exctype, value, tb):
        """Intercepts unhandled Python runtime crashes and logs them before exiting."""
        err_msg = "".join(traceback.format_exception(exctype, value, tb))
        self.logger.critical(f"[UNCAUGHT_CRASH] Unhandled Exception:\n{err_msg}")
        
        # Call original excepthook to preserve standard console printing/behavior
        sys.__excepthook__(exctype, value, tb)
