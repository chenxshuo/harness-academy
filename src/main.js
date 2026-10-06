/* Harness Academy - browser build.
 *
 * Ported from the server-backed version. The UI is unchanged; what changed is
 * underneath: curriculum comes from a static JSON bundle, code and progress
 * live in localStorage, Python runs in a Pyodide worker, and the tutor is a
 * small agent harness talking to OpenRouter with the learner's own key.
 *
 * There is no server. The whole thing is a folder of files.
 */

import { md, esc } from "./markdown.js";
import { linkSpecimenPaths, specimenLabel, specimenUrl } from "./specimen.js";
import * as store from "./store.js";
import * as P from "./progress.js";
import { checkPrediction, verify, runDemo } from "./verify.js";
import { onRuntimeEvent, ready, runtimeStatus, warmUp } from "./runtime.js";
import { createTutor } from "./tutor/index.js";
import { createEditor } from "./editor.js";
import {
  renderCurriculumDiagram,
  renderLanding,
  renderLandingFooter,
  updateLandingCta,
} from "./landing.js";
import { skillMapSvg } from "./skillmap.js";
import { HERO as HERO_COPY, curriculumSub } from "./content/landing.js";

// The button label was duplicated here as a literal, which is how it drifted
// from the copy file once already.
const HERO_CTA = HERO_COPY.cta;

const $ = (id) => document.getElementById(id);

const state = {
  content: null,
  acts: [],
  levels: [],
  levelsById: {},
  progress: null,
  summary: null,
  level: null,
  activeStep: 0,
  answers: {},
  confidence: {},
  hints: {},
  results: {},
  busy: false,
  quote: "",
  lastResult: null,
  lastPrediction: null,
};

let tutor = null;

// ------------------------------------------------------------ content load

/** Resolve a path against the deployed base (Vite's `base`, "./" here). */
export function assetUrl(path) {
  return new URL(path, document.baseURI).href;
}

async function loadContent() {
  const names = [
    "curriculum",
    "tests",
    "harnesskit",
    "specimen",
    "scripts",
    "diagrams",
  ];
  const [curriculum, tests, harnesskit, specimen, scripts, diagrams, runner] =
    await Promise.all([
      ...names.map((n) => fetch(assetUrl(`content/${n}.json`)).then((r) => r.json())),
      fetch(assetUrl("content/test_runner.py")).then((r) => r.text()),
    ]);

  return { curriculum, tests, harnesskit, specimen, scripts, diagrams, runner };
}

// ------------------------------------------------------------ toasts

function toast(message, kind = "") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = message;
  $("toasts").appendChild(el);
  setTimeout(
    () => {
      el.style.transition = "opacity .3s";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 300);
    },
    kind === "win" ? 5200 : 2800
  );
}

function celebrate(achievements) {
  for (const a of achievements || []) {
    toast(
      `<span style="font-size:18px">★</span> <div><strong>${esc(a.title)}</strong><br>
       <span style="color:var(--ink-mid);font-size:13px">${esc(a.detail)}</span></div>`,
      "win"
    );
  }
}

// ------------------------------------------------------------ terminal

const ANSI_FG = {
  30: "#2c2823", 31: "#e0705c", 32: "#8fbf8a", 33: "#d4a657",
  34: "#7fa7d4", 35: "#c08bc0", 36: "#79b8b0", 37: "#e8e2d6",
  90: "#8a8275", 91: "#f08a76", 92: "#a8d4a2", 93: "#e4c07a",
  94: "#9fc0e4", 95: "#d4a8d4", 96: "#98ccc4", 97: "#f8f6ef",
};

function ansiToHtml(line) {
  let html = "";
  let open = 0;
  const parts = String(line).split(/\x1b\[([0-9;]*)m/);
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 0) {
      if (parts[i]) html += esc(parts[i]);
      continue;
    }
    const codes = parts[i].split(";").filter(Boolean).map(Number);
    if (!codes.length || codes.includes(0)) {
      html += "</span>".repeat(open);
      open = 0;
      continue;
    }
    const style = [];
    for (const code of codes) {
      if (ANSI_FG[code]) style.push(`color:${ANSI_FG[code]}`);
      else if (code === 1) style.push("font-weight:600");
      else if (code === 2) style.push("opacity:.65");
      else if (code === 3) style.push("font-style:italic");
      else if (code === 4) style.push("text-decoration:underline");
    }
    if (style.length) {
      html += `<span style="${style.join(";")}">`;
      open++;
    }
  }
  return html + "</span>".repeat(open);
}

function terminalPanel({ title = "", hint = "" } = {}) {
  const el = document.createElement("div");
  el.className = "term";
  el.innerHTML = `
    <div class="term-bar">
      <span class="term-dots"><i></i><i></i><i></i></span>
      <span class="term-title" data-title>${esc(title)}</span>
      <span class="term-status" data-status></span>
    </div>
    <pre class="term-body" data-body>${
      hint ? `<span class="term-hint">${esc(hint)}</span>` : ""
    }</pre>`;

  const body = el.querySelector("[data-body]");
  return {
    el,
    setTitle: (t) => (el.querySelector("[data-title]").textContent = t),
    setStatus: (text, cls = "") => {
      const s = el.querySelector("[data-status]");
      s.textContent = text;
      s.className = `term-status ${cls}`;
    },
    clear: () => (body.innerHTML = ""),
    write: (html, cls = "") => {
      const row = document.createElement("div");
      if (cls) row.className = cls;
      row.innerHTML = html || "&nbsp;";
      body.appendChild(row);
      body.scrollTop = body.scrollHeight;
    },
  };
}

/** Run a demo script in a terminal panel. */
function createRunner(host, { path, label }) {
  const panel = terminalPanel({ hint: `Press ${label} to run this here.` });
  host.innerHTML = "";
  host.appendChild(panel.el);

  const actions = document.createElement("div");
  actions.className = "actions";
  actions.innerHTML = `
    <button class="primary" data-go>${esc(label)}</button>
    <span class="save-state" data-note></span>`;
  host.appendChild(actions);

  const button = actions.querySelector("[data-go]");
  const note = actions.querySelector("[data-note]");

  button.onclick = async () => {
    button.disabled = true;
    button.textContent = "Running...";
    panel.clear();
    panel.setStatus("running", "running");
    panel.setTitle(path);
    panel.write(`<span class="term-prompt">$</span> python ${esc(path)}`, "term-cmd");

    const stop = onRuntimeEvent((ev) => {
      if (ev.type === "stdout" || ev.type === "stderr") panel.write(ansiToHtml(ev.line));
      if (ev.type === "status" && ev.stage === "loading") panel.setStatus("booting Python", "running");
    });

    try {
      await ready(state.content);
      panel.setStatus("running", "running");
      const run = await runDemo(path);
      panel.setStatus(run.ok ? "done" : "error", run.ok ? "ok" : "bad");
      note.textContent = `${(run.durationMs / 1000).toFixed(2)}s`;
    } catch (err) {
      panel.write(ansiToHtml(String(err.message || err)));
      panel.setStatus("error", "bad");
    } finally {
      stop();
      button.disabled = false;
      button.textContent = `${label} again`;
    }
  };

  return panel;
}

// ------------------------------------------------------------ map

function refreshSummary() {
  state.summary = P.summary(state.progress, state.levels);
  return state.summary;
}

function renderXP() {
  const s = state.summary;
  if (!s) return;
  const pct = s.stepsTotal ? (s.stepsDone / s.stepsTotal) * 100 : 0;
  $("xp-fill").style.width = `${pct}%`;
  $("xp-label").textContent = `${s.levelsDone} / ${s.levelsTotal} levels`;
}

