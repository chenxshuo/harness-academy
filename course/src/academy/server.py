"""The local course server.

Architecture note, since this course is partly about architecture: the server
is deliberately thin. It owns no learning logic. It routes between four things
that already exist:

    curriculum.py  what to teach
    verify.py      whether the learner is right
    progress.py    what they know
    tutor.py       a real coding agent

The browser gets static files and JSON. No build step, no bundler, no
framework. Starting the course should never require an npm install.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from academy.diagrams import expand as expand_diagrams
from academy.curriculum import (
    all_levels,
    find_level,
    load_curriculum,
    write_starter_files,
)
from academy.progress import ACHIEVEMENTS, Progress, check_achievements
from academy.runner import cancel as cancel_run
from academy.runner import resolve as resolve_command
from academy.runner import stream_command
from academy.tutor import TutorContext, get_tutor
from academy.verify import (
    WORKBENCH,
    CheckOutcome,
    extract_failure_hint,
    run_pytest,
    run_trace,
)

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
CURRICULUM_DIR = ROOT / "curriculum"
TAU = ROOT / "tau"

app = FastAPI(title="Harness Academy")

ACTS = load_curriculum()
LEVELS = all_levels(ACTS)
PROGRESS = Progress(ROOT / ".academy" / "progress.json")

# Per-step UI state the tutor needs but that is not worth persisting.
_session: dict[str, Any] = {"last_result": {}, "hints_open": {}}


# ---------------------------------------------------------------- models


class PredictBody(BaseModel):
    level_id: str
    step_id: str
    answer: str | list[str]
    confidence: str = ""


class VerifyBody(BaseModel):
    level_id: str
    step_id: str


class SaveBody(BaseModel):
    path: str
    content: str


class ExplainBody(BaseModel):
    level_id: str
    step_id: str
    text: str


class AskBody(BaseModel):
    level_id: str = ""
    step_id: str = ""
    message: str
    # Text the learner highlighted in the page before asking.
    quote: str = ""


class StopBody(BaseModel):
    token: str


class HintBody(BaseModel):
    level_id: str
    step_id: str
    index: int


# ------------------------------------------------------------ curriculum


@app.get("/api/curriculum")
async def get_curriculum() -> dict[str, Any]:
    """The map: acts, levels, lock state, and progress."""
    acts_payload = []
    for act in ACTS:
        levels_payload = []
        for level in act.levels:
            data = level.public()
            data["unlocked"] = PROGRESS.unlocked(level, ACTS)
            data["done"] = PROGRESS.level_done(level)
            data["started"] = PROGRESS.level_started(level)
            data["steps_done"] = sum(
                1 for s in level.steps if PROGRESS.is_done(level.id, s.id)
            )
            levels_payload.append(data)
        acts_payload.append(
            {
                "id": act.id,
                "title": act.title,
                "subtitle": act.subtitle,
                "levels": levels_payload,
            }
        )
    return {
        "acts": acts_payload,
        "progress": PROGRESS.summary(ACTS),
        "achievements": ACHIEVEMENTS,
        "tutor_available": get_tutor().available(),
    }


@app.get("/api/level/{level_id}")
async def get_level(level_id: str) -> dict[str, Any]:
    level = find_level(ACTS, level_id)
    if level is None:
        raise HTTPException(404, "No such level")

    data = level.public()
    data["reveal"] = expand_diagrams(level.reveal)
    data["transfer"] = expand_diagrams(level.transfer)
    data["hook"] = expand_diagrams(data.get("hook", ""))
    data["unlocked"] = PROGRESS.unlocked(level, ACTS)

    for step_payload, step in zip(data["steps"], level.steps, strict=True):
        step_payload["body"] = expand_diagrams(step_payload.get("body", ""))
        done = PROGRESS.is_done(level.id, step.id)
        step_payload["done"] = done
        record = PROGRESS.steps.get(f"{level.id}/{step.id}")
        step_payload["attempts"] = record.attempts if record else 0
        # The "after" text is the payoff; only show it once earned.
        step_payload["after"] = expand_diagrams(step.after) if done else ""
        if step.kind == "implement" and step.target_file:
            path = WORKBENCH / step.target_file
            step_payload["code"] = (
                path.read_text(encoding="utf-8") if path.exists() else step.starter
            )
            step_payload["test_source"] = _read_test(step.test_file)
    return data


def _read_test(test_file: str) -> str:
    if not test_file:
        return ""
    path = WORKBENCH / test_file
    return path.read_text(encoding="utf-8") if path.exists() else ""


@app.get("/api/source")
async def get_source(path: str) -> dict[str, Any]:
    """Read a specimen file. Confined to the project root."""
    target = (ROOT / path).resolve()
    if not target.is_relative_to(ROOT) or not target.is_file():
        raise HTTPException(404, "Not found")
    if target.stat().st_size > 400_000:
        raise HTTPException(413, "File too large to display")
    return {"path": path, "content": target.read_text(encoding="utf-8", errors="replace")}


@app.get("/api/tree")
async def get_tree(path: str = "tau/src/tau_agent") -> dict[str, Any]:
    """List a specimen directory, for the file browser."""
    target = (ROOT / path).resolve()
    if not target.is_relative_to(ROOT) or not target.is_dir():
        raise HTTPException(404, "Not found")
    entries = []
    for child in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name)):
        if child.name.startswith((".", "__")):
            continue
        entries.append(
            {
                "name": child.name,
                "path": str(child.relative_to(ROOT)),
                "dir": child.is_dir(),
                "lines": (
                    len(child.read_text(errors="replace").splitlines())
                    if child.is_file() and child.suffix == ".py"
                    else None
                ),
            }
        )
    return {"path": path, "entries": entries}


# ---------------------------------------------------------------- checks


@app.post("/api/predict")
async def post_predict(body: PredictBody) -> dict[str, Any]:
    """Grade a prediction - against a recorded execution where one exists."""
    level = find_level(ACTS, body.level_id)
    step = level.step(body.step_id) if level else None
    if level is None or step is None:
        raise HTTPException(404, "No such step")

    expected: Any = step.answer
    evidence: Any = None

    # Prefer a computed answer over a hardcoded one.
    if step.trace:
        ok, payload, _err = await run_trace(CURRICULUM_DIR / step.trace)
        if ok and isinstance(payload, dict) and "answer" in payload:
            expected = payload["answer"]
            evidence = payload

    if step.multi:
        given = sorted(body.answer if isinstance(body.answer, list) else [body.answer])
        want = sorted(expected if isinstance(expected, list) else [expected])
        passed = given == want
    else:
        passed = str(body.answer) == str(expected)

    notes = {c.id: c.note for c in step.choices}
    chosen = body.answer if isinstance(body.answer, list) else [body.answer]

    PROGRESS.record(
        level_id=level.id,
        step_id=step.id,
        kind="predict",
        passed=passed,
        concepts=level.concepts,
        hints_used=_session["hints_open"].get(f"{level.id}/{step.id}", 0),
        confidence=body.confidence,
        answer=body.answer,
    )
    earned = check_achievements(PROGRESS)

    _session["last_result"] = {
        "passed": passed,
        "summary": "Prediction correct" if passed else "Prediction incorrect",
        "answer": body.answer,
        "expected": expected if not passed else None,
    }

    return {
        "passed": passed,
        # Notes on every option, so a right answer still teaches why the others
        # were wrong - that is usually where the misconception lives.
        "notes": [
            {"id": c.id, "label": c.label, "note": notes.get(c.id, ""),
             "chosen": c.id in chosen,
             "correct": c.id in (expected if isinstance(expected, list) else [expected])}
            for c in step.choices
        ],
        "after": expand_diagrams(step.after) if passed else "",
        "evidence": evidence,
        "achievements": [ACHIEVEMENTS[a] for a in earned],
        "progress": PROGRESS.summary(ACTS),
    }


@app.post("/api/verify")
async def post_verify(body: VerifyBody) -> dict[str, Any]:
    """Run a level's tests against the learner's code."""
    level = find_level(ACTS, body.level_id)
    step = level.step(body.step_id) if level else None
    if level is None or step is None or not step.test_file:
        raise HTTPException(404, "No test for this step")

    began = time.monotonic()
    report = await asyncio.to_thread(run_pytest, WORKBENCH / step.test_file)
    elapsed = int((time.monotonic() - began) * 1000)

    hint = extract_failure_hint(report)
    outcome = CheckOutcome(
        passed=report.ok,
        summary=(
            f"{report.passed} passed"
            if report.ok
            else f"{report.passed} passed, {report.failed + report.errors} failed"
        ),
        detail=hint,
        observed=[f["test"] for f in report.failures],
        duration_ms=elapsed,
    )

    PROGRESS.record(
        level_id=level.id,
        step_id=step.id,
        kind="implement",
        passed=report.ok,
        concepts=level.concepts,
        hints_used=_session["hints_open"].get(f"{level.id}/{step.id}", 0),
        seconds=elapsed / 1000,
    )
    earned = check_achievements(PROGRESS)
    _session["last_result"] = outcome.to_dict()

    return {
        **outcome.to_dict(),
        "failures": report.failures,
        "raw": report.raw[-4000:],
        "after": expand_diagrams(step.after) if report.ok else "",
        "achievements": [ACHIEVEMENTS[a] for a in earned],
        "progress": PROGRESS.summary(ACTS),
    }


@app.post("/api/explain")
async def post_explain(body: ExplainBody) -> dict[str, Any]:
    """Record a written explanation. Never auto-graded."""
    level = find_level(ACTS, body.level_id)
    step = level.step(body.step_id) if level else None
    if level is None or step is None:
        raise HTTPException(404, "No such step")
    if len(body.text.strip()) < 40:
        return {
            "passed": False,
            "summary": "Say more - a sentence or two at minimum.",
        }

    PROGRESS.add_note(level.id, body.text)
    PROGRESS.record(
        level_id=level.id,
        step_id=step.id,
        kind=step.kind,
        passed=True,
        concepts=level.concepts,
    )
    earned = check_achievements(PROGRESS)
    return {
        "passed": True,
        "summary": "Recorded. Ask the tutor to challenge it.",
        "after": expand_diagrams(step.after),
        "achievements": [ACHIEVEMENTS[a] for a in earned],
        "progress": PROGRESS.summary(ACTS),
    }


@app.get("/api/workfile")
async def get_workfile(path: str) -> dict[str, Any]:
    """Read one of the learner's own workbench files.

    Used by "bring forward", so code written in an earlier step can be copied
    into the next one without retyping it.
    """
    target = (WORKBENCH / path).resolve()
    if not target.is_relative_to(WORKBENCH) or not target.is_file():
        raise HTTPException(404, "Not found")
    return {"path": path, "content": target.read_text(encoding="utf-8")}


@app.post("/api/save")
async def post_save(body: SaveBody) -> dict[str, Any]:
    """Write the learner's workbench file."""
    target = (WORKBENCH / body.path).resolve()
    if not target.is_relative_to(WORKBENCH):
        raise HTTPException(400, "Path outside the workbench")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body.content, encoding="utf-8")
    return {"saved": True, "path": body.path}


