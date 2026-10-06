/* Learner model: what you know, what you keep missing, how hard to push.
 *
 * Ported from the Python `academy.progress`. Deliberately simple and
 * inspectable - you can read your own progress JSON - because an opaque
 * "learning model" would be one more thing to take on faith.
 *
 * Mastery is tracked per *concept*, not per level, so a misconception
 * surfaces wherever it actually lives. It is split into two kinds of
 * evidence, because being able to predict a behaviour and being able to
 * build it are different skills, and the gap between them is actionable.
 */

import { loadProgress, saveProgress } from "./store.js";

export const ACHIEVEMENTS = {
  oracle: {
    title: "Five correct predictions",
    detail: "You called five behaviours right on the first try, with no hints.",
  },
  "no-net": {
    title: "Solved without hints",
    detail: "You finished an implementation step without opening a single hint.",
  },
  breaker: {
    title: "Broke it on purpose",
    detail: "You violated an invariant deliberately and explained the failure.",
  },
  archaeologist: {
    title: "Traced a decision to its cause",
    detail: "You followed a design choice back to the note that forced it.",
  },
  cartographer: {
    title: "Mapped two harnesses",
    detail: "You matched an abstraction across two different implementations.",
  },
  architect: {
    title: "Built a working harness",
    detail: "You passed the final reconstruction challenge.",
  },
};

const emptyMastery = (concept) => ({
  concept,
  predictedRight: 0,
  predictedWrong: 0,
  implementedOk: 0,
  implementedFailed: 0,
  explained: 0,
});

function ratio(right, wrong) {
  const total = right + wrong;
  return total ? right / total : 0;
}

export function masteryLevel(m) {
  const seen = m.predictedRight + m.predictedWrong + m.implementedOk + m.implementedFailed;
  if (seen === 0) return "untouched";
  const canPredict = ratio(m.predictedRight, m.predictedWrong);
  const canImplement = ratio(m.implementedOk, m.implementedFailed);
  const built = m.implementedOk + m.implementedFailed > 0;
  const score = built ? (canPredict + canImplement) / 2 : canPredict;
  if (score >= 0.8) return "solid";
  if (score >= 0.5) return "shaky";
  return "weak";
}

/** An imbalance worth acting on: can explain but not build, or vice versa. */
export function masteryGap(m) {
  const canPredict = ratio(m.predictedRight, m.predictedWrong);
  const canImplement = ratio(m.implementedOk, m.implementedFailed);
  if (canPredict >= 0.75 && m.implementedFailed && canImplement < 0.5) {
    return "predicts-but-cannot-build";
  }
  if (canImplement >= 0.75 && m.predictedWrong && canPredict < 0.5) {
    return "builds-but-cannot-explain";
  }
  return "";
}

export function stepKey(levelId, stepId) {
  return `${levelId}/${stepId}`;
}

export function isDone(progress, levelId, stepId) {
  const record = progress.steps[stepKey(levelId, stepId)];
  return Boolean(record && record.passed);
}

export function levelDone(progress, level) {
  return level.steps.length > 0 && level.steps.every((s) => isDone(progress, level.id, s.id));
}

export function levelStarted(progress, level) {
  return level.steps.some((s) => stepKey(level.id, s.id) in progress.steps);
}

/* Review mode: open every level regardless of prerequisites.
 *
 * Gating exists so concepts arrive in dependency order, which is a teaching
 * decision rather than a security one. Anyone reviewing the course, or
 * returning to a level out of order, should be able to turn it off. It is a
 * setting, not a hack, so it survives a reload and can be turned back on.
 */
export function unlockAllEnabled() {
  try {
    return localStorage.getItem("harness-academy:unlock-all") === "1";
  } catch {
    return false;
  }
}

export function setUnlockAll(enabled) {
  try {
    enabled
      ? localStorage.setItem("harness-academy:unlock-all", "1")
      : localStorage.removeItem("harness-academy:unlock-all");
  } catch {
    /* private browsing */
  }
  return enabled;
}

export function levelUnlocked(progress, level, levelsById) {
  if (unlockAllEnabled()) return true;
  if (!level.requires.length) return true;
  return level.requires.every((id) => {
    const prereq = levelsById[id];
    return !prereq || levelDone(progress, prereq);
  });
}

/**
 * Record one step attempt.
 *
 * Only the *first* resolution of a step counts toward concept mastery, so
 * grinding retries cannot inflate it.
 */
