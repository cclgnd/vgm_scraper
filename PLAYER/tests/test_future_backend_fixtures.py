from __future__ import annotations

import json
import unittest
from pathlib import Path

from simpleplayer.engines import BackendRegistry, BackendUnavailableError, EngineError


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "chiptunes"
MANIFEST = FIXTURES / "MANIFEST.json"


class FutureBackendFixtureTests(unittest.TestCase):
    def test_future_fixture_manifest_has_requested_counts(self) -> None:
        if not MANIFEST.exists():
            self.skipTest("Future fixture manifest not downloaded yet.")
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        counts = manifest.get("counts", {})
        self.assertTrue(counts, "future fixture manifest has no files")
        for extension, count in counts.items():
            self.assertLessEqual(count, 10, extension)

    def test_available_future_backends_render_their_fixtures(self) -> None:
        if not MANIFEST.exists():
            self.skipTest("Future fixture manifest not downloaded yet.")

        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        registry = BackendRegistry()
        failures: list[str] = []
        rendered = 0

        for item in manifest.get("files", []):
            path = ROOT / item["path"]
            spec = registry.find(path)
            if spec is None or not spec.available:
                continue
            engine = None
            try:
                engine = registry.create_for(path)
                tracks = engine.open(path)
                self.assertGreaterEqual(len(tracks), 1, str(path))
                # Try to find a track that has sound (e.g. try first 3 tracks for multi-track files)
                peak = 0
                max_tracks_to_try = min(len(tracks), 3)
                for track_idx in range(max_tracks_to_try):
                    if track_idx > 0:
                        engine.start_track(track_idx)
                    
                    # Render up to 5 seconds to skip initial silence
                    peak = 0
                    for _ in range(5):
                        pcm = engine.render(48_000)
                        self.assertEqual(len(pcm), 96_000, str(path))
                        track_peak = max(abs(int(sample)) for sample in pcm)
                        if track_peak > peak:
                            peak = track_peak
                        if peak > 16:
                            break
                    if peak > 16:
                        break

                self.assertGreater(peak, 16, str(path))
                rendered += 1
            except (BackendUnavailableError, EngineError, OSError, AssertionError) as exc:
                failures.append(f"{path.relative_to(ROOT)}: {exc}")
            finally:
                if engine:
                    engine.close()

        if failures:
            self.fail("\n".join(failures[:25]))
        if rendered == 0:
            self.skipTest("No future backends are active yet.")


if __name__ == "__main__":
    unittest.main()
