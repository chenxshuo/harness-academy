/* Headless check that every test file runs under Pyodide and agrees with
   pytest. This is the cross-check that keeps the two execution paths honest.
 */
import { loadPyodide } from "pyodide";
import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..", "..");
const MODE = process.argv[2] || "solutions";
const SRC = MODE === "solutions" ? join(REPO, ".solutions") : join(REPO, "workbench");

const py = await loadPyodide({ stdout: () => {}, stderr: () => {} });
py.FS.mkdirTree("/work/tests");
py.FS.mkdirTree("/work/harnesskit");
py.FS.mkdirTree("/tmp");

for (const f of readdirSync(join(REPO, "src", "harnesskit")).filter((f) => f.endsWith(".py"))) {
  py.FS.writeFile(`/work/harnesskit/${f}`, readFileSync(join(REPO, "src", "harnesskit", f), "utf8"));
}
for (const f of readdirSync(SRC).filter((f) => f.endsWith(".py"))) {
  py.FS.writeFile(`/work/${f}`, readFileSync(join(SRC, f), "utf8"));
}
const TESTS = readdirSync(join(REPO, "workbench", "tests"))
  .filter((f) => f.startsWith("test_") && f.endsWith(".py")).sort();
for (const f of TESTS) {
  py.FS.writeFile(`/work/tests/${f}`, readFileSync(join(REPO, "workbench", "tests", f), "utf8"));
}
py.FS.writeFile("/work/_runner.py", readFileSync(join(HERE, "..", "runtime", "test_runner.py"), "utf8"));
py.runPython(`import sys\nfor p in ("/work","/work/tests"):\n  sys.path.insert(0,p)`);

let pass = 0, fail = 0;
for (const file of TESTS) {
  const name = file.replace(/\.py$/, "");
  const raw = await py.runPythonAsync(
    `import json,_runner\njson.dumps(await _runner.run_test_file(${JSON.stringify(name)}))`
  );
  const results = JSON.parse(raw);
  const p = results.filter((r) => r.passed).length;
  pass += p; fail += results.length - p;
  if (results.length - p) {
    console.log(`${file}: ${p} passed, ${results.length - p} failed`);
    for (const r of results.filter((x) => !x.passed).slice(0, 2)) {
      console.log(`   ${r.name}: ${(r.message || "").split("\n")[0].slice(0, 110)}`);
    }
  }
}
console.log(`\n==> ${pass} passed, ${fail} failed under Pyodide (mode=${MODE})`);
process.exit(MODE === "solutions" && fail > 0 ? 1 : 0);
