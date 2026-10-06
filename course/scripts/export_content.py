"""Export the curriculum, tests, starters, specimen and diagrams to static JSON.

This is the bridge between the Python authoring format (which keeps the course
content next to the code that validates it) and the browser bundle.

Run via ``npm run build:content``. Output lands in ``web-next/public/content/``.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

# In the deploy repo this file lives at course/scripts/, and the site
# root is two levels up.
COURSE = Path(__file__).resolve().parents[1]
ROOT = COURSE.parent
sys.path.insert(0, str(COURSE / "src"))

from academy.curriculum import all_levels, load_curriculum  # noqa: E402
from academy.diagrams import DIAGRAMS, expand, render  # noqa: E402

OUT = ROOT / "public" / "content"
WORKBENCH = COURSE / "workbench"
TAU = ROOT / "tau"

# Files the curriculum cites by path. Bundled so "open the specimen" works
# with no server. Derived from specimen_paths plus the paths named in prose.
SPECIMEN = [
    "tau/src/tau_agent/loop.py",
    "tau/src/tau_agent/harness.py",
    "tau/src/tau_agent/events.py",
    "tau/src/tau_agent/tools.py",
    "tau/src/tau_agent/tool_history.py",
    "tau/src/tau_agent/messages.py",
    "tau/src/tau_agent/provider.py",
    "tau/src/tau_agent/provider_events.py",
    "tau/src/tau_agent/session/entries.py",
    "tau/src/tau_agent/session/memory.py",
    "tau/src/tau_agent/session/storage.py",
    "tau/src/tau_agent/session/tree.py",
    "tau/src/tau_coding/context_window.py",
    "tau/src/tau_coding/tools.py",
    "tau/src/tau_coding/rendering/plain.py",
    "tau/src/tau_coding/rendering/json.py",
    "tau/dev-notes/push-based-persistence.md",
    "tau/dev-notes/tool-history-recovery.md",
    "tau/dev-notes/design/01-architecture.md",
    "tau/dev-notes/design/02-agent-loop.md",
    "tau/dev-notes/design/harness.md",
    "tau/website/content/internals/design-principles.md",
    "tau/website/content/internals/architecture.md",
    "tau/README.md",
    "tau/AGENTS.md",
]

# session.py is 5k lines; the capstone only points at it rhetorically.
SPECIMEN_EXCERPT_LINES = 400


def _expand_level(level) -> dict:
    """Serialise one level, with diagrams expanded and answers retained.

    Answers ship to the browser - there is no server to hide them behind.
    This is a self-directed course, so peeking only costs the peeker, and
    trace-computed answers are resistant anyway.
    """
    data = {
        "id": level.id,
        "title": level.title,
        "question": level.question,
        "minutes": level.minutes,
        "teaser": level.teaser,
        "hook": expand(level.hook),
        "reveal": expand(level.reveal),
        "transfer": expand(level.transfer),
        "requires": list(level.requires),
        "concepts": list(level.concepts),
        "optional": level.optional,
        "steps": [],
    }
    for step in level.steps:
        payload = {
            "id": step.id,
            "kind": step.kind,
            "title": step.title,
            "body": expand(step.body),
            "question": step.question,
            "choices": [
                {"id": c.id, "label": c.label, "note": c.note} for c in step.choices
            ],
            "answer": step.answer,
            "multi": step.multi,
            "trace": step.trace,
            "targetFile": step.target_file,
            "starter": step.starter,
            "testFile": step.test_file,
            "carriesFrom": step.carries_from,
            "carriesNote": step.carries_note,
            "specimenPaths": list(step.specimen_paths),
            "stanceQuestion": step.stance_question,
            "stances": [
                {"id": c.id, "label": c.label, "note": c.note} for c in step.stances
            ],
            "writingPrompt": step.writing_prompt,
            "hints": list(step.hints),
            "after": expand(step.after),
            "runCommand": step.run_command,
            "runLabel": step.run_label,
            "xp": step.xp,
        }
        data["steps"].append(payload)
    return data


def export_curriculum(acts) -> dict:
    return {
        "acts": [
            {
                "id": act.id,
                "title": act.title,
                "subtitle": act.subtitle,
                "levels": [_expand_level(lv) for lv in act.levels],
            }
            for act in acts
        ]
    }


def export_tests() -> dict:
    """Every test file, keyed by filename."""
    out = {}
    for path in sorted((WORKBENCH / "tests").glob("test_*.py")):
        out[path.name] = path.read_text(encoding="utf-8")
    return out


def export_harnesskit() -> dict:
    """The substrate mounted into Pyodide."""
    out = {}
    for path in sorted((COURSE / "src" / "harnesskit").glob("*.py")):
        out[path.name] = path.read_text(encoding="utf-8")
    return out


def export_specimen() -> dict:
    """Bundle the cited tau files so 'open the specimen' works offline."""
    out = {}
    missing = []
    for rel in SPECIMEN:
        path = ROOT / rel
        if not path.is_file():
            missing.append(rel)
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        truncated = False
        if len(lines) > SPECIMEN_EXCERPT_LINES * 4:
            lines = lines[: SPECIMEN_EXCERPT_LINES]
            text = "\n".join(lines) + (
                f"\n\n# ... truncated. Read the full file in the repository:\n"
                f"# https://github.com/huggingface/tau/blob/main/{rel[4:]}\n"
            )
            truncated = True
        out[rel] = {"content": text, "truncated": truncated}
    if missing:
        print(f"  warning: {len(missing)} specimen files missing: {missing[:3]}")
    return out


def export_traces() -> dict:
    """Trace scripts whose execution produces a prediction's expected answer."""
    out = {}
    trace_dir = COURSE / "curriculum" / "traces"
    if trace_dir.is_dir():
        for path in sorted(trace_dir.glob("*.py")):
            out[f"traces/{path.name}"] = path.read_text(encoding="utf-8")
    for name in ("demo_async.py", "demo_first_contact.py"):
        path = COURSE / "curriculum" / name
        if path.is_file():
            out[name] = path.read_text(encoding="utf-8")
    return out


def main() -> None:
    acts = load_curriculum()
    levels = all_levels(acts)

    OUT.mkdir(parents=True, exist_ok=True)

    payloads = {
        "curriculum.json": export_curriculum(acts),
        "tests.json": export_tests(),
        "harnesskit.json": export_harnesskit(),
        "specimen.json": export_specimen(),
        "scripts.json": export_traces(),
        "diagrams.json": {name: render(name) for name in DIAGRAMS},
    }

    for filename, payload in payloads.items():
        target = OUT / filename
        target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        size = target.stat().st_size
        print(f"  {filename:20} {size / 1024:7.1f} KB")

    total = sum((OUT / f).stat().st_size for f in payloads)
    print(f"  {'total':20} {total / 1024:7.1f} KB raw")
    print(f"  {len(levels)} levels, {len(payloads['tests.json'])} test files")


if __name__ == "__main__":
    main()