function levelIndex(id) {
  return state.levels.findIndex((l) => l.id === id) + 1;
}

function renderMap() {
  refreshSummary();
  const unlocked = (lv) => P.levelUnlocked(state.progress, lv, state.levelsById);
  const next = state.levels.find((lv) => unlocked(lv) && !P.levelDone(state.progress, lv));

  // The call to action stays an instruction. Naming the next level made the
  // button read as a label rather than something to press.
  const label = next ? HERO_CTA : "Review the course";

  const difficultyNote = {
    "too-easy": "You are finding these easy. Harder challenges are worth trying.",
    "too-hard": "Lean on the tutor and hints. That is what they are for.",
    "well-matched": "Difficulty looks well matched.",
    calibrating: "",
  }[state.summary.difficulty];

  // Review mode is a local toggle for browsing out of order. It used to
  // announce itself here, under the call to action, where a first-time
  // visitor reads the pitch - the wrong place for a debug affordance. The
  // settings panel still says whether it is on.
  const note = state.summary.levelsDone
    ? difficultyNote ||
      `${state.summary.levelsDone} of ${state.summary.levelsTotal} levels done.`
    : "No signup. Nothing to install. Runs in this tab.";

  const landing = $("landing");
  // Render once; later visits only refresh the call to action, so the page
  // does not flash on every return from a level.
  if (!landing.dataset.rendered) {
    renderLanding(landing, {
      onStart: () => openLevel((next || state.levels[0]).id),
      startLabel: label,
      resumeNote: note,
    });
    landing.dataset.rendered = "1";
    // The act overview belongs with the level list it summarises, so it is
    // rendered into its own host under the curriculum heading.
    renderCurriculumDiagram(
      $("curriculum-diagram"),
      state.content.diagrams?.["course-map"] || ""
    );
    // Social proof and the footer sit *after* the curriculum, so the level
    // list is not buried below a credibility band.
    renderLandingFooter($("landing-foot"));
  } else {
    updateLandingCta(landing, { label, note });
    landing.querySelector("[data-start]").onclick = () =>
      openLevel((next || state.levels[0]).id);
  }

  const sub = $("curriculum-sub");
  if (sub) {
    sub.textContent = curriculumSub(state.acts.length, state.levels.length);
  }

  $("acts").innerHTML = state.acts
    .map(
      (act) => `
    <div class="act">
      <div class="act-head">
        <h3>${esc(act.title)}</h3>
        <p>${esc(act.subtitle)}</p>
      </div>
      <div class="levels">
        ${act.levels
          .map((lv) => {
            const done = P.levelDone(state.progress, lv);
            const started = P.levelStarted(state.progress, lv);
            const open = unlocked(lv);
            const stepsDone = lv.steps.filter((s) =>
              P.isDone(state.progress, lv.id, s.id)
            ).length;
            return `
          <div class="level-card ${done ? "done" : ""} ${started ? "started" : ""} ${
            open ? "" : "locked"
          }" data-id="${lv.id}">
            <div class="level-num">${
              done
                ? "&#10003;"
                : open
                  ? String(levelIndex(lv.id)).padStart(2, "0")
                  : "&#128274;"
            }</div>
            <div class="level-info">
              <h4>${esc(lv.title)}</h4>
              <p>${esc(open ? lv.teaser : "Complete earlier levels to unlock")}</p>
            </div>
            <div class="level-meta">
              ${started && !done ? `<span class="pill">${stepsDone}/${lv.steps.length}</span>` : ""}
              ${done ? `<span class="pill done">done</span>` : ""}
              <span>${lv.minutes}m</span>
            </div>
          </div>`;
          })
          .join("")}
      </div>
    </div>`
    )
    .join("");

  for (const card of document.querySelectorAll(".level-card:not(.locked)")) {
    card.onclick = () => openLevel(card.dataset.id);
  }
  renderXP();
}

// ------------------------------------------------------------ level

async function openLevel(id, { anchor = "" } = {}) {
  const anchorEl = anchor ? document.getElementById(anchor) : null;
  const anchorTop = anchorEl ? anchorEl.getBoundingClientRect().top : null;

  const level = state.levelsById[id];
  if (!level) return;
  state.level = level;

  const firstOpen = level.steps.findIndex((s) => !P.isDone(state.progress, level.id, s.id));
  state.activeStep = firstOpen === -1 ? level.steps.length - 1 : firstOpen;

  $("view-map").classList.add("hidden");
  $("view-level").classList.remove("hidden");
  renderLevel();

  if (anchorTop !== null) {
    requestAnimationFrame(() => {
      const again = document.getElementById(anchor);
      if (again) {
        window.scrollTo(0, window.scrollY + again.getBoundingClientRect().top - anchorTop);
      }
    });
  } else {
    window.scrollTo(0, 0);
  }

  // The first editor is usually a scroll away; start Python warming now.
  if (level.steps.some((s) => s.kind === "implement" || s.runCommand)) {
    ready(state.content).catch(() => {});
  }
}

/**
 * Return to the map.
 *
 * `toCurriculum` scrolls to the level list rather than the top: someone
 * leaving a level wants to pick the next one, not re-read the hero. Clicking
 * the brand still goes to the top, which is what a logo usually means.
 */
function backToMap({ toCurriculum = true } = {}) {
  state.level = null;
  $("view-level").classList.add("hidden");
  $("view-map").classList.remove("hidden");
  renderMap();

  const anchor = toCurriculum ? document.querySelector(".curriculum-head") : null;
  if (anchor) {
    // Offset for the sticky top bar so the heading is not tucked under it.
    const top = anchor.getBoundingClientRect().top + window.scrollY - 76;
    window.scrollTo({ top, behavior: "instant" in window ? "instant" : "auto" });
  } else {
    window.scrollTo(0, 0);
  }
}

function stepDone(step) {
  return P.isDone(state.progress, state.level.id, step.id);
}

function renderLevel() {
  const lv = state.level;
  $("level-title").textContent = lv.title;
  $("level-question").textContent = lv.question;
  renderDots();

  const allDone = lv.steps.every(stepDone);
  const body = $("level-body");

  body.innerHTML = `
    ${lv.hook ? `<div class="block hook prose">${prose(lv.hook)}</div>` : ""}
    <div id="steps"></div>
    ${
      allDone && lv.reveal
        ? `<div class="block reveal" id="sec-reveal">
             <div class="reveal-head">The real implementation</div>
             <div class="reveal-body prose">${prose(lv.reveal)}</div>
           </div>`
        : ""
    }
    ${
      allDone && lv.transfer
        ? `<div class="block transfer prose" id="sec-transfer">${prose(lv.transfer)}</div>`
        : ""
    }
    <div class="nav-foot">
      <button class="ghost" id="nav-map">Back to map</button>
      ${allDone ? `<button class="primary" id="nav-next">Next level &rarr;</button>` : ""}
    </div>`;

  const steps = $("steps");
  lv.steps.forEach((step, index) => steps.appendChild(renderStep(step, index)));

  $("nav-map").onclick = () => backToMap();
  const next = $("nav-next");
  if (next) {
    next.onclick = () => {
      const candidate = state.levels.find(
        (l) => P.levelUnlocked(state.progress, l, state.levelsById) && !P.levelDone(state.progress, l)
      );
      candidate ? openLevel(candidate.id) : backToMap();
    };
  }
  renderTutorChips();
  renderToc();
}

