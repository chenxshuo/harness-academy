"""Act II-B: the systems that surround the loop.

Four levels filling genuine gaps against the broader coding-agent landscape,
each one a subsystem the specimen actually implements:

    system prompt assembly   tau_coding/system_prompt.py
    permission / trust       tau_coding/project_trust.py
    retry and error recovery tau_ai/retry.py
    extensions and skills    tau_coding/extensions/, skills.py

Deliberately excluded: MCP, cron, agent teams, worktree isolation, todo
lists. Those appear in other curricula but are absent from tau, and teaching
from something the learner cannot open and read would undo the point.
"""

from __future__ import annotations

from academy.curriculum import Act, Choice, Level, Step


def act_systems() -> Act:
    return Act(
        id="act2b",
        title="Act II½ - Around the Loop",
        subtitle=(
            "The loop is small. These are the systems that decide what it sees, "
            "what it may do, and what happens when it fails."
        ),
        levels=[_system_prompt(), _permission(), _recovery(), _extensions()],
    )


# --------------------------------------------------------------------------


def _system_prompt() -> Level:
    return Level(
        id="l13-system-prompt",
        title="Where the Prompt Comes From",
        teaser="The system prompt is assembled, not written.",
        question="Who decides what the model is told before it sees anything?",
        minutes=20,
        requires=["l04-tools"],
        concepts=["system-prompt", "context-assembly", "provenance"],
        hook="""\
Open any agent's source looking for its system prompt and you will usually
find there isn't one. There is a *function that builds one*.

Tau's is assembled from at least six sources: a default preamble, the tool
list, guidelines derived from which tools are loaded, project instructions
from `AGENTS.md`, user skills, and whatever the runtime appends. The text sent
to the model on any given run may never have existed as a literal string
anywhere in the repository.

That has a consequence worth feeling before you read the code.

{{diagram:prompt-assembly}}
""",
        steps=[
            Step(
                id="who-contributes",
                kind="predict",
                title="A rule appears from nowhere",
                body="""\
Your agent suddenly starts refusing to touch files under `generated/`. You did
not write that rule. It is not in the default prompt.

The system prompt is built per run from several sources.
""",
                question="Which of these can legitimately add text to the system prompt?",
                multi=True,
                choices=[
                    Choice(
                        id="project",
                        label="An AGENTS.md file in the project you started the agent in.",
                        note="Yes. This is the main mechanism for project-specific instruction, and it is why the same agent behaves differently in two repositories.",
                    ),
                    Choice(
                        id="tools",
                        label="The set of tools loaded for this session.",
                        note="Yes. Tau derives guideline text from the tools present, so a session without `bash` is told different things than one with it.",
                    ),
                    Choice(
                        id="extension",
                        label="An installed extension.",
                        note="Yes - `PromptSection` exists for exactly this. It is also why an untrusted extension is a real concern, which is the next level.",
                    ),
                    Choice(
                        id="model",
                        label="The model itself, carrying instructions between sessions.",
                        note="No. The model is stateless between requests. Anything that persists was put there by the harness, which is the whole point: every word is attributable.",
                    ),
                ],
                answer=["project", "tools", "extension"],
                hints=[
                    "Think about what differs between running the same agent in two different repositories.",
                    "One of these four cannot possibly carry state between runs.",
                ],
                after="""\
Three sources, none of them the model. That is the property that matters:
**every word in the system prompt was put there by code you can find.**

Tau takes this further than most. `build_system_prompt_inspection()` returns
not just the text but a list of `SystemPromptSource` records - each contiguous
section labelled with where it came from. The TUI can show you the effective
prompt with provenance.

That exists because a prompt assembled from six places is otherwise
unexplainable when it misbehaves.
""",
                xp=20,
            ),
            Step(
                id="assemble",
                kind="implement",
                title="Assemble a prompt with provenance",
                body="""\
Write `build_system_prompt` in the editor below.

It takes a default preamble, a list of tools, project context files, and
optional extra sections, and returns both the assembled text **and** a record
of which source produced each section.

Keeping provenance is the interesting constraint. It is easy to concatenate
strings; it is slightly harder to concatenate strings and still be able to say
where each one came from, and that is what makes the result debuggable.

Six tests.
""",
                target_file="system_prompt.py",
                test_file="tests/test_l13_system_prompt.py",
                specimen_paths=["tau/src/tau_coding/system_prompt.py"],
                starter='''\
"""Assemble a system prompt, and remember where each part came from.

Concatenating strings is easy. Concatenating strings while staying able to
explain the result is the part that makes a prompt debuggable when it starts
behaving oddly.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PromptSource:
    """One contiguous, attributed section of the final prompt."""

    kind: str      # "default" | "tools" | "context" | "extra"
    label: str     # human-readable, e.g. "Project instructions"
    content: str


@dataclass
class PromptResult:
    text: str
    sources: list[PromptSource] = field(default_factory=list)


def format_tools(tools) -> str:
    """Render the tool list for the prompt.

    One line per tool: "- name: description".
    """
    # TODO
    raise NotImplementedError


def build_system_prompt(
    *,
    preamble: str,
    tools=(),
    context_files=(),   # [(path, content), ...]
    extra_sections=(),  # [(label, body), ...]
) -> PromptResult:
    """Assemble the prompt and record every section's origin.

    Order matters and is part of the contract:
        1. preamble                     kind="default"
        2. the tool list                kind="tools"    (only if tools exist)
        3. each project context file    kind="context"  (one source each)
        4. each extra section           kind="extra"

    Sections are joined with a blank line between them.
    """
    # TODO
    raise NotImplementedError
''',
                hints=[
                    "Build a `list[PromptSource]` first, then join their `.content` with '\\n\\n' to make the text. Doing it in that order means provenance cannot drift from the text.",
                    "format_tools: `'\\n'.join(f'- {t.name}: {t.description}' for t in tools)`.",
                    "Skip the tools section entirely when there are no tools - an empty 'Available tools:' header is worse than none.",
                    "Each context file gets its own source, labelled with its path, so the UI can say which file caused a rule.",
                ],
                after="""\
You can now answer "why did it do that?" by looking at the prompt it was
given, section by section.

Compare with `tau/src/tau_coding/system_prompt.py`. Tau's version has the
same shape and more kinds: `default`, `system`, `append`, `extension`,
`context`, `skill`, `runtime`. Note `system` and `append` are separate - an
override replaces the default entirely, while an append adds to it, and
conflating them would make the override impossible to reason about.
""",
                xp=35,
            ),
        ],
        reveal="""\
The prompt is a *product*, not a constant. Tau's docs put it plainly: "The
system prompt is a generated product of policy, tools, skills, and context."

Two design decisions worth noticing in
`tau/src/tau_coding/system_prompt.py`:

1. **Guidelines are derived from the tools present.** A session without a
   `bash` tool is not told how to use one. The prompt adapts to the
   capabilities, rather than describing a fixed imaginary agent.

2. **Provenance is a first-class return value**, not a debug flag. Once a
   prompt comes from six places, "show me the effective prompt" stops being a
   nicety and becomes the only way to explain behaviour.
""",
        transfer="""\
**Transferable:** when you open an unfamiliar agent, find the function that
*builds* the system prompt rather than searching for prompt text. Then ask
what can contribute to it. That set is the real list of things that can change
the agent's behaviour without changing its code - and it is usually larger
than people expect.
""",
    )


