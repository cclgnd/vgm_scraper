"""Best-effort in-process duration probing for supported file formats."""

import gzip
import os
import struct


class DurationProbe:
    """Probe simple durations without external tools.

    Unknown is a valid result. Availability must never depend on duration.
    """

    VGM_SAMPLE_RATE = 44100

    def probe(self, file_path: str) -> float | None:
        ext = os.path.splitext(file_path.lower())[1]
        if ext in {".vgm", ".vgz"}:
            return self._probe_vgm(file_path, compressed=ext == ".vgz")
        return None

    def _probe_vgm(self, file_path: str, compressed: bool) -> float | None:
        try:
            opener = gzip.open if compressed else open
            with opener(file_path, "rb") as handle:
                header = handle.read(0x28)
            if len(header) < 0x18 or header[:4] != b"Vgm ":
                return None
            total_samples = struct.unpack_from("<I", header, 0x18)[0]
            if total_samples <= 0:
                return None
            return total_samples / self.VGM_SAMPLE_RATE
        except Exception:
            return None
