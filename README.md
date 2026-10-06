# Harness Academy

**An interactive course that teaches coding-agent harness architecture by
making you rebuild one.** Runs entirely in the browser — no server, no
account, no install.

You predict what a real agent does before running it, implement the loop
yourself, deliberately break an invariant and watch a provider reject you, and
finish by assembling a working coding agent.

The study specimen is [`tau`](https://github.com/huggingface/tau), a Python
coding-agent harness written to be read.

```bash
npm install
npm run dev          # http://localhost:5273
```

---

## How it works with no server

| what | how |
|---|---|
| curriculum, tests, specimen | a static JSON bundle, ~107 KB gzipped |
| **running your Python** | **Pyodide — CPython 3.12 in WebAssembly** |
| your code and progress | localStorage, exportable as JSON |
| the AI tutor | a small agent harness in this tab, your OpenRouter key |

Your code runs in a Web Worker in your own browser. Nothing is uploaded, and
there is nothing to attack: the course cannot execute code on anyone's
machine but yours.

### Verification is real

All 116 tests run under Pyodide with verdicts **identical to real pytest** —
cross-checked on every `npm run check`. Prediction answers are computed by
*executing a trace script*, not hardcoded, so the course cannot drift from the
specimen.

```bash
npm run check         # everything, in order

npm test              # unit tests + the full suite under real pytest
npm run test:pyodide  # the same suite in WASM, verdicts must match
npm run test:browser  # builds nothing, serves dist/ itself, drives a browser
```

`test:browser` starts its own server, so it needs no preview running. Point it
at one with `URL=http://localhost:5273/` if you prefer.

### The tutor is the thing you are studying

`src/tutor/harness.js` is a coding-agent harness in about 200 lines: a loop
whose stop condition is "the assistant asked for no tools", tools as a schema
plus a function, and a typed event stream the UI renders from. It is the
architecture the course teaches, running in the same tab, and you can read it.

It has three tools: read the specimen, read your code, run Python. It is
instructed not to hand you answers, and to climb a hint ladder one rung at a
time.

**Connecting a model.** One click via OpenRouter OAuth (PKCE), or paste a key.
The key is stored in your browser and sent only to OpenRouter — there is no
server to send it to.

The free-model list is **fetched live** from OpenRouter rather than hardcoded,
because free endpoints are retired without notice. Click the model name in the
tutor header to switch; models that support tool calling are marked, and the
tutor prefers them. Free models also require "prompt logging" enabled in your
OpenRouter privacy settings.

Everything except the tutor works with no key at all.

---

## The curriculum

### Act I — The Engine
1. **First Contact** — a model cannot read files. So how does "read this file" work?
2. **Build the Engine** — can you write the loop you just described? (5 staged steps)
3. **Why Events?** — the loop knows everything. Why not let it just print?
4. **The Tool Boundary** — what has to be true where an agent touches the real world?

### Act II — Memory
5. **The Harness** — your loop takes a message list. Who owns that list?
6. **Interruption** — the user types while the agent works. Where does it go?
7. **The Invariant** — which transcript shapes are illegal, and who prevents them?
8. **Running Out of Room** — context is full. What do you throw away?

### Act III — The Application
9. **The Vanishing Write** — who writes a message to disk, and when?
10. **Who Decides What?** — where is the line between the brain and the application?
11. **Same Idea, Different Code** — what is fundamental, and what is this project's choice?

### Act IV — Reconstruction
12. **Capstone** — can you build one yourself?

Level 9 reconstructs a genuine data-loss bug from the specimen's history: a
message correct in memory and missing from disk. You find it before reading
the explanation. The fix is one line of ordering.

---

## Commands

```bash
npm run dev        # dev server with hot reload
npm run build      # static site in dist/
npm run preview    # serve the build
npm run content    # re-export curriculum JSON from the Python source
npm run check      # every verification path
```

Deploy `dist/` to any static host. There is no backend.

```bash
npm run build
# then upload dist/ — e.g.
npx wrangler pages deploy dist          # Cloudflare Pages
netlify deploy --prod --dir dist        # Netlify
```

About 288 KB gzipped. Pyodide (~5 MB) loads from a CDN on demand, after the
first page paints, so time-to-interactive does not wait on it.

## Layout

```
src/
  main.js            UI
  runtime.js         Pyodide worker client
  verify.js          grading: tests and trace-computed answers
  progress.js        the learner model (mastery, gaps, unlocking)
  store.js           localStorage
  markdown.js        renderer; raw HTML is opt-in, never for model output
  editor.js          CodeMirror 6, Python
  tutor/
    harness.js       the agent loop — read this one
    openrouter.js    provider + PKCE auth
    context.js       prompt and context assembly
runtime/
  test_runner.py     the pytest substitute that runs in WASM
public/content/      generated JSON bundle
```

The course content lives upstream in Python (`../src/academy/content_*.py`),
next to the reference solutions that validate it. `npm run content` exports it.

## Reviewing out of order

Levels unlock in sequence because each assumes the last. To browse freely —
reviewing, or giving feedback — open **Achievements → Review mode → Unlock all
levels**, or load `/?unlock=1` (and `/?unlock=0` to restore). It only changes
what is reachable; it records no progress you have not earned.

## What the web build gives up

- **`bash` in the capstone.** WASM has no subprocesses. No test needs it.
- **`git log` over the specimen.** Level 10 links to GitHub instead.
- **Stopping a runaway test** kills the page's worker rather than a process;
  if your code loops forever, reload.

## License

MIT. The `tau` specimen is MIT-licensed and belongs to its authors.
