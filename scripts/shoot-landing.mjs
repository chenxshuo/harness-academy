/* Screenshot the built landing page, for visual review.
 *
 * Serves dist/ the same way verify-browser.mjs does, then captures the hero,
 * the pillars, and the band between the curriculum and the footer - the
 * three areas most recently changed.
 *
 *   node scripts/shoot-landing.mjs [outdir]
 */
import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFile, stat, mkdir } from "node:fs/promises";
import { join, dirname, extname, normalize } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const DIST = join(HERE, "..", "dist");
const OUT = process.argv[2] || join(HERE, "..", ".shots");

const MIME = {
  ".html": "text/html", ".js": "text/javascript", ".css": "text/css",
  ".json": "application/json", ".py": "text/plain", ".svg": "image/svg+xml",
  ".wasm": "application/wasm",
};

const server = createServer(async (req, res) => {
  const rel = normalize(decodeURIComponent(req.url.split("?")[0]))
    .replace(/^(\.\.[/\\])+/, "");
  let file = join(DIST, rel === "/" ? "index.html" : rel);
  try {
    if ((await stat(file)).isDirectory()) file = join(file, "index.html");
    res.writeHead(200, { "Content-Type": MIME[extname(file)] || "application/octet-stream" });
    res.end(await readFile(file));
  } catch {
    res.writeHead(404).end("not found");
  }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${server.address().port}/`;

await mkdir(OUT, { recursive: true });
const browser = await chromium.launch();
// `viewport`, not `viewportSize`: the latter is silently ignored by
// newPage, which left every shot at the 1280px default.
const page = await browser.newPage({ viewport: { width: 1440, height: 980 } });
await page.goto(base, { waitUntil: "networkidle" });
await page.waitForSelector(".hero h1");
await page.waitForTimeout(700); // webfonts

// Above the fold, full width: the hero banner bleeds past the text column,
// so an element-scoped crop cannot show it. Taken before any scrolling.
await page.evaluate(() => window.scrollTo(0, 0));
await page.waitForTimeout(200);
await page.screenshot({ path: join(OUT, "fold.png") });
console.log(`  fold -> ${join(OUT, "fold.png")}`);

const shots = {
  hero: ".hero",
  pillars: ".pillars",
  foot: ".landing-foot",
};
for (const [name, selector] of Object.entries(shots)) {
  const el = await page.$(selector);
  if (!el) { console.log(`  ${name}: selector ${selector} not found`); continue; }
  await el.screenshot({ path: join(OUT, `${name}.png`) });
  console.log(`  ${name} -> ${join(OUT, `${name}.png`)}`);
}

// Where the curriculum ends and the page closes. `.trusted` is behind a
// flag and usually absent, so fall back to the footer.
await page.evaluate(() => {
  const el = document.querySelector(".trusted") ||
             document.querySelector(".landing-footer");
  if (el) el.scrollIntoView({ block: "center" });
});
await page.waitForTimeout(300);
await page.screenshot({ path: join(OUT, "seam.png") });
console.log(`  seam -> ${join(OUT, "seam.png")}`);

// Favicon, rendered at tab size and large, side by side.
await page.setContent(`<body style="margin:0;background:#f8f6ef;
  display:flex;gap:28px;align-items:center;padding:24px;font-family:system-ui">
  <img src="${base}favicon.svg" width="16" height="16">
  <img src="${base}favicon.svg" width="32" height="32">
  <img src="${base}favicon.svg" width="128" height="128">
</body>`);
await page.waitForTimeout(300);
await (await page.$("body")).screenshot({ path: join(OUT, "favicon.png") });
console.log(`  favicon -> ${join(OUT, "favicon.png")}`);

await browser.close();
await new Promise((r) => server.close(r));
