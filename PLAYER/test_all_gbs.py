import sys; sys.path.insert(0, '.')
import os
from pathlib import Path
from simpleplayer.engines.gme import GmeEngine
import numpy as np

engine = GmeEngine()

gbs_files = sorted(Path('chiptunes/Nintendo Game Boy').glob('*.gbs'))

for gbs in gbs_files:
    engine.open(gbs.resolve())
    tracks = engine.tracks()
    
    # Render 2 seconds
    all_samples = []
    for i in range(20):
        buf = engine.render(1000)
        samples = np.frombuffer(bytes(buf), dtype=np.int16)
        all_samples.append(samples)
    
    combined = np.concatenate(all_samples)
    non_zero = np.count_nonzero(combined)
    peak = np.max(np.abs(combined.astype(np.int32)))
    mean = np.mean(np.abs(combined.astype(np.int32)))
    dc = np.mean(combined.astype(np.float64))
    
    print(f'{gbs.name}:')
    print(f'  Tracks: {len(tracks)}, System: {tracks[0].system if tracks else "N/A"}')
    print(f'  Non-zero: {non_zero}/{len(combined)}, Peak: {peak}, Mean: {mean:.1f}, DC: {dc:.1f}')
    
    engine.close()
