"""Run curriculum commands and stream their output to the browser.

Deliberately **not** a shell. The learner never types a command here; the
course offers specific commands as buttons, and this module will run only
those. An arbitrary-command endpoint on localhost is a remote code execution
hole for any web page the user happens to have open.

Each command is a fixed argv list. Nothing from the request is interpolated
into a shell string.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
WORKBENCH = ROOT / "workbench"


@dataclass(frozen=True, slots=True)
class Command:
    """One runnable curriculum command."""

    id: str
    label: str
    display: str          # what to echo as the prompt line
    argv: tuple[str, ...]
    timeout: int = 120


def _python() -> str:
    venv = ROOT / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else "python3"


def _pytest_argv(test_file: str) -> tuple[str, ...]:
    return (
        _python(), "-m", "pytest", f"workbench/tests/{test_file}",
        "-q", "--no-header", "-p", "no:cacheprovider", "--tb=short", "--color=yes",
    )


# The whitelist. Anything not here cannot be run.
COMMANDS: dict[str, Command] = {
    "async": Command(
        id="async",
        label="Run the async demo",
        display="make async",
        argv=(_python(), "curriculum/demo_async.py"),
    ),
    "first": Command(
        id="first",
        label="Run the agent demo",
        display="make run-first",
        argv=(_python(), "curriculum/demo_first_contact.py"),
    ),
}


def command_for_test(test_file: str) -> Command:
    """Build a pytest command for one level's test file."""
    name = Path(test_file).name
    return Command(
        id=f"test:{name}",
        label=f"Run {name}",
        display=f"pytest workbench/tests/{name}",
        argv=_pytest_argv(name),
        # Shorter than the default: these suites run in well under a second,
        # so anything near this is a loop that will not terminate.
        timeout=25,
    )


def resolve(command_id: str) -> Command | None:
    """Resolve an id to a whitelisted command, or None."""
    if command_id in COMMANDS:
        return COMMANDS[command_id]
    if command_id.startswith("test:"):
        name = Path(command_id.split(":", 1)[1]).name
        # Only real test files in the workbench may be run.
        if name.startswith("test_") and name.endswith(".py"):
            if (WORKBENCH / "tests" / name).is_file():
                return command_for_test(name)
    return None


async def stream_command(
    command: Command, *, token: str | None = None
) -> AsyncIterator[dict[str, Any]]:
    """Run a command, yielding its output line by line.

    If ``token`` is given, the process is registered so ``cancel(token)`` can
    kill it. An infinite loop in learner code is an expected outcome here, not
    an exceptional one - there has to be a stop button.

    Yields:
        {"type": "start",  "command": str}
        {"type": "out",    "line": str}
        {"type": "exit",   "code": int, "seconds": float, "cancelled": bool}
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(WORKBENCH), str(ROOT / "src"), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # Keep ANSI colour from pytest; the frontend renders it.
    env["FORCE_COLOR"] = "1"
    env["TERM"] = "xterm-256color"

    yield {"type": "start", "command": command.display}

    started = asyncio.get_running_loop().time()
    try:
        process = await asyncio.create_subprocess_exec(
            *command.argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(ROOT),
            env=env,
            # Own process group, so killing it also kills anything it spawned.
            start_new_session=True,
        )
    except OSError as exc:
        yield {"type": "out", "line": f"could not start: {exc}"}
        yield {"type": "exit", "code": 127, "seconds": 0.0, "cancelled": False}
        return

    if token:
        _RUNNING[token] = process

    assert process.stdout is not None
    timed_out = False
    try:
        while True:
            try:
                raw = await asyncio.wait_for(
                    process.stdout.readline(), timeout=command.timeout
                )
            except TimeoutError:
                timed_out = True
                _terminate(process)
                yield {
                    "type": "out",
                    "line": f"timed out after {command.timeout}s - killed",
                }
                break
            if not raw:
                break
            yield {"type": "out", "line": raw.decode(errors="replace").rstrip("\n")}
        await process.wait()
    finally:
        if process.returncode is None:
            _terminate(process)
            await process.wait()
        if token:
            _RUNNING.pop(token, None)

    cancelled = token is not None and token in _CANCELLED
    _CANCELLED.discard(token or "")
    if cancelled:
        yield {"type": "out", "line": "stopped"}

    elapsed = asyncio.get_running_loop().time() - started
    yield {
        "type": "exit",
        "code": process.returncode if process.returncode is not None else -1,
        "seconds": round(elapsed, 2),
        "cancelled": cancelled or timed_out,
    }


# Processes currently running, keyed by a client-supplied token.
_RUNNING: dict[str, asyncio.subprocess.Process] = {}
_CANCELLED: set[str] = set()


def _terminate(process: asyncio.subprocess.Process) -> None:
    """Kill a process and its whole group.

    SIGKILL on the group rather than SIGTERM on the leader: a Python process
    spinning in a tight loop may not service a signal handler promptly, and
    the point of the stop button is that it always works.
    """
    import os as _os
    import signal

    with suppress(ProcessLookupError, PermissionError, OSError):
        _os.killpg(_os.getpgid(process.pid), signal.SIGKILL)
    with suppress(ProcessLookupError):
        process.kill()


def cancel(token: str) -> bool:
    """Kill the run registered under ``token``. Returns whether one was found."""
    process = _RUNNING.get(token)
    if process is None:
        return False
    _CANCELLED.add(token)
    _terminate(process)
    return True