function renderDots() {
  const lv = state.level;
  $("step-dots").innerHTML = lv.steps
    .map(
      (s, i) =>
        `<div class="dot ${stepDone(s) ? "done" : ""} ${
          i === state.activeStep ? "active" : ""
        }"></div>`
    )
    .join("");
}

function renderToc() {
  const lv = state.level;
  const toc = $("level-toc");
  if (!lv) {
    toc.innerHTML = "";
    return;
  }

  const entries = lv.steps.map((step, index) => ({
    id: `step-${step.id}`,
    label: step.title,
    done: stepDone(step),
    active: index === state.activeStep,
  }));
  if (lv.steps.every(stepDone)) {
    if (lv.reveal) entries.push({ id: "sec-reveal", label: "The real implementation" });
    if (lv.transfer) entries.push({ id: "sec-transfer", label: "What transfers" });
  }

  toc.innerHTML = `
    <div class="toc-head">On this page</div>
    <ul class="toc-list">
      ${entries
        .map(
          (e) => `
        <li>
          <a href="#${e.id}" data-jump="${e.id}"
             class="${e.active ? "active" : ""} ${e.done ? "done" : ""}">
            <span class="toc-mark">${e.done ? "&#10003;" : "&bull;"}</span>
            <span>${esc(e.label)}</span>
          </a>
        </li>`
        )
        .join("")}
    </ul>`;

  for (const link of toc.querySelectorAll("[data-jump]")) {
    link.onclick = (ev) => {
      ev.preventDefault();
      document.getElementById(link.dataset.jump)?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    };
  }
}

/** Render curriculum prose: markdown, then link specimen paths. */
function prose(text) {
  return linkSpecimenPaths(md(text, { trusted: true }));
}

