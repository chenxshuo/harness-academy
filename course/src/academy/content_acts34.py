"""Act III and IV: the application layer, and transfer beyond this repository.

Act III is where "an agent loop" becomes "a coding agent you can ship". Act IV
exists because the GOAL's success criterion is explicitly about *other*
codebases - so the final levels deliberately leave the specimen behind.
"""

from __future__ import annotations

from academy.curriculum import Act, Choice, Level, Step

# --------------------------------------------------------------------------
# Act III - From engine to product
# --------------------------------------------------------------------------


def act_three() -> Act:
    return Act(
        id="act3",
        title="Act III - The Application",
        subtitle="A loop is not a product. This is everything between them.",
        levels=[_l09(), _l10(), _l11()],
    )


def _l09() -> Level:
    return Level(
        id="l09-persistence",
        title="The Vanishing Write",
        teaser="A real data-loss bug. Find it before reading the answer.",
        question="Who is responsible for writing a message to disk, and when?",
        minutes=30,
        requires=["l05-harness"],
        concepts=["persistence", "events", "subscriber-vs-consumer"],
        hook="""\
This level reconstructs a real bug from the specimen's history. It is subtle,
it is the kind that survives code review, and the fix changes an architectural
assumption rather than a line.

Here is the setup. Sessions are saved by iterating the event stream:

```python
async for event in harness.prompt(text):
    if isinstance(event, MessageEndEvent):
        await storage.append(event.message)
    render(event)
```

Clean, obvious, and it works in every test. Then a user presses Esc during a
tool call, and their session file ends up invalid.
""",
        steps=[
            Step(
                id="find-bug",
                kind="predict",
                title="Where does the write go?",
                body="""\
Full sequence:

1. The agent calls a tool. It is slow.
2. The user presses Esc. The TUI cancels the task consuming `harness.prompt()`.
3. The harness's `finally` block appends a synthetic
   `ToolResultMessage("Tool call interrupted by user")` - correctly, so the
   transcript stays valid in memory.
4. The session file ends with `assistant(tool_use)` followed by a user message.
   **The interrupted tool result was never written.**

{{diagram:memory-vs-disk}}

Memory is correct. Disk is corrupt. Why?
""",
                question="Why was the synthetic tool result never persisted?",
                choices=[
                    Choice(
                        id="consumer-gone",
                        label="Persistence ran inside the `async for`, and cancellation destroyed that loop before the event arrived.",
                        note="Exactly. The writer was a *consumer* of the stream. Cancelling the consumer cancels the writes. The harness emitted the event into a loop that no longer existed.",
                    ),
                    Choice(
                        id="finally-order",
                        label="The `finally` block ran after the storage handle was closed.",
                        note="Plausible, and worth ruling out by reading the code - but the handle is per-write here. The problem is earlier: nothing even attempted the write.",
                    ),
                    Choice(
                        id="async-race",
                        label="A race between the write and process exit.",
                        note="This would be intermittent. The bug is deterministic, which is a strong clue that it is structural rather than timing.",
                    ),
                    Choice(
                        id="not-emitted",
                        label="The harness never emitted an event for the synthetic message.",
                        note="Close, and this is the right question to ask. But the harness does emit it - the issue is that emission reaches listeners, not an abandoned consumer loop.",
                    ),
                ],
                answer="consumer-gone",
                hints=[
                    "Trace the cancellation. Which code is still running after the task consuming `prompt()` is cancelled?",
                    "The harness's `finally` runs. The `async for` body does not. What does that imply about where writes must live?",
                ],
                after="""\
The write was a **consumer** of the event stream. Consumers can be cancelled.

The fix is to make persistence a **subscriber** instead:

```python
harness.subscribe(persist_listener)        # fires via _notify
async for event in harness.prompt(text):   # only renders now
    render(event)
```

Now look back at a hint from Level 5: *notify listeners before yielding*. That
ordering is this bug. `_notify(event)` runs inside the harness, on the
harness's own call stack, before the event is handed to anyone outside. Cancel
the outside and the notification still happened.

One line of ordering; the difference between durable and lossy.
""",
                xp=30,
            ),
            Step(
                id="append-only",
                kind="implement",
                title="Step A - append-only JSONL storage",
                body="""\
Three small steps build the session store. This is the first: just write and
read.

In the editor below, implement:

- `append(entry)` - write one JSON line, fsync, **return the entry**
- `read_all()` - parse every line back into `Entry` objects

No tree, no replay - those are steps B and C.

**Why JSONL rather than one big JSON array**

A JSON array must be re-read, parsed, modified and rewritten for every append.
JSONL appends with a single `write()` to the end of the file. It is also
readable by hand and survives a truncated final line.

**Why fsync**

`write()` only hands bytes to the OS. If the machine loses power before the
kernel flushes, the write is gone. `os.fsync(file.fileno())` forces it to
disk. Sessions are the one thing a user cannot regenerate.

Five tests.
""",
                target_file="session_store.py",
                test_file="tests/test_l09a_storage.py",
                specimen_paths=["tau/src/tau_agent/session/storage.py"],
                starter='''\
"""Append-only, branchable session storage.

Two ideas carry this file:

  1. Append-only  - entries are never modified or deleted.
  2. Tree-shaped  - each entry names its parent, so history can branch.

Together they give resume, branching, compaction-without-loss, and an audit
trail, from one data structure.

You will edit this file three times - steps A, B and C of Level 9.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from harnesskit.messages import (
    AgentMessage,
    AssistantMessage,
    ToolResultMessage,
    UserMessage,
)


def new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class Entry:
    """One append-only session record."""

    type: str                      # "message" | "compaction" | "session_info"
    id: str = field(default_factory=new_id)
    parent_id: str | None = None
    timestamp: float = 0.0
    # type == "message"
    role: str = ""                 # "user" | "assistant" | "tool"
    text: str = ""
    tool_call_id: str = ""
    tool_name: str = ""
    # type == "compaction"
    summary: str = ""
    first_kept_entry_id: str | None = None


class SessionStore:
    """JSONL-backed append-only storage."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    # ---------------------------------------------------------- step A

    def append(self, entry: Entry) -> Entry:
        """Append one entry durably, and return it."""
        # TODO
        #   self.path.parent.mkdir(parents=True, exist_ok=True)
        #   with self.path.open("a", encoding="utf-8") as f:
        #       f.write(json.dumps(asdict(entry)) + "\\n")
        #       f.flush()
        #       os.fsync(f.fileno())
        #   return entry
        raise NotImplementedError

    def read_all(self) -> list[Entry]:
        """Read every entry in file order. Missing file -> []."""
        # TODO: skip blank lines; Entry(**json.loads(line))
        raise NotImplementedError

    # ---------------------------------------------------------- step B

    def path_to(self, entry_id: str) -> list[Entry]:
        """Return the root-to-entry path by following parent_id."""
        raise NotImplementedError

    # ---------------------------------------------------------- step C

    def replay(self, entries: list[Entry]) -> list[AgentMessage]:
        """Fold a path of entries into the active message list."""
        raise NotImplementedError
''',
                hints=[
                    "append: `self.path.parent.mkdir(parents=True, exist_ok=True)` first, then open in 'a' mode.",
                    "`json.dumps(asdict(entry))` turns the dataclass into a line. Remember the trailing newline.",
                    "After writing: `f.flush()` then `os.fsync(f.fileno())`. Both, in that order.",
                    "read_all: `if not self.path.exists(): return []`, then skip blank lines and build `Entry(**json.loads(line))`.",
                ],
                after="""\
You have durable storage. Nothing clever yet - but note what you already get
for free: the file is readable with `cat`, a crash can only ever lose the last
line, and nothing you wrote earlier can be corrupted by a later write.
""",
                xp=25,
            ),
            Step(
                id="tree",
                kind="implement",
                title="Step B - make history a tree",
                body="""\
Right now entries are a flat list. Add one method and they become a tree:

- `path_to(entry_id)` - follow `parent_id` up to the root, return the path in
  root-to-entry order

{{diagram:session-tree}}

**Why a tree and not a list**

Because the user will eventually say *"go back and try that differently"*.

With a list, that means deleting the tail - destroying work that might have
been right. With parent pointers, a branch is just a new entry whose parent is
an older node. Both histories stay on disk and both stay replayable.

Note that **branching needs no code**. You are only writing
`path_to`. Two entries sharing a `parent_id` already produce two different
paths. One of the tests checks exactly that.

Four tests.
""",
                target_file="session_store.py",
                test_file="tests/test_l09b_tree.py",
                specimen_paths=["tau/src/tau_agent/session/tree.py"],
                hints=[
                    "Build a lookup first: `by_id = {e.id: e for e in self.read_all()}`.",
                    "Then walk: start at `by_id.get(entry_id)`, append it, move to its parent, repeat while the current entry is not None.",
                    "You collected the path leaf-to-root, so `return list(reversed(chain))`.",
                    "Guard against a missing id: `by_id.get(cur.parent_id) if cur.parent_id else None` ends the walk cleanly at the root.",
                ],
                after="""\
Branching, for free.

This is a good moment to notice a general principle: choosing the right data
structure can make a feature disappear instead of requiring code. A list would
have needed explicit branch management, copy-on-write, and a story for what
happens to the discarded tail. Parent pointers need none of it.
""",
                xp=25,
            ),
            Step(
                id="replay",
                kind="implement",
                title="Step C - replay a path into messages",
                body="""\
Entries are storage. The harness needs `AgentMessage` objects. `replay`
converts one into the other - and this is where compaction earns its keep.

- `replay(entries)` - fold a path into a message list

Two rules:

1. A `"message"` entry becomes a `UserMessage`, `AssistantMessage` or
   `ToolResultMessage` depending on `role`.
2. A `"compaction"` entry **replaces everything before
   `first_kept_entry_id`** with a single summary message.

**Why this happens at replay time**

Rule 2 happens at *replay time*. The compaction entry is appended; nothing is
deleted. The file still contains every message. What changed is how a replay
turns out.

That means compaction is reversible, auditable, and safe to get wrong. It is
the same reasoning as a database write-ahead log or a git object store:
nothing is mutated, new facts are appended, and current state is a fold over
them.

Four tests, and the last one checks that nothing was deleted.
""",
                target_file="session_store.py",
                test_file="tests/test_l09c_replay.py",
                specimen_paths=["tau/src/tau_agent/session/memory.py"],
                hints=[
                    "Keep `(entry_id, message)` pairs as you build, not bare messages - the compaction rule needs to know which entry each message came from.",
                    "role 'user' -> UserMessage(content=e.text); 'assistant' -> AssistantMessage(content=e.text, stop_reason='stop'); 'tool' -> ToolResultMessage(tool_call_id=e.tool_call_id, tool_name=e.tool_name, content=e.text).",
                    "On a compaction entry: find the index of `first_kept_entry_id` within `entries`, then keep only the rows whose entry id appears at or after that index.",
                    "Prefix the kept rows with one UserMessage carrying the summary text.",
                    "At the end return just the messages: `[m for _id, m in rows]`.",
                ],
                after="""\
You built resume, branching, and compaction-without-loss from one idea.

Worth noticing what you did *not* need: no migrations, no rewrite-in-place, no
locking around mutation. Append-only data structures trade disk space for an
enormous reduction in the number of states your code can be in.

Tau's version adds cross-process file locking (`fcntl.flock`), atomic
replacement via temp-file-plus-rename, and directory fsync. Read
`tau/src/tau_agent/session/storage.py` - the comments explain which failure
each defends against. Two `tau` processes in one project is not exotic.
""",
                xp=30,
            ),
        ],
        reveal="""\
The authoritative account is `tau/dev-notes/push-based-persistence.md`. It is
worth reading in full, but the key passage:

> With pull-side persistence, everything after the last consumed event was
> silently dropped... The fault stayed hidden - the in-memory repair protected
> the live session and the `load()` repair protected restarts - until a replay
> that skipped repair (`/tree`) sent the transcript to a provider, which
> rejected it with a 400.

Notice the failure chain. Two layers of repair *masked* the bug for a long
time. It only surfaced through a path that bypassed both.

That is a general hazard of defense in depth: redundant safety can hide the
defect it is compensating for. Worth remembering when you add a repair layer -
make sure something still reports that it fired.
""",
        transfer="""\
**Transferable:** in any event-driven system, ask whether a given handler is a
*subscriber* or a *consumer*. Subscribers run on the producer's stack and
survive consumer teardown; consumers die with their loop. Anything durable -
persistence, audit logs, metrics - belongs on the subscriber side. This
distinction causes real data loss in systems well beyond agents.
""",
    )


