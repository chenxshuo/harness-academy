"""Learner state: what you know, what you keep missing, how hard to push.

This is the adaptive core. It is deliberately simple and inspectable - a JSON
file you can read - because an opaque "learning model" would be one more thing
to take on faith.

Mastery is tracked per *concept*, not per level, so that a misconception
surfaces wherever it actually lives.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

Confidence = Literal["guess", "unsure", "confident"]


@dataclass
class StepRecord:
    step_id: str
    level_id: str
    kind: str
    passed: bool = False
    attempts: int = 0
    hints_used: int = 0
    first_try: bool = False
    confidence: str = ""
    # For predict steps: what they said vs. what happened.
    last_answer: Any = None
    seconds: float = 0.0
    completed_at: float = 0.0


@dataclass
class ConceptMastery:
    """Evidence about one concept, split by the two ways of knowing.

    The split matters: the GOAL explicitly asks the system to notice concepts
    the learner can explain but not implement, and vice versa.
    """

    concept: str
    predicted_right: int = 0
    predicted_wrong: int = 0
    implemented_ok: int = 0
    implemented_failed: int = 0
    explained: int = 0

    @property
    def can_predict(self) -> float:
        total = self.predicted_right + self.predicted_wrong
        return self.predicted_right / total if total else 0.0

    @property
    def can_implement(self) -> float:
        total = self.implemented_ok + self.implemented_failed
        return self.implemented_ok / total if total else 0.0

    @property
    def level(self) -> str:
        seen = (
            self.predicted_right
            + self.predicted_wrong
            + self.implemented_ok
            + self.implemented_failed
        )
        if seen == 0:
            return "untouched"
        score = (self.can_predict + self.can_implement) / 2 if self.implemented_ok or self.implemented_failed else self.can_predict
        if score >= 0.8:
            return "solid"
        if score >= 0.5:
            return "shaky"
        return "weak"

    @property
    def gap(self) -> str:
        """Identify an explain/implement imbalance worth acting on."""
        if self.can_predict >= 0.75 and self.implemented_failed and self.can_implement < 0.5:
            return "predicts-but-cannot-build"
        if self.can_implement >= 0.75 and self.predicted_wrong and self.can_predict < 0.5:
            return "builds-but-cannot-explain"
        return ""


class Progress:
    """Durable learner state, persisted as JSON."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.steps: dict[str, StepRecord] = {}
        self.concepts: dict[str, ConceptMastery] = {}
        self.achievements: set[str] = set()
        self.started_at: float = time.time()
        self.notes: list[dict[str, Any]] = []
        self.load()

    # ---------------------------------------------------------------- io

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        self.steps = {k: StepRecord(**v) for k, v in raw.get("steps", {}).items()}
        self.concepts = {k: ConceptMastery(**v) for k, v in raw.get("concepts", {}).items()}
        self.achievements = set(raw.get("achievements", []))
        self.started_at = raw.get("started_at", time.time())
        self.notes = raw.get("notes", [])

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "steps": {k: asdict(v) for k, v in self.steps.items()},
            "concepts": {k: asdict(v) for k, v in self.concepts.items()},
            "achievements": sorted(self.achievements),
            "started_at": self.started_at,
            "notes": self.notes[-200:],
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # ------------------------------------------------------------ record

    def record(
        self,
        *,
        level_id: str,
        step_id: str,
        kind: str,
        passed: bool,
        concepts: list[str],
        hints_used: int = 0,
        confidence: str = "",
        answer: Any = None,
        seconds: float = 0.0,
    ) -> StepRecord:
        key = f"{level_id}/{step_id}"
        record = self.steps.get(key) or StepRecord(step_id=step_id, level_id=level_id, kind=kind)
        was_done = record.passed
        record.attempts += 1
        record.hints_used = max(record.hints_used, hints_used)
        record.confidence = confidence or record.confidence
        record.last_answer = answer
        record.seconds += seconds
        if passed and not was_done:
            record.passed = True
            record.first_try = record.attempts == 1 and hints_used == 0
            record.completed_at = time.time()
        self.steps[key] = record

        # Only the first resolution of a step counts toward mastery, so that
        # grinding retries cannot inflate it.
        if not was_done:
            for concept in concepts:
                mastery = self.concepts.setdefault(concept, ConceptMastery(concept=concept))
                if kind == "predict":
                    if passed:
                        mastery.predicted_right += 1
                    else:
                        mastery.predicted_wrong += 1
                elif kind == "implement":
                    if passed:
                        mastery.implemented_ok += 1
                    else:
                        mastery.implemented_failed += 1
                elif kind in {"explain", "compare", "inspect"} and passed:
                    mastery.explained += 1

        self.save()
        return record

    def add_note(self, level_id: str, text: str) -> None:
        self.notes.append({"level": level_id, "text": text, "at": time.time()})
        self.save()

    # ------------------------------------------------------------ query

    def is_done(self, level_id: str, step_id: str) -> bool:
        record = self.steps.get(f"{level_id}/{step_id}")
        return bool(record and record.passed)

    def level_done(self, level: Any) -> bool:
        return bool(level.steps) and all(self.is_done(level.id, s.id) for s in level.steps)

    def level_started(self, level: Any) -> bool:
        return any(f"{level.id}/{s.id}" in self.steps for s in level.steps)

    def unlocked(self, level: Any, acts: list[Any]) -> bool:
        """A level unlocks when its prerequisites are complete."""
        if not level.requires:
            return True
        from academy.curriculum import find_level

        for required in level.requires:
            prereq = find_level(acts, required)
            if prereq and not self.level_done(prereq):
                return False
        return True

    @property
    def xp(self) -> int:
        return sum(10 for r in self.steps.values() if r.passed)

    def struggling_with(self) -> list[str]:
        """Concepts that justify a review prompt."""
        return [c.concept for c in self.concepts.values() if c.level in {"weak", "shaky"}]

    def gaps(self) -> list[dict[str, str]]:
        return [
            {"concept": c.concept, "gap": c.gap}
            for c in self.concepts.values()
            if c.gap
        ]

    def difficulty_signal(self) -> str:
        """Infer whether to dial challenge up or down.

        Used to decide whether to surface optional harder challenges, and to
        tell the tutor how much scaffolding to offer.
        """
        recent = sorted(
            [r for r in self.steps.values() if r.completed_at],
            key=lambda r: r.completed_at,
        )[-8:]
        if len(recent) < 3:
            return "calibrating"
        clean = sum(1 for r in recent if r.first_try)
        struggled = sum(1 for r in recent if r.attempts >= 3 or r.hints_used >= 2)
        if clean >= len(recent) * 0.75:
            return "too-easy"
        if struggled >= len(recent) * 0.5:
            return "too-hard"
        return "well-matched"

    def summary(self, acts: list[Any]) -> dict[str, Any]:
        from academy.curriculum import all_levels

        levels = all_levels(acts)
        done = [lv for lv in levels if self.level_done(lv)]
        return {
            "xp": self.xp,
            "levels_done": len(done),
            "levels_total": len(levels),
            "steps_done": sum(1 for r in self.steps.values() if r.passed),
            "achievements": sorted(self.achievements),
            "difficulty": self.difficulty_signal(),
            "struggling": self.struggling_with(),
            "gaps": self.gaps(),
            "concepts": {
                name: {
                    "level": m.level,
                    "predict": round(m.can_predict, 2),
                    "implement": round(m.can_implement, 2),
                    "gap": m.gap,
                }
                for name, m in sorted(self.concepts.items())
            },
        }


