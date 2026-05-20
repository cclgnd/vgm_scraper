from __future__ import annotations

import unittest
from pathlib import Path

from simpleplayer.engines import BackendRegistry, BackendUnavailableError, EngineError


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "chiptunes"


class ChiptuneFixtureTests(unittest.TestCase):
    def test_downloaded_ready_formats_render_pcm(self) -> None:
        if not FIXTURES.exists():
            self.skipTest("No chiptune fixtures downloaded yet.")

        registry = BackendRegistry()
        ready_extensions = registry.supported_extensions(include_planned=False)
        files = [
            path
            for path in FIXTURES.rglob("*")
            if path.is_file() and path.suffix.lower() in ready_extensions
        ]
        if not files:
            self.skipTest("No ready-format chiptune fixtures found.")

        failures: list[str] = []
        rendered = 0
        for path in files:
            engine = None
            try:
                engine = registry.create_for(path)
                tracks = engine.open(path)
                self.assertGreaterEqual(len(tracks), 1, str(path))
                pcm = engine.render(1024)
                self.assertEqual(len(pcm), 2048, str(path))
                rendered += 1
            except (BackendUnavailableError, EngineError, OSError, AssertionError) as exc:
                failures.append(f"{path.relative_to(ROOT)}: {exc}")
            finally:
                if engine:
                    engine.close()

        if failures:
            self.fail("\n".join(failures[:25]))
        self.assertGreater(rendered, 0)

    def test_kss_fixtures_start_on_audible_selector(self) -> None:
        kss_files = sorted((FIXTURES / "kss").glob("*.kss"))
        if not kss_files:
            self.skipTest("No KSS fixtures found.")

        registry = BackendRegistry()
        failures: list[str] = []
        for path in kss_files:
            engine = None
            try:
                engine = registry.create_for(path)
                tracks = engine.open(path)
                self.assertGreater(len(tracks), 0, str(path))
                pcm = engine.render(48_000)
                peak = max(abs(int(sample)) for sample in pcm)
                self.assertGreater(peak, 16, str(path))
            except (BackendUnavailableError, EngineError, OSError, AssertionError) as exc:
                failures.append(f"{path.relative_to(ROOT)}: {exc}")
            finally:
                if engine:
                    engine.close()

        if failures:
            self.fail("\n".join(failures))


if __name__ == "__main__":
    unittest.main()