def _l10() -> Level:
    return Level(
        id="l10-provenance",
        title="Who Decides What?",
        teaser="Follow a design decision back to the moment it was forced.",
        question="Where is the line between the reusable brain and the application?",
        minutes=25,
        requires=["l09-persistence"],
        concepts=["layering", "boundaries", "design-rationale"],
        hook="""\
The specimen states a rule it refuses to break:

> `tau_agent` must not import CLI, Rich, Textual, or resource-loading code.

Easy to say. The interesting question is what it costs - because several
features *want* to cross that line, and watching how they are kept out teaches
more than the rule itself.
""",
        steps=[
            Step(
                id="place-features",
                kind="predict",
                title="Which layer owns it?",
                body="""\
Tau's layers:

{{diagram:layers}}

For each feature below, decide where it belongs. Some are genuinely arguable -
the reasoning matters more than the answer.
""",
                question="Which of these belong in `tau_agent` (the portable brain)?",
                multi=True,
                choices=[
                    Choice(
                        id="retry",
                        label="Retrying a request after an HTTP 429.",
                        note="Belongs in `tau_ai`. It is a property of talking to a specific HTTP API, and the brain should not know that providers are even reachable over HTTP.",
                    ),
                    Choice(
                        id="pairing",
                        label="Ensuring every tool call has a matching result.",
                        note="Belongs in `tau_agent`. It is an invariant of the transcript itself, true regardless of provider, UI, or storage.",
                    ),
                    Choice(
                        id="agents-md",
                        label="Reading AGENTS.md from the project directory.",
                        note="Belongs in `tau_coding`. It assumes a filesystem, a project layout, and a convention - all application policy.",
                    ),
                    Choice(
                        id="queue",
                        label="Queuing a steering message during an active run.",
                        note="Belongs in `tau_agent`. It is transcript-and-run semantics. *Which keystroke triggers it* is the UI's business; *when it becomes visible to the model* is the brain's.",
                    ),
                    Choice(
                        id="naming",
                        label="Auto-generating a session title from the first message.",
                        note="Belongs in `tau_coding` - and Tau says so explicitly in its design principles, calling it 'application workflow rather than agent-loop behavior'. A nice example of resisting a convenient but boundary-violating placement.",
                    ),
                ],
                answer=["pairing", "queue"],
                hints=[
                    "Ask of each: would a completely different frontend - a web app, a CI bot - still need this exact behavior?",
                    "If a feature assumes a filesystem, a terminal, or a config directory, it is application policy.",
                ],
                after="""\
The test that resolves most cases: **would a different frontend need this
identical behavior?**

- Tool pairing: yes, always - providers demand it regardless of UI.
- Steering semantics: yes - any frontend allowing mid-run input needs the same
  turn-boundary rule.
- Reading AGENTS.md: no - a web frontend may have no filesystem at all.
- Retry on 429: no, and it is lower still - only the HTTP layer should know.

Session naming is the instructive one. It is tempting to put in the harness,
it would work there, and Tau deliberately keeps it out, documenting the
reasoning. Boundaries hold because people defend them in the specific cases
where crossing would be convenient.
""",
                xp=25,
            ),
            Step(
                id="trace-decision",
                kind="predict",
                title="Archaeology",
                multi=True,
                body="""\
Every odd-looking decision in a mature codebase was forced by something. Three
forces account for almost all of them:

1. **A provider rejected something.** External, non-negotiable.
2. **Data already on disk.** You cannot retroactively fix what users have.
3. **A user interaction the simple design could not express.** Cancel
   mid-tool, type-while-running, branch from an earlier point.

Below are four real decisions from the specimen. Work out which force produced
each one, then answer the question: it asks only about the ones caused by
**force 2, data already on disk**.

- `AssistantMessage` keeps both `stop_reason` and `error_message`.
- `CompactionEntry` has both `replaces_entry_ids` and `first_kept_entry_id`.
  (See `dev-notes/first-kept-compaction.md`.)
- Tool-call ids are rewritten to `tc_<hash>` at the provider boundary, and the
  persisted JSONL is deliberately *not* rewritten.
  (See `dev-notes/portable-tool-call-ids.md`.)
- `ModelChangeEntry.provider` defaults to `None`.

The notes are in `tau/dev-notes/` (71 of them) and `tau/dev-notes/adr/`. The
tutor can read them with you and run `git -C tau log` to date the problem.
""",
                question=(
                    "Which of these exist because of sessions already written "
                    "to users' disks by an older version? Select all that apply."
                ),
                choices=[
                    Choice(
                        id="first-kept",
                        label="`CompactionEntry` carrying both `replaces_entry_ids` and `first_kept_entry_id`.",
                        note=(
                            "Correct, and the source says so outright: "
                            "`replaces_entry_ids` is the legacy shape, kept so "
                            "sessions already written still replay. New records "
                            "omit it and store one boundary id instead, which "
                            "is also why it got replaced - the old field grew "
                            "by one id for every summarized entry. Two fields "
                            "meaning nearly the same thing is almost always "
                            "this: a format that had to grow without breaking "
                            "what was on disk."
                        ),
                    ),
                    Choice(
                        id="tool-ids",
                        label="Rewriting tool-call ids at the boundary while leaving the JSONL untouched.",
                        note=(
                            "Correct, and note it is forces 1 and 2 together. "
                            "Anthropic rejects Codex-shaped ids, which is force "
                            "1 and is what makes the conversion necessary. "
                            "Doing it in memory rather than rewriting the file "
                            "is force 2: old sessions stay intact and are "
                            "repaired on the way out."
                        ),
                    ),
                    Choice(
                        id="provider-none",
                        label="`ModelChangeEntry.provider` defaulting to `None`.",
                        note=(
                            "Correct. An optional field with a null default, in "
                            "a persisted record, nearly always means the field "
                            "did not exist when some rows were written. The "
                            "default is what those rows deserialize to."
                        ),
                    ),
                    Choice(
                        id="stop-reason",
                        label="`AssistantMessage` keeping both `stop_reason` and `error_message`.",
                        note=(
                            "This one is force 3, not force 2. `stop_reason` is "
                            "an enum - `stop`, `length`, `toolUse`, `error`, "
                            "`aborted` - so it says which *category* of ending "
                            "happened. `error_message` carries the detail no "
                            "enum can hold. They are a category and its "
                            "explanation, not a duplicate: `length` is a "
                            "success that got truncated, `aborted` is a user "
                            "cancelling, and only `error` has text to show."
                        ),
                    ),
                ],
                answer=["first-kept", "tool-ids", "provider-none"],
                specimen_paths=["tau/dev-notes/", "tau/dev-notes/adr/"],
                hints=[
                    "`grep -rl \"<keyword>\" tau/dev-notes/` finds the relevant note fastest.",
                    "Ask of each field: could a file written by last month's version still be read if this were removed? If not, it is force 2.",
                    "Three of the four are backward-compatibility scars. The odd one out is about telling two different outcomes apart, not about old data.",
                ],
                after="""\
Three of the four are the same scar: **a format that had to grow without
invalidating what was already on disk.** Once you can see that pattern, a
whole category of apparent redundancy stops being mysterious. Optional field
with a null default, two fields that nearly duplicate each other, a conversion
applied on read rather than in place - these are usually the shape of a
migration that could not happen.

`stop_reason` and `error_message` are the contrast, and worth holding onto:
they look redundant but are a category and its explanation. `stop_reason` is
an enum of how a turn ended; `error_message` is the detail an enum cannot
carry. A turn that stopped at a length limit is a success with nothing to
explain.

Learning to read code for *which force produced it* is the difference between
knowing a codebase and understanding it. It is also what lets you evaluate an
unfamiliar project quickly: code shaped by force 1 is usually solid; code with
no visible force behind it is often speculative.
""",
                xp=30,
            ),
        ],
        reveal="""\
`tau/dev-notes/` is unusual and worth appreciating as an artifact: 73 notes
recording not just what was built but what went wrong first. The project states
the policy in AGENTS.md:

> Each substantial phase should leave behind beginner-friendly notes under
> `dev-notes/`, explaining what was added, why it exists, how it maps to Pi's
> design, and how to test or use it.

When you next evaluate an unfamiliar agent framework, look for this. A repo
with design notes, ADRs, or detailed PR descriptions can be understood. A repo
with only code requires you to rediscover every force yourself.
""",
        transfer="""\
**Transferable:** layer boundaries are only real if something enforces them and
someone defends them in inconvenient cases. When assessing a new codebase, find
the stated boundary, then look for the feature that most wants to violate it -
how that case was handled tells you whether the architecture is real or
aspirational.
""",
    )


