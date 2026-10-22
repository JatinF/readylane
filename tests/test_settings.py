"""Settings fail closed and do not echo tokens."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from readylane.settings import Settings

ROOT = Path(__file__).resolve().parents[1]


def test_matching_tokens_are_rejected_without_echoing_them():
    token = "same-token-value"
    with pytest.raises(ValueError) as exc:
        Settings(token, "SYN-USER-LEAD", token, "SYN-USER-APPROVER", "gate.sqlite").validated()
    assert "must differ" in str(exc.value)
    assert token not in str(exc.value)


def test_process_exits_when_tokens_are_missing():
    env = {key: value for key, value in os.environ.items() if not key.startswith("READYLANE_")}
    env["PYTHONPATH"] = str(ROOT / "src")
    env["READYLANE_LEAD_TOKEN"] = "short"
    env["READYLANE_APPROVER_TOKEN"] = "approver-token-ok"
    env["READYLANE_LEAD_SUBJECT"] = "SYN-USER-LEAD"
    env["READYLANE_APPROVER_SUBJECT"] = "SYN-USER-APPROVER"
    env["READYLANE_DB"] = "gate.sqlite"
    proc = subprocess.run(
        [sys.executable, "-m", "readylane"],
        env=env,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert proc.returncode == 2
    assert "at least 8 characters" in proc.stderr
    assert "short" not in proc.stderr
    assert "approver-token-ok" not in proc.stderr
