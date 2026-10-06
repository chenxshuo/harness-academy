/* The tutor's prompt and context, ported from the Python version.
 *
 * Two modes, because free models vary a lot in tool-calling reliability:
 *
 *   tools    - the model fetches what it needs. Better reasoning, needs a
 *              model that can actually call functions.
 *   stuffed  - the specimen files and the learner's code are pre-loaded into
 *              the context. Works with any model, costs more tokens.
 *
 * "auto" starts in tools mode and falls back to stuffed if the model makes no
 * tool calls while visibly needing one. A tutor that cannot read the specimen
 * degrades into a generic chatbot, which is the thing the course must not be.
 */

export const TUTOR_SYSTEM = `You are the tutor inside Harness Academy, a course where the learner
reconstructs a coding-agent harness instead of reading about one.

THE ONE RULE: do not do the learner's thinking for them.

They have a verification engine that tells them whether their code is correct.
They do not need you for that. They need you for the thing a test cannot do:
provoke the right question.

Default moves, roughly in order of preference:
  - Ask what they expect to happen, then suggest the experiment that checks it.
  - Ask them to name the component responsible before you confirm it.
  - Point at a specific runtime observation ("look at provider.calls - how many
    entries?") rather than explaining what it would show.
  - When they propose a design, ask what breaks it, not whether it is right.
  - When they are wrong, ask a question whose honest answer exposes the problem.

HINT LADDER. When stuck, climb one rung at a time, never start at the top:
  1. conceptual   - "what has to be true for the loop to stop?"
  2. architectural- "which layer should own that decision?"
  3. subsystem    - "this lives in the harness, not the loop"
  4. file         - "look at tau/src/tau_agent/harness.py"
  5. function     - "read _append_interrupted_tool_results"
  6. explanation  - only now, and only if they have genuinely tried

Judge where they are from the context block, not from how plainly they ask. If
they have already failed three times and used two hints, skip to rung 4 or 5;
grinding is not productive struggle. If they are on their first attempt, stay
at rung 1 even if they ask you to just tell them. Say plainly that you are
holding back and why.

If the learner is clearly frustrated or has burned a lot of attempts, drop the
Socratic posture and help concretely. The goal is understanding, not ritual.

NEVER paste a working implementation of the current step's target file.
Showing the finished answer destroys the only reason the exercise exists.
Sketches of *shape* ("you will need a while loop whose condition is...") are
fine.

Be concise. Terminal-width prose, no preamble. Plain text and markdown, no
emoji. Never output raw HTML.`;

export const TUTOR_SYSTEM_TOOLS = `${TUTOR_SYSTEM}

TOOLS. You are a coding agent, so act like one. Read the specimen with
read_specimen before describing it. Read the learner's code with read_my_code
before commenting on it. Use run_python to settle a question empirically
rather than asserting an answer. Ground explanations in a path and a line.`;

export const TUTOR_SYSTEM_STUFFED = `${TUTOR_SYSTEM}

You have no tools. The relevant specimen files and the learner's current code
are included in the context block below. Work from those; if you need
something that is not there, say which file you would want to see and why,
and suggest the experiment the learner could run.`;

/** Build the context block prepended to each learner message. */
export function renderContext(ctx) {
  const lines = ["<learning-context>"];

  if (ctx.levelTitle) lines.push(`Level: ${ctx.levelTitle} (${ctx.levelId})`);
  if (ctx.levelQuestion) lines.push(`Driving question: ${ctx.levelQuestion}`);
  if (ctx.stepTitle) lines.push(`Current step [${ctx.stepKind}]: ${ctx.stepTitle}`);
  if (ctx.stepBody) {
    const body = ctx.stepBody.trim();
    lines.push(`Step brief:\n${body.length > 900 ? body.slice(0, 900) + "..." : body}`);
  }
  if (ctx.specimenPaths?.length) {
    lines.push("Relevant specimen files: " + ctx.specimenPaths.join(", "));
  }

  lines.push(`Attempts on this step: ${ctx.attempts || 0}. Hints opened: ${ctx.hintsUsed || 0}.`);

  const readable = {
    "too-easy": "Recent work has been easy for them - push harder.",
    "too-hard": "They have been struggling - be more concrete.",
    "well-matched": "Difficulty is about right.",
    calibrating: "Not enough data on their level yet.",
  }[ctx.difficulty];
  if (readable) lines.push(`Difficulty read: ${readable}`);

  if (ctx.struggling?.length) lines.push("Shaky concepts: " + ctx.struggling.join(", "));

  for (const gap of ctx.gaps || []) {
    if (gap.gap === "predicts-but-cannot-build") {
      lines.push(
        `NOTE: they can predict '${gap.concept}' but not implement it. ` +
          "Push toward writing code, not more discussion."
      );
    } else if (gap.gap === "builds-but-cannot-explain") {
      lines.push(
        `NOTE: they can implement '${gap.concept}' but not explain it. ` +
          "Ask them to articulate why it works."
      );
    }
  }

  if (ctx.targetFile && ctx.learnerCode) {
    const code =
      ctx.learnerCode.length > 6000 ? ctx.learnerCode.slice(0, 6000) + "\n... (truncated)" : ctx.learnerCode;
    lines.push(`\nTheir current ${ctx.targetFile}:\n\`\`\`python\n${code}\n\`\`\``);
  }

  if (ctx.lastResult) {
    const status = ctx.lastResult.passed ? "PASSED" : "FAILED";
    lines.push(`\nLast verification: ${status} - ${ctx.lastResult.summary || ""}`);
    if (ctx.lastResult.detail) {
      lines.push(`Failure detail: ${String(ctx.lastResult.detail).slice(0, 700)}`);
    }
  }

  if (ctx.lastPrediction) {
    const verdict = ctx.lastPrediction.passed ? "correct" : "incorrect";
    lines.push(
      `\nTheir last prediction was ${verdict}. They answered: ${JSON.stringify(ctx.lastPrediction.answer)}.`
    );
    if (!ctx.lastPrediction.passed) {
      lines.push(
        "Do NOT state the right answer. Ask a question that makes the mismatch visible to them."
      );
    }
  }

  if (ctx.quote) {
    const quoted = ctx.quote.trim();
    lines.push(
      `\nThey highlighted this passage in the page and are asking about it ` +
        `specifically:\n<<<\n${quoted.length > 1500 ? quoted.slice(0, 1500) + "..." : quoted}\n>>>\n` +
        "Answer about THIS text. If it is course prose, explain the idea; if " +
        "it is code, reason about that code."
    );
  }

  // Stuffed mode: inline what tools would otherwise fetch.
  if (ctx.stuffedFiles?.length) {
    lines.push("\n<reference-files>");
    for (const { path, content } of ctx.stuffedFiles) {
      const body = content.length > 9000 ? content.slice(0, 9000) + "\n... (truncated)" : content;
      lines.push(`\n--- ${path} ---\n${body}`);
    }
    lines.push("</reference-files>");
  }

  lines.push("</learning-context>");
  return lines.join("\n");
}

/** Files to inline when running without tools. */
export function stuffedFilesFor(ctx, specimen) {
  const out = [];
  for (const path of (ctx.specimenPaths || []).slice(0, 2)) {
    const entry = specimen[path];
    if (entry) out.push({ path, content: entry.content });
  }
  return out;
}
