"""Keep the case store on a Databricks Unity Catalog volume when the app's own disk does not survive a restart.

At start, an empty data directory is restored from the volume. While the app runs, a consistent copy of the database
and every new original file are written to the volume every ``interval`` seconds, and once more at shutdown, so a
restart loses at most the last interval. Original files are stored by their SHA-256 and never change, so each is
uploaded once. One app instance writes a volume; a second instance would need its own.

    CASEPATH_VOLUME=/Volumes/<catalog>/<schema>/<volume>[/<folder>]
"""
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import threading

import httpx

from .volume import VolumeClient, VolumeError


class VolumeMirror:
    def __init__(self, data_dir, volume, host, token, *, transport=None, interval=30):
        self.data, self.volume = Path(data_dir), volume.rstrip("/")
        self.files = VolumeClient(host, token, transport=transport)
        self.interval, self._stop, self._thread = interval, threading.Event(), None
        self._sent, self._db_hash, self._lock = set(), None, threading.Lock()

    def restore(self):
        """Bring the volume's copy into an empty data directory; returns the number of files restored."""
        if (self.data / "casepath.db").exists():
            return 0
        database = self.files.get(f"{self.volume}/casepath.db")
        if database is None:
            return 0
        self.data.mkdir(parents=True, exist_ok=True)
        (self.data / "casepath.db").write_bytes(database)
        restored = 0
        for folder in self.files.list(f"{self.volume}/files"):
            for entry in self.files.list(folder["path"]) if folder.get("is_directory") else []:
                digest = Path(entry["path"]).name
                target = self.data / "files" / digest[:2] / digest
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(self.files.get(entry["path"]))
                self._sent.add(digest)
                restored += 1
        return restored

    def sync(self):
        """Write new original files, then the database if it changed; returns what was written."""
        with self._lock:
            written = {"files": 0, "database": False}
            for path in sorted((self.data / "files").glob("*/*")):
                if path.suffix == ".part" or path.name in self._sent:
                    continue
                self.files.put(f"{self.volume}/files/{path.name[:2]}/{path.name}", path.read_bytes())
                self._sent.add(path.name)
                written["files"] += 1
            source = self.data / "casepath.db"
            if source.exists():
                with tempfile.TemporaryDirectory() as scratch:
                    copy = Path(scratch) / "casepath.db"
                    with sqlite3.connect(source) as live, sqlite3.connect(copy) as target:
                        live.backup(target)  # a consistent copy while the app keeps writing
                    data = copy.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                if digest != self._db_hash:
                    self.files.put(f"{self.volume}/casepath.db", data)
                    self._db_hash, written["database"] = digest, True
            return written

    def start(self):
        def loop():
            while not self._stop.wait(self.interval):
                try:
                    self.sync()
                except (VolumeError, httpx.HTTPError, OSError, sqlite3.Error):
                    pass  # tried again at the next interval and at shutdown
        self._thread = threading.Thread(target=loop, name="casepath-mirror", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        self.sync()
