from __future__ import annotations

import ctypes
import os
from pathlib import Path
from threading import RLock

from .base import CHANNELS, SAMPLE_RATE, EngineError, TrackInfo


class GmeError(EngineError):
    pass


class _GmeInfo(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_int),
        ("intro_length", ctypes.c_int),
        ("loop_length", ctypes.c_int),
        ("play_length", ctypes.c_int),
        ("fade_length", ctypes.c_int),
        ("i5", ctypes.c_int),
        ("i6", ctypes.c_int),
        ("i7", ctypes.c_int),
        ("i8", ctypes.c_int),
        ("i9", ctypes.c_int),
        ("i10", ctypes.c_int),
        ("i11", ctypes.c_int),
        ("i12", ctypes.c_int),
        ("i13", ctypes.c_int),
        ("i14", ctypes.c_int),
        ("i15", ctypes.c_int),
        ("system", ctypes.c_char_p),
        ("game", ctypes.c_char_p),
        ("song", ctypes.c_char_p),
        ("author", ctypes.c_char_p),
        ("copyright", ctypes.c_char_p),
        ("comment", ctypes.c_char_p),
        ("dumper", ctypes.c_char_p),
        ("s7", ctypes.c_char_p),
        ("s8", ctypes.c_char_p),
        ("s9", ctypes.c_char_p),
        ("s10", ctypes.c_char_p),
        ("s11", ctypes.c_char_p),
        ("s12", ctypes.c_char_p),
        ("s13", ctypes.c_char_p),
        ("s14", ctypes.c_char_p),
        ("s15", ctypes.c_char_p),
    ]


def _decode(value: bytes | None) -> str:
    if not value:
        return ""
    return value.decode("utf-8", errors="replace")


def _library_candidates() -> list[Path | str]:
    root = Path(__file__).resolve().parents[2]
    names = ("gme.dll", "libgme.dll", "libgme.so", "libgme.dylib")
    candidates: list[Path | str] = []

    if env_path := os.environ.get("SIMPLEPLAYER_GME_DLL"):
        candidates.append(Path(env_path))

    for folder in (root / "engines", root):
        candidates.extend(folder / name for name in names)

    candidates.extend(names)
    return candidates


