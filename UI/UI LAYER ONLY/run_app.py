import sys
import os

# Add the project root to the system path to allow internal module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chiptunepalace.gui.main_window import main

if __name__ == "__main__":
    main()