def _l11() -> Level:
    return Level(
        id="l11-transfer",
        title="Same Idea, Different Code",
        teaser="Map one architecture onto another. Find what's universal.",
        question="Which parts of what you learned are fundamental, and which are Tau's choices?",
        minutes=25,
        requires=["l10-provenance"],
        concepts=["transfer", "comparison", "universals"],
        hook="""\
Everything so far came from one repository. The risk is obvious: you may have
learned Tau rather than coding agents.

This level separates the two, using a second harness you already have: the
tutor on this page. It is a real one - a loop, tools, an event stream, a
transcript - written in JavaScript, against a different provider API, for a
different purpose, by someone who was not porting Tau.

Where two harnesses built under different constraints agree, the agreement is
worth something. The exercise is to work out which agreements those are.
""",
        steps=[
            Step(
                id="map-abstractions",
                kind="predict",
                title="Map the abstractions",
                multi=True,
                body="""\
There is a second harness on this page. The tutor you have been using is one:
a loop, a tool registry, an event stream, a transcript it owns between
prompts, written in JavaScript in about two hundred lines. It was written
against a different language, a different provider API and a different UI from
Tau, by someone solving a different problem.

So it is a natural experiment. Where the two agree, the agreement is unlikely
to be taste.

Here is the tutor harness's loop, with its event names intact:

```js
yield { type: "agent_start" };
for (let turn = 0; turn < this.maxTurns; turn++) {
  yield { type: "turn_start", turn };
  // ... stream the provider, collect `assistant` ...
  this.messages.push(assistant);
  const calls = assistant.tool_calls || [];
  if (!calls.length) {                    // the stop condition
    yield { type: "turn_end", message: assistant };
    break;
  }
  for (const call of calls) {
    yield { type: "tool_execution_start", name: call.name };
    const content = await tool.execute(call.arguments || {});
    yield { type: "tool_execution_end", name: call.name, isError };
    this.messages.push({ role: "tool", tool_call_id: call.id, ... });
  }
  yield { type: "turn_end", message: assistant };
}
```

Compare it with `tau/src/tau_agent/loop.py` and `tau_agent/events.py`, which
you can open below. Then decide which agreements are real.
""",
                question=(
                    "Which of these does the tutor harness share with Tau "
                    "because the same force acts on both, rather than by "
                    "coincidence? Select all that apply."
                ),
                choices=[
                    Choice(
                        id="stop",
                        label="The stop condition is \"the assistant requested no tools\".",
                        note=(
                            "Yes. Neither could terminate any other way without "
                            "inventing a judgement about answer quality. This is "
                            "Level 1's answer appearing in a second codebase "
                            "that never looked at the first."
                        ),
                    ),
                    Choice(
                        id="pairing",
                        label="A tool result is appended immediately after the call that produced it.",
                        note=(
                            "Yes, and this one is not a choice at all: the "
                            "provider rejects any other arrangement. Both "
                            "codebases are obeying the same external contract, "
                            "which is why Level 7 treats it as an invariant "
                            "rather than a convention."
                        ),
                    ),
                    Choice(
                        id="events",
                        label="Progress is published as a typed event stream rather than returned at the end.",
                        note=(
                            "Yes. Both have a UI that must show something "
                            "before the run finishes, and that requirement "
                            "alone forces a generator over a return. The event "
                            "names differ; the shape does not."
                        ),
                    ),
                    Choice(
                        id="names",
                        label="The event names themselves: `turn_start`, `turn_end`, `message_update`.",
                        note=(
                            "This is the one to be careful with. The names are "
                            "strikingly similar, but names are the cheapest "
                            "thing to copy and carry no force - both authors "
                            "read the same ecosystem. The *existence* of "
                            "turn-level events is forced; what they are called "
                            "is not. Treating vocabulary as evidence of "
                            "convergence is the easiest mistake in this kind of "
                            "comparison."
                        ),
                    ),
                ],
                answer=["stop", "pairing", "events"],
                specimen_paths=["tau/src/tau_agent/loop.py", "tau/src/tau_agent/events.py"],
                hints=[
                    "Ask of each one: could a competent author have reasonably done it differently, and what would have broken? If nothing breaks, it is taste.",
                    "One of these four is cheap to copy and costs nothing to get wrong. That is the one that is not evidence.",
                    "The tutor can read both: ask it to open tau_agent/events.py and compare the event list with the code above.",
                ],
                after="""\
{{diagram:convergence}}

Three of those are forced, and the fourth is the trap. The loop stops the same
way because nothing else can work without judging answer quality. Tool results
are adjacent because providers reject anything else. Events exist because both
have a UI that cannot wait for the end of the run.

The names are a near-match too, but names are evidence of a shared ecosystem,
not of a shared force. Keeping that distinction is what makes this kind of
comparison worth anything.

Tau goes further than the tutor in one place worth noting, and where it does
so is itself informative. `tau_agent/events.py`, the portable core, ends a run
with `agent_end`. The application layer in `tau_coding/events.py` adds
`agent_settled`, meaning "truly finished, after any retry or
auto-compaction". The tutor harness has neither retry nor compaction, so it
needs no such distinction and does not have one.

That is the honest version of convergence: the same forces produce the same
structures, and where a system does not face a force, the structure is simply
absent. The extra event is not Tau being more thorough. It is Tau having a
problem the tutor does not have.
""",
                xp=35,
            ),
            Step(
                id="universals",
                kind="explain",
                title="What is actually universal?",
                body="""\
Write your own list, in two columns:

**Fundamental** - any competent coding agent must have this, or an equivalent.

**Implementation choice** - a reasonable alternative exists, and some system
probably makes it.

Candidates to classify: the loop stop condition; a typed event stream; durable
append-only history; tool-call/result pairing; context compaction; the
steering queue; separating portable core from application; a scripted provider
for tests; tree-structured sessions; `stop_reason` on assistant messages.

For each "fundamental", state *what force makes it unavoidable*. For each
"choice", name the alternative and what it would cost.

This is the level's real output: a transferable checklist you can apply to the
next agent codebase you open.
""",
                stance_question=(
                    "Start with the hardest one. Tree-structured sessions: "
                    "forced, or a choice?"
                ),
                stances=[
                    Choice(
                        id="forced",
                        label="Forced. Users always want to go back and try differently.",
                        note="Wanting it does not make it forced. Plenty of shipped agents have a flat transcript and no branching, and they work - the user starts a new session instead.",
                    ),
                    Choice(
                        id="choice",
                        label="A choice. A flat list works; branching is a feature built on top.",
                        note="The defensible answer. A list is simpler and loses the ability to revisit an abandoned path. Tau chose the tree because parent pointers make branching cost almost no code - see the Level 9 diagram.",
                    ),
                    Choice(
                        id="append-forced",
                        label="Append-only is forced; the tree part is a choice.",
                        note="The sharpest answer, and arguably better than the one above. Durability forces append-only - you cannot lose a session to a crash mid-write. Given append-only, the tree is nearly free, which is why it is easy to mistake for forced.",
                    ),
                ],
                writing_prompt=(
                    "Now sort the rest. For each 'fundamental', name the force "
                    "that makes it unavoidable; for each 'choice', name the "
                    "alternative and what it costs."
                ),
                hints=[
                    "A good test for 'fundamental': can you describe a working coding agent that lacks it? If not, it is forced.",
                    "Tree-structured sessions are a good one to think hard about. Is branching required, or is it a feature? What does a list-based design lose?",
                ],
                after="""\
A defensible split:

**Fundamental** - forced by external reality:
- The loop and its stop condition (the model cannot act, only request)
- Tool-call/result pairing (providers reject violations)
- Some context-limit strategy (windows are finite)
- Durable history (sessions outlive processes)
- An interruption story (runs are long; users change their minds)

**Choice** - defensible alternatives exist:
- Typed events vs. callbacks vs. direct rendering (events scale best, but a
  single-frontend tool may not need them)
- Append-only tree vs. mutable list (tree enables branching; list is simpler)
- Summarizing vs. truncating compaction (quality vs. cost and latency)
- Steering queue vs. cancel-and-restart (restart is simpler, loses work)
- Separate core package vs. one module (separation pays off only with a second
  frontend - and a one-frontend tool genuinely may not need it)

The last point deserves emphasis. Tau's layering is *right for Tau*, which has
four frontends and ships as a library. A 300-line personal agent with one
frontend would be worse, not better, for adopting it. Recognizing which
constraints justify which structure is the actual skill.
""",
                xp=30,
            ),
        ],
        reveal="""\
Tau's own notes do this comparison constantly, with commit-pinned references.
From `tau/dev-notes/design/project-trust.md`:

> Pi was inspected at the exact revision below on 2026-08-03:
> repository: earendil-works/pi, commit: fa07e7bd...

They record *which revision* they compared against, because "Pi does X" decays.
That is unusually careful engineering practice and worth imitating: when you
document a comparison against another system, pin it.
""",
        transfer="""\
**Transferable:** the fastest way to tell fundamentals from choices is to read
two implementations. What both do, under different constraints and languages,
is forced. What they do differently is a decision - and then the interesting
question is what each team optimized for.
""",
    )