class GmeEngine:
    display_name = "Game Music Emu / libgme"
    kss_scan_seconds_per_selector = 1
    kss_scan_peak_threshold = 16
    supported_extensions = {
        ".ay",
        ".gbs",
        ".gym",
        ".hes",
        ".kss",
        ".nsf",
        ".nsfe",
        ".sap",
        ".spc",
    }

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        self.sample_rate = sample_rate
        self._lock = RLock()
        self._lib = self._load_library()
        self._emu = ctypes.c_void_p()
        self._path: Path | None = None
        self._current_track = 0
        self._visible_to_native_tracks: list[int] | None = None
        self._native_to_visible_tracks: dict[int, int] = {}
        self._configure_api()

    @staticmethod
    def is_supported(path: Path) -> bool:
        return path.suffix.lower() in GmeEngine.supported_extensions

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def current_track(self) -> int:
        return self._current_track

    def open(self, path: Path, track: int = 0) -> list[TrackInfo]:
        if not path.exists():
            raise GmeError(f"File does not exist: {path}")
        if not self.is_supported(path):
            raise GmeError(f"Unsupported emulated format: {path.suffix or '(none)'}")

        with self._lock:
            self.close()
            emu = ctypes.c_void_p()
            err = self._lib.gme_open_file(os.fsencode(path), ctypes.byref(emu), self.sample_rate)
            self._raise_if_error(err)
            self._emu = emu
            self._path = path
            self._visible_to_native_tracks = None
            self._native_to_visible_tracks = {}
            if path.suffix.lower() == ".kss":
                self._build_kss_audible_track_map()
            tracks = self.tracks()
            self.start_track(min(track, max(len(tracks) - 1, 0)))
            return tracks

    def close(self) -> None:
        with self._lock:
            if self._emu:
                self._lib.gme_delete(self._emu)
                self._emu = ctypes.c_void_p()
            self._path = None
            self._current_track = 0
            self._visible_to_native_tracks = None
            self._native_to_visible_tracks = {}

    def tracks(self) -> list[TrackInfo]:
        with self._lock:
            self._require_open()
            if self._visible_to_native_tracks is not None:
                return [
                    self._track_info(native_index, visible_index)
                    for visible_index, native_index in enumerate(self._visible_to_native_tracks)
                ]
            count = self._lib.gme_track_count(self._emu)
            return [self._track_info(index, index) for index in range(count)]

    def start_track(self, index: int) -> None:
        with self._lock:
            self._require_open()
            native_index = self._visible_to_native(index)
            if native_index < 0 or native_index >= self._lib.gme_track_count(self._emu):
                raise GmeError(f"Track index out of range: {index + 1}")
            err = self._lib.gme_start_track(self._emu, native_index)
            self._raise_if_error(err)
            self._current_track = index

    def seek_ms(self, position_ms: int) -> None:
        with self._lock:
            self._require_open()
            err = self._lib.gme_seek(self._emu, max(0, position_ms))
            self._raise_if_error(err)

    def tell_ms(self) -> int:
        with self._lock:
            if not self._emu:
                return 0
            return int(self._lib.gme_tell(self._emu))

    def ended(self) -> bool:
        with self._lock:
            return bool(self._emu and self._lib.gme_track_ended(self._emu))

    def render(self, frames: int) -> ctypes.Array[ctypes.c_short]:
        sample_count = frames * CHANNELS
        buffer_type = ctypes.c_short * sample_count
        buffer = buffer_type()

        with self._lock:
            if not self._emu:
                return buffer
            err = self._lib.gme_play(self._emu, sample_count, buffer)
            self._raise_if_error(err)
            return buffer

    def voice_names(self) -> list[str]:
        with self._lock:
            if not self._emu:
                return []
            count = self._lib.gme_voice_count(self._emu)
            return [_decode(self._lib.gme_voice_name(self._emu, i)) or f"Voice {i + 1}" for i in range(count)]

    def mute_voice(self, index: int, muted: bool) -> None:
        with self._lock:
            self._require_open()
            self._lib.gme_mute_voice(self._emu, index, int(muted))

    def mute_all(self, mask: int) -> None:
        with self._lock:
            self._require_open()
            self._lib.gme_mute_voices(self._emu, mask)

    def set_tempo(self, tempo: float) -> None:
        with self._lock:
            self._require_open()
            self._lib.gme_set_tempo(self._emu, ctypes.c_double(tempo))

    def _track_info(self, native_index: int, visible_index: int) -> TrackInfo:
        info_ptr = ctypes.POINTER(_GmeInfo)()
        err = self._lib.gme_track_info(self._emu, ctypes.byref(info_ptr), native_index)
        self._raise_if_error(err)
        try:
            info = info_ptr.contents
            title = _decode(info.song)
            if self._visible_to_native_tracks is not None:
                title = title or f"Selector {native_index}"
            return TrackInfo(
                index=visible_index,
                title=title or f"Track {visible_index + 1}",
                game=_decode(info.game),
                system=_decode(info.system),
                author=_decode(info.author),
                length_ms=info.length,
                play_length_ms=info.play_length,
            )
        finally:
            self._lib.gme_free_info(info_ptr)

    def _visible_to_native(self, visible_index: int) -> int:
        if self._visible_to_native_tracks is None:
            return visible_index
        if visible_index < 0 or visible_index >= len(self._visible_to_native_tracks):
            raise GmeError(f"Track index out of range: {visible_index + 1}")
        return self._visible_to_native_tracks[visible_index]

    def _build_kss_audible_track_map(self) -> None:
        count = self._lib.gme_track_count(self._emu)
        original_visible = self._current_track
        audible_native: list[int] = []

        for native_index in range(count):
            peak = self._scan_track_peak(native_index)
            if peak >= self.kss_scan_peak_threshold:
                audible_native.append(native_index)

        if audible_native:
            self._visible_to_native_tracks = audible_native
            self._native_to_visible_tracks = {native: visible for visible, native in enumerate(audible_native)}
        else:
            self._visible_to_native_tracks = None
            self._native_to_visible_tracks = {}

        try:
            self.start_track(original_visible)
        except GmeError:
            self.start_track(0)

    def _scan_track_peak(self, native_index: int) -> int:
        err = self._lib.gme_start_track(self._emu, native_index)
        self._raise_if_error(err)
        frames = self.sample_rate * self.kss_scan_seconds_per_selector
        sample_count = frames * CHANNELS
        buffer_type = ctypes.c_short * sample_count
        buffer = buffer_type()
        err = self._lib.gme_play(self._emu, sample_count, buffer)
        self._raise_if_error(err)
        return max((abs(int(sample)) for sample in buffer), default=0)

    def _require_open(self) -> None:
        if not self._emu:
            raise GmeError("No emulated music file is open.")

    def _raise_if_error(self, err: bytes | None) -> None:
        if err:
            raise GmeError(_decode(err))

    def _load_library(self) -> ctypes.CDLL:
        errors: list[str] = []
        for candidate in _library_candidates():
            try:
                return ctypes.CDLL(str(candidate))
            except OSError as exc:
                errors.append(f"{candidate}: {exc}")

        searched = "\n".join(f"  - {candidate}" for candidate in _library_candidates())
        raise GmeError(
            "Could not load libgme. Place gme.dll/libgme.dll in the engines folder, "
            "put it on PATH, or set SIMPLEPLAYER_GME_DLL.\nSearched:\n" + searched
        )

    def _configure_api(self) -> None:
        self._lib.gme_open_file.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_int]
        self._lib.gme_open_file.restype = ctypes.c_char_p
        self._lib.gme_track_count.argtypes = [ctypes.c_void_p]
        self._lib.gme_track_count.restype = ctypes.c_int
        self._lib.gme_start_track.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._lib.gme_start_track.restype = ctypes.c_char_p
        self._lib.gme_play.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_short)]
        self._lib.gme_play.restype = ctypes.c_char_p
        self._lib.gme_delete.argtypes = [ctypes.c_void_p]
        self._lib.gme_delete.restype = None
        self._lib.gme_track_ended.argtypes = [ctypes.c_void_p]
        self._lib.gme_track_ended.restype = ctypes.c_int
        self._lib.gme_tell.argtypes = [ctypes.c_void_p]
        self._lib.gme_tell.restype = ctypes.c_int
        self._lib.gme_seek.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._lib.gme_seek.restype = ctypes.c_char_p
        self._lib.gme_track_info.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(_GmeInfo)), ctypes.c_int]
        self._lib.gme_track_info.restype = ctypes.c_char_p
        self._lib.gme_free_info.argtypes = [ctypes.POINTER(_GmeInfo)]
        self._lib.gme_free_info.restype = None
        self._lib.gme_voice_count.argtypes = [ctypes.c_void_p]
        self._lib.gme_voice_count.restype = ctypes.c_int
        self._lib.gme_voice_name.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._lib.gme_voice_name.restype = ctypes.c_char_p
        self._lib.gme_mute_voice.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        self._lib.gme_mute_voice.restype = None
        self._lib.gme_mute_voices.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._lib.gme_mute_voices.restype = None
        self._lib.gme_set_tempo.argtypes = [ctypes.c_void_p, ctypes.c_double]
        self._lib.gme_set_tempo.restype = None
