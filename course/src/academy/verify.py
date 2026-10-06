"""Verification: the course's source of truth.

A core design rule of Harness Academy: **the tutor never grades**. An LLM
saying "looks right!" teaches nothing and is sometimes wrong. Instead every
claim the course makes about your code is produced by running your code.

Three check kinds, in increasing order of what they prove:

``predict``
    You state what will happen before running anything. Graded by comparing
    your answer to a *recorded execution*, not to an answer key written by
    hand. If the specimen changes, the expected answer changes with it.

``implement``
    Your code is imported and exercised by real pytest assertions. Pass/fail
    comes from the interpreter.

``explain``
    Free-form reasoning. This is the only kind the tutor assesses, and it is
    never gating - it produces feedback, not a score.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
WORKBENCH = ROOT / "workbench"
CURRICULUM = ROOT / "curriculum"
TAU = ROOT / "tau"


@dataclass(slots=True)
class CheckOutcome:
    """The result of one verification run."""

    passed: bool
    summary: str
    detail: str = ""
    # Structured observations the UI can render, e.g. an event trace diff.
    observed: Any = None
    expected: Any = None
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TestReport:
    passed: int = 0
    failed: int = 0
    errors: int = 0
    failures: list[dict[str, str]] = field(default_factory=list)
    raw: str = ""

    @property
    def ok(self) -> bool:
        return self.failed == 0 and self.errors == 0 and self.passed > 0


def _python() -> str:
    """Return the interpreter that has harnesskit importable."""
    venv = ROOT / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else sys.executable


def run_pytest(test_file: Path, *, timeout: int = 90) -> TestReport:
    """Run one pytest file against the learner's workbench and parse results.

    The workbench is placed first on ``PYTHONPATH`` so the test imports *your*
    module, not a reference implementation.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(WORKBENCH), str(ROOT / "src"), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    try:
        proc = subprocess.run(
            [
                _python(),
                "-m",
                "pytest",
                str(test_file),
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
                "--tb=short",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(ROOT),
        )
        raw = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return TestReport(errors=1, raw=f"Timed out after {timeout}s. Infinite loop?")

    return _parse_pytest(raw)


def _parse_pytest(raw: str) -> TestReport:
    report = TestReport(raw=raw)
    for line in raw.splitlines():
        stripped = line.strip()
        # pytest -q summary line, e.g. "3 failed, 2 passed in 0.41s"
        if " in " in stripped and ("passed" in stripped or "failed" in stripped):
            for chunk in stripped.split(" in ")[0].split(","):
                chunk = chunk.strip()
                parts = chunk.split()
                if len(parts) != 2 or not parts[0].isdigit():
                    continue
                count, label = int(parts[0]), parts[1]
                if label.startswith("passed"):
                    report.passed = count
                elif label.startswith("failed"):
                    report.failed = count
                elif label.startswith("error"):
                    report.errors = count
        if stripped.startswith("FAILED ") or stripped.startswith("ERROR "):
            name, _, reason = stripped.partition(" - ")
            report.failures.append(
                {"test": name.split("::")[-1].strip(), "reason": reason.strip()}
            )
    if report.passed == 0 and report.failed == 0 and report.errors == 0:
        if "no tests ran" in raw.lower() or "collected 0" in raw.lower():
            report.errors = 1
    return report


def extract_failure_hint(report: TestReport) -> str:
    """Pull the single most useful line out of a pytest failure.

    Learners drown in tracebacks. One precise assertion line teaches more.
    """
    if report.failures:
        first = report.failures[0]
        return f"{first['test']}: {first['reason']}" if first["reason"] else first["test"]
    for line in report.raw.splitlines():
        stripped = line.strip()
        if stripped.startswith("E   ") and len(stripped) > 6:
            return stripped[4:].strip()
        if "ModuleNotFoundError" in stripped or "ImportError" in stripped:
            return stripped
    return ""


async def run_trace(script: Path, *, timeout: int = 60) -> tuple[bool, Any, str]:
    """Execute a trace-producing script and return its JSON payload.

    Used by ``predict`` checks: the "expected answer" is whatever the specimen
    actually does right now.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(WORKBENCH), str(ROOT / "src"), str(TAU / "src"), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)

    proc = await asyncio.create_subprocess_exec(
        _python(),
        str(script),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=str(ROOT),
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        return False, None, f"Trace timed out after {timeout}s"

    text = out.decode()
    try:
        # The script's last stdout line is its JSON result.
        payload = json.loads([ln for ln in text.splitlines() if ln.strip()][-1])
        return True, payload, err.decode()
    except (json.JSONDecodeError, IndexError):
        return False, None, (err.decode() or text)[:2000]
