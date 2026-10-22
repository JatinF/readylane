"""Process settings. Tokens come from the environment and are never logged."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    lead_token: str
    lead_subject: str
    approver_token: str
    approver_subject: str
    database_path: str
    host: str = "127.0.0.1"
    port: int = 8080

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            lead_token=os.environ.get("READYLANE_LEAD_TOKEN", ""),
            lead_subject=os.environ.get("READYLANE_LEAD_SUBJECT", ""),
            approver_token=os.environ.get("READYLANE_APPROVER_TOKEN", ""),
            approver_subject=os.environ.get("READYLANE_APPROVER_SUBJECT", ""),
            database_path=os.environ.get("READYLANE_DB", ""),
            host=os.environ.get("READYLANE_HOST", "127.0.0.1"),
            port=_port(os.environ.get("READYLANE_PORT", "8080")),
        )

    def validated(self) -> "Settings":
        if len(self.lead_token) < 8 or len(self.approver_token) < 8:
            raise ValueError("lead and approver tokens must be at least 8 characters")
        if self.lead_token == self.approver_token:
            raise ValueError("lead and approver tokens must differ")
        if not self.lead_subject.strip() or not self.approver_subject.strip():
            raise ValueError("lead and approver subjects are required")
        if self.lead_subject == self.approver_subject:
            raise ValueError("lead and approver subjects must differ")
        if not self.database_path.strip():
            raise ValueError("READYLANE_DB is required")
        if not self.host.strip():
            raise ValueError("READYLANE_HOST is required")
        if not 1 <= self.port <= 65535:
            raise ValueError("READYLANE_PORT is out of range")
        return self


def _port(raw: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError("READYLANE_PORT is out of range") from exc
