"""The committed workstation run is the file benchmarks/run_live.py wrote."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "benchmarks" / "results" / "live_run.json"


def test_committed_live_run_records_a_restart():
    report = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert report["evidence_class"] == "MEASURED"
    assert report["process_listen"] == "measured"
    assert report["image_build"] == "not-run"
    assert report["customer_cloud"] == "not-used"
    assert report["persisted_after_restart"] is True
    assert report["final_stage"] == "approved"
    assert report["health_status"] == 200
    assert report["ready_status"] == 200
    assert report["lead_decision_status"] == 403
    assert report["approve_status"] == 200
    assert report["byte_length"] == len(b"readylane-artifact-v1")
    assert report["approver_subject"] == "SYN-USER-APPROVER"
    assert report["duration_ms"] >= 0
    assert report["machine"]["python"].startswith("3.12")
    assert len(report["sha256"]) == 64
