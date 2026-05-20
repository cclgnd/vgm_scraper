from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .base import AudioEngine, EngineError
from .asap_backend import AsapEngine
from .gme import GmeEngine
from .psf import PsfEngine
from .psf2 import Psf2Engine
from .ssf_dsf import SsfDsfEngine
from .gsf import GsfEngine
from .usf import UsfEngine
from .twosf import TwosfEngine
from .vgm import VgmEngine
from .qsf import QsfEngine


class BackendUnavailableError(EngineError):
    pass


@dataclass(frozen=True)
class BackendSpec:
    name: str
    extensions: set[str]
    factory: Callable[[], AudioEngine] | None
    status: str
    notes: str

    @property
    def available(self) -> bool:
        return self.factory is not None


class BackendRegistry:
    def __init__(self, specs: list[BackendSpec] | None = None) -> None:
        self._specs = specs or default_backend_specs()

    @property
    def specs(self) -> tuple[BackendSpec, ...]:
        return tuple(self._specs)

    def supported_extensions(self, include_planned: bool = False) -> set[str]:
        return {
            extension
            for spec in self._specs
            if include_planned or spec.available
            for extension in spec.extensions
        }

    def describe(self) -> list[str]:
        return [
            f"{spec.name}: {spec.status} ({', '.join(sorted(spec.extensions))})"
            for spec in self._specs
        ]

    def find(self, path: Path) -> BackendSpec | None:
        extension = path.suffix.lower()
        for spec in self._specs:
            if extension in spec.extensions:
                return spec
        return None

    def create_for(self, path: Path) -> AudioEngine:
        spec = self.find(path)
        if not spec:
            raise BackendUnavailableError(f"No emulated backend is registered for {path.suffix or '(no extension)'}.")
        if not spec.factory:
            raise BackendUnavailableError(
                f"{spec.name} is planned but not installed yet.\n\n"
                f"Why it is isolated: {spec.notes}"
            )
        return spec.factory()


def default_backend_specs() -> list[BackendSpec]:
    return [
        BackendSpec(
            name="Game Music Emu / libgme",
            extensions=GmeEngine.supported_extensions,
            factory=GmeEngine,
            status="installed",
            notes="Small native C API; already used for real-time chip playback.",
        ),
        BackendSpec(
            name="ASAP / Atari POKEY",
            extensions=AsapEngine.supported_extensions,
            factory=None,
            status="selected; runtime needed",
            notes="Fidelity target for Atari SAP/CMC/RMT/MPT/TMC family. Use ASAP before libgme for supported Atari files once runtime is staged.",
        ),
        BackendSpec(
            name="PSF1 / Audio Overload",
            extensions=PsfEngine.supported_extensions,
            factory=PsfEngine,
            status="installed",
            notes="Fidelity target: Audio Overload PSF1 core in an isolated helper process with miniPSF library resolution.",
        ),
        BackendSpec(
            name="PSF2",
            extensions=Psf2Engine.supported_extensions,
            factory=Psf2Engine,
            status="installed",
            notes="Fidelity target: Audio Overload PSF2 core in an isolated helper process with miniPSF2 library resolution.",
        ),
        BackendSpec(
            name="USF",
            extensions=UsfEngine.supported_extensions,
            factory=UsfEngine,
            status="installed",
            notes="Fidelity target: lazyusf2-derived Nintendo 64 core in an isolated helper process with miniUSF library resolution.",
        ),
        BackendSpec(
            name="GSF",
            extensions=GsfEngine.supported_extensions,
            factory=GsfEngine,
            status="installed",
            notes="Fidelity target: playgsf/VBA-derived GSF core in an isolated helper process with miniGSF library resolution.",
        ),
        BackendSpec(
            name="2SF",
            extensions=TwosfEngine.supported_extensions,
            factory=TwosfEngine,
            status="installed",
            notes="Fidelity target: vio2sf/DeSmuME-derived core; Nintendo DS playback needs its own adapter and dependency loader.",
        ),
        BackendSpec(
            name="SSF/DSF",
            extensions=SsfDsfEngine.supported_extensions,
            factory=SsfDsfEngine,
            status="installed",
            notes="Fidelity target: Highly Theoretical-derived Saturn/Dreamcast core; load only on matching files.",
        ),
        BackendSpec(
            name="VGM / libvgm",
            extensions=VgmEngine.supported_extensions,
            factory=VgmEngine,
            status="installed",
            notes="Handles VGM, VGZ, S98 (Japanese PC FM logs) and DRO (DOS OPL logs) via libvgm helper.",
        ),
        BackendSpec(
            name="QSF",
            extensions=QsfEngine.supported_extensions,
            factory=QsfEngine,
            status="installed",
            notes="Fidelity target: aoqsf/QSound-oriented core; isolated via helper process.",
        ),
        BackendSpec(
            name="Hoot/MAME arcade",
            extensions={".hoot", ".m1", ".xml"},
            factory=None,
            status="research (superseded by VGM)",
            notes="Official Hoot source is closed. Arcade playback covered by VGM backend (.vgm/.vgz) which uses MAME-derived chip cores via libvgm.",
        ),
    ]