# --------------------------------------------------------------------------


def _permission() -> Level:
    return Level(
        id="l14-permission",
        title="The Decision Point",
        teaser="Some tools should ask first. Which, and who decides?",
        question="An agent can run shell commands. What stops it running the wrong one?",
        minutes=25,
        requires=["l04-tools"],
        concepts=["permission", "trust", "security-boundary"],
        hook="""\
You `cd` into a repository you cloned five minutes ago and start your agent.

Before you type anything, it has already read that repository's `AGENTS.md`
and loaded its instructions into the system prompt. If the repo ships a `.tau/`
directory, it may have loaded skills and extensions from it too - and an
extension is Python that runs in your process.

Nothing has been exploited here. This is the designed behaviour, and it is why
every serious agent has a decision point before that loading happens.

{{diagram:permission-gate}}
""",
        steps=[
            Step(
                id="what-needs-asking",
                kind="predict",
                title="Which of these needs a decision?",
                body="""\
Your agent is about to do several things. Some are routine; some should stop
and ask.

Think about the difference between *reversible* and *irreversible*, and
between *you asked for it* and *something else asked for it*.
""",
                question="Which should require an explicit decision before proceeding?",
                multi=True,
                choices=[
                    Choice(
                        id="project-files",
                        label="Loading instructions and extensions from a repository you just cloned.",
                        note="Yes. This is the subtle one: it happens before you type anything, and the repository is untrusted input. Tau calls this project trust.",
                    ),
                    Choice(
                        id="shell",
                        label="Running a shell command the model composed.",
                        note="Yes - this is the obvious one. Though note the interesting cases are not `rm -rf`; they are commands that look routine and are not.",
                    ),
                    Choice(
                        id="read",
                        label="Reading a file inside the working directory.",
                        note="Generally no. It is reversible, scoped, and asking every time would make the agent unusable - which is itself a security problem, because people disable prompts they cannot act on.",
                    ),
                    Choice(
                        id="write-outside",
                        label="Writing a file outside the working directory.",
                        note="Yes. You built this check in Level 4. The path escape is the mechanism; the decision point is the policy.",
                    ),
                ],
                answer=["project-files", "shell", "write-outside"],
                hints=[
                    "One of these happens before the learner types anything at all.",
                    "One of them is routine enough that asking would train people to click through - which is worse than not asking.",
                ],
                after="""\
The one people miss is the first: **the repository is input.** Starting an
agent inside it already hands it instructions.

Tau's design note on this is unusually careful. From
`tau/dev-notes/design/project-trust.md`:

> A repository can currently influence Tau merely because Tau starts in that
> repository. Project trust will put a decision in front of that implicit
> input loading. It is not a judgment that every file in the repository is
> safe.

That last sentence matters. Trust here means "I accept this repo's
configuration", not "this code is safe" - a distinction most permission
dialogs blur.
""",
                xp=25,
            ),
            Step(
                id="build-gate",
                kind="implement",
                title="Build the decision point",
                body="""\
In the editor below, write a gate the loop consults before each tool
runs.

Three pieces:

- `classify(tool_name, arguments, cwd)` - returns `"allow"`, `"ask"`, or
  `"deny"`.
- `PermissionGate` - remembers decisions so the same question is not asked
  twice, and supports "always allow this tool".
- `before_tool_call(call)` - the hook signature the loop already supports,
  returning `(blocked, reason)`.

The policy the tests expect:

| case | verdict |
|---|---|
| `read` inside cwd | allow |
| `write` inside cwd | allow |
| `write` escaping cwd | **deny** - not "ask" |
| `bash` | ask |
| unknown tool | ask |

**Why deny rather than ask for the path escape.** A prompt is only a safety
feature if the person can evaluate it. "Write to `../../../.ssh/authorized_keys`?"
arrives in the middle of a refactor, with no context, and the honest answer is
that nobody knows. A rule that cannot be evaluated should be a rule, not a
question.

Eight tests.
""",
                target_file="permission.py",
                test_file="tests/test_l14_permission.py",
                specimen_paths=["tau/src/tau_coding/project_trust.py"],
                starter='''\
"""A permission gate for tool calls.

The loop already supports this: `run_agent_loop(before_tool_call=...)` is
consulted before each tool runs and can block it. That hook is the whole
integration point - the policy lives here, not in the loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ALLOW = "allow"
ASK = "ask"
DENY = "deny"

# Tools that only read, scoped to the working directory.
READ_ONLY = {"read", "list", "grep"}
# Tools that can affect anything outside this process.
DANGEROUS = {"bash", "shell", "exec"}


def escapes_cwd(path_value, cwd) -> bool:
    """Return whether a path argument would leave the working directory."""
    # TODO: resolve against cwd, then compare. Do not pattern-match on ".."
    #       - symlinks and absolute paths defeat that.
    raise NotImplementedError


def classify(tool_name: str, arguments: dict, cwd) -> str:
    """Return ALLOW, ASK or DENY for one tool call."""
    # TODO
    #   read-only tool            -> ALLOW
    #   write with a path escape  -> DENY  (a question nobody can answer)
    #   write inside cwd          -> ALLOW
    #   dangerous tool            -> ASK
    #   anything unrecognised     -> ASK   (default closed)
    raise NotImplementedError


@dataclass
class PermissionGate:
    """Applies the policy, and remembers what the user already decided."""

    cwd: Path
    # Tools the user chose to always allow this session.
    always_allow: set = field(default_factory=set)
    # Supplied by the frontend; returns True to permit one call.
    ask_fn: object = None
    asked: list = field(default_factory=list)

    async def before_tool_call(self, call):
        """Return (blocked, reason) - the loop's before_tool_call contract."""
        # TODO
        raise NotImplementedError
''',
                hints=[
                    "escapes_cwd: `(Path(cwd) / value).resolve().is_relative_to(Path(cwd).resolve())` - negate it. The resolve() is what defeats symlinks.",
                    "classify is a chain of early returns. Put the DENY case before the general write case, or an escaping write gets allowed.",
                    "In the gate: check `always_allow` first, then classify. ALLOW -> `(False, None)`; DENY -> `(True, reason)`; ASK -> call `ask_fn` and record it in `asked`.",
                    "`ask_fn` may be None - treat that as 'no frontend to ask', which means block. Default closed.",
                    "Return `(blocked, reason)` in that order; the loop yields the reason back to the model as an error result, so the model can try something else.",
                ],
                after="""\
Note where this sits. The gate is *not* in the loop - the loop just calls a
hook. That means permission policy can differ per frontend: a TUI asks, a CI
run denies everything interactive, a test allows all.

Tau places this boundary in the same place, which is why `before_tool_call`
exists in `tau_agent` while the policy lives in `tau_coding`.
""",
                xp=40,
            ),
        ],
        reveal="""\
Read `tau/dev-notes/design/project-trust.md`. It is a model of how to write
this kind of design note: it states the problem from first principles, records
what the reference implementation does **at a pinned commit**, audits current
behaviour, and only then fixes a design.

The detail worth stealing: Tau distinguishes what *triggers* a trust decision
from what trust *grants*. A bare `.tau/` directory triggers nothing. A
`.tau/extensions` directory does, because extensions are code. Asking about
things that cannot hurt you is how you train people to stop reading dialogs.
""",
        transfer="""\
**Transferable:** every agent that touches a filesystem has a permission
story, even if the story is "there isn't one". Ask three questions: what can
happen before the user types anything? which actions are irreversible? and can
the user actually evaluate the question being asked? The third is where most
permission UX fails.
""",
    )


