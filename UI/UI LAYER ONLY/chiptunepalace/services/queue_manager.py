import random
from typing import List
from chiptunepalace.services.track_service import TrackService
from chiptunepalace.services.audio_engine import AudioEngine

class QueueManager:
    """
    Manages the current playlist, shuffle state, and queue transitions.
    """
    def __init__(self, track_service: TrackService, audio_engine: AudioEngine):
        self.track_service = track_service
        self.audio_engine = audio_engine
        self.original_playlist: List[int] = []  # Stores track_ids in original sequence
        self.current_queue: List[int] = []     # Current order (might be shuffled)
        self.current_index: int = -1
        self.is_shuffling: bool = False
        self.max_consecutive_failures: int = 3
        
        # Connect to audio engine signals
        self.audio_engine.track_finished.connect(self.advance_to_next_track)

    def load_playlist(self, track_ids: List[int]):
        """Sets the current playlist queue."""
        sanitized = []
        for tid in track_ids:
            try:
                sanitized.append(int(tid))
            except (ValueError, TypeError):
                sanitized.append(tid)
        self.original_playlist = sanitized
        self._update_queue()
        self.current_index = -1
        print(f"QueueManager: Playlist loaded with {len(sanitized)} tracks.")
        
    def _update_queue(self):
        """Updates current_queue based on shuffle state."""
        if self.is_shuffling:
            self.current_queue = self.original_playlist[:]
            random.shuffle(self.current_queue)
        else:
            self.current_queue = self.original_playlist[:]

    def toggle_shuffle(self):
        """Toggles whether tracks should be played in shuffled order."""
        self.is_shuffling = not self.is_shuffling
        current_track_id = self.get_current_track_id()
        self._update_queue()
        
        # If we were playing something, try to find it in the new queue to maintain continuity
        if current_track_id in self.current_queue:
            self.current_index = self.current_queue.index(current_track_id)
            
        print(f"QueueManager: Shuffle mode toggled to {self.is_shuffling}")

    def get_current_track_id(self) -> int | None:
        if 0 <= self.current_index < len(self.current_queue):
            return self.current_queue[self.current_index]
        return None

    def advance_to_next_track(self):
        """
        Advances to the next track and instructs the AudioEngine to load it.
        Implements non-stop playback (loops back to start).
        """
        if not self.current_queue:
            print("QueueManager: Queue is empty.")
            self.audio_engine.stop()
            return

        self.current_index += 1
        if self.current_index >= len(self.current_queue):
            self.current_index = 0 # Non-stop loop
            if self.is_shuffling:
                random.shuffle(self.current_queue) # Re-shuffle on loop

        next_id = self.current_queue[self.current_index]
        self._play_track_by_id(next_id)

    def previous_track(self):
        """Moves to the previous track."""
        if not self.current_queue:
            return

        self.current_index -= 1
        if self.current_index < 0:
            self.current_index = len(self.current_queue) - 1
            
        next_id = self.current_queue[self.current_index]
        self._play_track_by_id(next_id)

    def _play_track_by_id(self, track_id: int, _attempted=None, auto_advance_on_failure: bool = False):
        if _attempted is None:
            _attempted = set()
            
        if track_id in _attempted or len(_attempted) >= self.max_consecutive_failures:
            print("QueueManager: All tracks in queue failed to load. Stopping playback.")
            self.audio_engine.stop()
            return
            
        _attempted.add(track_id)
        print(f"QueueManager: Loading track ID: {track_id}")
        
        try:
            db_id = int(track_id)
        except (ValueError, TypeError):
            print(f"QueueManager: Invalid track ID format: {track_id}")
            if auto_advance_on_failure:
                self._advance_on_failure(_attempted)
            return

        track_details = self.track_service.get_track_by_id(db_id)
        if track_details and track_details.get('file_path'):
            path = track_details['file_path']
            member = track_details.get('member_name')
            success = self.audio_engine.load_track(path, member_name=member)
            if success:
                self.audio_engine.play()
            else:
                print("QueueManager: Failed to load track file.")
                if auto_advance_on_failure:
                    self._advance_on_failure(_attempted)
                else:
                    self.audio_engine.stop()
        else:
            print(f"QueueManager: Track {track_id} not found or path missing.")
            if auto_advance_on_failure:
                self._advance_on_failure(_attempted)

    def _advance_on_failure(self, attempted):
        if not self.current_queue:
            return
        self.current_index += 1
        if self.current_index >= len(self.current_queue):
            self.current_index = 0
        next_id = self.current_queue[self.current_index]
        self._play_track_by_id(next_id, attempted, auto_advance_on_failure=True)

    def start_playback(self, initial_track_id: int = None):
        """Initiates playback from a specific track or the beginning."""
        if not self.current_queue and self.original_playlist:
            self._update_queue()

        if initial_track_id is not None:
            try:
                initial_track_id = int(initial_track_id)
            except (ValueError, TypeError):
                pass

        if initial_track_id is not None and initial_track_id in self.current_queue:
            self.current_index = self.current_queue.index(initial_track_id)
        else:
            self.current_index = 0

        if self.current_queue:
            self._play_track_by_id(self.current_queue[self.current_index])