function renderStep(step, index) {
  const el = document.createElement("div");
  const done = stepDone(step);
  el.className = `step ${done ? "is-done" : ""}`;
  el.id = `step-${step.id}`;

  el.innerHTML = `
    <div class="step-head">
      <span class="kind ${step.kind}">${step.kind}</span>
      <h3>${esc(step.title)}</h3>
      ${done ? `<span class="step-check">&#10003;</span>` : ""}
    </div>
    <div class="step-body">
      ${step.body ? `<div class="prose">${prose(step.body)}</div>` : ""}
      <div class="step-interaction"></div>
      ${step.hints.length ? `<div class="hints" data-hints></div>` : ""}
      <div class="step-after">${
        done && step.after ? `<div class="after prose">${prose(step.after)}</div>` : ""
      }</div>
    </div>`;

  const zone = el.querySelector(".step-interaction");
  if (step.kind === "predict") buildPredict(zone, step);
  else if (step.kind === "implement") buildImplement(zone, step);
  else buildExplain(zone, step);

  if (step.hints.length) buildHints(el.querySelector("[data-hints]"), step);
  const cached = state.results[step.id];
  if (cached) showResult(el, step, cached);
  return el;
}

function markStepDone(step, stepEl, after) {
  stepEl.classList.add("is-done");
  stepEl.querySelector(".step-after").innerHTML = `<div class="after prose">${prose(after)}</div>`;
  advance();
}

function advance() {
  const lv = state.level;
  const nextIndex = lv.steps.findIndex((s) => !stepDone(s));
  if (nextIndex === -1) {
    const last = lv.steps[lv.steps.length - 1];
    setTimeout(() => openLevel(lv.id, { anchor: `step-${last.id}` }), 700);
  } else {
    state.activeStep = nextIndex;
    renderDots();
    renderToc();
  }
}

// ---------------------------------------------------- predict

function buildPredict(zone, step) {
  const keys = "ABCD".split("");
  const done = stepDone(step);

  zone.innerHTML = `
    ${step.runCommand ? `<div data-term style="margin-bottom:1.2rem"></div>` : ""}
    <p style="font-weight:600;margin:4px 0 0">${esc(step.question)}</p>
    ${step.multi ? `<p style="color:var(--ink-soft);font-size:13px;margin:2px 0 0">Select all that apply.</p>` : ""}
    <div class="choices"></div>
    <div class="confidence">
      <span>How sure are you?</span>
      ${["guess", "unsure", "confident"]
        .map((c) => `<button class="conf-btn" data-conf="${c}">${c}</button>`)
        .join("")}
    </div>
    <div class="actions">
      <button class="primary" data-submit ${done ? "disabled" : ""}>
        ${done ? "Answered" : "Submit"}
      </button>
    </div>`;

  const termHost = zone.querySelector("[data-term]");
  if (termHost && step.runCommand) {
    createRunner(termHost, {
      path: scriptPathFor(step.runCommand),
      label: step.runLabel || "Run",
    });
  }

  const list = zone.querySelector(".choices");
  step.choices.forEach((choice, i) => {
    const btn = document.createElement("button");
    btn.className = "choice";
    btn.dataset.choice = choice.id;
    btn.innerHTML = `<span class="choice-key">${keys[i]}</span><span>${esc(choice.label)}</span>`;
    btn.disabled = done;
    btn.onclick = () => {
      if (step.multi) {
        const set = new Set(state.answers[step.id] || []);
        set.has(choice.id) ? set.delete(choice.id) : set.add(choice.id);
        state.answers[step.id] = [...set];
      } else {
        state.answers[step.id] = choice.id;
      }
      sync();
      // Picking again after a wrong answer re-arms the button.
      const submit = zone.querySelector("[data-submit]");
      if (submit && !stepDone(step)) {
        submit.disabled = false;
        submit.textContent = "Submit";
      }
    };
    list.appendChild(btn);
  });

  function sync() {
    const value = state.answers[step.id];
    for (const btn of list.querySelectorAll(".choice")) {
      const on = step.multi
        ? (value || []).includes(btn.dataset.choice)
        : value === btn.dataset.choice;
      btn.classList.toggle("selected", on);
    }
  }
  sync();

  for (const btn of zone.querySelectorAll("[data-conf]")) {
    btn.onclick = () => {
      state.confidence[step.id] = btn.dataset.conf;
      for (const other of zone.querySelectorAll("[data-conf]")) {
        other.classList.toggle("on", other === btn);
      }
    };
  }

  zone.querySelector("[data-submit]").onclick = async (ev) => {
    const answer = state.answers[step.id];
    if (!answer || (step.multi && !answer.length)) return toast("Pick an answer first.");
    ev.target.disabled = true;
    ev.target.textContent = "Checking...";

    let data;
    try {
      // A trace-backed prediction needs Python; everything else is instant.
      if (step.trace) await ready(state.content);
      data = await checkPrediction(step, answer);
    } catch (err) {
      ev.target.disabled = false;
      ev.target.textContent = "Submit";
      toast(`Could not check that. ${String(err.message || err).slice(0, 90)}`);
      return;
    }

    // On a wrong answer, reveal only the note for what they chose. Marking
    // the correct option immediately would make the retry meaningless.
    for (const note of data.notes) {
      const btn = list.querySelector(`[data-choice="${note.id}"]`);
      if (!btn) continue;
      btn.classList.remove("selected");
      const reveal = data.passed ? note.chosen || note.correct : note.chosen;
      if (!reveal) continue;

      if (data.passed && note.correct) btn.classList.add("correct");
      else if (note.chosen) btn.classList.add("wrong");

      if (note.note) {
        btn.querySelector(".choice-note")?.remove();
        const div = document.createElement("div");
        div.className = "choice-note prose";
        div.innerHTML = md(note.note);
        btn.appendChild(div);
      }
      // A wrong option stays visible but unselectable; everything else is
      // still open so another answer can be tried.
      if (!data.passed) btn.disabled = true;
    }

    if (data.passed) {
      for (const btn of list.querySelectorAll(".choice")) btn.disabled = true;
    }

    ev.target.textContent = data.passed ? "Correct" : "Try another";
    ev.target.disabled = data.passed;

    P.record(state.progress, {
      levelId: state.level.id,
      stepId: step.id,
      kind: "predict",
      passed: data.passed,
      concepts: state.level.concepts,
      hintsUsed: (state.hints[step.id] || []).length,
      confidence: state.confidence[step.id] || "",
      answer,
    });
    state.lastPrediction = { passed: data.passed, answer, expected: data.expected };
    const earned = P.checkAchievements(state.progress);
    refreshSummary();
    renderXP();
    celebrate(earned);

    const stepEl = ev.target.closest(".step");
    if (data.passed) {
      markStepDone(step, stepEl, step.after);
    } else {
      // Clear the selection so the next click is a deliberate choice.
      delete state.answers[step.id];
      const remaining = list.querySelectorAll(".choice:not([disabled])").length;
      toast(
        remaining
          ? "Not that one - read the note, then pick again."
          : "Out of options. Open a hint or ask the tutor."
      );
    }
  };
}

function scriptPathFor(command) {
  return command === "async" ? "demo_async.py" : "demo_first_contact.py";
}

// ---------------------------------------------------- implement

function buildImplement(zone, step) {
  const saved = store.readFile(step.targetFile);
  const starterHash = store.hashString(step.starter || "");
  const savedHash = store.fileStarterHash(step.targetFile);
  const stale = saved !== null && savedHash && savedHash !== starterHash;

  zone.innerHTML = `
    ${
      stale
        ? `<div class="notice" data-stale>
             A newer version of this starter exists. Your code is kept; press
             <strong>Reset</strong> to take the update.
           </div>`
        : ""
    }
    <div class="editor-wrap">
      <div class="editor-bar">
        <div class="tabs">
          <button class="tab on" data-tab="code">${esc(step.targetFile)}</button>
          <button class="tab" data-tab="test">${esc(step.testFile.split("/").pop())}</button>
        </div>
        <span class="editor-tools">
          ${
            step.carriesFrom
              ? `<button class="tab" data-carry title="Copy in ${esc(
                  step.carriesNote || step.carriesFrom
                )}">&#8595; Bring forward</button>`
              : ""
          }
          <button class="tab" data-reset title="Restore the original starter">Reset</button>
        </span>
        <span class="save-state" data-save>saved</span>
      </div>
      <div data-editor-host></div>
      <pre class="readonly-code hidden" data-test>${esc(
        state.content.tests[step.testFile.split("/").pop()] || ""
      )}</pre>
    </div>
    <div class="actions">
      <button class="primary" data-run>Run tests</button>
      <button class="ghost danger hidden" data-stop>Stop</button>
      <span class="save-state" data-meta></span>
      <span class="save-state" style="margin-left:auto">${
        navigator.platform.includes("Mac") ? "⌘" : "Ctrl"
      }+Enter to run</span>
    </div>
    <div data-term-host></div>`;

  const host = zone.querySelector("[data-editor-host]");
  const testView = zone.querySelector("[data-test]");
  const saveState = zone.querySelector("[data-save]");
  const record = state.progress.steps[P.stepKey(state.level.id, step.id)];
  if (record) {
    zone.querySelector("[data-meta]").textContent = `${record.attempts} attempt${
      record.attempts > 1 ? "s" : ""
    }`;
  }

  let saveTimer = null;
  const scheduleSave = (text) => {
    saveState.textContent = "unsaved";
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      const ok = store.saveFile(step.targetFile, text, starterHash);
      saveState.textContent = ok ? "saved" : "save failed";
    }, 500);
  };

  const editor = createEditor({
    parent: host,
    doc: saved ?? step.starter,
    onChange: scheduleSave,
  });

  for (const tab of zone.querySelectorAll(".tab[data-tab]")) {
    tab.onclick = () => {
      const showCode = tab.dataset.tab === "code";
      host.classList.toggle("hidden", !showCode);
      testView.classList.toggle("hidden", showCode);
      for (const t of zone.querySelectorAll(".tab[data-tab]")) {
        t.classList.toggle("on", t === tab);
      }
    };
  }

  const carryButton = zone.querySelector("[data-carry]");
  if (carryButton) {
    carryButton.onclick = () => {
      const current = editor.getValue().trim();
      if (
        current &&
        current !== (step.starter || "").trim() &&
        !confirm(`Replace what is in ${step.targetFile} with your ${step.carriesFrom}?`)
      ) {
        return;
      }
      const source = store.readFile(step.carriesFrom);
      if (source === null) {
        toast(`Could not read ${step.carriesFrom} - have you started that step?`);
        return;
      }
      editor.setValue(source);
      scheduleSave(source);
      toast(`Copied in your ${step.carriesFrom}.`);
    };
  }

  zone.querySelector("[data-reset]").onclick = () => {
    if (!confirm(`Discard your changes to ${step.targetFile} and restore the starter?`)) return;
    editor.setValue(step.starter || "");
    store.saveFile(step.targetFile, step.starter || "", starterHash);
    saveState.textContent = "saved";
    zone.querySelector("[data-stale]")?.remove();
    toast("Starter restored.");
  };

  const termHost = zone.querySelector("[data-term-host]");
  const runButton = zone.querySelector("[data-run]");
  const stopButton = zone.querySelector("[data-stop]");

  const runTests = async () => {
    if (state.busy) return;
    state.busy = true;
    runButton.disabled = true;
    runButton.textContent = "Running...";

    clearTimeout(saveTimer);
    store.saveFile(step.targetFile, editor.getValue(), starterHash);
    saveState.textContent = "saved";

    const panel = terminalPanel();
    termHost.innerHTML = "";
    termHost.appendChild(panel.el);
    panel.el.classList.add("term-inline");
    panel.setStatus("running", "running");
    panel.setTitle(`pytest ${step.testFile.split("/").pop()}`);
    panel.write(
      `<span class="term-prompt">$</span> pytest ${esc(step.testFile.split("/").pop())}`,
      "term-cmd"
    );

    // Tests run in a worker; stopping means discarding the result, since a
    // tight loop in learner code would otherwise block that worker.
    let abandoned = false;
    stopButton.classList.remove("hidden");
    stopButton.disabled = false;
    stopButton.textContent = "Stop";
    stopButton.onclick = () => {
      abandoned = true;
      stopButton.disabled = true;
      panel.setStatus("stopped", "");
      panel.write("stopped - reload the page if Python stays busy");
      finish();
      toast("Stopped. If your code loops forever, reload the page.");
    };

    const finish = () => {
      stopButton.classList.add("hidden");
      runButton.disabled = false;
      runButton.textContent = "Run tests";
      state.busy = false;
    };

    let data;
    try {
      await ready(state.content);
      data = await verify(step);
      if (abandoned) return;
    } catch (err) {
      if (abandoned) return;
      panel.write(ansiToHtml(String(err.message || err)));
      panel.setStatus("error", "bad");
      finish();
      return;
    }

    for (const result of data.results) {
      if (result.passed) continue;
      panel.write(
        `<span style="color:#f08a76">FAILED</span> ${esc(result.name)}` +
          (result.message ? ` - ${esc(result.message.split("\n")[0])}` : "")
      );
    }
    panel.write(
      data.passed
        ? `<span style="color:#a8d4a2">${data.passed ? data.results.length : 0} passed</span> in ${(
            data.durationMs / 1000
          ).toFixed(2)}s`
        : `<span style="color:#f08a76">${data.failures.length} failed</span>, ${
            data.results.length - data.failures.length
          } passed in ${(data.durationMs / 1000).toFixed(2)}s`
    );
    panel.setStatus(data.passed ? "passed" : "failed", data.passed ? "ok" : "bad");
    finish();

    state.results[step.id] = data;
    state.lastResult = data;

    P.record(state.progress, {
      levelId: state.level.id,
      stepId: step.id,
      kind: "implement",
      passed: data.passed,
      concepts: state.level.concepts,
      hintsUsed: (state.hints[step.id] || []).length,
      seconds: data.durationMs / 1000,
    });
    const earned = P.checkAchievements(state.progress);
    refreshSummary();
    renderXP();

    const stepEl = runButton.closest(".step");
    showResult(stepEl, step, data);
    celebrate(earned);

    if (data.passed) {
      toast("All tests passing.");
      markStepDone(step, stepEl, step.after);
    }
  };

  runButton.onclick = runTests;
  zone.addEventListener("keydown", (ev) => {
    if ((ev.metaKey || ev.ctrlKey) && ev.key === "Enter") {
      ev.preventDefault();
      runTests();
    }
  });
}

function showResult(stepEl, step, data) {
  let box = stepEl.querySelector(".result");
  if (!box) {
    box = document.createElement("div");
    stepEl.querySelector(".step-interaction").appendChild(box);
  }
  box.className = `result ${data.passed ? "pass" : "fail"}`;
  box.innerHTML = `
    <div class="result-head">
      <span>${data.passed ? "&#10003;" : "&#10007;"}</span>
      <span>${esc(data.summary)}</span>
      <span class="result-time">${data.durationMs}ms</span>
    </div>
    ${
      data.passed || !data.detail
        ? ""
        : `<div class="result-body"><div class="fail-line">${esc(data.detail)}</div></div>`
    }`;
}

// ---------------------------------------------------- explain / inspect


/** Buttons for a step's specimen files: read inline, or open on GitHub. */
function specimenButtons(paths) {
  return `<div class="specimen-row">
    ${paths
      .map(
        (p) => `<span class="specimen-chip">
           <button class="chip-main" data-open="${esc(p)}" title="Read here">${esc(
             specimenLabel(p)
           )}</button>
           <a class="chip-link" href="${specimenUrl(p)}" target="_blank"
              rel="noopener noreferrer" title="Open ${esc(p)} on GitHub">
             <svg viewBox="0 0 24 24" width="11" height="11" fill="none"
                  stroke="currentColor" stroke-width="2.4" stroke-linecap="round"
                  stroke-linejoin="round" aria-hidden="true">
               <path d="M7 17 17 7"/><path d="M8 7h9v9"/></svg>
           </a>
         </span>`
      )
      .join("")}
  </div>`;
}

/* Explain and inspect steps.
 *
 * Every one of these now leads with a choice. A blank textarea is not a
 * prompt: there is nothing to react to and nothing happens if you skip it,
 * so in practice it gets skipped, and the step teaches nothing. Picking a
 * position costs one click, is immediately answered by the note on that
 * option, and gives the tutor something specific to argue with.
 *
 * The writing box stays, because on these four steps the reasoning is the
 * point - but it is optional. Committing to a position is what advances the
 * step; elaborating is offered, not demanded.
 */
function buildExplain(zone, step) {
  const done = stepDone(step);
  const keys = "ABCD".split("");
  const hasStances = !!(step.stances && step.stances.length);

  zone.innerHTML = `
    ${step.runCommand ? `<div data-term></div>` : ""}
    ${step.specimenPaths.length ? specimenButtons(step.specimenPaths) : ""}
    ${
      hasStances
        ? `<div class="stance" data-stance>
             <p class="stance-q">${esc(step.stanceQuestion)}</p>
             <div class="choices">
               ${step.stances
                 .map(
                   (c, i) => `
                 <button class="choice" data-stance-pick="${esc(c.id)}">
                   <span class="choice-key">${keys[i]}</span><span>${esc(c.label)}</span>
                 </button>`
                 )
                 .join("")}
             </div>
           </div>
           <div class="writing hidden" data-writing>
             <p class="writing-prompt">${esc(step.writingPrompt || "Say why.")}
               <span class="writing-optional">optional</span>
             </p>
             <textarea class="plain-answer" data-answer></textarea>
           </div>`
        : `<textarea class="plain-answer" data-answer
             placeholder="Write your reasoning..."></textarea>`
    }
    <div class="actions" data-actions ${hasStances && !done ? 'style="display:none"' : ""}>
      <button class="primary" data-submit ${done ? "disabled" : ""}>
        ${done ? "Recorded" : "Record"}
      </button>
      <button class="ghost" data-challenge>Ask the tutor to challenge it</button>
    </div>`;

  // Committing to a position is what makes the writing worth doing: there is
  // something concrete to defend, and the tutor has something specific to
  // push back on.
  let stance = null;
  for (const btn of zone.querySelectorAll("[data-stance-pick]")) {
    btn.onclick = () => {
      stance = step.stances.find((c) => c.id === btn.dataset.stancePick);
      for (const other of zone.querySelectorAll("[data-stance-pick]")) {
        other.classList.toggle("selected", other === btn);
        other.querySelector(".choice-note")?.remove();
      }
      if (stance?.note) {
        const div = document.createElement("div");
        div.className = "choice-note prose";
        div.innerHTML = md(stance.note);
        btn.appendChild(div);
      }
      zone.querySelector("[data-writing]")?.classList.remove("hidden");
      const actions = zone.querySelector("[data-actions]");
      if (actions) actions.style.display = "";
      zone.querySelector("[data-answer]")?.focus();
    };
  }

  const termHost = zone.querySelector("[data-term]");
  if (termHost && step.runCommand) {
    createRunner(termHost, {
      path: scriptPathFor(step.runCommand),
      label: step.runLabel || "Run",
    });
  }

  for (const btn of zone.querySelectorAll("[data-open]")) {
    btn.onclick = () => openSource(btn.dataset.open);
  }

  zone.querySelector("[data-submit]").onclick = (ev) => {
    const text = zone.querySelector("[data-answer]").value;
    if (hasStances && !stance) {
      return toast("Pick a position first.");
    }
    // Writing is required only where there is no position to commit to.
    // Where there is one, the pick is the commitment and the prose is a
    // bonus; demanding forty characters just taught people to type "asdf".
    if (!hasStances && text.trim().length < 40) {
      return toast("Say more - a sentence or two at minimum.");
    }
    const note = stance ? `[${stance.label}] ${text}` : text;
    P.addNote(state.progress, state.level.id, note);
    P.record(state.progress, {
      levelId: state.level.id,
      stepId: step.id,
      kind: step.kind,
      passed: true,
      concepts: state.level.concepts,
    });
    const earned = P.checkAchievements(state.progress);
    refreshSummary();
    renderXP();
    celebrate(earned);

    ev.target.disabled = true;
    ev.target.textContent = "Recorded";
    markStepDone(step, ev.target.closest(".step"), step.after);
  };

  zone.querySelector("[data-challenge]").onclick = () => {
    const text = zone.querySelector("[data-answer]")?.value.trim() || "";
    openTutor();
    if (stance && text) {
      $("tutor-text").value =
        `I chose: ${stance.label}\n\nMy reasoning:\n${text}\n\n` +
        "Challenge it - find the case I have not considered.";
    } else if (stance) {
      $("tutor-text").value =
        `I chose: ${stance.label}\n\nWhat am I not seeing about this choice?`;
    } else if (text) {
      $("tutor-text").value =
        `Here is my reasoning. Challenge it - find the case I have not considered.\n\n${text}`;
    } else {
      $("tutor-text").value =
        "I am not sure how to approach this step. What should I look at first?";
    }
    $("tutor-form").dispatchEvent(new Event("submit"));
  };
}

// ---------------------------------------------------- hints

function buildHints(container, step) {
  const shown = state.hints[step.id] || [];
  container.innerHTML =
    shown
      .map(
        (h, i) => `<div class="hint"><span class="hint-n">${i + 1}</span><span>${esc(h)}</span></div>`
      )
      .join("") +
    (shown.length < step.hints.length
      ? `<button class="ghost" data-hint style="margin-top:4px">
           ${shown.length ? "Another hint" : "I'm stuck - hint"}
           <span style="opacity:.55">(${shown.length}/${step.hints.length})</span>
         </button>`
      : `<p style="color:var(--ink-soft);font-size:13px;margin:6px 0 0">
           No hints left. Ask the tutor - it can see your code.</p>`);

  const btn = container.querySelector("[data-hint]");
  if (btn) {
    btn.onclick = () => {
      state.hints[step.id] = [...shown, step.hints[shown.length]];
      buildHints(container, step);
    };
  }
}

// ---------------------------------------------------- source viewer

function openSource(path) {
  const entry = state.content.specimen[path];
  const url = specimenUrl(path);

  if (!entry) {
    // Not bundled, but still readable - send them to the source.
    window.open(url, "_blank", "noopener");
    return;
  }
  showModal(
    path,
    `<div class="actions" style="margin:0 0 12px">
       <a class="ghost" href="${url}" target="_blank" rel="noopener noreferrer">
         Open on GitHub &#8599;</a>
       ${entry.truncated
         ? `<span class="save-state">excerpt - the full file is on GitHub</span>`
         : ""}
     </div>
     <pre class="readonly-code" style="max-height:60vh">${esc(entry.content)}</pre>`
  );
}

function showModal(title, html) {
  $("modal-title").textContent = title;
  $("modal-body").innerHTML = html;
  $("modal").classList.remove("hidden");
}

// ---------------------------------------------------- selection -> tutor

function initSelectionToTutor() {
  const bubble = document.createElement("button");
  bubble.className = "sel-bubble hidden";
  bubble.innerHTML = `<span class="sel-bubble-icon">&#8594;</span> Ask tutor about this`;
  document.body.appendChild(bubble);

  let pending = "";
  const hide = () => bubble.classList.add("hidden");

  document.addEventListener("selectionchange", () => {
    if (document.activeElement?.id === "tutor-text") return hide();
    const selection = window.getSelection();
    const text = selection ? selection.toString().trim() : "";
    if (!text || text.length < 3) return hide();

    const anchor = selection.anchorNode;
    const host = anchor && (anchor.nodeType === 1 ? anchor : anchor.parentElement);
    // Only offer this where there is something to ask about. On the landing
    // page it fires while someone is reading marketing copy.
    if (!host || !host.closest("#view-level, .modal-body")) return hide();

    pending = text;
    const rect = selection.getRangeAt(0).getBoundingClientRect();
    bubble.style.top = `${window.scrollY + rect.top - 42}px`;
    bubble.style.left = `${window.scrollX + rect.left + rect.width / 2}px`;
    bubble.classList.remove("hidden");
  });

  document.addEventListener("mousedown", (ev) => {
    if (ev.target !== bubble && !bubble.contains(ev.target)) hide();
  });

  bubble.onclick = (ev) => {
    ev.preventDefault();
    attachQuote(pending);
    hide();
    window.getSelection()?.removeAllRanges();
  };
}

