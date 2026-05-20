import sys
import os
import traceback

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

error_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gui_error.txt')

try:
    import tkinter as tk
    root = tk.Tk()
    root.title('VGM Scraper')
    root.geometry('1200x800')
    root.lift()
    root.attributes('-topmost', True)
    root.after(200, lambda: root.attributes('-topmost', False))
    
    from vgm_scraper.gui import VGMScraperGUI
    app = VGMScraperGUI(root)
    root.mainloop()
except Exception as e:
    tb = traceback.format_exc()
    with open(error_file, 'w') as f:
        f.write(f'{e}\n\n{tb}')
    print(f'ERROR: {e}')
    print(tb)
