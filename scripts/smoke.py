"""HTTP smoke for a running release gate. It does not start the process."""

import argparse
import hashlib
import json
import sys
import time

import httpx

ARTIFACT = "readylane-artifact-v1"
CHANGE_ID = "CHG-1001"


def wait_for_health(base_url: str, timeout_s: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout_s
    last = "not-started"
    with httpx.Client(timeout=2.0) as client:
        while time.monotonic() < deadline:
            try:
                response = client.get(base_url.rstrip("/") + "/healthz")
                if response.status_code == 200:
                    return response.json()
                last = f"status {response.status_code}"
            except httpx.HTTPError as exc:
                last = exc.__class__.__name__
            time.sleep(0.15)
    raise RuntimeError(f"healthz did not become ready: {last}")


def run_flow(base_url: str, lead_token: str, approver_token: str, change_id: str = CHANGE_ID, artifact: str = ARTIFACT) -> dict:
    root = base_url.rstrip("/")
    expected = hashlib.sha256(artifact.encode("utf-8")).hexdigest()
    with httpx.Client(timeout=5.0) as client:
        health = wait_for_health(root)
        ready = client.get(root + "/readyz")
        created = client.post(
            root + "/v1/changes",
            headers={"Authorization": f"Bearer {lead_token}"},
            json={"change_id": change_id, "title": "Ship the release gate"},
        )
        verified = client.post(
            root + f"/v1/changes/{change_id}/verify",
            headers={"Authorization": f"Bearer {lead_token}"},
            json={"artifact": artifact},
        )
        lead_decision = client.post(
            root + f"/v1/changes/{change_id}/decision",
            headers={"Authorization": f"Bearer {lead_token}"},
            json={"decision": "approve"},
        )
        released = client.post(
            root + f"/v1/changes/{change_id}/release",
            headers={"Authorization": f"Bearer {lead_token}"},
        )
        approved = client.post(
            root + f"/v1/changes/{change_id}/decision",
            headers={"Authorization": f"Bearer {approver_token}"},
            json={"decision": "approve"},
        )
        fetched = client.get(
            root + f"/v1/changes/{change_id}",
            headers={"Authorization": f"Bearer {lead_token}"},
        )
    body = fetched.json()
    problems = []
    if ready.status_code != 200:
        problems.append(f"ready {ready.status_code}")
    if created.status_code != 201:
        problems.append(f"create {created.status_code}")
    if verified.status_code != 200 or verified.json().get("sha256") != expected:
        problems.append("verify digest mismatch")
    if artifact in verified.text:
        problems.append("verify echoed the artifact")
    if lead_decision.status_code != 403:
        problems.append(f"lead decision {lead_decision.status_code}")
    if released.status_code != 200 or released.json().get("stage") != "pending":
        problems.append("release did not pend")
    if approved.status_code != 200 or approved.json().get("stage") != "approved":
        problems.append("approve failed")
    if body.get("stage") != "approved" or body.get("sha256") != expected:
        problems.append("fetch mismatch")
    if lead_token in fetched.text or approver_token in fetched.text:
        problems.append("response included a token")
    if problems:
        raise RuntimeError("; ".join(problems))
    return {
        "health_status": 200,
        "health": health,
        "ready_status": ready.status_code,
        "create_status": created.status_code,
        "verify_status": verified.status_code,
        "lead_decision_status": lead_decision.status_code,
        "release_status": released.status_code,
        "approve_status": approved.status_code,
        "fetch_status": fetched.status_code,
        "final_stage": body["stage"],
        "sha256": body["sha256"],
        "byte_length": body["byte_length"],
        "approver_subject": body["approver_subject"],
    }


def run_check(base_url: str, lead_token: str, change_id: str = CHANGE_ID, artifact: str = ARTIFACT) -> dict:
    root = base_url.rstrip("/")
    expected = hashlib.sha256(artifact.encode("utf-8")).hexdigest()
    wait_for_health(root)
    with httpx.Client(timeout=5.0) as client:
        ready = client.get(root + "/readyz")
        fetched = client.get(
            root + f"/v1/changes/{change_id}",
            headers={"Authorization": f"Bearer {lead_token}"},
        )
    body = fetched.json()
    if ready.status_code != 200 or fetched.status_code != 200:
        raise RuntimeError(f"check failed ready={ready.status_code} get={fetched.status_code}")
    if body.get("stage") != "approved" or body.get("sha256") != expected:
        raise RuntimeError(f"persisted record is {body.get('stage')}")
    if lead_token in fetched.text:
        raise RuntimeError("response included a token")
    return {"ready_status": ready.status_code, "fetch_status": fetched.status_code, "final_stage": body["stage"], "sha256": body["sha256"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--lead-token", required=True)
    parser.add_argument("--approver-token", default="")
    parser.add_argument("--change-id", default=CHANGE_ID)
    parser.add_argument("--mode", choices=("flow", "check"), default="flow")
    args = parser.parse_args()
    try:
        if args.mode == "flow":
            if len(args.approver_token) < 8:
                raise RuntimeError("approver token is required for flow mode")
            result = run_flow(args.base_url, args.lead_token, args.approver_token, args.change_id)
        else:
            result = run_check(args.base_url, args.lead_token, args.change_id)
    except Exception as exc:
        print(f"smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result))


if __name__ == "__main__":
    main()
