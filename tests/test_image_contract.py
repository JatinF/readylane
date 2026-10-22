"""The image definition and the container procedure stay aligned."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_image_bakes_no_token_and_the_smoke_replaces_the_container():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    script = (ROOT / "scripts" / "container_smoke.sh").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "USER appuser" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "TOKEN" not in dockerfile
    assert "python:3.12-slim" in dockerfile
    assert "docker build -t readylane:ci" in script
    assert "docker rm -f" in script
    assert "/data/readylane.sqlite" in script
    assert "--mode check" in script
    assert "chmod 777" in script
    assert "ubuntu-24.04" in workflow
    assert 'python-version: "3.12"' in workflow
    assert "bash scripts/container_smoke.sh" in workflow
    assert "pytest" in workflow
