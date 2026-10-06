"""`academy` - start the course."""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _free_port(preferred: int) -> tuple[int, bool]:
    """Return a usable port and whether it differs from the one requested."""
    for candidate in range(preferred, preferred + 20):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", candidate)) != 0:
                return candidate, candidate != preferred
    return preferred, False


def _preflight() -> list[str]:
    """Check the environment and return human-readable warnings."""
    warnings: list[str] = []
    if not (ROOT / "tau").is_dir():
        warnings.append(
            "The study specimen was not found at ./tau - levels that read it "
            "will not work. Clone https://github.com/huggingface/tau into ./tau"
        )
    import shutil

    if shutil.which("pi") is None:
        warnings.append(
            "The `pi` command was not found, so the AI tutor is disabled. "
            "Everything else works: all exercises are verified locally."
        )
    return warnings


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="academy", description="Harness Academy - learn coding-agent architecture."
    )
    parser.add_argument("--port", type=int, default=7788)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--reload", action="store_true", help="Developer auto-reload.")
    args = parser.parse_args()

    import uvicorn

    from academy.server import prepare

    prepare()
    port, moved = _free_port(args.port)
    url = f"http://{args.host}:{port}/"

    print("\n  Harness Academy")
    print(f"  {url}\n")
    if moved:
        # Say so loudly. Silently moving ports means a stale server on the
        # original one keeps answering a browser tab you forgot to close.
        print(
            f"  note: port {args.port} was already in use, so this instance is\n"
            f"        on {port}. If a browser tab is open on {args.port}, it is\n"
            f"        talking to a DIFFERENT server. Close it, or stop that\n"
            f"        process with: lsof -ti:{args.port} | xargs kill\n"
        )
    for warning in _preflight():
        print(f"  note: {warning}\n")

    if not args.no_browser:
        def open_later() -> None:
            time.sleep(1.2)
            webbrowser.open(url)

        threading.Thread(target=open_later, daemon=True).start()

    uvicorn.run(
        "academy.server:app",
        host=args.host,
        port=port,
        reload=args.reload,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
