"""Start and stop one local release-gate process."""

import socket
import subprocess
from contextlib import contextmanager


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def running(python: str, env: dict, log_path: str):
    with open(log_path, "w", encoding="utf-8") as log:
        proc = subprocess.Popen(
            [python, "-m", "readylane"],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            yield proc
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=8)
