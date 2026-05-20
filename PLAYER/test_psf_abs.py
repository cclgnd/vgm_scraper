import sys; sys.path.insert(0, '.')
from pathlib import Path
import subprocess
import os
import numpy as np

# Test PSF helper with ABSOLUTE path
psf_file = Path('chiptunes/Sony PlayStation/01_shinobinoroku-00.psf').resolve()
helper = Path('engines/aopsf/aopsf_helper.exe').resolve()

print(f'Testing PSF with absolute path: {psf_file}')

creationflags = 0
if os.name == 'nt':
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

proc = subprocess.Popen(
    [str(helper), str(psf_file)],
    cwd=str(helper.parent),
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    startupinfo=startupinfo,
    creationflags=creationflags,
)

import time
time.sleep(1)
data = proc.stdout.read(4096)
samples = np.frombuffer(data[:len(data) - (len(data) % 4)], dtype=np.int16).reshape(-1, 2)
non_zero = np.count_nonzero(samples)
print(f'PSF (absolute): {non_zero}/{len(samples)} non-zero, peak={np.max(np.abs(samples))}')

proc.kill()
proc.wait()
stderr = proc.stderr.read().decode('utf-8', errors='replace')
print(f'Stderr: {stderr[:200]}')
