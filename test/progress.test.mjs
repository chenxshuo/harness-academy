/* The learner model: mastery, gaps, unlocking. Pure functions, so testable
   without a browser. */
import assert from "node:assert/strict";

// Minimal localStorage stub so store.js works under Node.
const mem = new Map();
globalThis.localStorage = {
  getItem: (k) => (mem.has(k) ? mem.get(k) : null),
  setItem: (k, v) => mem.set(k, String(v)),
  removeItem: (k) => mem.delete(k),
};
globalThis.structuredClone ??= (v) => JSON.parse(JSON.stringify(v));

const P = await import("../src/progress.js");

const progress = { version: 1, startedAt: 0, steps: {}, concepts: {}, achievements: [], notes: [] };

// A first-try correct prediction builds predict-mastery only.
P.record(progress, { levelId: "l1", stepId: "a", kind: "predict", passed: true, concepts: ["loop"] });
assert.equal(progress.concepts.loop.predictedRight, 1);
assert.equal(progress.concepts.loop.implementedOk, 0);
assert.equal(progress.steps["l1/a"].firstTry, true);

// Retries must not inflate mastery: only the first resolution counts.
P.record(progress, { levelId: "l1", stepId: "a", kind: "predict", passed: true, concepts: ["loop"] });
assert.equal(progress.concepts.loop.predictedRight, 1, "retry must not re-count");
assert.equal(progress.steps["l1/a"].attempts, 2);

// The gap the course is designed to surface.
const m = { concept: "x", predictedRight: 4, predictedWrong: 0, implementedOk: 0, implementedFailed: 3, explained: 0 };
assert.equal(P.masteryGap(m), "predicts-but-cannot-build");

// Unlocking follows prerequisites.
const l1 = { id: "l1", requires: [], steps: [{ id: "a" }] };
const l2 = { id: "l2", requires: ["l1"], steps: [{ id: "b" }] };
const byId = { l1, l2 };
assert.equal(P.levelUnlocked(progress, l2, byId), true, "l1/a is passed, so l2 opens");

const fresh = { version: 1, startedAt: 0, steps: {}, concepts: {}, achievements: [], notes: [] };
assert.equal(P.levelUnlocked(fresh, l2, byId), false, "locked until the prereq is done");

// Hints disqualify the no-hints achievement.
const hinted = { version: 1, startedAt: 0, steps: {}, concepts: {}, achievements: [], notes: [] };
P.record(hinted, { levelId: "l1", stepId: "i", kind: "implement", passed: true, concepts: [], hintsUsed: 2 });
assert.equal(P.checkAchievements(hinted).some((a) => a.key === "no-net"), false);

console.log("progress: 8 assertions passed");

// Review mode opens everything without altering recorded progress.
{
  const locked = { version: 1, startedAt: 0, steps: {}, concepts: {}, achievements: [], notes: [] };
  const a = { id: "a", requires: [], steps: [{ id: "x" }] };
  const b = { id: "b", requires: ["a"], steps: [{ id: "y" }] };
  const byId = { a, b };

  assert.equal(P.levelUnlocked(locked, b, byId), false, "gated by default");
  P.setUnlockAll(true);
  assert.equal(P.levelUnlocked(locked, b, byId), true, "review mode opens it");
  assert.equal(Object.keys(locked.steps).length, 0, "must not fake completion");
  P.setUnlockAll(false);
  assert.equal(P.levelUnlocked(locked, b, byId), false, "and locks again");
}

console.log("review mode: 4 assertions passed");
