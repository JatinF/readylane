"""Start the release gate. Missing settings exit 2 and do not print tokens."""

import sys

import uvicorn

from readylane.settings import Settings


def main() -> None:
    try:
        settings = Settings.from_env().validated()
    except ValueError as exc:
        print(f"readylane: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    uvicorn.run(
        "readylane.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