function attachQuote(text) {
  state.quote = text;
  openTutor();
  const holder = $("tutor-quote");
  holder.innerHTML = `
    <div class="quote-card">
      <div class="quote-text">${esc(text.length > 400 ? text.slice(0, 400) + "..." : text)}</div>
      <button class="ghost icon quote-drop" title="Remove">&times;</button>
    </div>`;
  holder.classList.remove("hidden");
  holder.querySelector(".quote-drop").onclick = clearQuote;
  $("tutor-text").focus();
}

function clearQuote() {
  state.quote = "";
  $("tutor-quote").innerHTML = "";
  $("tutor-quote").classList.add("hidden");
}

// ---------------------------------------------------- tutor panel

function openTutor() {
  $("tutor").classList.remove("hidden");
  document.body.classList.add("tutor-open");
  $("tutor-text").focus();
}

function closeTutor() {
  $("tutor").classList.add("hidden");
  document.body.classList.remove("tutor-open");
}

function toggleTutor() {
  $("tutor").classList.contains("hidden") ? openTutor() : closeTutor();
}

function renderTutorChips() {
  const host = $("tutor-chips");
  // The chips live inside the intro block, which the connect prompt replaces.
  // Once that has happened there is nowhere to put them, and that is fine.
  if (!host) return;

  const chips = state.level
    ? [
        "What should I be looking at first?",
        "Give me a conceptual hint, not the answer.",
        "Why does this matter architecturally?",
        "Show me where this lives in the specimen.",
      ]
    : ["What is a coding agent harness?", "How should I approach this course?"];
  host.innerHTML = chips.map((c) => `<button class="chip">${esc(c)}</button>`).join("");
  for (const chip of host.querySelectorAll(".chip")) {
    chip.onclick = () => {
      $("tutor-text").value = chip.textContent;
      $("tutor-form").dispatchEvent(new Event("submit"));
    };
  }
}

