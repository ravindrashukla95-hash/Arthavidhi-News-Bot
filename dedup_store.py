"""
Tracks which announcement IDs have already been sent to Telegram,
so restarts / overlapping poll windows never cause duplicate alerts.
"""
import sqlite3
import threading
from datetime import datetime, timezone


class DedupStore:
    def __init__(self, db_path: str):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_announcements (
                id TEXT PRIMARY KEY,
                exchange TEXT NOT NULL,
                bucket TEXT,
                first_seen_utc TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def is_new(self, announcement_id: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM seen_announcements WHERE id = ?", (announcement_id,)
            ).fetchone()
        return row is None

    def mark_seen(self, announcement_id: str, exchange: str, bucket: str = "") -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO seen_announcements (id, exchange, bucket, first_seen_utc) "
                "VALUES (?, ?, ?, ?)",
                (announcement_id, exchange, bucket, datetime.now(timezone.utc).isoformat()),
            )
            self._conn.commit()

    def count(self) -> int:
        with self._lock:
            (n,) = self._conn.execute("SELECT COUNT(*) FROM seen_announcements").fetchone()
        return n

    def close(self) -> None:
        self._conn.close()
