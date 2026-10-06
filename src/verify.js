/* Verification: the course's source of truth, now client-side.
 *
 * The design rule is unchanged from the server version: **the tutor never
 * grades**. Implementation steps are checked by running the learner's code.
 * Prediction answers are checked against a *recorded execution* where a trace
 * script exists, so the course cannot drift from the specimen.
 */

import { runScript, runTests } from "./runtime.js";
import { loadFiles } from "./store.js";

/** Every learner file, in the shape the worker wants. */
function learnerFiles() {
  const out = {};
  for (const [name, entry] of Object.entries(loadFiles())) {
    out[name] = entry.content;
  }
  return out;
}

/** Pull the single most useful line out of a failing run. */
export function failureHint(results) {
  const failed = results.find((r) => !r.passed);
  if (!failed) return "";
  const firstLine = (failed.message || "").split("\n")[0].trim();
  return firstLine ? `${failed.name}: ${firstLine}` : failed.name;
}

/**
 * Run one step's tests against the learner's current code.
 * Mirrors the old /api/verify response so the UI needs no changes.
 */
export async function verify(step) {
  const testFile = step.testFile.split("/").pop();
  const run = await runTests({ testFile, files: learnerFiles() });

  return {
    passed: run.ok,
    summary: run.ok
      ? `${run.passed} passed`
      : `${run.passed} passed, ${run.failed} failed`,
    detail: failureHint(run.results),
    results: run.results,
    failures: run.results.filter((r) => !r.passed).map((r) => ({
      test: r.name,
      reason: (r.message || "").split("\n")[0],
    })),
    durationMs: run.durationMs,
  };
}

/* Trace results are cached per session: the scripts are deterministic, so
   re-running them for every attempt only costs time. */
const traceCache = new Map();

/** Compute a prediction's expected answer by executing its trace script. */
export async function expectedAnswer(step) {
  if (!step.trace) return { answer: step.answer, evidence: null };
  if (traceCache.has(step.trace)) return traceCache.get(step.trace);

  try {
    const run = await runScript({ path: step.trace, captureLastLine: true });
    if (run.ok && run.payload && "answer" in run.payload) {
      const result = { answer: run.payload.answer, evidence: run.payload };
      traceCache.set(step.trace, result);
      return result;
    }
  } catch {
    /* fall through to the authored answer */
  }
  // If the trace cannot run, fall back rather than blocking the learner.
  return { answer: step.answer, evidence: null };
}

/** Grade a prediction. */
export async function checkPrediction(step, given) {
  const { answer: expected, evidence } = await expectedAnswer(step);

  let passed;
  if (step.multi) {
    const a = [...(Array.isArray(given) ? given : [given])].sort();
    const b = [...(Array.isArray(expected) ? expected : [expected])].sort();
    passed = a.length === b.length && a.every((v, i) => v === b[i]);
  } else {
    passed = String(given) === String(expected);
  }

  const correctSet = Array.isArray(expected) ? expected : [expected];
  const chosen = Array.isArray(given) ? given : [given];

  return {
    passed,
    expected: passed ? null : expected,
    evidence,
    // Notes on every option, so a right answer still teaches why the others
    // were wrong - that is usually where the misconception lives.
    notes: step.choices.map((choice) => ({
      id: choice.id,
      label: choice.label,
      note: choice.note,
      chosen: chosen.includes(choice.id),
      correct: correctSet.includes(choice.id),
    })),
  };
}

/** Run a demo script, streaming its output to the terminal. */
export async function runDemo(path) {
  return runScript({ path, files: learnerFiles() });
}
