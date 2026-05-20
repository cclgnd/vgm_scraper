from __future__ import annotations

import atexit
import os
import subprocess
import ctypes
from pathlib import Path
from threading import RLock

import numpy as np

from .base import CHANNELS, SAMPLE_RATE, EngineError, TrackInfo


_SOURCE_HELPER_PROCESSES: list[subprocess.Popen[bytes]] = []


def _cleanup_helpers() -> None:
    for proc in _SOURCE_HELPER_PROCESSES:
        try:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=2)
        except Exception:
            pass
    _SOURCE_HELPER_PROCESSES.clear()


atexit.register(_cleanup_helpers)


SOURCE_SAMPLE_RATE = 44_100


class VgmEngineError(EngineError):
    pass


class VgmEngine:
    display_name = "VGM / libvgm"
    supported_extensions = {".s98", ".dro", ".vgm", ".vgz"}

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        self.sample_rate = sample_rate
        self._lock = RLock()
        self._helper = self._helper_path()
        self._process: subprocess.Popen[bytes] | None = None
        self._path: Path | None = None
        self._current_track = 0
        self._pending = np.empty((0, CHANNELS), dtype=np.int16)
        self._source_phase = 0.0
        self._rendered_frames = 0
        self._title = ""
        self._system = ""

    @staticmethod
    def is_supported(path: Path) -> bool:
        return path.suffix.lower() in VgmEngine.supported_extensions

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def current_track(self) -> int:
        return self._current_track

    def open(self, path: Path, track: int = 0) -> list[TrackInfo]:
        if not path.exists():
            raise VgmEngineError(f"File does not exist: {path}")
        if not self.is_supported(path):
            raise VgmEngineError(f"Unsupported format: {path.suffix or '(none)'}")

        with self._lock:
            self.close()
            self._path = path
            self._current_track = 0
            self._pending = np.empty((0, CHANNELS), dtype=np.int16)
            self._source_phase = 0.0
            self._rendered_frames = 0
            self._start_helper()
            suffix = path.suffix.lower()
            system_map = {
                ".s98": "S98",
                ".dro": "DRO",
            }
            self._system = system_map.get(suffix, suffix.upper())
            self._title = path.stem
            return [TrackInfo(index=0, title=self._title, system=self._system)]

    def close(self) -> None:
        with self._lock:
            if self._process:
                process = self._process
                self._process = None
                if process in _SOURCE_HELPER_PROCESSES:
                    _SOURCE_HELPER_PROCESSES.remove(process)
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=1)
                if process.stdout:
                    process.stdout.close()
                if process.stderr:
                    process.stderr.close()
            self._path = None
            self._current_track = 0
            self._pending = np.empty((0, CHANNELS), dtype=np.int16)
            self._source_phase = 0.0
            self._rendered_frames = 0
            self._title = ""
            self._system = ""

    def tracks(self) -> list[TrackInfo]:
        if not self._path:
            return []
        return [TrackInfo(index=0, title=self._title, system=self._system)]

    def start_track(self, index: int) -> None:
        if index != 0:
            raise VgmEngineError("VGM files expose one streamed track per file.")
        if self._path:
            self.open(self._path)

    def seek_ms(self, position_ms: int) -> None:
        if position_ms != 0:
            raise VgmEngineError("VGM seeking is not implemented yet; restart is supported.")
        if self._path:
            self.open(self._path)

    def tell_ms(self) -> int:
        return int(self._rendered_frames * 1000 / SAMPLE_RATE)

    def render(self, frames: int):
        sample_count = frames * CHANNELS
        buffer_type = ctypes.c_short * sample_count
        if frames <= 0:
            return buffer_type()

        with self._lock:
            if not self._process or not self._process.stdout:
                return buffer_type()

            needed_source_frames = int(self._source_phase + (frames - 1) * SOURCE_SAMPLE_RATE / SAMPLE_RATE) + 2
            self._fill_pending(needed_source_frames)

            if len(self._pending) < 2:
                return buffer_type()

            positions = self._source_phase + (SOURCE_SAMPLE_RATE / SAMPLE_RATE) * np.arange(frames)
            indices = np.floor(positions).astype(np.int64)
            fractions = (positions - indices).astype(np.float32)[:, None]
            max_index = len(self._pending) - 2
            clipped_indices = np.clip(indices, 0, max_index)

            left = self._pending[clipped_indices].astype(np.float32)
            right = self._pending[clipped_indices + 1].astype(np.float32)
            out = np.clip(left + (right - left) * fractions, -32768, 32767).astype(np.int16)

            total_source_advance = self._source_phase + frames * SOURCE_SAMPLE_RATE / SAMPLE_RATE
            consume = int(total_source_advance)
            self._source_phase = total_source_advance - consume
            if consume > 0:
                self._pending = self._pending[min(consume, len(self._pending)):]
            self._rendered_frames += frames

            return (ctypes.c_short * sample_count)(*out.reshape(-1))

    def _fill_pending(self, minimum_frames: int) -> None:
        assert self._process and self._process.stdout
        missing_frames = minimum_frames - len(self._pending)
        if missing_frames <= 0:
            return

        data = self._process.stdout.read(missing_frames * CHANNELS * 2)
        if not data:
            padding = np.zeros((missing_frames, CHANNELS), dtype=np.int16)
            self._pending = np.vstack([self._pending, padding])
            return

        usable = len(data) - (len(data) % (CHANNELS * 2))
        samples = np.frombuffer(data[:usable], dtype=np.int16).reshape(-1, CHANNELS)
        if len(samples) < missing_frames:
            padding = np.zeros((missing_frames - len(samples), CHANNELS), dtype=np.int16)
            samples = np.vstack([samples, padding])
        self._pending = np.vstack([self._pending, samples])

    def _start_helper(self) -> None:
        if not self._path:
            raise VgmEngineError("No VGM file loaded.")
        if not self._helper.exists():
            raise VgmEngineError(
                f"VGM helper is not built: {self._helper}. Run native/vgm/build_vgm.py first."
            )

        creationflags = 0
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        abs_path = str(self._path.resolve())
        self._process = subprocess.Popen(
            [str(self._helper), abs_path],
            cwd=str(self._helper.parent),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        _SOURCE_HELPER_PROCESSES.append(self._process)

    def voice_names(self) -> list[str]:
        return []

    def mute_voice(self, index: int, muted: bool) -> None:
        pass

    @staticmethod
    def _helper_path() -> Path:
        return Path(__file__).resolve().parents[2] / "engines" / "vgm_helper.exe"
