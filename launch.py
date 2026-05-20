import sys
import os
import traceback

# Ensure parent directory is in path so vgm_scraper package is found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from vgm_scraper.gui import main
    main()
except Exception as e:
    error_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'startup_error.txt')
    with open(error_file, 'w') as f:
        f.write(f'{e}\n\n{traceback.format_exc()}')
    print(f'Error: {e}')
    print(traceback.format_exc())
    input('Press Enter to exit...')
