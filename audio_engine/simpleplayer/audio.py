from __future__ import annotations

import numpy as np
import sounddevice as sd

from .engines import AudioEngine
from .engines.base import CHANNELS, SAMPLE_RATE


class RealtimeAudioOutput:
    def __init__(self) -> None:
        self.engine: AudioEngine | None = None
        self.playing = False
        self.volume = 1.0
        self._stream: sd.OutputStream | None = None
        self.device_id: int | None = None

    def set_engine(self, engine: AudioEngine | None) -> None:
        self.playing = False
        self.engine = engine

    def set_device(self, device_id: int | None) -> None:
        if self.device_id == device_id:
            return
        self.device_id = device_id
        if self._stream:
            was_playing = self.playing
            self.stop()
            try:
                self.start()
                self.playing = was_playing
            except Exception as e:
                # Fallback to default device
                self.device_id = None
                try:
                    self.start()
                    self.playing = was_playing
                except Exception:
                    pass
                raise e

    def start(self) -> None:
        if self._stream:
            return
        self._stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=2048,
            latency="high",
            callback=self._callback,
            device=self.device_id,
        )
        self._stream.start()

    def stop(self) -> None:
        if not self._stream:
            return
        self._stream.stop()
        self._stream.close()
        self._stream = None

    def _callback(self, outdata: np.ndarray, frames: int, _time, status) -> None:
        if not self.playing:
            outdata.fill(0)
            return

        try:
            if not self.engine:
                outdata.fill(0)
                return
            raw = self.engine.render(frames)
            pcm = np.ctypeslib.as_array(raw).reshape(frames, CHANNELS)
            if self.volume >= 0.999:
                outdata[:] = pcm
            else:
                outdata[:] = np.clip(pcm.astype(np.float32) * self.volume, -32768, 32767).astype(np.int16)
        except Exception:
            outdata.fill(0)
            self.playing = False