function currentStep() {
  return state.level ? state.level.steps[state.activeStep] : null;
}

function tutorContext() {
  const level = state.level;
  const step = currentStep();
  const record = step ? state.progress.steps[P.stepKey(level.id, step.id)] : null;
  return {
    levelId: level?.id || "",
    levelTitle: level?.title || "",
    levelQuestion: level?.question || "",
    stepId: step?.id || "",
    stepKind: step?.kind || "",
    stepTitle: step?.title || "",
    stepBody: step?.body || "",
    specimenPaths: step?.specimenPaths || [],
    targetFile: step?.targetFile || "",
    learnerCode: step?.targetFile ? store.readFile(step.targetFile) || "" : "",
    attempts: record?.attempts || 0,
    hintsUsed: (state.hints[step?.id] || []).length,
    difficulty: state.summary?.difficulty || "",
    struggling: state.summary?.struggling || [],
    gaps: state.summary?.gaps || [],
    lastResult: state.lastResult,
    lastPrediction: state.lastPrediction,
    quote: "",
  };
}

async function askTutor(message, quote = "") {
  const log = $("tutor-log");
  log.querySelector(".tutor-intro")?.remove();

  const you = document.createElement("div");
  you.className = "msg you";
  you.innerHTML = `<div class="msg-who"><span class="who-dot"></span>You</div>
                   ${quote ? `<div class="msg-quote"></div>` : ""}
                   <div class="msg-text"></div>`;
  if (quote) you.querySelector(".msg-quote").textContent = quote;
  you.querySelector(".msg-text").textContent = message;
  log.appendChild(you);

  const reply = document.createElement("div");
  reply.className = "msg tutor";
  reply.innerHTML = `<div class="msg-who"><span class="who-dot"></span>Tutor</div>
                     <div class="msg-text"><span class="cursor-blink"></span></div>`;
  const replyText = reply.querySelector(".msg-text");
  log.appendChild(reply);
  log.scrollTop = log.scrollHeight;

  const send = $("tutor-send");
  send.disabled = true;

  const atBottom = () => log.scrollHeight - log.scrollTop - log.clientHeight < 60;
  let text = "";
  const tools = [];
  const paint = () => {
    const stick = atBottom();
    replyText.innerHTML =
      (tools.length
        ? tools.map((t) => `<div class="tool-trace">&rarr; ${esc(t)}</div>`).join("")
        : "") +
      // Untrusted: model output never gets raw-HTML passthrough.
      (text ? `<div class="prose">${md(text)}</div>` : `<span class="cursor-blink"></span>`);
    if (stick) log.scrollTop = log.scrollHeight;
  };

  try {
    const context = { ...tutorContext(), quote };
    for await (const event of tutor.ask(message, context)) {
      if (event.type === "message_update") {
        text += event.delta;
        paint();
      } else if (event.type === "tool_execution_start") {
        tools.push(`used ${event.name}`);
        paint();
      } else if (event.type === "error") {
        reply.className = "msg err";
        reply.querySelector(".msg-who").innerHTML = `<span class="who-dot"></span>Tutor error`;
        replyText.textContent = event.message;
      }
    }
    if (!text && !reply.classList.contains("err")) {
      // The provider now reports empty replies as errors, so reaching here
      // means the turn ended without any event at all.
      reply.className = "msg err";
      reply.querySelector(".msg-who").innerHTML = `<span class="who-dot"></span>Tutor error`;
      replyText.textContent =
        "The model sent nothing back. Free endpoints are often busy - retry, " +
        "or click the model name above to switch.";
    }
  } catch (err) {
    reply.className = "msg err";
    reply.querySelector(".msg-who").innerHTML = `<span class="who-dot"></span>Tutor error`;
    replyText.textContent = String(err.message || err);
  } finally {
    send.disabled = false;
  }
}