# --------------------------------------------------------------------------


def _recovery() -> Level:
    return Level(
        id="l15-recovery",
        title="When the Provider Fails",
        teaser="Not every failure deserves a retry. Which do?",
        question="The request failed. Should you try again?",
        minutes=25,
        requires=["l05-harness"],
        concepts=["error-recovery", "retry", "failure-classification"],
        hook="""\
Your agent is forty tool calls into a refactor. The next request returns
HTTP 429.

Retrying is obviously right here. Now the one after returns HTTP 400,
`invalid_request_error`. Retrying that is obviously wrong - it will fail
identically, forever, while burning the user's time.

The harness cannot tell these apart by looking at the exception type. It has
to classify.

{{diagram:failure-taxonomy}}
""",
        steps=[
            Step(
                id="classify-failures",
                kind="predict",
                title="Which of these should be retried?",
                body="""\
Five real failures. For each, ask: would the identical request plausibly
succeed a moment later?
""",
                question="Select every failure worth retrying unchanged.",
                multi=True,
                choices=[
                    Choice(
                        id="429",
                        label="429 Too Many Requests",
                        note="Yes, with backoff. The request is fine; the timing is not. This is the case retries exist for.",
                    ),
                    Choice(
                        id="500",
                        label="500 Internal Server Error from the provider",
                        note="Yes. Transient server faults are common at scale and usually clear within seconds.",
                    ),
                    Choice(
                        id="400",
                        label="400 Bad Request: malformed tool_result block",
                        note="No. The request is wrong and will stay wrong. This one needs *repair* - which is exactly Level 7's tool-history fix - not a retry.",
                    ),
                    Choice(
                        id="401",
                        label="401 Unauthorized",
                        note="No. The key will not become valid by waiting. Retrying here just delays telling the user the one thing they need to know.",
                    ),
                    Choice(
                        id="overflow",
                        label="400: prompt is too long, 213k tokens > 200k maximum",
                        note="Not unchanged - but this is the interesting case. It is deterministic, yet recoverable: compact the context and retry once. Tau does exactly this.",
                    ),
                ],
                answer=["429", "500"],
                hints=[
                    "Ask of each: is the request itself wrong, or was the moment wrong?",
                    "Two of the 'no' answers still have a sensible recovery - it just is not 'send the same thing again'.",
                ],
                after="""\
Three categories, not two:

- **Transient** - retry with backoff. 429, 500, connection resets.
- **Terminal** - stop and tell the user. 401, malformed requests.
- **Recoverable-but-not-by-retrying** - change something, then try again.
  Context overflow is the headline case: compact, then retry once.

That third category is what separates a harness that survives long sessions
from one that dies at the two-hour mark. Tau's compaction has an
overflow-recovery path for precisely this, because token estimation is
approximate and will sometimes be wrong.
""",
                xp=25,
            ),
            Step(
                id="build-retry",
                kind="implement",
                title="Classify and back off",
                body="""\
In the editor below, write:

- `classify_error(status, message)` - returns `"transient"`, `"terminal"`, or
  `"overflow"`.
- `retry_delay(attempt, max_delay)` - exponential backoff, capped.
- `with_retry(fn, max_retries, on_retry)` - calls `fn`, retrying transient
  failures only.

**Two things the tests check that are easy to miss.**

Backoff must be *capped*. Unbounded exponential backoff eventually means a
user waiting four minutes for a request they would rather have seen fail.

And `with_retry` must re-raise terminal errors *immediately*, not after
exhausting the attempt budget. A 401 that takes thirty seconds to report is a
worse user experience than one that fails instantly.

Nine tests.
""",
                target_file="recovery.py",
                test_file="tests/test_l15_recovery.py",
                specimen_paths=["tau/src/tau_ai/retry.py"],
                starter='''\
"""Classify provider failures, and retry only the ones worth retrying.

The classification is the whole value here. Retrying is trivial; knowing what
*not* to retry is what keeps a harness responsive when something is actually
broken.
"""

from __future__ import annotations

import asyncio

TRANSIENT = "transient"
TERMINAL = "terminal"
OVERFLOW = "overflow"

BASE_DELAY_SECONDS = 0.25

# Status codes where the request is fine and the moment is not.
TRANSIENT_STATUS = {408, 409, 429, 500, 502, 503, 504}


class ProviderError(Exception):
    """A failed provider request, carrying its HTTP status."""

    def __init__(self, status: int, message: str = ""):
        super().__init__(message or f"HTTP {status}")
        self.status = status
        self.message = message


def classify_error(status: int, message: str = "") -> str:
    """Return TRANSIENT, TERMINAL or OVERFLOW."""
    # TODO
    #   context-length messages -> OVERFLOW, even though they arrive as 400
    #   TRANSIENT_STATUS        -> TRANSIENT
    #   anything else           -> TERMINAL
    #
    # Hint: look for "too long", "context length" or "maximum context" in the
    # message. Providers word this differently, which is itself the lesson -
    # classification is heuristic, so it must fail safe.
    raise NotImplementedError


def retry_delay(attempt: int, max_delay: float = 8.0) -> float:
    """Exponential backoff for `attempt` (0-based), capped at max_delay."""
    # TODO
    raise NotImplementedError


async def with_retry(fn, *, max_retries: int = 2, max_delay: float = 8.0, on_retry=None):
    """Call `fn()`, retrying only transient failures.

    `on_retry(attempt, delay, reason)` is called before each wait, so a
    frontend can tell the user what is happening instead of appearing frozen.
    """
    # TODO
    raise NotImplementedError
''',
                hints=[
                    "classify_error: check the overflow phrases first, because they arrive as 400 and would otherwise be classified terminal.",
                    "retry_delay: `min(max_delay, BASE_DELAY_SECONDS * (2 ** attempt))`. The cap is what the tests check.",
                    "with_retry: loop `for attempt in range(max_retries + 1)`, try `await fn()`, and on ProviderError classify it.",
                    "Terminal and overflow must `raise` immediately - only TRANSIENT continues the loop. Overflow is recoverable, but not by this function; the caller compacts and retries.",
                    "Call `on_retry(attempt, delay, reason)` before `await asyncio.sleep(delay)`, so a UI can show a countdown rather than appearing hung.",
                ],
                after="""\
Compare with `tau/src/tau_ai/retry.py`. One detail worth copying: Tau emits a
`ProviderRetryEvent` through the same event stream as everything else, with a
human-readable message.

That is the Act I lesson applied again. A retry is progress, so it is an
event, so every frontend can render it without knowing anything about HTTP.
""",
                xp=40,
            ),
        ],
        reveal="""\
Tau's recovery story has three layers, and they are worth separating:

1. **Transport retries** in `tau_ai` - backoff on transient HTTP failures.
2. **Transcript repair** in `tau_agent` - the Level 7 pairing fix, which turns
   a class of 400s into something that cannot happen.
3. **Overflow compaction** in `tau_coding` - compact and retry once when the
   context was too long.

Each lives at a different layer, because each knows something the others do
not. The transport layer knows about HTTP; the agent layer knows about
transcript shape; the application layer knows about compaction. Pushing all
three into one place is how error handling turns into a thicket.
""",
        transfer="""\
**Transferable:** any agent talking to a remote model needs a failure
taxonomy. The question to ask of a new codebase is not "does it retry" but
"how does it decide". If every exception is retried the same way, long
sessions will hang on unrecoverable errors; if nothing is retried, they will
die on a transient 429.
""",
    )


