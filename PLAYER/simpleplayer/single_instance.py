from __future__ import annotations

import json
import socket
import threading
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Signal


HOST = "127.0.0.1"
PORT = 47291


class SingleInstanceServer(QObject):
    files_received = Signal(list)

    def __init__(self, on_files: Callable[[list[Path]], None]) -> None:
        super().__init__()
        self.files_received.connect(on_files)
        self._stop = threading.Event()
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((HOST, PORT))
            server.listen()
            server.settimeout(0.5)
        except OSError:
            return False

        self._socket = server
        self._thread = threading.Thread(target=self._serve, name="SimplePlayerSingleInstance", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass

    def _serve(self) -> None:
        assert self._socket is not None
        while not self._stop.is_set():
            try:
                conn, _addr = self._socket.accept()
            except TimeoutError:
                continue
            except OSError:
                break

            with conn:
                data = b""
                while True:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    data += chunk

            try:
                payload = json.loads(data.decode("utf-8"))
                files = [Path(item) for item in payload.get("files", []) if item]
            except Exception:
                files = []

            if files:
                self.files_received.emit(files)


def send_to_running_instance(files: list[Path]) -> bool:
    if not files:
        return False
    payload = json.dumps({"files": [str(path) for path in files]}).encode("utf-8")
    try:
        with socket.create_connection((HOST, PORT), timeout=0.35) as client:
            client.sendall(payload)
        return True
    except OSError:
        return False
