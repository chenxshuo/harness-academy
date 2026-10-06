/* Main-thread client for the Pyodide worker.
 *
 * Boot is deferred and idempotent: Level 1 needs no Python, so the runtime
 * downloads in the background while the learner reads. By the time they reach
 * the first editor it is usually already warm.
 */

let worker = null;
let nextId = 1;
const pending = new Map();
const listeners = new Set();

let bootPromise = null;
let mountPromise = null;
let status = "cold"; // cold | loading | ready | mounted | failed

export function onRuntimeEvent(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function emit(event) {
  for (const fn of listeners) fn(event);
}

export function runtimeStatus() {
  return status;
}

function ensureWorker() {
  if (worker) return worker;
  // Resolve against the deployed base so the site works from a subpath too.
  worker = new Worker(new URL("pyodide-worker.js", document.baseURI));
  worker.onmessage = (event) => {
    const data = event.data;
    if (data.type === "result") {
      const entry = pending.get(data.id);
      if (!entry) return;
      pending.delete(data.id);
      data.error ? entry.reject(new Error(data.error)) : entry.resolve(data.result);
      return;
    }
    if (data.type === "status") {
      status = data.stage;
      emit({ type: "status", stage: data.stage, message: data.message });
      return;
    }
    emit(data); // stdout / stderr
  };
  worker.onerror = (err) => {
    status = "failed";
    emit({ type: "status", stage: "failed", message: String(err.message || err) });
  };
  return worker;
}

function call(action, payload = {}) {
  const id = nextId++;
  ensureWorker().postMessage({ id, action, payload });
  return new Promise((resolve, reject) => pending.set(id, { resolve, reject }));
}

/** Start downloading the runtime. Safe to call repeatedly. */
export function warmUp() {
  if (!bootPromise) {
    status = "loading";
    bootPromise = call("boot").catch((err) => {
      status = "failed";
      throw err;
    });
  }
  return bootPromise;
}

/**
 * Boot and mount the course files. Everything that needs Python awaits this.
 * `content` is the fetched JSON bundle.
 */
export function ready(content) {
  if (!mountPromise) {
    mountPromise = (async () => {
      await warmUp();
      await call("mount", {
        harnesskit: content.harnesskit,
        tests: content.tests,
        runner: content.runner,
        scripts: content.scripts,
      });
      status = "mounted";
      return true;
    })().catch((err) => {
      status = "failed";
      mountPromise = null;
      throw err;
    });
  }
  return mountPromise;
}

export async function runTests({ testFile, files }) {
  return call("runTests", { testFile, files });
}

export async function runScript({ path, files, captureLastLine = false }) {
  return call("runScript", { path, files, captureLastLine });
}
