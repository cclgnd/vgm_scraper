"""
Player integration API.

Provides a simple HTTP/JSON API for the player GUI to:
- Browse the catalog (consoles → games → collections → tracks)
- Check track availability
- Request on-demand retrieval
- Get retrieval status
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from vgm_scraper.db.manager import DatabaseManager
from vgm_scraper.catalog.library import LibraryManager
from vgm_scraper.acquisition.retrieval import RetrievalManager
from vgm_scraper.acquisition.verifier import GameVerifier


class APIHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, db=None, library=None, retrieval=None, verifier=None, **kwargs):
        self.db = db
        self.library = library
        self.retrieval = retrieval
        self.verifier = verifier
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        pass  # Suppress default logging

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        path = self.path.rstrip("/")

        if path == "/api/consoles":
            self._handle_list_consoles()
        elif path == "/api/audition/queue":
            self._handle_audition_queue()
        elif path == "/api/audition/stats":
            self._handle_audition_stats()
        elif path.startswith("/api/consoles/") and path.endswith("/games"):
            console_id = path.split("/")[-2]
            self._handle_list_games(int(console_id))
        elif path.startswith("/api/games/") and path.endswith("/collections"):
            game_id = path.split("/")[-2]
            self._handle_list_collections(int(game_id))
        elif path.startswith("/api/games/") and path.endswith("/files"):
            game_id = path.split("/")[-2]
            self._handle_game_files(int(game_id))
        elif path.startswith("/api/collections/") and path.endswith("/tracks"):
            collection_id = path.split("/")[-2]
            self._handle_list_tracks(int(collection_id))
        elif path.startswith("/api/tracks/"):
            track_id = path.split("/")[-1]
            self._handle_track_status(int(track_id))
        elif path.startswith("/api/games/") and path.endswith("/audition"):
            game_id = path.split("/")[-2]
            self._handle_game_audition(int(game_id))
        elif path == "/api/tree":
            self._handle_full_tree()
        elif path == "/api/search":
            query = self.path.split("?query=")[-1] if "?query=" in self.path else ""
            self._handle_search(query)
        elif path == "/api/stats":
            self._handle_stats()
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = self.path.rstrip("/")

        if path.startswith("/api/tracks/") and path.endswith("/request"):
            track_id = path.split("/")[-2]
            self._handle_request_track(int(track_id))
        elif path.startswith("/api/games/") and path.endswith("/retry"):
            game_id = path.split("/")[-2]
            self._handle_game_retry(int(game_id))
        elif path.startswith("/api/tracks/") and path.endswith("/audition"):
            track_id = path.split("/")[-2]
            self._handle_record_track_audition(int(track_id))
        elif path.startswith("/api/games/") and path.endswith("/audition"):
            game_id = path.split("/")[-2]
            self._handle_record_game_audition(int(game_id))
        else:
            self._send_json({"error": "Not found"}, 404)

    def _handle_list_consoles(self):
        consoles = self.library.list_consoles()
        self._send_json({"consoles": [c.to_dict() for c in consoles]})

    def _handle_list_games(self, console_id):
        games = self.library.list_games(console_id)
        self._send_json({"games": [g.to_dict() for g in games]})

    def _handle_list_collections(self, game_id):
        collections = self.library.list_collections(game_id)
        self._send_json({"collections": [c.to_dict() for c in collections]})

    def _handle_game_files(self, game_id):
        game = self.db.get_game(game_id)
        if not game:
            self._send_json({"error": "Game not found"}, 404)
            return
        result = self.verifier.open_game(game_id)
        result["game_id"] = game_id
        self._send_json(result)

    def _handle_game_retry(self, game_id):
        game = self.db.get_game(game_id)
        if not game:
            self._send_json({"error": "Game not found"}, 404)
            return
        result = self.verifier.open_game(game_id, retry_failed=True)
        result["game_id"] = game_id
        self._send_json(result)

    def _handle_list_tracks(self, collection_id):
        tracks = self.library.list_tracks(collection_id=collection_id)
        self._send_json({"tracks": [t.to_dict() for t in tracks]})

    def _handle_track_status(self, track_id):
        status = self.retrieval.get_track_status(track_id)
        self._send_json(status)

    def _handle_game_audition(self, game_id):
        latest = self.db.get_latest_audition_event(game_id=game_id)
        self._send_json({
            "game_id": game_id,
            "audition_status": latest["status"] if latest else "pending",
            "latest_audition_event": latest,
        })

    def _handle_audition_queue(self):
        status = "needs_audition"
        limit = 100
        if "?" in self.path:
            from urllib.parse import parse_qs, urlparse
            query = parse_qs(urlparse(self.path).query)
            status = query.get("status", [status])[0]
            try:
                limit = int(query.get("limit", [limit])[0])
            except ValueError:
                limit = 100
        self._send_json({"items": self.db.get_audition_queue(status=status, limit=limit)})

    def _handle_audition_stats(self):
        self._send_json({
            "status_counts": self.db.get_audition_status_counts(),
            "source_stats": self.db.get_audition_source_stats(),
        })

    def _handle_request_track(self, track_id):
        result = self.retrieval.request_track(track_id)
        self._send_json(result)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def _handle_record_track_audition(self, track_id):
        try:
            body = self._read_json_body()
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        status = body.get("status")
        if status not in {"manual_passed", "manual_failed", "needs_audition"}:
            self._send_json({"error": "Invalid audition status"}, 400)
            return

        track = self.db.get_track(track_id)
        if not track:
            self._send_json({"error": "Track not found"}, 404)
            return

        event_id = self.db.add_audition_event(
            track_id=track_id,
            game_id=track.get("game_id"),
            event_type="manual_audition",
            status=status,
            details={"note": body.get("note", "")},
        )
        self._send_json({"event_id": event_id, "track_id": track_id, "status": status})

    def _handle_record_game_audition(self, game_id):
        try:
            body = self._read_json_body()
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
            return

        status = body.get("status")
        if status not in {"manual_passed", "manual_failed", "needs_audition"}:
            self._send_json({"error": "Invalid audition status"}, 400)
            return

        game = self.db.get_game(game_id)
        if not game:
            self._send_json({"error": "Game not found"}, 404)
            return

        event_id = self.db.add_audition_event(
            game_id=game_id,
            event_type="manual_audition",
            status=status,
            details={"note": body.get("note", "")},
        )
        self._send_json({"event_id": event_id, "game_id": game_id, "status": status})

    def _handle_full_tree(self):
        tree = self.library.get_full_tree()
        self._send_json({"tree": tree})

    def _handle_search(self, query):
        if not query:
            self._send_json({"error": "Missing query parameter"}, 400)
            return
        results = self.library.search(query)
        self._send_json({"results": results})

    def _handle_stats(self):
        stats = self.db.get_stats()
        self._send_json(stats)


class APIServer:
    """HTTP API server for player integration."""

    def __init__(self, db: DatabaseManager, library: LibraryManager, retrieval: RetrievalManager,
                 verifier: GameVerifier = None, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.db = db
        self.library = library
        self.retrieval = retrieval
        self.verifier = verifier
        self.server = None
        self._jobs_running = False

    def start(self):
        """Start the API server in a background thread."""
        if self.verifier is None:
            from vgm_scraper.config import DEFAULT_DOWNLOAD_DIR
            self.verifier = GameVerifier(self.db, DEFAULT_DOWNLOAD_DIR)

        def handler_factory(*args, **kwargs):
            return APIHandler(*args, db=self.db, library=self.library,
                              retrieval=self.retrieval, verifier=self.verifier, **kwargs)

        self.server = HTTPServer((self.host, self.port), handler_factory)
        self._jobs_running = True
        jobs_thread = threading.Thread(target=self._process_retrieval_jobs_loop, daemon=True)
        jobs_thread.start()
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        print(f"API server started at http://{self.host}:{self.port}")

    def stop(self):
        self._jobs_running = False
        if self.server:
            self.server.shutdown()

    def _process_retrieval_jobs_loop(self):
        while self._jobs_running:
            try:
                self.retrieval.process_pending_jobs()
            except Exception:
                pass
            import time
            time.sleep(1.0)
