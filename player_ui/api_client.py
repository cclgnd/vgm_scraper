from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class PlayerApiError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


class PlayerApiClient:
    """Tiny stdlib client for the scraper player API."""

    def __init__(self, base_url: str = "http://127.0.0.1:8765", timeout: float = 1.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def tree(self) -> list[dict]:
        return self._get("/api/tree").get("tree", [])

    def game_files(self, game_id: int) -> dict:
        return self._get(f"/api/games/{game_id}/files")

    def retry_game(self, game_id: int) -> dict:
        return self._post(f"/api/games/{game_id}/retry")

    def _get(self, path: str) -> dict:
        return self._request("GET", path)

    def _post(self, path: str) -> dict:
        return self._request("POST", path)

    def _request(self, method: str, path: str) -> dict:
        url = f"{self.base_url}{path}"
        request = Request(url, data=b"" if method == "POST" else None, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raise PlayerApiError(f"API {method} {path} failed: HTTP {exc.code}") from exc
        except URLError as exc:
            raise PlayerApiError(f"API unavailable at {self.base_url}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise PlayerApiError(f"API timed out at {self.base_url}") from exc

        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise PlayerApiError(f"API returned invalid JSON for {path}") from exc
