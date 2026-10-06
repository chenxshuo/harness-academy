/* End-to-end check against the built site.
 *
 * This is the claim that matters: the course works with no server. So the
 * test drives a real browser against `dist/`, completes a prediction, and
 * runs a step's tests in Pyodide.
 *
 * It serves `dist/` itself so it can be run standalone, including in CI.
 * Point it at an already-running server with URL=... to skip that.
 */
import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { join, dirname, extname, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const DIST = join(dirname(fileURLToPath(import.meta.url)), "..", "dist");

const MIME = {
  ".html": "text/html", ".js": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".py": "text/plain", ".svg": "image/svg+xml",
  ".wasm": "application/wasm",
};

/** Minimal static server for dist/. Returns [url, close]. */
async function serveDist() {
  try {
    await stat(join(DIST, "index.html"));
  } catch {
    console.error("FAIL: dist/ not found. Run `npm run build` first.");
    process.exit(1);
  }

  const server = createServer(async (req, res) => {
    // Strip the query and refuse to escape dist/.
    const rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "");
    let file = join(DIST, rel === "/" ? "index.html" : rel);
    try {
      if ((await stat(file)).isDirectory()) file = join(file, "index.html");
      const body = await readFile(file);
      res.writeHead(200, {
        "Content-Type": MIME[extname(file)] || "application/octet-stream",
      });
      res.end(body);
    } catch {
      res.writeHead(404).end("not found");
    }
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  return [`http://127.0.0.1:${port}/`, () => new Promise((r) => server.close(r))];
}

const external = Boolean(process.env.URL);
const [URL, closeServer] = external
  ? [process.env.URL, async () => {}]
  : await serveDist();
console.log(`serving: ${URL}${external ? " (external)" : " (dist/)"}`);

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1500, height: 950 } });

const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => m.type() === "error" && errors.push("console: " + m.text()));

const fail = (msg) => {
  console.error("FAIL:", msg);
  process.exitCode = 1;
};

await page.goto(URL, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);

// 1. curriculum renders from static JSON
// Assert against the bundle rather than a hardcoded number, so adding a
// level does not break the check for the wrong reason.
const expected = await page.evaluate(async () => {
  const data = await fetch("content/curriculum.json").then((r) => r.json());
  return data.acts.reduce((n, a) => n + a.levels.length, 0);
});
const cards = await page.locator(".level-card").count();
console.log(`levels rendered: ${cards} (bundle says ${expected})`);
if (cards !== expected) fail(`expected ${expected} level cards, got ${cards}`);

// 2. a prediction can be answered, graded by a trace script in Pyodide
await page.click('.level-card[data-id="l01-first-contact"]');
await page.waitForTimeout(600);
await page.click('.choice[data-choice="2"]');
await page.click("[data-submit]");
await page.waitForTimeout(25000); // first answer boots Pyodide for the trace
const correct = await page.locator(".choice.correct").count();
console.log(`prediction graded: ${correct > 0 ? "yes" : "no"}`);
if (!correct) fail("prediction was not graded");

// 3. progress persisted to localStorage
const stored = await page.evaluate(() =>
  JSON.parse(localStorage.getItem("harness-academy:progress") || "{}")
);
const steps = Object.keys(stored.steps || {}).length;
console.log(`progress persisted: ${steps} step record(s)`);
if (!steps) fail("progress was not written to localStorage");

// 4. the real test: run a level's tests in the browser
await page.locator('[data-choice="no-tools"]').click();
await page.locator(".step").nth(1).locator("[data-submit]").click();
await page.waitForTimeout(2500);
await page.click("#nav-map");
await page.waitForTimeout(800);
await page.click('.level-card[data-id="l02-build-loop"]');
await page.waitForTimeout(2000);

const runButtons = await page.locator("[data-run]").count();
console.log(`implement steps with a run button: ${runButtons}`);
if (!runButtons) fail("no run buttons found");

await page.locator("[data-run]").first().click();
await page.waitForTimeout(30000);
const status = await page.locator(".term-inline .term-status").first().textContent();
console.log(`in-browser pytest status: ${status}`);
if (!/passed|failed/.test(status || "")) fail(`unexpected test status: ${status}`);

// 5. editor is live
const hasEditor = await page.evaluate(() => !!document.querySelector(".cm-editor"));
console.log(`code editor mounted: ${hasEditor}`);
if (!hasEditor) fail("CodeMirror did not mount");

console.log(`\npage errors: ${errors.length ? errors.slice(0, 3).join(" | ") : "none"}`);
if (errors.length) fail("page produced errors");

await browser.close();
await closeServer();
if (!process.exitCode) console.log("\n==> browser verification PASSED");
