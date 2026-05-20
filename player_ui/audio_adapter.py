from __future__ import annotations

from pathlib import Path


class AudioAdapterError(RuntimeError):
    pass


class PlayerAudioAdapter:
    """Thin UI wrapper over the salvaged audio engine."""

    def __init__(self):
        self._output = None
        self._engine = None
        self._registry = None
        self._import_error = None

    def _ensure_ready(self):
        if self._registry is not None and self._output is not None:
            return
        try:
            from audio_engine.simpleplayer.audio import RealtimeAudioOutput
            from audio_engine.simpleplayer.engines.registry import BackendRegistry
        except Exception as exc:
            self._import_error = exc
            raise AudioAdapterError(f"Audio engine unavailable: {exc}") from exc

        self._registry = BackendRegistry()
        self._output = RealtimeAudioOutput()

    def play_file(self, file_path: str) -> str:
        path = Path(file_path)
        if not path.exists():
            raise AudioAdapterError(f"Local file not found: {file_path}")

        self._ensure_ready()
        self.stop()

        try:
            engine = self._registry.create_for(path)
            engine.open(path)
            self._output.set_engine(engine)
            self._output.start()
            self._output.playing = True
            self._engine = engine
        except Exception as exc:
            raise AudioAdapterError(f"Playback failed: {exc}") from exc

        return engine.display_name

    def toggle_pause(self) -> bool:
        self._ensure_ready()
        if not self._output.engine:
            return False
        self._output.playing = not self._output.playing
        return self._output.playing

    def stop(self):
        if self._output:
            self._output.playing = False
            self._output.stop()
        if self._engine:
            try:
                self._engine.close()
            except Exception:
                pass
        self._engine = None
