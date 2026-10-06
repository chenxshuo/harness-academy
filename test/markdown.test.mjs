/* The XSS boundary: tutor output and curriculum prose share a renderer, so
   raw-HTML passthrough must be opt-in. */
import { md } from "../src/markdown.js";
import assert from "node:assert/strict";

const ATTACK = `<figure class="diagram"><img src=x onerror="steal()"></figure>`;
const LEGIT = `<figure class="diagram"><svg viewBox="0 0 10 10"></svg></figure>`;

const untrusted = md(ATTACK);
// What matters is that no live element is produced. The attribute text may
// survive as inert characters; a browser only acts on a real <img> tag.
assert.ok(!/<img/i.test(untrusted), "model output must not produce a live element");
assert.ok(!/<figure/i.test(untrusted), "model output must not produce a live figure");
assert.ok(untrusted.includes("&lt;figure"), "model output must be escaped");

const trusted = md(LEGIT, { trusted: true });
assert.ok(trusted.includes("<svg"), "curriculum diagrams must pass through");

// Ordinary markdown still works in both modes.
assert.ok(md("**bold**").includes("<strong>bold</strong>"));
assert.ok(md("- a\n- b").includes("<li>a</li>"));
assert.ok(md("`code`").includes("<code>code</code>"));
assert.ok(md("```\nx = 1\n```").includes("<pre><code>"));
assert.ok(md("| a | b |\n|---|---|\n| 1 | 2 |").includes("<table>"));

// Script tags in model output are inert either way.
assert.ok(!/<script/i.test(md(`<script>bad()</script>`)));

// An <img> outside the figure wrapper is equally inert.
assert.ok(!/<img/i.test(md(`<img src=x onerror=1>`)));

console.log("markdown: 10 assertions passed");