// ---------------------------------------------------- achievements modal

function showAchievements() {
  const s = refreshSummary();
  const earned = new Set(s.achievements);

  const achievementsHtml = Object.entries(P.ACHIEVEMENTS)
    .map(
      ([key, a]) => `
    <div class="ach ${earned.has(key) ? "earned" : "locked"}">
      <div class="ach-mark">${earned.has(key) ? "★" : "☆"}</div>
      <div class="ach-text"><strong>${esc(a.title)}</strong><span>${esc(a.detail)}</span></div>
    </div>`
    )
    .join("");

  const conceptHtml = Object.keys(s.concepts).length
    ? `<h4 style="margin:24px 0 12px;font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-mid)">
         Concept mastery</h4>
       <div class="concept-grid">
         ${Object.entries(s.concepts)
           .map(
             ([name, c]) => `
           <div class="concept-row">
             <span>${esc(name)}</span>
             <div class="bar"><i style="width:${Math.round(
               ((c.predict + c.implement) / 2) * 100
             )}%"></i></div>
             <span class="tag ${c.level}">${c.level}</span>
           </div>
           ${
             c.gap
               ? `<div style="font-size:12.5px;color:var(--amber);padding:0 13px 4px">
                    ${
                      c.gap === "predicts-but-cannot-build"
                        ? "You can predict this but not yet build it - try the implementation again."
                        : "You can build this but not yet explain it - try articulating why it works."
                    }
                  </div>`
               : ""
           }`
           )
           .join("")}
       </div>`
    : "";

  const dataHtml = `
    <h4 style="margin:24px 0 12px;font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-mid)">
      Review mode</h4>
    <p style="font-size:13.5px;color:var(--ink-mid);margin:0 0 10px">
      Levels normally unlock in order, because each one assumes the last. Turn
      that off to browse or review out of sequence.</p>
    <div class="actions">
      <button class="ghost" id="btn-unlock">${
        P.unlockAllEnabled() ? "Re-lock levels" : "Unlock all levels"
      }</button>
      <span class="save-state">${P.unlockAllEnabled() ? "all levels open" : "unlocking in order"}</span>
    </div>

    <h4 style="margin:24px 0 12px;font-size:12px;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-mid)">
      Your data</h4>
    <p style="font-size:13.5px;color:var(--ink-mid);margin:0 0 10px">
      Progress and code live in this browser only. Export to move machines or keep a backup.</p>
    <div class="actions">
      <button class="ghost" id="btn-export">Export progress</button>
      <button class="ghost" id="btn-import">Import</button>
      <button class="ghost danger" id="btn-reset">Reset progress</button>
    </div>`;

  showModal("Progress", achievementsHtml + conceptHtml + dataHtml);

  $("btn-unlock").onclick = () => {
    const next = !P.unlockAllEnabled();
    P.setUnlockAll(next);
    $("modal").classList.add("hidden");
    backToMap();
    toast(next ? "All levels unlocked." : "Levels lock in order again.");
  };

  $("btn-export").onclick = () => {
    const blob = new Blob([store.exportAll()], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `harness-academy-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };
  $("btn-import").onclick = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "application/json";
    input.onchange = async () => {
      try {
        store.importAll(await input.files[0].text());
        location.reload();
      } catch (err) {
        toast(String(err.message || err));
      }
    };
    input.click();
  };
  $("btn-reset").onclick = () => {
    if (!confirm("Clear all progress? Your code is kept.")) return;
    state.progress = store.resetProgress();
    $("modal").classList.add("hidden");
    backToMap();
    toast("Progress cleared.");
  };
}

// ------------------------------------------------------------ boot

async function main() {
  // ?unlock=1 turns review mode on (and ?unlock=0 off) without hunting for
  // the toggle. Handy when sharing a link to a specific level for feedback.
  const flag = new URLSearchParams(location.search).get("unlock");
  if (flag !== null) {
    P.setUnlockAll(flag !== "0" && flag !== "false");
    history.replaceState({}, "", location.pathname);
  }

  state.content = await loadContent();
  state.acts = state.content.curriculum.acts;
  state.levels = state.acts.flatMap((a) => a.levels);
  state.levelsById = Object.fromEntries(state.levels.map((l) => [l.id, l]));
  state.progress = store.loadProgress();

  tutor = createTutor({
    specimen: state.content.specimen,
    readLearnerFile: (name) => store.readFile(name),
  });
  await tutor.restore();
  updateTutorStatus();

  renderMap();
  renderTutorChips();
  initSelectionToTutor();

  // Nothing in Level 1 needs Python, so fetch the runtime while they read.
  if ("requestIdleCallback" in window) {
    requestIdleCallback(() => warmUp().catch(() => {}), { timeout: 4000 });
  } else {
    setTimeout(() => warmUp().catch(() => {}), 2500);
  }
}

function updateTutorStatus() {
  const sub = $("tutor-sub");
  if (!tutor?.isConnected()) {
    sub.textContent = "not connected";
    sub.onclick = null;
    sub.classList.remove("clickable");
    renderTutorConnect();
  } else {
    sub.textContent = tutor.modelLabel();
    // Free endpoints go busy or get retired, so switching must be one click
    // away rather than buried.
    sub.classList.add("clickable");
    sub.title = "Change model";
    sub.onclick = showModelPicker;
  }
}

function showModelPicker() {
  const models = tutor.availableModels();
  const current = tutor.currentModel();

  const rows = models.length
    ? models
        .map(
          (m) => `
      <button class="model-row ${m.id === current ? "on" : ""}" data-model="${esc(m.id)}">
        <span class="model-name">${esc(m.name)}</span>
        <span class="model-meta">
          ${m.tools ? `<span class="pill">tools</span>` : `<span class="pill warn">no tools</span>`}
          ${m.context ? `<span>${Math.round(m.context / 1000)}k</span>` : ""}
        </span>
      </button>`
        )
        .join("")
    : `<p style="color:var(--ink-mid)">Could not reach OpenRouter's model list.</p>`;

  showModal(
    "Tutor model",
    `<p style="font-size:13.5px;color:var(--ink-mid);margin:0 0 12px">
       Free models, fetched live from OpenRouter. Ones marked <strong>tools</strong>
       can read the specimen and your code; without that the tutor falls back to
       pre-loaded context.</p>
     <div class="model-list">${rows}</div>
     <div class="actions" style="margin-top:14px">
       <button class="ghost" id="btn-refresh-models">Refresh list</button>
     </div>`
  );

  for (const row of document.querySelectorAll("[data-model]")) {
    row.onclick = () => {
      tutor.setModel(row.dataset.model);
      updateTutorStatus();
      $("modal").classList.add("hidden");
      toast(`Tutor model: ${row.dataset.model.split("/").pop()}`);
    };
  }
  $("btn-refresh-models").onclick = async () => {
    await tutor.refreshModels();
    showModelPicker();
  };
}

function renderTutorConnect() {
  const log = $("tutor-log");
  const intro = log.querySelector(".tutor-intro");
  if (!intro) return;
  intro.innerHTML = `
    <p>The tutor is a small coding agent running in this tab. It can read the
       specimen, read your code, and run Python to check a claim.</p>
    <p>It needs a model. Connect a free OpenRouter account - your key stays in
       this browser and is never sent anywhere but OpenRouter.</p>
    <div class="actions">
      <button class="primary" id="btn-connect">Connect OpenRouter</button>
      <button class="ghost" id="btn-paste-key">Paste a key</button>
    </div>
    <p style="font-size:12px;color:var(--ink-soft);margin-top:10px">
      Free models require "prompt logging" enabled in your OpenRouter privacy
      settings. Everything else in the course works without a tutor.</p>`;

  $("btn-connect").onclick = () => tutor.beginConnect();
  $("btn-paste-key").onclick = async () => {
    const key = prompt("Paste your OpenRouter API key (starts with sk-or-):");
    if (!key) return;
    await tutor.connectWithKey(key.trim());
    updateTutorStatus();
    renderTutorChips();
    toast("Tutor connected.");
  };
}

// ------------------------------------------------------------ skill map

/**
 * Open the course map over whatever is on screen.
 *
 * It is an overlay, not a view: the curriculum list stays on the landing
 * page, and opening the map from inside a level leaves that level mounted
 * underneath. Pressing Map used to navigate back to the landing page, which
 * discarded your place for the sake of seeing where you were.
 */
function openMapView() {
  const unlocked = (lv) => P.levelUnlocked(state.progress, lv, state.levelsById);
  const status = (lv) =>
    P.levelDone(state.progress, lv) ? "done" : unlocked(lv) ? "open" : "locked";

  $("mapview-body").innerHTML = skillMapSvg(state.acts, status, {
    activeId: state.level?.id || "",
  });

  const done = state.levels.filter((lv) => status(lv) === "done").length;
  const open = state.levels.filter((lv) => status(lv) === "open").length;
  $("mapview-sub").textContent =
    `${done} done, ${open} open, ${state.levels.length} total`;

  for (const node of $("mapview-body").querySelectorAll("[data-map-level]")) {
    const level = state.levelsById[node.dataset.mapLevel];
    if (!level || status(level) === "locked") continue;
    const go = () => {
      closeMapView();
      openLevel(level.id);
    };
    node.onclick = go;
    node.onkeydown = (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        go();
      }
    };
  }

  $("mapview").classList.remove("hidden");
}