@app.post("/api/hint")
async def post_hint(body: HintBody) -> dict[str, Any]:
    """Reveal one hint. Opening hints is recorded - it informs the tutor."""
    level = find_level(ACTS, body.level_id)
    step = level.step(body.step_id) if level else None
    if level is None or step is None:
        raise HTTPException(404, "No such step")
    if body.index >= len(step.hints):
        return {"hint": "", "exhausted": True}

    key = f"{level.id}/{step.id}"
    _session["hints_open"][key] = max(_session["hints_open"].get(key, 0), body.index + 1)
    return {
        "hint": step.hints[body.index],
        "index": body.index,
        "total": len(step.hints),
        "exhausted": body.index + 1 >= len(step.hints),
    }


# ----------------------------------------------------------------- tutor


@app.post("/api/ask")
async def post_ask(body: AskBody) -> StreamingResponse:
    """Stream a tutor reply as server-sent events."""
    level = find_level(ACTS, body.level_id) if body.level_id else None
    step = level.step(body.step_id) if level and body.step_id else None

    context = TutorContext(
        difficulty=PROGRESS.difficulty_signal(),
        struggling=PROGRESS.struggling_with(),
        gaps=PROGRESS.gaps(),
        last_result=_session.get("last_result") or None,
    )
    if level is not None:
        context.level_id = level.id
        context.level_title = level.title
        context.level_question = level.question
        context.specimen_paths = list(level.steps[0].specimen_paths) if level.steps else []
    if step is not None:
        context.step_id = step.id
        context.step_kind = step.kind
        context.step_title = step.title
        context.step_body = step.body
        context.specimen_paths = step.specimen_paths or context.specimen_paths
        record = PROGRESS.steps.get(f"{level.id}/{step.id}") if level else None
        context.attempts = record.attempts if record else 0
        context.hints_used = _session["hints_open"].get(
            f"{level.id}/{step.id}" if level else "", 0
        )
        if step.kind == "implement" and step.target_file:
            path = WORKBENCH / step.target_file
            context.target_file = step.target_file
            context.learner_code = path.read_text(encoding="utf-8") if path.exists() else ""

    if body.quote:
        context.quote = body.quote

    async def stream():
        tutor = get_tutor()
        try:
            async for event in tutor.ask(body.message, context):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:  # the tutor must never take down the course
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        yield "data: {\"type\": \"close\"}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/progress")
async def get_progress() -> dict[str, Any]:
    return PROGRESS.summary(ACTS)


