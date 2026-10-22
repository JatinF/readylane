"""HTTP rules for the release gate."""

import hashlib

from fastapi.testclient import TestClient

from readylane.settings import Settings
from readylane.store import Store

LEAD = "lead-token-aaa"
APPROVER = "approver-token-bbb"
ARTIFACT = "readylane-artifact-v1"


def _settings(tmp_path) -> Settings:
    return Settings(
        lead_token=LEAD,
        lead_subject="SYN-USER-LEAD",
        approver_token=APPROVER,
        approver_subject="SYN-USER-APPROVER",
        database_path=str(tmp_path / "gate.sqlite"),
        host="127.0.0.1",
        port=8080,
    ).validated()


def _client(tmp_path):
    settings = _settings(tmp_path)
    return settings, TestClient(create_app(settings))


def create_app(settings):
    from readylane.app import create_app as factory

    return factory(settings)


def test_health_is_open_and_hides_tokens(tmp_path):
    settings, client = _client(tmp_path)
    with client:
        health = client.get("/healthz")
        ready = client.get("/readyz")
    assert health.status_code == 200
    assert health.json()["package"] == "readylane"
    assert health.json()["customer_cloud"] == "not-used"
    assert ready.status_code == 200
    assert ready.json()["database"] == "ok"
    assert LEAD not in health.text
    assert settings.database_path not in health.text


def test_release_flow_and_the_rows_survive_a_new_connection(tmp_path):
    settings, client = _client(tmp_path)
    headers = {"Authorization": f"Bearer {LEAD}"}
    expected = hashlib.sha256(ARTIFACT.encode("utf-8")).hexdigest()
    with client:
        missing = client.post("/v1/changes", json={"change_id": "CHG-1001", "title": "Ship the release gate"})
        assert missing.status_code == 401
        created = client.post(
            "/v1/changes",
            headers=headers,
            json={"change_id": "CHG-1001", "title": "Ship the release gate"},
        )
        assert created.status_code == 201
        assert created.json()["stage"] == "open"
        duplicate = client.post(
            "/v1/changes",
            headers=headers,
            json={"change_id": "CHG-1001", "title": "Ship the release gate"},
        )
        assert duplicate.status_code == 409
        early = client.post(f"/v1/changes/CHG-1001/release", headers=headers)
        assert early.status_code == 409
        assert early.json()["detail"] == "stage is open"
        empty = client.post(
            "/v1/changes/CHG-1001/verify",
            headers=headers,
            json={"artifact": ""},
        )
        assert empty.status_code == 400
        verified = client.post(
            "/v1/changes/CHG-1001/verify",
            headers=headers,
            json={"artifact": ARTIFACT},
        )
        assert verified.status_code == 200
        assert verified.json()["sha256"] == expected
        assert ARTIFACT not in verified.text
        again = client.post(
            "/v1/changes/CHG-1001/verify",
            headers=headers,
            json={"artifact": ARTIFACT},
        )
        assert again.status_code == 200
        assert again.json()["stage"] == "verified"
        extra = client.post(
            "/v1/changes/CHG-1001/decision",
            headers={"Authorization": f"Bearer {APPROVER}"},
            json={"decision": "approve", "note": "skip"},
        )
        assert extra.status_code == 422
        lead_decision = client.post(
            "/v1/changes/CHG-1001/decision",
            headers=headers,
            json={"decision": "approve"},
        )
        assert lead_decision.status_code == 403
        assert lead_decision.json()["detail"] == "approver role required"
        released = client.post("/v1/changes/CHG-1001/release", headers=headers)
        assert released.json()["stage"] == "pending"
        approved = client.post(
            "/v1/changes/CHG-1001/decision",
            headers={"Authorization": f"Bearer {APPROVER}"},
            json={"decision": "approve"},
        )
        assert approved.status_code == 200
        assert approved.json()["stage"] == "approved"
        assert approved.json()["approver_subject"] == "SYN-USER-APPROVER"
        repeat = client.post(
            "/v1/changes/CHG-1001/decision",
            headers={"Authorization": f"Bearer {APPROVER}"},
            json={"decision": "approve"},
        )
        assert repeat.status_code == 409
        fetched = client.get("/v1/changes/CHG-1001", headers={"Authorization": f"Bearer {APPROVER}"})
        assert fetched.json()["stage"] == "approved"
        assert LEAD not in fetched.text
        assert APPROVER not in fetched.text

    reopened = Store(settings.database_path)
    assert reopened.get("CHG-1001")["stage"] == "approved"
    reopened.close()


def test_rejected_release_stays_rejected(tmp_path):
    _settings_obj, client = _client(tmp_path)
    headers = {"Authorization": f"Bearer {LEAD}"}
    with client:
        client.post("/v1/changes", headers=headers, json={"change_id": "CHG-2002", "title": "Hold the release"})
        client.post("/v1/changes/CHG-2002/verify", headers=headers, json={"artifact": ARTIFACT})
        client.post("/v1/changes/CHG-2002/release", headers=headers)
        rejected = client.post(
            "/v1/changes/CHG-2002/decision",
            headers={"Authorization": f"Bearer {APPROVER}"},
            json={"decision": "reject"},
        )
        assert rejected.json()["stage"] == "rejected"
        second = client.post(
            "/v1/changes/CHG-2002/decision",
            headers={"Authorization": f"Bearer {APPROVER}"},
            json={"decision": "approve"},
        )
        assert second.status_code == 409
        assert second.json()["detail"] == "release is already decided"


def test_approver_cannot_create_and_bad_ids_are_rejected(tmp_path):
    _settings_obj, client = _client(tmp_path)
    with client:
        created = client.post(
            "/v1/changes",
            headers={"Authorization": f"Bearer {APPROVER}"},
            json={"change_id": "CHG-3003", "title": "no"},
        )
        assert created.status_code == 403
        assert created.json()["detail"] == "lead role required"
        bad = client.post(
            "/v1/changes",
            headers={"Authorization": f"Bearer {LEAD}"},
            json={"change_id": "bad id", "title": "no"},
        )
        assert bad.status_code == 400
        blank = client.post(
            "/v1/changes",
            headers={"Authorization": f"Bearer {LEAD}"},
            json={"change_id": "CHG-3003", "title": "   "},
        )
        assert blank.status_code == 400
