"""Digest the release artifact. The bytes are not stored."""

import hashlib

MAX_ARTIFACT_BYTES = 1_000_000


def digest_artifact(text: str) -> dict:
    raw = text.encode("utf-8")
    if not raw:
        raise ValueError("artifact is empty")
    if len(raw) > MAX_ARTIFACT_BYTES:
        raise ValueError("artifact is too large")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "byte_length": len(raw)}
