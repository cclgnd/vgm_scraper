from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


SAMPLE_RATE = 48_000
CHANNELS = 2


@dataclass(frozen=True)
class TrackInfo:
    index: int
    title: str
    game: str = ""
    system: str = ""
    author: str = ""
    length_ms: int = -1
    play_length_ms: int = -1


class EngineError(RuntimeError):
    pass


class AudioEngine(Protocol):
    display_name: str
    supported_extensions: set[str]

    @staticmethod
    def is_supported(path: Path) -> bool:
        ...

    @property
    def path(self) -> Path | None:
        ...

    @property
    def current_track(self) -> int:
        ...

    def open(self, path: Path, track: int = 0) -> list[TrackInfo]:
        ...

    def close(self) -> None:
        ...

    def tracks(self) -> list[TrackInfo]:
        ...

    def start_track(self, index: int) -> None:
        ...

    def seek_ms(self, position_ms: int) -> None:
        ...

    def tell_ms(self) -> int:
        ...

    def render(self, frames: int):
        ...