function closeMapView() {
  $("mapview").classList.add("hidden");
}

function toggleMapView() {
  $("mapview").classList.contains("hidden") ? openMapView() : closeMapView();
}

// --------------------------------------------------------- event wiring

$("btn-back").onclick = () => openMapView();
$("btn-map").onclick = toggleMapView;
$("mapview-close").onclick = closeMapView;
$("mapview").onclick = (ev) => {
  if (ev.target.id === "mapview") closeMapView();
};
$("go-map").onclick = () => backToMap({ toCurriculum: false });
$("go-map-text").onclick = () => backToMap({ toCurriculum: false });
$("btn-tutor-toggle").onclick = toggleTutor;
$("btn-tutor-close").onclick = closeTutor;
$("btn-achievements").onclick = showAchievements;
$("modal-close").onclick = () => $("modal").classList.add("hidden");
$("modal").onclick = (ev) => {
  if (ev.target.id === "modal") $("modal").classList.add("hidden");
};

$("tutor-form").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const text = $("tutor-text").value.trim();
  const quote = state.quote;
  if (!text && !quote) return;
  if (!tutor.isConnected()) {
    toast("Connect a model first.");
    return;
  }
  $("tutor-text").value = "";
  clearQuote();
  askTutor(text || "What does this mean?", quote);
});

$("tutor-text").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && !ev.shiftKey) {
    ev.preventDefault();
    $("tutor-form").dispatchEvent(new Event("submit"));
  }
});

document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape") {
    $("modal").classList.add("hidden");
    closeMapView();
  }
  if ((ev.metaKey || ev.ctrlKey) && ev.key === "/") {
    const el = document.activeElement;
    if (el && (el.closest(".cm-editor") || el.tagName === "TEXTAREA" || el.tagName === "INPUT")) {
      return;
    }
    ev.preventDefault();
    toggleTutor();
  }
});

(function makeResizable() {
  const grip = $("tutor-grip");
  if (!grip) return;
  const saved = store.loadSettings().tutorWidth;
  if (saved) document.documentElement.style.setProperty("--tutor-w", saved);

  let dragging = false;
  grip.addEventListener("mousedown", (ev) => {
    dragging = true;
    ev.preventDefault();
    document.body.style.userSelect = "none";
  });
  window.addEventListener("mousemove", (ev) => {
    if (!dragging) return;
    const width = Math.min(Math.max(window.innerWidth - ev.clientX, 360), 900);
    document.documentElement.style.setProperty("--tutor-w", `${width}px`);
  });
  window.addEventListener("mouseup", () => {
    if (!dragging) return;
    dragging = false;
    document.body.style.userSelect = "";
    store.saveSettings({
      tutorWidth: getComputedStyle(document.documentElement)
        .getPropertyValue("--tutor-w")
        .trim(),
    });
  });
})();

// Python loads in the background and only matters when a step needs it, so
// it is reported where that happens rather than in the chrome. A failure is
// worth surfacing, though - silence there would be confusing.
onRuntimeEvent((ev) => {
  if (ev.type !== "status") return;
  const el = $("runtime-status");
  if (!el) return;
  const failed = ev.stage === "failed";
  el.textContent = failed ? "Python failed to load" : "";
  el.className = `runtime-status ${failed ? "failed" : ""}`;
});

main().catch((err) => {
  document.body.innerHTML = `<div style="padding:3rem;font-family:system-ui">
    <h1>Could not start</h1><pre>${esc(String(err.stack || err))}</pre></div>`;
});
