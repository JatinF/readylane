"""SQLite release records. One connection, shared across request threads."""

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from readylane.errors import GateError


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _public(row: sqlite3.Row) -> dict:
    return {
        "change_id": row["change_id"],
        "title": row["title"],
        "stage": row["stage"],
        "sha256": row["artifact_sha256"],
        "byte_length": row["artifact_bytes"],
        "requester_subject": row["requester_subject"],
        "approver_subject": row["approver_subject"],
        "created_at": row["created_at"],
    }


class Store:
    def __init__(self, path: str) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.path = str(target)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=2000")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS changes (
                    change_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    artifact_sha256 TEXT,
                    artifact_bytes INTEGER,
                    stage TEXT NOT NULL,
                    requester_subject TEXT NOT NULL,
                    approver_subject TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def ping(self) -> None:
        with self._lock:
            self._conn.execute("SELECT 1").fetchone()

    def create(self, change_id: str, title: str, requester: str) -> dict:
        with self._lock:
            existing = self._conn.execute(
                "SELECT change_id FROM changes WHERE change_id = ?",
                (change_id,),
            ).fetchone()
            if existing is not None:
                raise GateError("conflict", "change already exists")
            self._conn.execute(
                """
                INSERT INTO changes (
                    change_id, title, artifact_sha256, artifact_bytes, stage,
                    requester_subject, approver_subject, created_at
                ) VALUES (?, ?, NULL, NULL, 'open', ?, NULL, ?)
                """,
                (change_id, title, requester, _now()),
            )
            self._conn.commit()
            return _public(self._one(change_id))

    def get(self, change_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM changes WHERE change_id = ?", (change_id,)).fetchone()
            return _public(row) if row else None

    def verify(self, change_id: str, sha256: str, byte_length: int) -> dict:
        with self._lock:
            row = self._one(change_id)
            recorded = row["artifact_sha256"]
            if recorded and recorded != sha256:
                raise GateError("conflict", "artifact already recorded")
            if row["stage"] == "open":
                self._conn.execute(
                    """
                    UPDATE changes
                    SET artifact_sha256 = ?, artifact_bytes = ?, stage = 'verified'
                    WHERE change_id = ?
                    """,
                    (sha256, byte_length, change_id),
                )
                self._conn.commit()
            return _public(self._one(change_id))

    def request_release(self, change_id: str) -> dict:
        with self._lock:
            row = self._one(change_id)
            if row["stage"] == "pending":
                return _public(row)
            if row["stage"] != "verified":
                raise GateError("conflict", f"stage is {row['stage']}")
            self._conn.execute("UPDATE changes SET stage = 'pending' WHERE change_id = ?", (change_id,))
            self._conn.commit()
            return _public(self._one(change_id))

    def decide(self, change_id: str, subject: str, decision: str) -> dict:
        if decision not in {"approve", "reject"}:
            raise GateError("invalid", "decision must be approve or reject")
        stage = "approved" if decision == "approve" else "rejected"
        with self._lock:
            row = self._one(change_id)
            if row["stage"] in {"approved", "rejected"}:
                raise GateError("conflict", "release is already decided")
            if row["stage"] != "pending":
                raise GateError("conflict", f"stage is {row['stage']}")
            if subject == row["requester_subject"]:
                raise GateError("denied", "requester cannot approve")
            self._conn.execute(
                "UPDATE changes SET stage = ?, approver_subject = ? WHERE change_id = ?",
                (stage, subject, change_id),
            )
            self._conn.commit()
            return _public(self._one(change_id))

    def _one(self, change_id: str) -> sqlite3.Row:
        row = self._conn.execute("SELECT * FROM changes WHERE change_id = ?", (change_id,)).fetchone()
        if row is None:
            raise GateError("not_found", "change not found")
        return row
