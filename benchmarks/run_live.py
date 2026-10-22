"""Start the gate, approve one change, restart the process, and record the result."""

import json
import os
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.serve import free_port, running
from scripts.smoke import run_check, run_flow

RESULTS = ROOT / "benchmarks" / "results" / "live_run.json"
LEAD = "local-lead-token"
APPROVER = "local-approver-token"


def main() -> None:
    data = ROOT / "benchmarks" / "results"
    data.mkdir(parents=True, exist_ok=True)
    database = data / "live.sqlite"
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(database) + suffix)
        if path.exists():
            path.unlink()
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
    log_path = str(data / "live.log")
    started = time.perf_counter()
    with running(sys.executable, env, log_path):
        first = run_flow(base, LEAD, APPROVER)
    with running(sys.executable, env, log_path):
        second = run_check(base, LEAD)
    duration_ms = round((time.perf_counter() - started) * 1000, 4)
    report = {
        "evidence_class": "MEASURED",
        "process_listen": "measured",
        "image_build": "not-run",
        "customer_cloud": "not-used",
        "persisted_after_restart": second["final_stage"] == "approved" and second["sha256"] == first["sha256"],
        "duration_ms": duration_ms,
        "base_url": base,
        "health_status": first["health_status"],
        "ready_status": first["ready_status"],
        "create_status": first["create_status"],
        "verify_status": first["verify_status"],
        "lead_decision_status": first["lead_decision_status"],
        "release_status": first["release_status"],
        "approve_status": first["approve_status"],
        "fetch_status": first["fetch_status"],
        "final_stage": second["final_stage"],
        "sha256": second["sha256"],
        "byte_length": first["byte_length"],
        "approver_subject": first["approver_subject"],
        "machine": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
        },
    }
    RESULTS.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(database) + suffix)
        if path.exists():
            path.unlink()
    print(
        f"stage={report['final_stage']} persisted={report['persisted_after_restart']} "
        f"duration_ms={report['duration_ms']} image_build={report['image_build']}"
    )
    if not report["persisted_after_restart"] or report["final_stage"] != "approved":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
