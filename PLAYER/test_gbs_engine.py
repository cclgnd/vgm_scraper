import sys; sys.path.insert(0, '.')
import os
from pathlib import Path
from simpleplayer.engines.gme import GmeEngine
import numpy as np

# Test with current engine (no accuracy mode)
engine = GmeEngine()
gbs = Path('chiptunes/Nintendo Game Boy/01_4-in-1 funpak 1.gbs').resolve()
engine.open(gbs)

buf = engine.render(4800)
samples = np.frombuffer(bytes(buf), dtype=np.int16)
non_zero = np.count_nonzero(samples)
print('Default engine (no accuracy):')
print('  Non-zero:', non_zero, '/', len(samples))
print('  Peak:', np.max(np.abs(samples.astype(np.int32))))
engine.close()

# Now test with accuracy enabled by modifying the engine
engine2 = GmeEngine()
gbs2 = Path('chiptunes/Nintendo Game Boy/01_4-in-1 funpak 1.gbs').resolve()
engine2.open(gbs2)

# Enable accuracy
err = engine2._lib.gme_enable_accuracy(engine2._emu, 1)
if err:
    print('Accuracy error:', err)
else:
    print('Accuracy enabled successfully')

buf2 = engine2.render(4800)
samples2 = np.frombuffer(bytes(buf2), dtype=np.int16)
non_zero2 = np.count_nonzero(samples2)
print('Engine with accuracy:')
print('  Non-zero:', non_zero2, '/', len(samples2))
print('  Peak:', np.max(np.abs(samples2.astype(np.int32))))
engine2.close()
