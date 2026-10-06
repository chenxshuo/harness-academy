"""The AI tutor: a real coding agent, wired to your current context.

The tutor is the user's installed ``pi`` agent driven over its RPC protocol
(JSON lines on stdin/stdout). That choice is pedagogical as well as practical:
pi is a production coding-agent harness, so while you reconstruct the
architecture, a working instance of that same architecture is answering your
questions. The event stream you will learn to read in Act I is literally the
stream this module parses.

What the tutor can see, assembled fresh on every message:
    - the level and step you are on, and the question it poses
    - your current workbench file
    - the most recent verification output (including the failing assertion)
    - your last prediction and whether it was right
    - your mastery profile and whether you are being over- or under-challenged
    - the specimen at ``tau/``, which it can read, grep, and run

What the tutor is told *not* to do: hand you the answer.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

TUTOR_SYSTEM = """\
You are the tutor inside Harness Academy, a course where the learner
reconstructs a coding-agent harness instead of reading about one.

THE ONE RULE: do not do the learner's thinking for them.

They have a verification engine that tells them whether their code is correct.
They do not need you for that. They need you for the thing a test cannot do:
provoke the right question.

Default moves, roughly in order of preference:
  - Ask what they expect to happen, then suggest the experiment that checks it.
  - Ask them to name the component responsible before you confirm it.
  - Point at a specific runtime observation ("look at provider.calls - how many
    entries?") rather than explaining what it would show.
  - When they propose a design, ask what breaks it, not whether it is right.
  - When they are wrong, ask a question whose honest answer exposes the problem.

HINT LADDER. When stuck, climb one rung at a time, never start at the top:
  1. conceptual   - "what has to be true for the loop to stop?"
  2. architectural- "which layer should own that decision?"
  3. subsystem    - "this lives in the harness, not the loop"
  4. file         - "look at tau/src/tau_agent/harness.py"
  5. function     - "read _append_interrupted_tool_results"
  6. explanation  - only now, and only if they have genuinely tried

Judge where they are from the context block, not from how plainly they ask. If
they have already failed three times and used two hints, skip to rung 4 or 5;
grinding is not productive struggle. If they are on their first attempt, stay
at rung 1 even if they ask you to just tell them. Say plainly that you are
holding back and why.

If the learner is clearly frustrated or has burned a lot of attempts, drop the
Socratic posture and help concretely. The goal is understanding, not ritual.

TOOLS. You are a coding agent, so act like one. Read the specimen at tau/.
Grep it. Run a snippet to settle a question empirically. Read their workbench
file before commenting on their code. Prefer a verifiable observation over an
assertion - and when you do explain, ground it in a path and a line.

NEVER paste a working implementation of the current step's target file. Showing
the finished answer destroys the only reason the exercise exists. Sketches of
*shape* ("you will need a while loop whose condition is...") are fine.

Be concise. Terminal-width prose, no preamble. Plain text, no emoji.
"""


@dataclass
class TutorContext:
    """Everything the tutor is allowed to know about the current moment."""

    level_id: str = ""
    level_title: str = ""
    level_question: str = ""
    step_id: str = ""
    step_kind: str = ""
    step_title: str = ""
    step_body: str = ""
    target_file: str = ""
    learner_code: str = ""
    last_result: dict[str, Any] | None = None
    last_prediction: dict[str, Any] | None = None
    attempts: int = 0
    hints_used: int = 0
    difficulty: str = ""
    struggling: list[str] = field(default_factory=list)
    gaps: list[dict[str, str]] = field(default_factory=list)
    specimen_paths: list[str] = field(default_factory=list)
    # Text the learner highlighted in the page before asking.
    quote: str = ""

    def render(self) -> str:
        """Render the context block prepended to each learner message."""
        lines = ["<learning-context>"]
        if self.level_title:
            lines.append(f"Level: {self.level_title} ({self.level_id})")
        if self.level_question:
            lines.append(f"Driving question: {self.level_question}")
        if self.step_title:
            lines.append(f"Current step [{self.step_kind}]: {self.step_title}")
        if self.step_body:
            body = self.step_body.strip()
            if len(body) > 900:
                body = body[:900] + "..."
            lines.append(f"Step brief:\n{body}")
        if self.specimen_paths:
            lines.append("Relevant specimen files: " + ", ".join(self.specimen_paths))

        lines.append(
            f"Attempts on this step: {self.attempts}. Hints opened: {self.hints_used}."
        )
        if self.difficulty:
            readable = {
                "too-easy": "Recent work has been easy for them - push harder.",
                "too-hard": "They have been struggling - be more concrete.",
                "well-matched": "Difficulty is about right.",
                "calibrating": "Not enough data on their level yet.",
            }.get(self.difficulty, self.difficulty)
            lines.append(f"Difficulty read: {readable}")
        if self.struggling:
            lines.append("Shaky concepts: " + ", ".join(self.struggling))
        for gap in self.gaps:
            if gap.get("gap") == "predicts-but-cannot-build":
                lines.append(
                    f"NOTE: they can predict '{gap['concept']}' but not implement it. "
                    "Push toward writing code, not more discussion."
                )
            elif gap.get("gap") == "builds-but-cannot-explain":
                lines.append(
                    f"NOTE: they can implement '{gap['concept']}' but not explain it. "
                    "Ask them to articulate why it works."
                )

        if self.target_file and self.learner_code:
            code = self.learner_code
            if len(code) > 6000:
                code = code[:6000] + "\n... (truncated)"
            lines.append(f"\nTheir current {self.target_file}:\n```python\n{code}\n```")

        if self.last_result:
            result = self.last_result
            status = "PASSED" if result.get("passed") else "FAILED"
            lines.append(f"\nLast verification: {status} - {result.get('summary', '')}")
            if detail := result.get("detail"):
                lines.append(f"Failure detail: {str(detail)[:700]}")

        if self.quote:
            quoted = self.quote.strip()
            if len(quoted) > 1500:
                quoted = quoted[:1500] + "..."
            lines.append(
                "\nThey highlighted this passage in the page and are asking "
                f"about it specifically:\n<<<\n{quoted}\n>>>\n"
                "Answer about THIS text. If it is course prose, explain the "
                "idea; if it is code, reason about that code."
            )

        if self.last_prediction:
            pred = self.last_prediction
            verdict = "correct" if pred.get("passed") else "incorrect"
            lines.append(
                f"\nTheir last prediction was {verdict}. "
                f"They answered: {pred.get('answer')!r}."
            )
            if not pred.get("passed") and pred.get("expected") is not None:
                lines.append(
                    "Do NOT state the right answer. Ask a question that makes the "
                    "mismatch visible to them."
                )

        lines.append("</learning-context>")
        return "\n".join(lines)


class TutorUnavailable(RuntimeError):
    pass


class PiTutor:
    """Drives one persistent ``pi --mode rpc`` subprocess.

    Conversation history lives inside pi's own session, which is the point:
    the tutor accumulates context about the learner across a sitting, the same
    way a coding agent accumulates context about a task.
    """

    def __init__(self, cwd: Path | None = None) -> None:
        self.cwd = cwd or ROOT
        self._proc: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._next_id = 0
        self.last_error: str = ""

    @staticmethod
    def available() -> bool:
        return shutil.which("pi") is not None

    async def start(self) -> None:
        if self._proc and self._proc.returncode is None:
            return
        if not self.available():
            raise TutorUnavailable(
                "The `pi` command was not found. Install it, or use the course "
                "without the tutor - every exercise is verified locally and "
                "works fine without an agent."
            )

        prompt_file = ROOT / ".academy" / "tutor-system.md"
        prompt_file.parent.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text(TUTOR_SYSTEM, encoding="utf-8")

        env = dict(os.environ)
        env["PI_OFFLINE"] = "1"  # no startup network chatter
        self._proc = await asyncio.create_subprocess_exec(
            "pi",
            "--mode",
            "rpc",
            "--no-session",
            "--system-prompt",
            TUTOR_SYSTEM,
            "--approve",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.cwd),
            env=env,
        )

    async def stop(self) -> None:
        if self._proc and self._proc.returncode is None:
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except (TimeoutError, ProcessLookupError):
                self._proc.kill()
        self._proc = None

    async def ask(self, message: str, context: TutorContext) -> AsyncIterator[dict[str, Any]]:
        """Send one message and yield normalized events as the tutor responds.

        Yielded shapes:
            {"type": "text", "delta": str}   streaming assistant text
            {"type": "tool", "name": str}    the tutor used a coding tool
            {"type": "done"}                 turn finished
            {"type": "error", "message": str}
        """
        async with self._lock:
            try:
                await self.start()
            except TutorUnavailable as exc:
                yield {"type": "error", "message": str(exc)}
                return

            proc = self._proc
            if proc is None or proc.stdin is None or proc.stdout is None:
                yield {"type": "error", "message": "Tutor process is not running."}
                return

            self._next_id += 1
            request_id = str(self._next_id)
            payload = f"{context.render()}\n\n{message}"
            command = json.dumps(
                {"id": request_id, "type": "prompt", "message": payload}
            )

            try:
                proc.stdin.write((command + "\n").encode())
                await proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                await self.stop()
                yield {"type": "error", "message": "Tutor connection dropped. Retry."}
                return

            async for event in self._read_turn(proc):
                yield event

    async def _read_turn(
        self, proc: asyncio.subprocess.Process
    ) -> AsyncIterator[dict[str, Any]]:
        """Translate pi's RPC event stream into UI events, until the turn settles."""
        assert proc.stdout is not None
        while True:
            try:
                raw = await asyncio.wait_for(proc.stdout.readline(), timeout=240)
            except TimeoutError:
                yield {"type": "error", "message": "Tutor timed out."}
                return
            if not raw:
                yield {"type": "error", "message": "Tutor process ended."}
                await self.stop()
                return

            try:
                event = json.loads(raw.decode())
            except json.JSONDecodeError:
                continue

            kind = event.get("type")

            if kind == "response" and not event.get("success", True):
                yield {"type": "error", "message": str(event.get("error", "rpc error"))}
                return

            if kind == "message_update":
                inner = event.get("assistantMessageEvent") or {}
                if inner.get("type") == "text_delta" and (delta := inner.get("delta")):
                    yield {"type": "text", "delta": delta}

            elif kind == "tool_execution_start":
                if name := event.get("toolName") or event.get("tool_name"):
                    yield {"type": "tool", "name": name}

            elif kind == "message_end":
                message = event.get("message") or {}
                # Surface provider failures rather than hanging silently.
                if message.get("role") == "assistant" and message.get("stopReason") == "error":
                    yield {
                        "type": "error",
                        "message": message.get("errorMessage") or "Model request failed.",
                    }

            elif kind == "agent_settled":
                yield {"type": "done"}
                return


_tutor: PiTutor | None = None


def get_tutor() -> PiTutor:
    global _tutor
    if _tutor is None:
        _tutor = PiTutor()
    return _tutor
