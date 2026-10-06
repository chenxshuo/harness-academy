/* Pyodide worker: runs the learner's Python off the main thread.
 *
 * Everything CPU-bound happens here so the UI never janks: booting the
 * interpreter, mounting the virtual filesystem, running tests, running demos.
 *
 * The main thread talks to this worker with a small request/response protocol
 * plus streaming output messages for the terminal.
 */

let pyodide = null;
let booting = null;
let mounted = false;

const PYODIDE_VERSION = "0.28.3";
const CDN = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

function post(type, payload = {}) {
  self.postMessage({ type, ...payload });
}

/** Boot Pyodide once; concurrent callers share the same promise. */
async function boot() {
  if (pyodide) return pyodide;
  if (booting) return booting;

  booting = (async () => {
    post("status", { stage: "loading", message: "Loading Python runtime..." });
    importScripts(`${CDN}pyodide.js`);
    pyodide = await self.loadPyodide({
      indexURL: CDN,
      // Route Python's stdout/stderr to the terminal component.
      stdout: (line) => post("stdout", { line }),
      stderr: (line) => post("stderr", { line }),
    });
    post("status", { stage: "ready", message: "Python ready" });
    return pyodide;
  })();

  return booting;
}

/**
 * Lay out the virtual filesystem.
 *
 * /work                harnesskit + the learner's modules (on sys.path)
 * /work/tests          the test files
 * /work/_runner.py     our pytest substitute
 * /tmp                 scratch space for tmp_path
 */
async function mount({ harnesskit, tests, runner, scripts }) {
  const py = await boot();
  py.FS.mkdirTree("/work");
  py.FS.mkdirTree("/work/tests");
  py.FS.mkdirTree("/work/harnesskit");
  py.FS.mkdirTree("/work/curriculum");
  py.FS.mkdirTree("/tmp");

  for (const [name, source] of Object.entries(harnesskit)) {
    py.FS.writeFile(`/work/harnesskit/${name}`, source);
  }
  for (const [name, source] of Object.entries(tests)) {
    py.FS.writeFile(`/work/tests/${name}`, source);
  }
  for (const [name, source] of Object.entries(scripts || {})) {
    const path = `/work/curriculum/${name}`;
    const dir = path.slice(0, path.lastIndexOf("/"));
    py.FS.mkdirTree(dir);
    py.FS.writeFile(path, source);
  }
  py.FS.writeFile("/work/_runner.py", runner);

  py.runPython(`
import sys
for p in ("/work", "/work/tests"):
    if p not in sys.path:
        sys.path.insert(0, p)
`);
  mounted = true;
  post("status", { stage: "mounted", message: "Course files mounted" });
}

/** Write the learner's current files before each run. */
function syncLearnerFiles(files) {
  for (const [name, source] of Object.entries(files)) {
    pyodide.FS.writeFile(`/work/${name}`, source);
  }
  // Drop cached modules so edited code is re-imported.
  const names = Object.keys(files).map((f) => f.replace(/\.py$/, ""));
  pyodide.runPython(`
import sys
for _name in ${JSON.stringify(names)}:
    sys.modules.pop(_name, None)
`);
}

async function runTests({ testFile, files }) {
  const py = await boot();
  if (!mounted) throw new Error("filesystem not mounted");
  syncLearnerFiles(files);

  const moduleName = testFile.replace(/\.py$/, "").replace(/^.*\//, "");
  const started = performance.now();

  const raw = await py.runPythonAsync(`
import json, _runner
json.dumps(await _runner.run_test_file(${JSON.stringify(moduleName)}))
`);
  const results = JSON.parse(raw);
  const passed = results.filter((r) => r.passed).length;

  return {
    results,
    passed,
    failed: results.length - passed,
    ok: results.length > 0 && passed === results.length,
    durationMs: Math.round(performance.now() - started),
  };
}

/** Run a standalone script (a demo, or a trace that computes an answer). */
async function runScript({ path, files, captureLastLine }) {
  const py = await boot();
  if (!mounted) throw new Error("filesystem not mounted");
  if (files) syncLearnerFiles(files);

  const started = performance.now();
  const lines = [];
  const collect = (line) => {
    lines.push(line);
    post("stdout", { line });
  };

  // Swap stdout for the duration so we can both stream and capture.
  py.setStdout({ batched: collect });
  py.setStderr({ batched: (line) => { lines.push(line); post("stderr", { line }); } });

  let error = null;
  try {
    await py.runPythonAsync(`
import sys, runpy
sys.argv = [${JSON.stringify(path)}]
runpy.run_path(${JSON.stringify(`/work/curriculum/${path}`)}, run_name="__main__")
`);
  } catch (exc) {
    error = String(exc).split("\n").slice(-4).join("\n");
    post("stderr", { line: error });
  } finally {
    py.setStdout({ batched: (line) => post("stdout", { line }) });
    py.setStderr({ batched: (line) => post("stderr", { line }) });
  }

  let payload = null;
  if (captureLastLine) {
    const last = [...lines].reverse().find((l) => l.trim().startsWith("{"));
    if (last) {
      try {
        payload = JSON.parse(last);
      } catch {
        payload = null;
      }
    }
  }

  return {
    ok: !error,
    error,
    lines,
    payload,
    durationMs: Math.round(performance.now() - started),
  };
}

// ---------------------------------------------------------------- protocol

self.onmessage = async (event) => {
  const { id, action, payload } = event.data;
  try {
    let result;
    switch (action) {
      case "boot":
        await boot();
        result = { ready: true };
        break;
      case "mount":
        await mount(payload);
        result = { mounted: true };
        break;
      case "runTests":
        result = await runTests(payload);
        break;
      case "runScript":
        result = await runScript(payload);
        break;
      default:
        throw new Error(`unknown action: ${action}`);
    }
    post("result", { id, result });
  } catch (exc) {
    post("result", { id, error: String(exc && exc.message ? exc.message : exc) });
  }
};
