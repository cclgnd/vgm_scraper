import sys, os
sys.path.insert(0, '.')
os.chdir('D:\\SIMPLEPLAYER')

from pathlib import Path
from simpleplayer.engines.registry import BackendRegistry
from simpleplayer.engines.base import SAMPLE_RATE, CHANNELS
import numpy as np

registry = BackendRegistry()

fixtures = {}
for ext in registry.supported_extensions():
    for p in Path('chiptunes').rglob(f'*{ext}'):
        if '.lib' not in p.name.lower() and not p.name.startswith('.'):
            fixtures[ext] = p
            break

results = []
for ext in sorted(fixtures.keys()):
    path = fixtures[ext].resolve()
    spec = registry.find(path)
    
    if not spec or not spec.factory:
        results.append((ext, path.name, 'SKIP', 'No factory'))
        continue
    
    try:
        engine = spec.factory()
        tracks = engine.open(path)
        
        # Render 5 batches of 1000 frames
        all_samples = []
        for i in range(5):
            buf = engine.render(1000)
            samples = np.frombuffer(bytes(buf), dtype=np.int16)
            all_samples.append(samples)
        
        combined = np.concatenate(all_samples)
        non_zero = np.count_nonzero(combined)
        total = len(combined)
        peak = np.max(np.abs(combined.astype(np.int32)))
        mean = np.mean(np.abs(combined.astype(np.int32)))
        
        # Check for clipping
        clipped = np.sum(np.abs(combined) >= 32767)
        
        status = 'OK' if non_zero > 0 else 'SILENT'
        results.append((ext, path.name, status, f'{non_zero}/{total} non-zero, peak={peak}, mean={mean:.1f}, clipped={clipped}'))
        
        engine.close()
    except Exception as e:
        results.append((ext, path.name, 'ERROR', str(e)[:100]))

header = f"{'Format':<12} {'File':<50} {'Status':<8} {'Details'}"
print(header)
print('-' * 140)
for ext, name, status, details in results:
    print(f"{ext:<12} {name:<50} {status:<8} {details}")
