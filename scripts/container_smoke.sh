#!/usr/bin/env bash
# Build the image, run the release flow, replace the container, and read the same SQLite file.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
data="$(mktemp -d)"
name="readylane-ci"
cleanup() {
  docker rm -f "$name" >/dev/null 2>&1 || true
  rm -rf "$data"
}
trap cleanup EXIT
chmod 777 "$data"
docker build -t readylane:ci "$root"

run_container() {
  docker run -d --name "$name" \
    -p 127.0.0.1:8080:8080 \
    -e READYLANE_LEAD_TOKEN=ci-lead-token \
    -e READYLANE_LEAD_SUBJECT=SYN-USER-LEAD \
    -e READYLANE_APPROVER_TOKEN=ci-approver-token \
    -e READYLANE_APPROVER_SUBJECT=SYN-USER-APPROVER \
    -e READYLANE_DB=/data/readylane.sqlite \
    -e READYLANE_HOST=0.0.0.0 \
    -e READYLANE_PORT=8080 \
    -v "$data:/data" \
    readylane:ci
}

dump_logs() {
  docker logs "$name" || true
}

run_container
if ! python "$root/scripts/smoke.py" --base-url http://127.0.0.1:8080 --lead-token ci-lead-token --approver-token ci-approver-token --mode flow; then
  dump_logs
  exit 1
fi
docker rm -f "$name"
run_container
if ! python "$root/scripts/smoke.py" --base-url http://127.0.0.1:8080 --lead-token ci-lead-token --mode check --change-id CHG-1001; then
  dump_logs
  exit 1
fi
echo "container smoke passed"
