/* Diagrams and the skill map: the two places that generate SVG.
 *
 * Both failed silently before this file existed. The diagrams all declared
 * `<marker id="ah">`, and SVG ids are document-scoped, so the second figure
 * on a page had its arrowheads resolve to the first figure's marker. The
 * page threw nothing; the arrows just vanished.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { skillMapSvg } from "../src/skillmap.js";

const diagrams = JSON.parse(
  readFileSync(new URL("../public/content/diagrams.json", import.meta.url))
);
const curriculum = JSON.parse(
  readFileSync(new URL("../public/content/curriculum.json", import.meta.url))
);

/* ------------------------------------------------------------- diagrams */

const ids = (svg) => [...svg.matchAll(/<marker id="([^"]+)"/g)].map((m) => m[1]);
const refs = (svg) => [...svg.matchAll(/url\(#([^)]+)\)/g)].map((m) => m[1]);

const seen = new Map();
let withMarkers = 0;

for (const [name, svg] of Object.entries(diagrams)) {
  const declared = ids(svg);
  if (!declared.length) continue;
  withMarkers++;

  // Every reference must resolve inside its own figure.
  for (const ref of refs(svg)) {
    assert.ok(
      declared.includes(ref),
      `${name}: url(#${ref}) does not match any marker it declares`
    );
  }

  // No two figures may declare the same id: they share one document.
  for (const id of declared) {
    assert.ok(!seen.has(id), `duplicate marker id "${id}" in ${name} and ${seen.get(id)}`);
    seen.set(id, name);
  }
}

assert.ok(withMarkers >= 15, `expected most diagrams to use arrows, got ${withMarkers}`);
console.log(`diagrams: ${withMarkers} with markers, ${seen.size} unique ids, no collisions`);

/* ------------------------------------------------------------ skill map */

const acts = curriculum.acts;
const levels = acts.flatMap((a) => a.levels);

// Every level reaches the map, and no edge points at a level that is absent.
const map = skillMapSvg(acts, () => "open");
for (const level of levels) {
  assert.ok(map.includes(`data-map-level="${level.id}"`), `${level.id} missing from the map`);
}

// One edge per prerequisite. Matched on the attribute's closing quote so
// the `.map-edges` group wrapper is not counted as an edge.
const edgeCount = [...map.matchAll(/class="map-edge(?: live)?"/g)].length;
const required = levels.reduce((n, l) => n + l.requires.length, 0);
assert.equal(edgeCount, required, "one edge per prerequisite");

// Locked nodes must say what they are waiting on, or the map answers nothing.
const allLocked = skillMapSvg(acts, (lv) => (lv.requires.length ? "locked" : "open"));
assert.ok(allLocked.includes("needs "), "locked nodes should name their blockers");

// Titles are clipped to fit the box; nothing may silently run past it.
const longest = levels.reduce((a, b) => (a.title.length > b.title.length ? a : b));
assert.ok(longest.title.length > 30, "expected at least one long title to exercise wrapping");
const wrapped = skillMapSvg(acts, () => "open");
const titleRuns = [...wrapped.matchAll(/class="map-node-title"[^>]*>([^<]*)</g)].map(
  (m) => m[1]
);
for (const run of titleRuns) {
  assert.ok(run.length <= 21, `map title line too long to fit: ${JSON.stringify(run)}`);
}

// A level with three prerequisites in three different acts is the layout's
// worst case; make sure the fixture still contains one.
const multi = levels.filter((l) => l.requires.length >= 3);
assert.ok(multi.length, "expected a level with 3+ prerequisites (the capstone)");

console.log(
  `skill map: ${levels.length} levels, ${edgeCount} edges, ` +
    `${titleRuns.length} title lines all within the box`
);
