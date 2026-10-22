"""SQLite keeps an approved release after the connection closes."""

import hashlib

from readylane.store import Store
from readylane.verify import digest_artifact


def test_reopen_reads_the_approved_release(tmp_path):
    path = tmp_path / "gate.sqlite"
    digest = digest_artifact("readylane-artifact-v1")
    assert digest["sha256"] == hashlib.sha256(b"readylane-artifact-v1").hexdigest()
    store = Store(str(path))
    store.create("CHG-1001", "Ship the release gate", "SYN-USER-LEAD")
    store.verify("CHG-1001", digest["sha256"], digest["byte_length"])
    store.request_release("CHG-1001")
    store.decide("CHG-1001", "SYN-USER-APPROVER", "approve")
    store.close()

    again = Store(str(path))
    row = again.get("CHG-1001")
    again.close()
    assert row["stage"] == "approved"
    assert row["sha256"] == digest["sha256"]
    assert row["byte_length"] == len(b"readylane-artifact-v1")
    assert row["approver_subject"] == "SYN-USER-APPROVER"
    assert row["requester_subject"] == "SYN-USER-LEAD"