# Achievements reward evidence of understanding, not clicks.
ACHIEVEMENTS: dict[str, dict[str, str]] = {
    "oracle": {
        "title": "Five correct predictions",
        "detail": "You called five behaviours right on the first try, with no hints.",
    },
    "no-net": {
        "title": "Solved without hints",
        "detail": "You finished an implementation step without opening a single hint.",
    },
    "breaker": {
        "title": "Broke it on purpose",
        "detail": "You violated an invariant deliberately and explained the failure.",
    },
    "archaeologist": {
        "title": "Traced a decision to its cause",
        "detail": "You followed a design choice back to the note or commit that forced it.",
    },
    "cartographer": {
        "title": "Mapped two harnesses",
        "detail": "You matched an abstraction across two different implementations.",
    },
    "architect": {
        "title": "Built a working harness",
        "detail": "You passed the final reconstruction challenge.",
    },
}


def check_achievements(progress: Progress) -> list[str]:
    """Award any newly-earned achievements and return them."""
    earned: list[str] = []

    def award(key: str) -> None:
        if key not in progress.achievements:
            progress.achievements.add(key)
            earned.append(key)

    clean_predictions = sum(
        1 for r in progress.steps.values() if r.kind == "predict" and r.first_try
    )
    if clean_predictions >= 5:
        award("oracle")

    if any(
        r.kind == "implement" and r.passed and r.hints_used == 0
        for r in progress.steps.values()
    ):
        award("no-net")

    if progress.is_done("l07-invariant", "break-it"):
        award("breaker")
    if progress.is_done("l10-provenance", "trace-decision"):
        award("archaeologist")
    if progress.is_done("l11-transfer", "map-abstractions"):
        award("cartographer")
    if progress.is_done("l12-capstone", "build"):
        award("architect")

    if earned:
        progress.save()
    return earned
