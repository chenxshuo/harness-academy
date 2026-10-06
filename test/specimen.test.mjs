/* Specimen references must reach the real file, at a pinned revision. */
import assert from "node:assert/strict";
import { linkSpecimenPaths, specimenUrl } from "../src/specimen.js";

// The local checkout prefix is stripped; the revision is pinned.
assert.equal(
  specimenUrl("tau/src/tau_agent/loop.py"),
  "https://github.com/huggingface/tau/blob/v0.4.7/src/tau_agent/loop.py"
);
assert.ok(!specimenUrl("tau/src/x.py").includes("/main/"), "pin the revision, not main");
assert.ok(specimenUrl("tau/src/x.py", 185).endsWith("#L185"), "line anchors survive");

// Paths inside <code> become links; prose mentions are left alone.
const linked = linkSpecimenPaths("<p>read <code>tau/src/tau_agent/loop.py</code></p>");
assert.ok(linked.includes("<a class=\"specimen-link\""));
assert.ok(linked.includes("blob/v0.4.7/src/tau_agent/loop.py"));
assert.ok(linked.includes('target="_blank"'));
assert.ok(linked.includes('rel="noopener noreferrer"'), "external links need noopener");

const plain = linkSpecimenPaths("<p>the tau/src/tau_agent/loop.py file</p>");
assert.ok(!plain.includes("<a "), "bare prose mentions are not linked");

// Nothing to do is cheap and lossless.
assert.equal(linkSpecimenPaths("<p>no paths here</p>"), "<p>no paths here</p>");
assert.equal(linkSpecimenPaths(""), "");

// A path with a line number keeps the anchor.
const withLine = linkSpecimenPaths("<code>tau/src/tau_agent/loop.py:185</code>");
assert.ok(withLine.includes("#L185"));

console.log("specimen links: 10 assertions passed");
