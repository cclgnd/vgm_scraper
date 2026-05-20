from __future__ import annotations

from pathlib import Path

from .base import EngineError, TrackInfo


class AsapEngineUnavailable(EngineError):
    pass


class AsapEngine:
    display_name = "ASAP / Atari POKEY"
    supported_extensions = {
        ".sap",
        ".cmc",
        ".cm3",
        ".cmr",
        ".cms",
        ".dmc",
        ".dlt",
        ".fc",
        ".mpt",
        ".mpd",
        ".rmt",
        ".tmc",
        ".tm8",
        ".tm2",
    }

    @staticmethod
    def is_supported(path: Path) -> bool:
        return path.suffix.lower() in AsapEngine.supported_extensions

    def __init__(self) -> None:
        raise AsapEngineUnavailable(
            "ASAP is the selected fidelity backend for Atari POKEY formats, "
            "but a usable Python module/native runtime has not been staged yet."
        )

    @property
    def path(self) -> Path | None:
        return None

    @property
    def current_track(self) -> int:
        return 0

    def open(self, path: Path, track: int = 0) -> list[TrackInfo]:
        raise AsapEngineUnavailable("ASAP runtime is not installed yet.")

    def close(self) -> None:
        return None

    def tracks(self) -> list[TrackInfo]:
        return []

    def start_track(self, index: int) -> None:
        raise AsapEngineUnavailable("ASAP runtime is not installed yet.")

    def seek_ms(self, position_ms: int) -> None:
        raise AsapEngineUnavailable("ASAP runtime is not installed yet.")

    def tell_ms(self) -> int:
        return 0

    def render(self, frames: int):
        raise AsapEngineUnavailable("ASAP runtime is not installed yet.")
