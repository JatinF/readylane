"""The release flow against a real listening socket, then a second process."""

import os
import sys
from pathlib import Path

from scripts.serve import free_port, running
from scripts.smoke import run_check, run_flow

ROOT = Path(__file__).resolve().parents[1]
LEAD = "socket-lead-token"
APPROVER = "socket-approver-token"


def test_socket_restart_keeps_the_approved_release(tmp_path):
    database = tmp_path / "gate.sqlite"
    port = free_port()
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(ROOT / "src"),
            "READYLANE_LEAD_TOKEN": LEAD,
            "READYLANE_LEAD_SUBJECT": "SYN-USER-LEAD",
            "READYLANE_APPROVER_TOKEN": APPROVER,
            "READYLANE_APPROVER_SUBJECT": "SYN-USER-APPROVER",
            "READYLANE_DB": str(database),
            "READYLANE_HOST": "127.0.0.1",
            "READYLANE_PORT": str(port),
        }
    )
    base = f"http://127.0.0.1:{port}"
    log_path = str(tmp_path / "server.log")
    with running(sys.executable, env, log_path):
        first = run_flow(base, LEAD, APPROVER, change_id="CHG-1001")
    with running(sys.executable, env, log_path):
        second = run_check(base, LEAD, change_id="CHG-1001")
    assert first["final_stage"] == "approved"
    assert first["lead_decision_status"] == 403
    assert first["byte_length"] == len(b"readylane-artifact-v1")
    assert second["final_stage"] == "approved"
    assert second["sha256"] == first["sha256"]
    log_text = Path(log_path).read_text(encoding="utf-8")
    assert LEAD not in log_text
    assert APPROVER not in log_text
    assert "readylane listening" in log_text