# --------------------------------------------------------------------------
# Act IV - Build it
# --------------------------------------------------------------------------


def act_four() -> Act:
    return Act(
        id="act4",
        title="Act IV - Reconstruction",
        subtitle="Build a working coding agent. No scaffolding, no scripted provider.",
        levels=[_l12()],
    )


def _l12() -> Level:
    return Level(
        id="l12-capstone",
        title="Capstone: Build a Harness",
        teaser="Everything, assembled. A real agent on a real model.",
        question="Can you build one yourself?",
        minutes=90,
        requires=["l08-context", "l09-persistence", "l11-transfer"],
        concepts=["synthesis", "agent-loop", "harness", "persistence", "tools"],
        hook="""\
Everything you have written so far has been a fragment checked by a test.

{{diagram:capstone-assembly}}

Now assemble a coding agent that actually works: real model, real files, real
session persistence, running from the command line.

The tests here are different in kind. They do not check that you matched a
reference implementation - they check that your agent **does the job**: reads
a file it was not told the contents of, edits code correctly, survives a tool
failure, and resumes a session from disk.
""",
        steps=[
            Step(
                id="build",
                kind="implement",
                title="Assemble the agent",
                body="""\
In the editor below, write a working coding agent.

**Required**

1. `MyAgent(provider, model, cwd, session_path)`.
2. Tools: `read`, `write`, `bash`. Reuse your Level 4 implementations.
3. The loop from Level 2, the harness from Level 5.
4. Persistence as a **subscriber** (Level 9 - this is tested by cancelling
   mid-run and checking the file).
5. Tool-call pairing preserved under cancellation (Level 7).
6. Compaction when context exceeds a threshold (Level 8).
7. `async def run(prompt) -> str` returning the final assistant text.
8. `resume(session_path)` reconstructing state from disk.

**You choose** - and these choices are the point:

- Does compaction run automatically, on demand, or on overflow?
- Does a failing tool end the run or feed the error back?
- Is cancellation cooperative or immediate?

Each is a real tradeoff from the course. Make them deliberately; you will be
asked to defend them in the next step.

Run against the scripted provider for the graded tests. Then try it on a real
model - `make capstone-live` wires it to your configured provider, which is
where it stops being an exercise.
""",
                target_file="myagent.py",
                test_file="tests/test_l12_capstone.py",
                specimen_paths=[
                    "tau/src/tau_agent/harness.py",
                    "tau/src/tau_coding/session.py",
                ],
                starter='''\
"""Your coding agent.

Assemble what you have built. Import your own modules - this is the moment the
pieces become a system.

The grading tests check behavior, not structure. Any design that genuinely
works will pass. Designs that only work when nothing goes wrong will not.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harnesskit.events import AgentEvent, MessageEndEvent
from harnesskit.messages import AgentMessage, AssistantMessage, UserMessage

from compaction import compact, estimate_tokens
from harness import AgentHarness, AgentHarnessConfig
from session_store import Entry, SessionStore, new_id
from tools_impl import create_read_tool, create_write_tool


class MyAgent:
    """A coding agent: loop + harness + tools + persistence + compaction."""

    def __init__(
        self,
        *,
        provider: Any,
        model: str = "scripted",
        cwd: str | Path = ".",
        session_path: str | Path | None = None,
        system: str = "You are a coding assistant.",
        compact_threshold: int = 100_000,
    ) -> None:
        self.cwd = Path(cwd).resolve()
        self.store = SessionStore(session_path) if session_path else None
        self.compact_threshold = compact_threshold
        self._last_entry_id: str | None = None

        tools = [
            create_read_tool(self.cwd),
            create_write_tool(self.cwd),
            # TODO: add a bash tool
        ]
        self.harness = AgentHarness(
            AgentHarnessConfig(provider=provider, model=model, system=system, tools=tools)
        )

        # TODO: subscribe persistence here - NOT in the consuming loop.
        #       Remember Level 9: a consumer can be cancelled, a subscriber cannot.

    async def run(self, prompt: str) -> str:
        """Run one prompt to completion and return the final assistant text."""
        # TODO
        #  - compact first if estimate_tokens(self.harness.messages) > threshold
        #  - async for event in self.harness.prompt(prompt): collect
        #  - return the last assistant message's text
        raise NotImplementedError

    def resume(self) -> None:
        """Rebuild in-memory state from the session file."""
        # TODO: read entries, take the path to the last one, replay into messages,
        #       and load them into the harness
        raise NotImplementedError

    def _persist(self, event: AgentEvent) -> None:
        """Subscriber that writes each finished message to the session file."""
        # TODO: on MessageEndEvent, append an Entry with parent_id chaining
        raise NotImplementedError
''',
                hints=[
                    "Build in the order the tests fail: a bare run first, then persistence, then resume, then compaction. Do not try to write it all at once.",
                    "For bash, use `asyncio.create_subprocess_shell` with a timeout. Capture both stdout and stderr; the model needs the error text to recover.",
                    "`_persist` is a sync callback. If your store's append is async, use `asyncio.create_task` - but then make sure ordering is preserved, or keep append synchronous.",
                    "Chain parent_ids: each appended Entry's parent is the previously appended entry's id. That is what makes path_to work later.",
                    "For resume: `read_all()`, take the last entry, `path_to(it.id)`, `replay(path)`, then `harness._messages = list(result)` (or add a replace_messages method, which is what Tau does).",
                ],
                after="""\
You have built a coding agent harness.

Run it against a real model with `make capstone-live` and give it a genuine
task in a scratch directory. The moment it reads a file you did not describe,
decides what to change, and edits it correctly, the architecture stops being
theory.
""",
                xp=120,
            ),
            Step(
                id="defend",
                kind="explain",
                title="Defend your design",
                body="""\
Final step. Write an architecture note for your agent - the kind that would go
in `dev-notes/`.

Cover:

1. **Your layer boundaries.** What does each module own? What is it forbidden
   to know? Where did you deviate from Tau, and why?

2. **Three decisions you made.** For each: what you chose, what you rejected,
   and what it costs. Be concrete about the cost - every real choice has one.

3. **What you did not build, and why.** Steering? Branching? Multiple
   providers? Omissions are architecture too, when deliberate.

4. **The failure you would fix first.** Where is your agent most fragile? What
   would you need to see to confirm it?

The tutor will challenge this - expect to be asked about a case you did not
consider. That exchange is the final exercise.
""",
                stance_question="Before you write it: where is your agent most fragile?",
                stances=[
                    Choice(
                        id="cancel",
                        label="Cancellation. A run interrupted mid-tool leaves a bad transcript.",
                        note="A strong answer, and the one with the most evidence behind it - Levels 7 and 9 are both about failures in this area, in two different layers.",
                    ),
                    Choice(
                        id="context",
                        label="Context. Long sessions will hit the window and something will break.",
                        note="Likely true in practice. Note that your estimate is chars/4, so you will sometimes be wrong about when - which is why Tau has an overflow-retry path and not only a threshold.",
                    ),
                    Choice(
                        id="persistence",
                        label="Persistence. A write lost at the wrong moment corrupts the session.",
                        note="The subtlest, because it fails silently. The in-memory state stays correct, so nothing looks wrong until a later replay sends the broken transcript to a provider.",
                    ),
                    Choice(
                        id="tools",
                        label="Tools. Shell and file access touch things I cannot undo.",
                        note="The largest blast radius, and the one your design most clearly bounds - you wrote the containment check yourself. Worth saying what it does NOT cover.",
                    ),
                ],
                writing_prompt=(
                    "Now the note itself: boundaries, three decisions with "
                    "their costs, what you left out, and how you would "
                    "confirm that fragility is real."
                ),
                hints=[
                    "If a decision has no cost, you have probably not identified the real alternative.",
                    "For #4: think about the forces from Level 10 - provider rejections, old data on disk, interactions you cannot express.",
                ],
                after="""\
That note is the deliverable this whole course was aiming at.

Not the code - the ability to state what you built, why it is shaped that way,
what it cannot do, and where it will break first. That is what distinguishes
someone who has built an agent from someone who can design one.
""",
                xp=60,
            ),
        ],
        reveal="""\
Now read `tau/src/tau_coding/session.py` - all 5,234 lines of it.

It is the same assembly you just did, carrying everything a real product
requires: provider configuration, OAuth, skills, prompt templates, project
trust, extensions, slash commands, export, branching, auto-naming, resource
reloading.

The useful reaction is not "mine is small". It is that you can now *navigate*
it. You know where the loop is, where state lives, where the frontend boundary
runs, which parts are forced and which are choices.

That is what the course was for: not knowing Tau, but being able to read the
next one without a guide.
""",
        transfer="""\
**You can now:** open an unfamiliar coding-agent repository and ask the right
questions in the right order. Where is the loop? What stops it? Who owns the
transcript? What is the frontend contract? What invariants do providers
enforce? What happens when context fills, when a tool fails, when a user
interrupts? Which parts are forced by reality, and which did this team choose?

That is the transferable model. The specimen was a vehicle.
""",
    )