# --------------------------------------------------------------------------


def _extensions() -> Level:
    return Level(
        id="l16-extensions",
        title="Changing the Agent Without Changing the Agent",
        teaser="Skills, extensions, and the cost of an extension point.",
        question="How do you let people extend an agent without forking it?",
        minutes=25,
        requires=["l13-system-prompt"],
        concepts=["extensibility", "skills", "plugin-boundary"],
        hook="""\
Two users want the same agent to behave differently. One works on a Django
project and wants it to know the team's migration conventions. The other wants
a tool that files a ticket.

Neither should have to fork the agent. So you add an extension point - and now
you own a new problem: **every extension point is a contract you cannot break
later**, and a surface untrusted code can enter through.

{{diagram:extension-points}}
""",
        steps=[
            Step(
                id="which-mechanism",
                kind="predict",
                title="Knowledge or code?",
                body="""\
Those two users need different mechanisms, and conflating them is a common
design mistake.

One needs the model to *know something*. The other needs the agent to *be able
to do something*.
""",
                question="What is the right mechanism for the Django conventions?",
                choices=[
                    Choice(
                        id="skill",
                        label="A skill: markdown loaded into the prompt, only when relevant.",
                        note="Correct. It is knowledge, not capability. It needs no code, cannot crash the agent, and is safe to load from a repository - which matters given Level 14.",
                    ),
                    Choice(
                        id="extension",
                        label="An extension: Python that runs in the agent's process.",
                        note="Overkill, and it converts a text file into an execution surface. Reserve this for things that genuinely need to run code.",
                    ),
                    Choice(
                        id="tool",
                        label="A new tool the model can call.",
                        note="A tool is for *doing*, not knowing. The model would have to decide to call it before it knew the conventions existed - which is backwards.",
                    ),
                    Choice(
                        id="prompt",
                        label="Paste it into the system prompt permanently.",
                        note="Works, and costs those tokens in every session forever, including ones with nothing to do with Django. This is what 'loaded only when relevant' is for.",
                    ),
                ],
                answer="skill",
                hints=[
                    "One of these requirements is knowledge and the other is capability. Which is which?",
                    "Consider the cost of being wrong: what is the worst a bad markdown file can do, versus a bad Python file?",
                ],
                after="""\
**Knowledge and capability are different extension points**, and the
difference is mostly about blast radius.

A skill is markdown. The worst a bad one does is waste tokens or mislead the
model. An extension is code in your process - it can read your environment,
make network calls, and crash the agent. That is why Tau's project-trust
triggers include `.tau/extensions` but treat skills more carefully too.

Tau also loads skills *conditionally*: discovered up front, injected when
relevant. Otherwise every skill a user ever installed would be in the context
of every session.
""",
                xp=25,
            ),
            Step(
                id="build-registry",
                kind="implement",
                title="A skill registry and an extension point",
                body="""\
In the editor below, write:

- `Skill` - name, description, body, and `triggers` (keywords).
- `SkillRegistry.relevant_to(text)` - which skills apply to this prompt.
- `ExtensionHost` - lets an extension register tools and prompt sections, and
  **survives a broken extension**.

That last point is the one the tests lean on. An extension that raises on load
must not take the agent down with it - same reasoning as tools being an
isolation boundary in Level 4, applied one layer out. The host collects the
error, reports it as a diagnostic, and carries on with the extensions that did
load.

Nine tests.
""",
                target_file="extensions.py",
                test_file="tests/test_l16_extensions.py",
                specimen_paths=[
                    "tau/src/tau_coding/skills.py",
                    "tau/src/tau_coding/extensions/api.py",
                ],
                starter='''\
"""Skills (knowledge) and extensions (capability).

Two mechanisms, deliberately separate, because they carry very different
risk. A bad skill wastes tokens; a bad extension runs code in your process.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Skill:
    """Knowledge injected into the prompt when it is relevant."""

    name: str
    description: str
    body: str
    triggers: tuple = ()     # keywords that make this skill relevant


@dataclass
class SkillRegistry:
    skills: list = field(default_factory=list)

    def add(self, skill: Skill) -> None:
        # TODO
        raise NotImplementedError

    def relevant_to(self, text: str):
        """Return skills whose triggers appear in `text`, case-insensitively.

        A skill with no triggers is always relevant - that is how a user says
        "this one is general".
        """
        # TODO
        raise NotImplementedError

    def prompt_sections(self, text: str):
        """Return [(label, body), ...] for the relevant skills only."""
        # TODO
        raise NotImplementedError


@dataclass
class Diagnostic:
    """A non-fatal problem, surfaced rather than swallowed."""

    source: str
    message: str


@dataclass
class ExtensionHost:
    """Loads extensions and collects what they contribute.

    A failing extension is expected, not exceptional: it is third-party code.
    """

    tools: list = field(default_factory=list)
    sections: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)

    def register_tool(self, tool) -> None:
        # TODO
        raise NotImplementedError

    def register_prompt_section(self, label: str, body: str) -> None:
        # TODO
        raise NotImplementedError

    def load(self, name: str, setup_fn) -> bool:
        """Run one extension's setup, returning whether it succeeded.

        `setup_fn(host)` is third-party code. If it raises, record a
        diagnostic naming the extension and keep going.
        """
        # TODO
        raise NotImplementedError
''',
                hints=[
                    "relevant_to: lowercase the text once, then `any(t.lower() in lowered for t in skill.triggers)`. Remember the no-triggers case returns True.",
                    "prompt_sections: `[(s.name, s.body) for s in self.relevant_to(text)]`.",
                    "load: wrap `setup_fn(self)` in try/except Exception, append a Diagnostic on failure, and return False. Return True on success.",
                    "Catch broad `Exception` here deliberately - an extension is untrusted code at the edge of your system, exactly like a tool.",
                    "A partially-loaded extension may have registered some tools before failing. The tests accept that; cleaning up would need a transaction, which is more machinery than this earns.",
                ],
                after="""\
You have both extension points, with the failure boundary in the right place.

Look at what the host does *not* do: it does not sandbox. An extension that
wants to read your environment can. That is a deliberate position - Tau's
answer is project trust (Level 14), a decision point before loading, rather
than a sandbox after it.

Sandboxing Python properly is close to impossible, so the honest design is to
make the trust decision explicit instead of pretending the code is contained.
""",
                xp=40,
            ),
        ],
        reveal="""\
Tau's extension API (`tau/src/tau_coding/extensions/api.py`) is larger than
what you built, and worth skimming for the *shape* rather than the detail.

Extensions can subscribe to agent events, add tools, add prompt sections, add
sidebar widgets, provide model providers, and participate in the trust
decision. Each of those is a commitment: once an extension depends on an event
name, that name is API.

That is the real cost of extensibility, and it is not the code. It is that
your internal structure becomes a public contract. Note which of Tau's events
are exposed to extensions - `AGENT_EVENT_TYPES` is a deliberately curated
list, not "everything we happen to emit".
""",
        transfer="""\
**Transferable:** when evaluating an agent's extensibility, separate the
knowledge path from the capability path, and ask what a malicious extension
could do. Then ask the harder question: which internals became public API the
moment that extension point shipped? That is what the project can no longer
change.
""",
    )