export function record(progress, { levelId, stepId, kind, passed, concepts = [], hintsUsed = 0, confidence = "", answer = null, seconds = 0 }) {
  const key = stepKey(levelId, stepId);
  const existing = progress.steps[key];
  const wasDone = Boolean(existing && existing.passed);

  const next = existing || {
    stepId, levelId, kind,
    passed: false, attempts: 0, hintsUsed: 0,
    firstTry: false, confidence: "", lastAnswer: null,
    seconds: 0, completedAt: 0,
  };

  next.attempts += 1;
  next.hintsUsed = Math.max(next.hintsUsed, hintsUsed);
  next.confidence = confidence || next.confidence;
  next.lastAnswer = answer;
  next.seconds += seconds;

  if (passed && !wasDone) {
    next.passed = true;
    next.firstTry = next.attempts === 1 && hintsUsed === 0;
    next.completedAt = Date.now();
  }
  progress.steps[key] = next;

  if (!wasDone) {
    for (const concept of concepts) {
      const m = progress.concepts[concept] || emptyMastery(concept);
      if (kind === "predict") {
        passed ? m.predictedRight++ : m.predictedWrong++;
      } else if (kind === "implement") {
        passed ? m.implementedOk++ : m.implementedFailed++;
      } else if (passed) {
        m.explained++;
      }
      progress.concepts[concept] = m;
    }
  }

  saveProgress(progress);
  return next;
}

export function addNote(progress, levelId, text) {
  progress.notes.push({ level: levelId, text, at: Date.now() });
  progress.notes = progress.notes.slice(-200);
  saveProgress(progress);
}

/** Infer whether to dial challenge up or down from recent work. */
export function difficultySignal(progress) {
  const recent = Object.values(progress.steps)
    .filter((r) => r.completedAt)
    .sort((a, b) => a.completedAt - b.completedAt)
    .slice(-8);
  if (recent.length < 3) return "calibrating";
  const clean = recent.filter((r) => r.firstTry).length;
  const struggled = recent.filter((r) => r.attempts >= 3 || r.hintsUsed >= 2).length;
  if (clean >= recent.length * 0.75) return "too-easy";
  if (struggled >= recent.length * 0.5) return "too-hard";
  return "well-matched";
}

export function strugglingWith(progress) {
  return Object.values(progress.concepts)
    .filter((m) => ["weak", "shaky"].includes(masteryLevel(m)))
    .map((m) => m.concept);
}

export function gaps(progress) {
  return Object.values(progress.concepts)
    .map((m) => ({ concept: m.concept, gap: masteryGap(m) }))
    .filter((g) => g.gap);
}

export function summary(progress, levels) {
  const levelsById = Object.fromEntries(levels.map((l) => [l.id, l]));
  const done = levels.filter((l) => levelDone(progress, l));
  const stepsDone = Object.values(progress.steps).filter((r) => r.passed).length;
  const totalSteps = levels.reduce((n, l) => n + l.steps.length, 0);

  return {
    levelsDone: done.length,
    levelsTotal: levels.length,
    stepsDone,
    stepsTotal: totalSteps,
    achievements: [...progress.achievements],
    difficulty: difficultySignal(progress),
    struggling: strugglingWith(progress),
    gaps: gaps(progress),
    concepts: Object.fromEntries(
      Object.entries(progress.concepts)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([name, m]) => [
          name,
          {
            level: masteryLevel(m),
            predict: Number(ratio(m.predictedRight, m.predictedWrong).toFixed(2)),
            implement: Number(ratio(m.implementedOk, m.implementedFailed).toFixed(2)),
            gap: masteryGap(m),
          },
        ])
    ),
    levelsById,
  };
}

/** Award newly-earned achievements; returns the new ones for celebration. */
export function checkAchievements(progress) {
  const earned = [];
  const award = (key) => {
    if (!progress.achievements.includes(key)) {
      progress.achievements.push(key);
      earned.push(key);
    }
  };

  const records = Object.values(progress.steps);
  if (records.filter((r) => r.kind === "predict" && r.firstTry).length >= 5) award("oracle");
  if (records.some((r) => r.kind === "implement" && r.passed && r.hintsUsed === 0)) award("no-net");
  if (isDone(progress, "l07-invariant", "break-it")) award("breaker");
  if (isDone(progress, "l10-provenance", "trace-decision")) award("archaeologist");
  if (isDone(progress, "l11-transfer", "map-abstractions")) award("cartographer");
  if (isDone(progress, "l12-capstone", "build")) award("architect");

  if (earned.length) saveProgress(progress);
  return earned.map((key) => ({ key, ...ACHIEVEMENTS[key] }));
}

export { loadProgress };
