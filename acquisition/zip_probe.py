"""Remote ZIP member listing with HTTP range support."""

import os
import re
import struct
from dataclasses import dataclass

import requests

from vgm_scraper.config import AUDIO_EXTENSIONS, ARCHIVE_EXTENSIONS, USER_AGENT


@dataclass(frozen=True)
class ZipMember:
    name: str
    size: int
    compressed_size: int
    index: int


class RemoteZipProbe:
    """Read ZIP central directory names without downloading the whole archive."""

    TAIL_BYTES = 1024 * 1024
    EOCD_SIGNATURE = b"PK\x05\x06"
    CENTRAL_DIRECTORY_SIGNATURE = b"PK\x01\x02"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def list_supported_members(self, url: str) -> list[ZipMember]:
        data, content_length = self._fetch_tail(url)
        if not data:
            return []
        members = self._parse_tail(data, content_length)
        return [m for m in members if self._is_supported(m.name)]

    def _fetch_tail(self, url: str) -> tuple[bytes, int]:
        headers = {"User-Agent": USER_AGENT}
        head = requests.head(url, headers=headers, allow_redirects=True, timeout=self.timeout)
        length = int(head.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            data, length = self._fetch_length_or_body_from_range(url, headers)
            if data:
                return data, length
        if length <= 0:
            return b"", 0

        start = max(0, length - self.TAIL_BYTES)
        range_headers = dict(headers)
        range_headers["Range"] = f"bytes={start}-{length - 1}"
        response = requests.get(url, headers=range_headers, timeout=self.timeout)
        if response.status_code == 200 and response.content:
            return response.content, len(response.content)
        if response.status_code != 206:
            return b"", length
        return response.content, length

    def _fetch_length_or_body_from_range(self, url: str, headers: dict[str, str]) -> tuple[bytes, int]:
        range_headers = dict(headers)
        range_headers["Range"] = "bytes=0-0"
        response = requests.get(url, headers=range_headers, timeout=self.timeout)
        if response.status_code == 200 and response.content:
            return response.content, len(response.content)
        content_range = response.headers.get("Content-Range", "")
        match = re.search(r"/(\d+)$", content_range)
        if match:
            return b"", int(match.group(1))
        return b"", int(response.headers.get("Content-Length", "0") or 0)

    def _parse_tail(self, data: bytes, content_length: int) -> list[ZipMember]:
        eocd_index = data.rfind(self.EOCD_SIGNATURE)
        if eocd_index < 0 or eocd_index + 22 > len(data):
            return []

        eocd = data[eocd_index:eocd_index + 22]
        total_entries = struct.unpack_from("<H", eocd, 10)[0]
        central_size = struct.unpack_from("<I", eocd, 12)[0]
        central_offset = struct.unpack_from("<I", eocd, 16)[0]
        tail_global_offset = content_length - len(data)
        local_offset = central_offset - tail_global_offset
        if local_offset < 0 or local_offset + central_size > len(data):
            return []

        members = []
        cursor = local_offset
        for index in range(total_entries):
            if data[cursor:cursor + 4] != self.CENTRAL_DIRECTORY_SIGNATURE:
                break
            compressed_size = struct.unpack_from("<I", data, cursor + 20)[0]
            size = struct.unpack_from("<I", data, cursor + 24)[0]
            name_len = struct.unpack_from("<H", data, cursor + 28)[0]
            extra_len = struct.unpack_from("<H", data, cursor + 30)[0]
            comment_len = struct.unpack_from("<H", data, cursor + 32)[0]
            name_start = cursor + 46
            name_end = name_start + name_len
            name = data[name_start:name_end].decode("utf-8", errors="replace")
            if name and not name.endswith("/"):
                members.append(ZipMember(name=name, size=size, compressed_size=compressed_size, index=index + 1))
            cursor = name_end + extra_len + comment_len
        return members

    @staticmethod
    def _is_supported(name: str) -> bool:
        lower = name.lower()
        for compound in (".tar.gz", ".tar.bz2"):
            if lower.endswith(compound):
                return compound in ARCHIVE_EXTENSIONS
        return os.path.splitext(lower)[1] in AUDIO_EXTENSIONS
