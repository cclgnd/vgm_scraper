import os
import requests
import zipfile
import io
from urllib.parse import unquote
from PySide6.QtCore import QThread, Signal


class DownloadThread(QThread):
    """Background thread for downloading and extracting a single pack."""
    finished = Signal(str, str)    # (extract_path, job_id)
    error = Signal(str, str)       # (error_message, job_id)
    progress = Signal(str, int)    # (job_id, percent)
    status = Signal(str, str)      # (job_id, status_text)
    zip_ready = Signal(str, str)   # (zip_path, job_id) - new signal for ZIP stream

    def __init__(self, url, download_dir, job_id, extract=True):
        super().__init__()
        self.url = url
        self.download_dir = download_dir
        self.job_id = job_id
        self.extract = extract
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            if not os.path.exists(self.download_dir):
                os.makedirs(self.download_dir)

            self.status.emit(self.job_id, "CONNECTING...")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(self.url, stream=True, headers=headers, timeout=30)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            self.status.emit(self.job_id, "DOWNLOADING...")
            zip_data = io.BytesIO()
            for chunk in response.iter_content(chunk_size=8192):
                if self._is_cancelled:
                    self.status.emit(self.job_id, "CANCELLED")
                    return
                if chunk:
                    zip_data.write(chunk)
                    downloaded += len(chunk)
                if total_size > 0:
                    self.progress.emit(self.job_id, int(downloaded * 100 / total_size))

            # Derive filename from URL
            raw_filename = unquote(os.path.basename(self.url))
            if not raw_filename.endswith('.zip'):
                raw_filename += ".zip"
                
            zip_path = os.path.join(self.download_dir, raw_filename)
            
            # Save the ZIP to disk
            with open(zip_path, "wb") as f:
                f.write(zip_data.getvalue())

            if self.extract:
                self.status.emit(self.job_id, "EXTRACTING...")
                extract_path = zip_path.replace('.zip', '')
                with zipfile.ZipFile(zip_path) as zf:
                    zf.extractall(extract_path)
                self.status.emit(self.job_id, "DONE")
                self.finished.emit(extract_path, self.job_id)
            else:
                self.status.emit(self.job_id, "ZIP READY")
                self.zip_ready.emit(zip_path, self.job_id)
        except Exception as e:
            self.status.emit(self.job_id, f"FAILED: {str(e)[:40]}")
            self.error.emit(str(e), self.job_id)


class DownloadService:
    """Manages concurrent download jobs."""

    def __init__(self, download_dir='downloads'):
        self.download_dir = download_dir
        self._threads = {}
        self._job_counter = 0

    def download_pack(self, url, pack_name,
                      on_finished=None, on_error=None,
                      on_progress=None, on_status=None,
                      on_zip_ready=None, extract=True):
        """
        Start a new download job. Returns the job_id string.
        """
        self._job_counter += 1
        job_id = f"JOB-{self._job_counter:03d}"

        thread = DownloadThread(url, self.download_dir, job_id, extract=extract)
        self._threads[job_id] = thread # Store by ID

        if on_finished:
            thread.finished.connect(on_finished)
        if on_error:
            thread.error.connect(on_error)
        if on_progress:
            thread.progress.connect(on_progress)
        if on_status:
            thread.status.connect(on_status)
        if on_zip_ready:
            thread.zip_ready.connect(on_zip_ready)

        # prevent GC; auto-cleanup on finish
        thread.finished.connect(lambda p, j=job_id: self._cleanup_thread(j))
        thread.error.connect(lambda e, j=job_id: self._cleanup_thread(j))
        thread.start()

        return job_id

    def cancel_job(self, job_id):
        if job_id in self._threads:
            self._threads[job_id].cancel()

    def _cleanup_thread(self, job_id):
        # Optional: remove from dict after some time or immediately
        # del self._threads[job_id]
        pass

    def _cleanup(self, thread):
        """Legacy cleanup for any list-based calls."""
        to_del = [jid for jid, t in self._threads.items() if t == thread]
        for jid in to_del:
            del self._threads[jid]
