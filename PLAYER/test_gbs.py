import sys; sys.path.insert(0, '.')
from simpleplayer.engines.gme import GmeEngine
from pathlib import Path
import numpy as np

engine = GmeEngine()
gbs = Path('chiptunes/Nintendo Game Boy/01_4-in-1 funpak 1.gbs').resolve()
engine.open(gbs)

voices = engine.voice_names()
print('Voices:', voices)
print('Voice count:', len(voices))

tracks = engine.tracks()
print('Track count:', len(tracks))
if tracks:
    print('First track:', tracks[0].title)
    print('System:', tracks[0].system)

buf = engine.render(4800)
samples = np.frombuffer(bytes(buf), dtype=np.int16)

dc = np.mean(samples.astype(np.float64))
print('DC offset:', dc)
print('Min:', np.min(samples), 'Max:', np.max(samples))
print('Mean abs:', np.mean(np.abs(samples.astype(np.int32))))

unique_values = len(np.unique(samples))
print('Unique sample values:', unique_values)

diffs = np.diff(samples.astype(np.int32))
big_jumps = np.sum(np.abs(diffs) > 10000)
print('Big jumps (>10k):', big_jumps)

# Check if samples are quantized to 4-bit levels (Game Boy hardware)
# Real Game Boy has 4-bit DAC, so values should be multiples of ~2048
hist = np.histogram(samples, bins=64)
print('Histogram peaks:', np.where(hist[0] > 100)[0])

engine.close()