# --------------------------------------------------------------- terminal


@app.get("/api/run")
async def get_run(command: str, token: str = "") -> StreamingResponse:
    """Run one whitelisted curriculum command, streaming its output.

    GET rather than POST so EventSource can consume it. This is safe only
    because `resolve` accepts a fixed set of ids - never a shell string.

    `token` is a client-generated id used by /api/stop to kill this run.
    """
    resolved = resolve_command(command)

    async def stream():
        if resolved is None:
            payload = {"type": "out", "line": f"unknown command: {command}"}
            yield f"data: {json.dumps(payload)}\n\n"
            yield f"data: {json.dumps({'type': 'exit', 'code': 127, 'seconds': 0})}\n\n"
            return
        try:
            async for event in stream_command(resolved, token=token or None):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:  # a broken command must not kill the course
            yield f"data: {json.dumps({'type': 'out', 'line': str(exc)})}\n\n"
            yield f"data: {json.dumps({'type': 'exit', 'code': 1, 'seconds': 0})}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/stop")
async def post_stop(body: StopBody) -> dict[str, Any]:
    """Kill a running command. The stop button behind an infinite loop."""
    return {"stopped": cancel_run(body.token)}


@app.post("/api/reset")
async def post_reset() -> dict[str, Any]:
    """Clear progress. The workbench is left alone - that is the learner's work."""
    PROGRESS.steps.clear()
    PROGRESS.concepts.clear()
    PROGRESS.achievements.clear()
    PROGRESS.notes.clear()
    PROGRESS.save()
    return {"reset": True}


# ----------------------------------------------------------------- static


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


app.mount("/static", StaticFiles(directory=WEB), name="static")


def prepare() -> None:
    """Create workbench files and directories before serving."""
    WORKBENCH.mkdir(parents=True, exist_ok=True)
    (WORKBENCH / "tests").mkdir(exist_ok=True)
    write_starter_files(ACTS, WORKBENCH)
