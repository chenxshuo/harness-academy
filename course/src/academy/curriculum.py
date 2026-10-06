"""Curriculum data model.

A level is the unit of learning. Its fields encode the course's pedagogy:

``hook``       something observable, before any explanation
``steps``      the Observe -> Predict -> Act -> Compare cycle
``reveal``     the specimen's real implementation, shown *after* you commit
``transfer``   the idea restated so it survives leaving this repository
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

StepKind = Literal["predict", "implement", "explain", "inspect", "compare"]


@dataclass(slots=True)
class Choice:
    id: str
    label: str
    # Explains why a *wrong* choice is tempting. Shown after answering.
    note: str = ""


@dataclass(slots=True)
class Step:
    """One interaction inside a level."""

    id: str
    kind: StepKind
    title: str
    body: str = ""

    # predict
    question: str = ""
    choices: list[Choice] = field(default_factory=list)
    answer: str | list[str] = ""
    multi: bool = False
    # When set, the expected answer is computed by running this script rather
    # than being hardcoded, so the course cannot drift from the specimen.
    trace: str = ""

    # implement
    target_file: str = ""
    starter: str = ""
    test_file: str = ""
    # A previous step whose file this one builds on. The UI offers to copy
    # that work in, so the learner never retypes code they already wrote.
    carries_from: str = ""
    carries_note: str = ""

    # inspect / compare
    specimen_paths: list[str] = field(default_factory=list)
    # A whitelisted command the learner can run from the page itself
    # (see academy.runner). Keeps them out of a separate terminal.
    run_command: str = ""
    run_label: str = ""

    # explain / inspect: a commitment before the writing.
    #
    # A blank box is a poor prompt - there is no feedback until a human reads
    # it, and nothing to react to. Picking a position first gives the learner
    # something concrete to defend, and gives the tutor something specific to
    # challenge.
    stance_question: str = ""
    stances: list[Choice] = field(default_factory=list)
    writing_prompt: str = ""

    # shared
    hints: list[str] = field(default_factory=list)
    after: str = ""  # revealed once the step is complete
    xp: int = 10

    def public(self) -> dict[str, Any]:
        """Serialize for the browser, with answers stripped out."""
        data = asdict(self)
        data.pop("answer", None)
        data["hint_count"] = len(self.hints)
        data["starter_available"] = bool(self.starter)
        data.pop("hints", None)
        data.pop("after", None)
        return data


@dataclass(slots=True)
class Level:
    id: str
    title: str
    # The question the learner should be holding in mind.
    question: str
    minutes: int = 15
    # Short phrase shown on the map.
    teaser: str = ""
    hook: str = ""
    steps: list[Step] = field(default_factory=list)
    reveal: str = ""
    transfer: str = ""
    requires: list[str] = field(default_factory=list)
    # Concept ids this level builds mastery in; drives adaptive review.
    concepts: list[str] = field(default_factory=list)
    optional: bool = False

    @property
    def xp(self) -> int:
        return sum(step.xp for step in self.steps)

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "question": self.question,
            "minutes": self.minutes,
            "teaser": self.teaser,
            "hook": self.hook,
            "steps": [s.public() for s in self.steps],
            "requires": self.requires,
            "concepts": self.concepts,
            "optional": self.optional,
            "xp": self.xp,
        }

    def step(self, step_id: str) -> Step | None:
        return next((s for s in self.steps if s.id == step_id), None)


@dataclass(slots=True)
class Act:
    """A group of levels sharing one architectural theme."""

    id: str
    title: str
    subtitle: str
    levels: list[Level] = field(default_factory=list)


def load_curriculum() -> list[Act]:
    """Build the curriculum. Defined in Python so steps can carry real code."""
    from academy.content import build_acts

    return build_acts()


def all_levels(acts: list[Act]) -> list[Level]:
    return [level for act in acts for level in act.levels]


def find_level(acts: list[Act], level_id: str) -> Level | None:
    return next((lv for lv in all_levels(acts) if lv.id == level_id), None)


def curriculum_json(acts: list[Act]) -> str:
    return json.dumps(
        [
            {
                "id": act.id,
                "title": act.title,
                "subtitle": act.subtitle,
                "levels": [lv.public() for lv in act.levels],
            }
            for act in acts
        ]
    )


def write_starter_files(acts: list[Act], workbench: Path) -> list[Path]:
    """Create any missing workbench files so the learner always has a file to open."""
    written: list[Path] = []
    workbench.mkdir(parents=True, exist_ok=True)
    for level in all_levels(acts):
        for step in level.steps:
            if not (step.kind == "implement" and step.target_file and step.starter):
                continue
            path = workbench / step.target_file
            if path.exists():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(step.starter, encoding="utf-8")
            written.append(path)
    return written
