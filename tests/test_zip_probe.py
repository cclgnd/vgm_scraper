import io
import unittest
import zipfile
from unittest.mock import patch

from vgm_scraper.acquisition.zip_probe import RemoteZipProbe


class FakeResponse:
    def __init__(self, status_code=200, headers=None, content=b""):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content


class RemoteZipProbeTests(unittest.TestCase):
    def test_uses_range_total_when_head_has_no_content_length(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("01 Opening.vgz", b"vgz")
            zf.writestr("cover.txt", b"skip")
        data = archive.getvalue()
        calls = []

        def fake_head(*args, **kwargs):
            return FakeResponse(headers={"Accept-Ranges": "bytes"})

        def fake_get(url, headers=None, **kwargs):
            calls.append(headers.get("Range"))
            if headers.get("Range") == "bytes=0-0":
                return FakeResponse(
                    status_code=206,
                    headers={"Content-Range": f"bytes 0-0/{len(data)}"},
                    content=data[:1],
                )
            start = int(headers["Range"].split("=")[1].split("-")[0])
            return FakeResponse(
                status_code=206,
                headers={"Content-Range": f"bytes {start}-{len(data) - 1}/{len(data)}"},
                content=data[start:],
            )

        with patch("vgm_scraper.acquisition.zip_probe.requests.head", fake_head), \
             patch("vgm_scraper.acquisition.zip_probe.requests.get", fake_get):
            members = RemoteZipProbe().list_supported_members("https://example.test/music.zip")

        self.assertEqual(["bytes=0-0", f"bytes=0-{len(data) - 1}"], calls)
        self.assertEqual(["01 Opening.vgz"], [member.name for member in members])

    def test_accepts_full_body_when_server_ignores_range(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("01 Opening.vgz", b"vgz")
        data = archive.getvalue()

        def fake_head(*args, **kwargs):
            return FakeResponse(headers={"Accept-Ranges": "bytes"})

        def fake_get(*args, **kwargs):
            return FakeResponse(status_code=200, headers={}, content=data)

        with patch("vgm_scraper.acquisition.zip_probe.requests.head", fake_head), \
             patch("vgm_scraper.acquisition.zip_probe.requests.get", fake_get):
            members = RemoteZipProbe().list_supported_members("https://example.test/music.zip")

        self.assertEqual(["01 Opening.vgz"], [member.name for member in members])


if __name__ == "__main__":
    unittest.main()
