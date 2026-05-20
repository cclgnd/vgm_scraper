import os
import sys
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock

from chiptunepalace.services.debug_service import DebugService

class TestDebugLogging(unittest.TestCase):
    def setUp(self):
        # We will initialize the DebugService to make sure it exists
        self.debug_service = DebugService()
        self.log_filepath = self.debug_service.log_filepath

    def test_singleton_pattern(self):
        """Verifies that DebugService is a strict singleton."""
        ds2 = DebugService()
        self.assertIs(self.debug_service, ds2)

    def test_log_file_creation_and_formatting(self):
        """Verifies that logging creates the file and formats logs correctly."""
        # Ensure log file exists (it gets created upon init)
        self.assertTrue(os.path.exists(self.log_filepath))
        
        # Capture current log size or clean file content for parsing
        test_interaction_msg = "test_interaction_button_click"
        test_details = "Button=Play"
        self.debug_service.log_interaction(test_interaction_msg, test_details)
        
        # Read the log file and verify contains elements
        with open(self.log_filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        self.assertIn("[INTERACTION]", content)
        self.assertIn(test_interaction_msg, content)
        self.assertIn(test_details, content)
        
        # Test standard info, warning and errors
        self.debug_service.log_info("Test System Info Message")
        self.debug_service.log_warning("Test System Warning Message")
        self.debug_service.log_error("Test System Error Message")
        
        with open(self.log_filepath, "r", encoding="utf-8") as f:
            updated_content = f.read()
            
        self.assertIn("[INFO]", updated_content)
        self.assertIn("Test System Info Message", updated_content)
        self.assertIn("[WARNING]", updated_content)
        self.assertIn("Test System Warning Message", updated_content)
        self.assertIn("[ERROR]", updated_content)
        self.assertIn("Test System Error Message", updated_content)

    def test_sys_exception_hook_capture(self):
        """Verifies that sys_exception_hook intercepts and formats uncaught exceptions correctly."""
        # Manually invoke the exception hook
        try:
            raise ValueError("Uncaught crash test exception!")
        except ValueError as e:
            exctype, value, tb = sys.exc_info()
            
            # Temporarily replace standard __excepthook__ with dummy to avoid console stderr spam
            with patch('sys.__excepthook__') as mock_sys_hook:
                self.debug_service.sys_exception_hook(exctype, value, tb)
                mock_sys_hook.assert_called_once_with(exctype, value, tb)
                
        # Verify it was logged under CRITICAL uncaught crash header
        with open(self.log_filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        self.assertIn("[CRITICAL]", content)
        self.assertIn("[UNCAUGHT_CRASH] Unhandled Exception:", content)
        self.assertIn("ValueError: Uncaught crash test exception!", content)

if __name__ == '__main__':
    unittest.main()
