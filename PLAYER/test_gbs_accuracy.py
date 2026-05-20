import sys; sys.path.insert(0, '.')
import os
import ctypes
from simpleplayer.engines.gme import GmeEngine, _library_candidates
from pathlib import Path
import numpy as np

# Load libgme directly to test accuracy mode
lib = ctypes.CDLL('engines/libgme.dll')

# Configure gme_enable_accuracy
lib.gme_enable_accuracy.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.gme_enable_accuracy.restype = ctypes.c_char_p

# Configure gme_set_equalizer
lib.gme_set_equalizer.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lib.gme_set_equalizer.restype = ctypes.c_char_p

# Open a GBS file
emu = ctypes.c_void_p()
gbs_path = Path('chiptunes/Nintendo Game Boy/01_4-in-1 funpak 1.gbs').resolve()
err = lib.gme_open_file(os.fsencode(gbs_path), ctypes.byref(emu), 48000)
if err:
    print('Open error:', err)
    exit(1)

print('Opened GBS file')

# Test WITHOUT accuracy mode
buf1 = (ctypes.c_short * 9600)()
err = lib.gme_play(emu, 9600, buf1)
samples1 = np.frombuffer(bytes(buf1), dtype=np.int16)

# Reset track
err = lib.gme_start_track(emu, 0)
if err:
    print('Start error:', err)

# Enable accuracy mode
err = lib.gme_enable_accuracy(emu, 1)
if err:
    print('Accuracy error:', err)
else:
    print('Accuracy mode enabled')

# Test WITH accuracy mode
buf2 = (ctypes.c_short * 9600)()
err = lib.gme_play(emu, 9600, buf2)
samples2 = np.frombuffer(bytes(buf2), dtype=np.int16)

print('Without accuracy:')
print('  Non-zero:', np.count_nonzero(samples1))
print('  Peak:', np.max(np.abs(samples1.astype(np.int32))))
print('  Mean abs:', np.mean(np.abs(samples1.astype(np.int32))))
print('  Unique values:', len(np.unique(samples1)))

print('With accuracy:')
print('  Non-zero:', np.count_nonzero(samples2))
print('  Peak:', np.max(np.abs(samples2.astype(np.int32))))
print('  Mean abs:', np.mean(np.abs(samples2.astype(np.int32))))
print('  Unique values:', len(np.unique(samples2)))

# Check if they're different
diff = np.abs(samples1.astype(np.int32) - samples2.astype(np.int32))
print('Max difference:', np.max(diff))
print('Mean difference:', np.mean(diff))

lib.gme_delete(emu)
