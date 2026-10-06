"""Act I and II: the loop, and the state it carries.

Curriculum design notes, so the reasoning is auditable:

Every level opens with a *failure or surprise*, never a definition. The order
is derived from dependency, not from the specimen's file layout: you cannot
reason about compaction before you have felt context grow, and you cannot
appreciate the event contract before you have tried to render from inside the
loop.

Several "expected answers" are computed by running code in ``traces/`` rather
than hardcoded, so the course cannot drift away from what the specimen does.
"""

from __future__ import annotations

from academy.curriculum import Act, Choice, Level, Step

# --------------------------------------------------------------------------
# Act I - What is a coding agent, mechanically?
# --------------------------------------------------------------------------


def act_one() -> Act:
    return Act(
        id="act1",
        title="Act I - The Engine",
        subtitle="A coding agent is a loop. Find out what makes it turn, and what makes it stop.",
        levels=[_l01(), _l02(), _l03(), _l04()],
    )


def _l01() -> Level:
    return Level(
        id="l01-first-contact",
        title="First Contact",
        teaser="Watch one run. Count the round-trips.",
        question="A model cannot read files. So how does 'read this file and summarize it' ever work?",
        minutes=10,
        concepts=["agent-loop", "tool-calling"],
        hook="""\
Before any theory, run something.

The command below runs a complete, working agent against a scripted model. It
reads a file and reports on it. No network, no API key, fully deterministic.

Press **Run the agent demo** below, read the output, and come back. The whole exercise is to notice one
thing: **how many times the model was called.**
""",
        steps=[
            Step(
                id="count-calls",
                kind="predict",
                title="How many times did the model get called?",
                run_command="first",
                run_label="Run the agent demo",
                body="""\
The user typed one message: *"How many lines are in notes.txt?"*

The agent answered correctly. A model cannot open files, so somewhere in there
a real file was read by real Python code.

Commit to a number before you look.
""",
                question="How many separate requests did the agent send to the model?",
                choices=[
                    Choice(
                        id="1",
                        label="One. The model answered in a single response.",
                        note="This is the intuition most people start with, and it is the one worth losing first. A single request cannot work: at the moment the model is called, nobody has read the file yet.",
                    ),
                    Choice(
                        id="2",
                        label="Two. One to decide to read the file, one to answer using the contents.",
                        note="Correct. Round-trip one returns a *request to act*. The harness performs the action. Round-trip two sees the result and produces prose.",
                    ),
                    Choice(
                        id="3",
                        label="Three. Decide, read, then verify.",
                        note="Nothing in the loop verifies anything. The loop is simpler than you expect - it keeps going purely because the model keeps asking for tools.",
                    ),
                    Choice(
                        id="many",
                        label="It streams continuously; there are no discrete requests.",
                        note="Streaming happens *within* one request. The loop's structure is still discrete round-trips - a distinction that matters enormously once you build it.",
                    ),
                ],
                answer="2",
                trace="traces/t01_call_count.py",
                hints=[
                    "The model produced the file's contents in its final answer. When could it possibly have learned them?",
                    "Think about what the harness must do *between* model calls.",
                    "Run `make run-first` again and count the lines starting with 'provider call'.",
                ],
                after="""\
Two round-trips. That gap between them is where the entire field lives.

{{diagram:agent-loop}}

Round-trip 1 ends with the model saying, in effect, *"I want to call `read`
with path=notes.txt"*. It is not an answer; it is a request. The model then
stops and waits.

The harness - ordinary Python, no intelligence - reads the file and appends the
result to the transcript. Round-trip 2 sends that enlarged transcript back.
Now the model has the contents and can answer.

The agent's "ability" to read files is not in the model at all. It is in the
loop.
""",
                xp=15,
            ),
            Step(
                id="where-stop",
                kind="predict",
                title="What stopped it?",
                body="""\
The loop ran twice and then stopped. Something decided "we're done".

Rule out the tempting answers: there is no step limit involved here, no
confidence threshold, and nothing inspecting the text for completeness.
""",
                question="What condition ended the run?",
                choices=[
                    Choice(
                        id="no-tools",
                        label="The last assistant message requested no tool calls.",
                        note="Correct, and it is almost the whole algorithm. 'Keep going while the model keeps asking for tools' is the loop's termination rule.",
                    ),
                    Choice(
                        id="max",
                        label="It hit a maximum turn limit.",
                        note="Limits exist as a safety net, but if a turn cap were the normal exit, every run would burn the full budget.",
                    ),
                    Choice(
                        id="confident",
                        label="The model signalled it was confident in the answer.",
                        note="There is no such signal. Nothing in the harness evaluates answer quality - a point worth remembering when you are tempted to add that.",
                    ),
                    Choice(
                        id="user",
                        label="The user's request was satisfied.",
                        note="Nothing in the loop can know this. The harness has no model of the user's intent at all.",
                    ),
                ],
                answer="no-tools",
                hints=[
                    "The stop condition is checked on the assistant message. What varies between message 1 and message 2?",
                    "Round-trip 1's message had tool calls in it. Round-trip 2's did not.",
                ],
                after="""\
That is the engine, in one sentence:

> **Call the model. If it asked for tools, run them, append the results, and
> call again. Otherwise stop.**

You now know the core algorithm of every coding agent in existence - Claude
Code, Codex, Aider, Cursor, Pi, Tau. The differences between them are not in
this loop. They are in everything that surrounds it, which is what the rest of
this course is about.
""",
                xp=15,
            ),
        ],
        reveal="""\
Open the specimen's version: `tau/src/tau_agent/loop.py`.

It is 376 lines, but the skeleton you just derived is visible around line 98:

```python
while True:
    has_more_tools = True
    while has_more_tools or pending:
        ...
        assistant = <stream one provider response>
        ...
        calls = list(assistant.tool_calls)
        has_more_tools = bool(calls)
        for call in calls:
            <execute, append ToolResultMessage>
```

`has_more_tools = bool(calls)` is the stopping rule you just predicted.

Everything else in that file - timing, cancellation, steering queues, history
repair - is hardening wrapped around this. Being able to see the loop through
the hardening is a skill worth practising; it is how you will read the next
agent codebase you open.
""",
        transfer="""\
**Transferable:** an agent is a loop over (model -> tool requests -> tool
results -> model). Capability comes from the tools, continuation comes from the
loop, and intelligence comes from the model. When you open an unfamiliar agent
repo, finding this loop first makes everything else legible.
""",
    )


def _l02() -> Level:
    return Level(
        id="l02-build-loop",
        title="Build the Engine",
        teaser="Five small steps. Each one adds a single idea.",
        question="Can you write the thing you just described?",
        minutes=45,
        requires=["l01-first-contact"],
        concepts=["agent-loop", "tool-calling", "transcript", "events"],
        hook="""\
You know the algorithm. Now you build it - but not in one go.

This level has five steps. Each adds one idea and has its own small test
file.

```
0. async warm-up      the two keywords, nothing else
1. one provider call  no tools, no events - just get the message
2. add events         make progress observable
3. add the loop       keep going while the model asks for tools
4. add tools          actually execute them
```

Step 0 is a three-minute demo you run, not code you write. It fixes the
vocabulary the later steps use; skip it if `await`, `yield` and `async for`
are already familiar.
""",
        steps=[
            Step(
                id="async-primer",
                kind="predict",
                title="Step 0 - async, in three minutes",
                run_command="async",
                run_label="Run the async demo",
                body="""\
The loop you are about to write is an **async generator**. That is two
unfamiliar ideas stacked together, so let's separate them before they show up
inside something else.

{{diagram:async-timeline}}

**Three keywords, three jobs.** That is all you need:

| keyword | what it means |
|---|---|
| `await x` | pause here until `x` finishes, let other work proceed |
| `yield v` | hand `v` to whoever is looping over me, then remember my place |
| `async for` | the loop used to consume an async generator |

Press **Run the async demo** below. It prints four short demos: a normal
function, a generator, an async generator, and the fact that nothing runs
until you iterate. Demo 4 is the one worth watching closely.

Then answer this, which is the only part of async that will bite you later:
""",
                question=(
                    "You call `stream = who_does_the_work()`, where that "
                    "function is an `async def` containing a `yield`. "
                    "Before any `async for` runs, what has happened?"
                ),
                choices=[
                    Choice(
                        id="nothing",
                        label="Nothing. No line of the body has run yet.",
                        note=(
                            "Correct, and this is demo 4. Calling the function "
                            "builds an async generator object and returns it "
                            "immediately. The body does not start until "
                            "something iterates. Level 5 depends on this: the "
                            "harness can hold a stream it has not consumed, "
                            "and nothing happens until it decides to pull."
                        ),
                    ),
                    Choice(
                        id="first-yield",
                        label="The body ran up to the first `yield` and paused there.",
                        note=(
                            "This is how a *thread* would behave, and it is the "
                            "most common wrong model. Run demo 4 again: the "
                            "line `body is running NOW` prints after the "
                            "`async for`, not after the call."
                        ),
                    ),
                    Choice(
                        id="all",
                        label="The whole body ran and the values are waiting in a buffer.",
                        note=(
                            "That is what a function returning a list does, and "
                            "it is exactly what a generator exists to avoid. "
                            "Buffering everything would mean the agent loop "
                            "could show nothing until the run was over."
                        ),
                    ),
                    Choice(
                        id="task",
                        label="It was scheduled on the event loop and runs in the background.",
                        note=(
                            "Scheduling needs `asyncio.create_task`. A bare "
                            "call does not schedule anything. Nothing in an "
                            "async generator runs concurrently with you unless "
                            "you explicitly arrange it."
                        ),
                    ),
                ],
                answer="nothing",
                hints=[
                    "Demo 4 answers this directly. Watch where the line `body is running NOW` appears relative to the two comments.",
                    "If calling it ran the body, the demo could not print `...still nothing...` between the call and the loop.",
                ],
                after="""\
Vocabulary fixed: `await` to wait, `yield` to emit, `async for` to consume.
Every step below uses only these three.

And the rule you just confirmed: **an async generator is inert until
iterated.** Calling it costs nothing and does nothing. That is what makes it
safe for the harness in Level 5 to hold a stream it has not started.
""",
                xp=10,
            ),
            Step(
                id="one-call",
                kind="implement",
                title="Step 1 - one provider call, no events, no tools",
                body="""\
The smallest useful thing: ask the model once, keep what it said.

In the editor below, write `get_one_response(...)` so it:

1. calls `provider.stream_response(...)` (already written for you)
2. iterates the events with `async for`
3. when it sees an `AssistantDoneEvent`, saves `event.message`
4. returns that message

Four lines of code.

**The idea it rests on**

A provider does not hand you a finished message. It *streams*. You receive a
sequence of small events, and the complete message arrives in the last one:

```
AssistantStartEvent   "I'm starting"
TextDeltaEvent        "Hel"
TextDeltaEvent        "lo"
AssistantDoneEvent    <- the finished message is in here
```

So you need a variable declared *outside* the `async for` to hold the message
when it finally appears. A variable outside the loop, assigned inside it -
that is the only trick in this step, and you will reuse it three more times.

Three tests.
""",
                target_file="step1_one_call.py",
                test_file="tests/test_l02a_one_call.py",
                starter='''\
"""Step 1: get one response out of a provider.

No events, no tools, no loop. Ask once, keep the answer.
"""

from __future__ import annotations

from harnesskit.messages import AssistantMessage
from harnesskit.provider_events import (
    AssistantDoneEvent,
    AssistantErrorEvent,
    AssistantStartEvent,
    TextDeltaEvent,
)


async def get_one_response(
    *,
    provider,
    model: str = "scripted",
    system: str = "",
    messages: list | None = None,
    tools: list | None = None,
) -> AssistantMessage | None:
    """Call the provider once and return the finished assistant message.

    Returns None if the provider produced no final message.
    """
    stream = provider.stream_response(
        model=model,
        system=system,
        messages=messages or [],
        tools=tools or [],
    )

    # TODO
    #  1. declare a variable here to hold the result, starting at None
    #  2. async for event in stream:
    #  3. inside: if isinstance(event, AssistantDoneEvent): save event.message
    #  4. return it

    raise NotImplementedError
''',
                hints=[
                    "The skeleton is:\n\n    assistant = None\n    async for event in stream:\n        ...\n    return assistant",
                    "Inside the loop: `if isinstance(event, AssistantDoneEvent): assistant = event.message`",
                    "A failed turn produces `AssistantErrorEvent` instead, and its message is on `event.error` rather than `event.message`. One test covers that.",
                ],
                after="""\
You just consumed a provider stream. That is the innermost part of the agent
loop, and from here on it is something you already know how to do.

Notice what you did *not* need: no event types of your own, no transcript
bookkeeping, no tools. Those arrive one at a time.
""",
                xp=20,
            ),
            Step(
                id="add-events",
                kind="implement",
                title="Step 2 - emit events as it streams",
                body="""\
Step 1 returned a message *after* everything finished. A real UI cannot wait
that long - it needs to show text as it arrives.

So instead of `return`, we `yield`. The function becomes an async generator.

**Why two sets of event types?**

This is the part worth slowing down for. You now have:

- **provider events** - what the vendor's API gives you:
  `AssistantStartEvent`, `TextDeltaEvent`, `AssistantDoneEvent`
- **agent events** - what *your* harness publishes:
  `MessageStartEvent`, `MessageUpdateEvent`, `MessageEndEvent`

{{diagram:event-seam}}

They look redundant. They are not. Provider events are OpenAI's or
Anthropic's shape and differ between vendors. Agent events are yours, and
every frontend you ever write consumes only those. The translation you are
about to write is the seam that keeps everything above it vendor-neutral.

**The translation is mechanical:**

| provider event | becomes | meaning |
|---|---|---|
| `AssistantStartEvent` | `MessageStartEvent` | a message is beginning |
| `TextDeltaEvent` | `MessageUpdateEvent` | more text arrived |
| `AssistantDoneEvent` | `MessageEndEvent` | the message is final |

There is a fourth, `ToolCallEndEvent`, emitted when the model finishes asking
for a tool. It is imported for you. You can translate it to a
`MessageUpdateEvent` like a text delta, or ignore it for now - the tests here
do not check it, and Step 3 reads tool calls off the finished message instead.

Write `stream_one_turn(...)` in the editor below: same shape as
step 1, but `yield` a translated event for each one received.
""",
                target_file="step2_events.py",
                test_file="tests/test_l02b_events.py",
                specimen_paths=["tau/src/tau_agent/events.py"],
                starter='''\
"""Step 2: translate provider events into your own agent events.

Step 1 returned at the end. This yields along the way - which is what lets a
UI render progress while the model is still talking.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from harnesskit.events import (
    AgentEvent,
    MessageEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
)
from harnesskit.messages import AssistantMessage
from harnesskit.provider_events import (
    AssistantDoneEvent,
    AssistantErrorEvent,
    AssistantStartEvent,
    TextDeltaEvent,
    ToolCallEndEvent,
)


async def stream_one_turn(
    *,
    provider,
    model: str = "scripted",
    system: str = "",
    messages: list | None = None,
    tools: list | None = None,
) -> AsyncIterator[AgentEvent]:
    """Stream one provider turn, yielding agent events as it goes.

    The caller reads the final message off the last MessageEndEvent.
    """
    stream = provider.stream_response(
        model=model,
        system=system,
        messages=messages or [],
        tools=tools or [],
    )

    # TODO: async for event in stream, then translate:
    #
    #   AssistantStartEvent -> yield MessageStartEvent(message=event.partial)
    #   TextDeltaEvent      -> yield MessageUpdateEvent(message=event.partial,
    #                                                   provider_event=event)
    #   AssistantDoneEvent  -> yield MessageEndEvent(message=event.message)
    #   AssistantErrorEvent -> yield MessageEndEvent(message=event.error)
    #
    # Delete the two lines below once you have real yields.

    raise NotImplementedError
    yield  # pragma: no cover - keeps this an async generator
''',
                hints=[
                    "Use a chain of `if isinstance(event, X): ... elif isinstance(event, Y): ...` inside the `async for`.",
                    "`MessageStartEvent(message=event.partial)` - the provider's partial message is what a UI shows mid-stream.",
                    "For the delta: `MessageUpdateEvent(message=event.partial, provider_event=event)`.",
                    "Once your loop contains real `yield` statements, delete the trailing `raise NotImplementedError` and the bare `yield` placeholder.",
                ],
                after="""\
Your function is now an async generator publishing *your* event vocabulary
rather than the vendor's.

This is the single most reused idea in the course. Level 3 makes you feel why
it matters by having you build two different frontends on top of exactly these
events, without touching the loop.
""",
                xp=25,
            ),
            Step(
                id="add-loop",
                kind="implement",
                title="Step 3 - make it loop",
                body="""\
One turn works. Now keep going while the model asks for tools.

You are **not** executing tools yet. This step is only the control flow: when
to call the provider again, and when to stop.

In the editor below, write `run_loop(...)`:

```python
yield AgentStartEvent()
while True:
    yield TurnStartEvent()
    # stream one turn (your step 2 code), remembering the assistant message
    messages.append(assistant)
    yield TurnEndEvent(message=assistant)
    if not assistant.tool_calls:
        break
yield AgentEndEvent(messages=new_messages)
```

**Two new ideas, both small**

1. **`messages` is mutated in place.** The caller passes a list; you append to
   it. That list *is* the conversation, and the next provider call sends it.
   This is the mechanism by which turn 2 knows what happened in turn 1.

2. **`new_messages`** is a separate list holding only what this run added. The
   caller already had the older ones; `AgentEndEvent` reports the new.

The stop condition is the one you predicted in Level 1:
`if not assistant.tool_calls: break`.

No tools run yet, so the scripted provider returns a tool call that nothing
handles and the loop goes round again. The tests expect that.
""",
                target_file="step3_loop.py",
                test_file="tests/test_l02c_loop.py",
                carries_from="step2_events.py",
                carries_note="your step 2 translation, to paste inside the loop",
                starter='''\
"""Step 3: the loop itself.

No tool execution yet. Only: when do we call the provider again, and when do
we stop?
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from harnesskit.events import (
    AgentEndEvent,
    AgentEvent,
    AgentStartEvent,
    MessageEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    TurnEndEvent,
    TurnStartEvent,
)
from harnesskit.messages import AgentMessage, AssistantMessage
from harnesskit.provider_events import (
    AssistantDoneEvent,
    AssistantErrorEvent,
    AssistantStartEvent,
    TextDeltaEvent,
    ToolCallEndEvent,
)


async def run_loop(
    *,
    provider,
    model: str = "scripted",
    system: str = "",
    messages: list[AgentMessage],
    tools: list | None = None,
    max_turns: int | None = None,
) -> AsyncIterator[AgentEvent]:
    """Loop over provider turns until the assistant stops asking for tools.

    Appends every new message to ``messages`` in place.
    """
    new_messages: list[AgentMessage] = []

    yield AgentStartEvent()

    # TODO
    #   turn = 0
    #   while True:
    #       if max_turns is not None and turn >= max_turns: break
    #       turn += 1
    #       yield TurnStartEvent()
    #       assistant = None
    #       async for event in provider.stream_response(...):
    #           ...your step 2 translation, inline...
    #       messages.append(assistant); new_messages.append(assistant)
    #       yield TurnEndEvent(message=assistant)
    #       if not assistant.tool_calls: break

    yield AgentEndEvent(messages=new_messages)
''',
                hints=[
                    "Copy your step 2 translation straight into the body of the while loop. Reuse it, do not rewrite it.",
                    "`assistant` is declared inside the while loop but outside the `async for` - same pattern as step 1.",
                    "Stop condition goes after you append and yield TurnEndEvent: `if not assistant.tool_calls: break`.",
                    "For max_turns, check at the top of the while body and `break` before calling the provider.",
                    "Append to BOTH lists: `messages` (the whole conversation, mutated for the caller) and `new_messages` (only this run, reported by AgentEndEvent).",
                ],
                after="""\
That is a working agent loop. It calls, it continues, it stops.

The provider-call count in those tests is the proof: the model asked for a
tool, so the loop went round again. Nothing intelligent made that decision -
`if not assistant.tool_calls` did.
""",
                xp=30,
            ),
            Step(
                id="add-tools",
                kind="implement",
                title="Step 4 - execute the tools",
                body="""\
Last step. The loop already goes round when the model asks for a tool - now
actually run it and feed the result back.

In the editor below, write the complete `run_agent_loop`. Start by copying
your step 3 code, then add tool execution after `messages.append(assistant)`:

```python
for call in assistant.tool_calls:
    yield ToolExecutionStartEvent(...)
    # find the tool, run it, catch exceptions
    yield ToolExecutionEndEvent(...)
    # build a ToolResultMessage, append to messages, yield its start/end
yield TurnEndEvent(message=assistant, tool_results=results)
```

**Three rules the tests enforce**

{{diagram:transcript-pairing}}

1. **Order.** A `ToolResultMessage` must come *immediately after* the
   assistant message that requested it. Providers reject anything else. This
   is the most important invariant in the system; Level 7 is devoted to it.

2. **A failing tool is not a failing run.** If the tool raises, catch it,
   return an error result, keep going. The model can usually recover from an
   error message; it cannot recover from your crash.

3. **An unknown tool name** is the same case: return an error result rather
   than raising.

Ten tests. This file defines `run_agent_loop` for the rest of the course -
Level 5's harness imports it, and so does your capstone.
""",
                target_file="loop.py",
                test_file="tests/test_l02_loop.py",
                specimen_paths=["tau/src/tau_agent/loop.py"],
                carries_from="step3_loop.py",
                carries_note="your step 3 loop, as the starting point",
                starter='''\
"""Your agent loop - the complete version.

Start from your step3_loop.py and add tool execution. The tests in
tests/test_l02_loop.py are the specification; read them when the brief is
ambiguous.

This file is imported by Level 5's harness and by your capstone agent, so it
is worth keeping clean.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from harnesskit.events import (
    AgentEndEvent,
    AgentEvent,
    AgentStartEvent,
    MessageEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    TurnEndEvent,
    TurnStartEvent,
)
from harnesskit.messages import (
    AgentMessage,
    AssistantMessage,
    TextContent,
    ToolResultMessage,
)
from harnesskit.provider_events import (
    AssistantDoneEvent,
    AssistantErrorEvent,
    AssistantStartEvent,
    TextDeltaEvent,
    ToolCallEndEvent,
)
from harnesskit.tools import CancellationToken, Tool, ToolResult


async def run_agent_loop(
    *,
    provider,
    model: str,
    system: str,
    messages: list[AgentMessage],
    tools: Sequence[Tool] = (),
    max_turns: int | None = None,
    signal: CancellationToken | None = None,
) -> AsyncIterator[AgentEvent]:
    """Drive the provider/tool loop, yielding agent events.

    Mutates ``messages`` in place, appending every new message.
    """
    tool_by_name = {tool.name: tool for tool in tools}
    new_messages: list[AgentMessage] = []

    yield AgentStartEvent()

    # TODO: start from step3_loop.py, then add tool execution.
    #
    # Inside the while loop, after appending the assistant message:
    #
    #   tool_results = []
    #   for call in assistant.tool_calls:
    #       yield ToolExecutionStartEvent(tool_call_id=call.id,
    #                                     tool_name=call.name,
    #                                     args=dict(call.arguments))
    #       tool = tool_by_name.get(call.name)
    #       if tool is None:
    #           result = ToolResult(content=f"Tool {call.name} not found")
    #           is_error = True
    #       else:
    #           try:
    #               result = await tool.run(call.id, call.arguments, signal)
    #               is_error = False
    #           except Exception as exc:
    #               result, is_error = ToolResult(content=str(exc)), True
    #       yield ToolExecutionEndEvent(tool_call_id=call.id,
    #                                   tool_name=call.name,
    #                                   result=result, is_error=is_error)
    #       message = ToolResultMessage(
    #           tool_call_id=call.id, tool_name=call.name,
    #           content=[TextContent(text=result.content)], is_error=is_error)
    #       messages.append(message)
    #       new_messages.append(message)
    #       tool_results.append(message)
    #       yield MessageStartEvent(message=message)
    #       yield MessageEndEvent(message=message)
    #
    #   yield TurnEndEvent(message=assistant, tool_results=tool_results)

    yield AgentEndEvent(messages=new_messages)
''',
                hints=[
                    "Copy step3_loop.py wholesale first and confirm the no-tool tests still pass. Then add the tool block.",
                    "`tool_by_name.get(call.name)` returns None for an unknown tool - that is the case rule 3 covers.",
                    "The try/except wraps only `await tool.run(...)`. Catch broad `Exception`: a tool is untrusted code at the edge of your system.",
                    "Append the ToolResultMessage inside the for loop, immediately - not collected and appended afterwards. Order is the invariant.",
                    "TurnEndEvent now moves to AFTER the tool loop and carries `tool_results=tool_results`.",
                ],
                after="""\
You have a working agent loop. Structurally this is what runs in production
systems - the rest is hardening.

Worth noticing what you never had to decide: nothing about files, terminals,
or which model vendor. The loop touched a provider interface and a tool
interface and nothing else. That portability is deliberate, and Level 5 is
about why.
""",
                xp=40,
            ),
            Step(
                id="compare",
                kind="compare",
                title="Compare with the specimen",
                body="""\
Now read `tau/src/tau_agent/loop.py` with your own implementation fresh in
mind.

Find these three things, which you probably did not do:

1. **Line ~185, `_provider_context`.** Before sending history to the provider,
   Tau *filters it*. Failed assistant turns with empty content are kept in the
   durable record but removed from what the model sees.

2. **Line ~122.** A comment explaining that the assistant sub-generator is
   consumed rather than awaited, because Python async generators cannot
   cleanly pass a yielding callback through an await.

3. **Line ~343, `_run_tool`.** `except Exception` carrying the comment
   *tools are an isolation boundary*.

Pick whichever surprised you most and explain, in your own words, what problem
it solves. There is no grading here - the tutor will push back on your
reasoning.
""",
                specimen_paths=["tau/src/tau_agent/loop.py"],
                hints=[
                    "For #1: what happens on the *next* request if a failed, empty assistant turn stays in the history you send?",
                    "For #3: if a tool raises and the loop does not catch it, what happens to the model's half-finished tool call? Remember the pairing rule.",
                ],
                after="""\
Each of those is a scar. Someone shipped the simple version, something broke,
and the fix became part of the architecture.

`_provider_context` is the subtlest: it means **durable history and model
context are not the same thing.** Tau keeps a failed turn on disk for
diagnostics while hiding it from the model. Once you see that split, you start
seeing it everywhere - it is the same idea that makes compaction possible
(Level 8).
""",
                xp=20,
            ),
        ],
        reveal="""\
Your loop and Tau's loop differ mainly in what they tolerate. Yours assumes a
well-behaved world; Tau's assumes a hostile one - providers that error
mid-stream, users who hit Ctrl-C during a tool call, transcripts loaded from
disk that were written by an older version.

That is the normal trajectory of this kind of code. The core algorithm is
small and stays small; robustness accretes around it.

If you want to see the five steps you just took collapsed into one function,
that file is it - and it is readable to you now in a way it would not have
been an hour ago.
""",
        transfer="""\
**Transferable:** when reading any agent implementation, separate *the loop*
from *the hardening around the loop*. The loop is usually 30 lines and nearly
identical everywhere. The hardening is where that project's real history,
priorities, and hard-won knowledge live - read it to learn what actually goes
wrong in production.
""",
    )
def _l03() -> Level:
    return Level(
        id="l03-events",
        title="Why Events?",
        teaser="Make the loop print. Discover why that was a mistake.",
        question="The loop already knows everything. Why not let it just print?",
        minutes=20,
        requires=["l02-build-loop"],
        concepts=["events", "layering", "frontend-boundary"],
        hook="""\
Your loop yields events, because the brief told you to. That is not a reason.

So let's take them away. Imagine the simpler design: the loop prints directly.
No event types, no translation layer, less code. Many people's first agent
works this way, and for a single-user terminal script it is genuinely fine.

This level is about finding the exact moment it stops being fine.
""",
        steps=[
            Step(
                id="break-it",
                kind="predict",
                title="Four new requirements",
                body="""\
Your loop calls `print()` directly instead of yielding events. It works.

Now the product grows. Which of these requirements can that design still
satisfy without restructuring?

Think about each one concretely before answering.
""",
                question="Select every requirement a print-directly loop can still meet.",
                multi=True,
                choices=[
                    Choice(
                        id="json",
                        label="Add `--output json` for scripting.",
                        note="Breaks. The formatting decision was made deep inside the loop; the only way out is a format flag threaded through every print call.",
                    ),
                    Choice(
                        id="tui",
                        label="Add a full-screen TUI with a scrollback pane and a live status bar.",
                        note="Breaks badly. A TUI does not want a stream of text - it wants to *update a widget* when a message changes. print() cannot express that.",
                    ),
                    Choice(
                        id="test",
                        label="Assert in a test that a tool ran before the second model call.",
                        note="Breaks. You are reduced to capturing stdout and pattern-matching prose, which is why so many agent test suites are miserable.",
                    ),
                    Choice(
                        id="color",
                        label="Print assistant text in a different color.",
                        note="This one is fine, which is exactly the trap. Cosmetic changes stay easy, so the design feels healthy right up until a structural requirement arrives.",
                    ),
                ],
                answer=["color"],
                hints=[
                    "For each one ask: does this change *how output looks*, or does it change *who consumes the output*?",
                    "Three of these change the consumer. Only one changes the appearance.",
                ],
                after="""\
Only the color change survives.

{{diagram:frontend-fanout}}

The pattern: a print-directly loop has silently decided three things it had no
business deciding - the output *format*, the output *destination*, and the
output *timing*. Each is a policy question that belongs to whoever is
consuming, not to the engine.

Yielding events defers all three.
""",
                xp=20,
            ),
            Step(
                id="two-frontends",
                kind="implement",
                title="One run, two frontends",
                body="""\
Prove the claim rather than accepting it.

In the editor below, write two functions that consume **the same event
stream** from the loop you already wrote:

- `render_text(events)` - returns a human-readable transcript string.
- `render_json(events)` - returns a list of JSON-safe dicts.

Neither may call the provider, re-run the loop, or know anything about tools.
They receive events and produce output. That constraint *is* the architecture.

The tests check that both render the same run, and that adding a third renderer
would require no change to the loop.
""",
                target_file="renderers.py",
                test_file="tests/test_l03_renderers.py",
                specimen_paths=[
                    "tau/src/tau_coding/rendering/plain.py",
                    "tau/src/tau_coding/rendering/json.py",
                ],
                starter='''\
"""Two frontends over one event stream.

The point of this exercise is what these functions are *not allowed* to do:
call a provider, run the loop, or execute a tool. They consume events. That is
the entire contract between an agent core and a user interface.
"""

from __future__ import annotations

from typing import Any

from harnesskit.events import (
    AgentEndEvent,
    AgentEvent,
    AgentStartEvent,
    MessageEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    TurnEndEvent,
    TurnStartEvent,
)
from harnesskit.messages import AssistantMessage, ToolResultMessage, UserMessage


def render_text(events: list[AgentEvent]) -> str:
    """Render events as a readable transcript.

    Required shape (one per line):
        assistant: <final assistant text>
        tool(<name>): <result text>

    Use MessageEndEvent for assistant text - that is the event that carries the
    final message. MessageUpdateEvent carries partials, which you would use for
    live streaming but not for a final transcript.
    """
    lines: list[str] = []
    # TODO
    return "\\n".join(lines)


def render_json(events: list[AgentEvent]) -> list[dict[str, Any]]:
    """Render the same events as JSON-safe records.

    One dict per event, each with at least a "type" key. Message-bearing
    events should include a "role"; tool events should include "tool".
    """
    records: list[dict[str, Any]] = []
    # TODO
    return records
''',
                hints=[
                    "Iterate the list and branch on `isinstance(event, ...)` or on `event.type`.",
                    "For render_text, you only care about MessageEndEvent (for assistant messages) and ToolExecutionEndEvent.",
                    "An assistant message's text is `event.message.text`. A tool result's text is `event.result.content`.",
                    "For render_json, `{'type': event.type}` plus extras is enough. Do not try to serialize the whole dataclass.",
                ],
                after="""\
Two renderers, one loop, zero changes to the loop. A third - a web UI pushing
over SSE, say - would also need no changes.

This is the single most reused idea in agent architecture, and the reason this
course could even be built: the trace viewer you have been looking at is just
another renderer over the same events.
""",
                xp=35,
            ),
        ],
        reveal="""\
Tau makes this boundary explicit and load-bearing. From its design principles
(`tau/website/content/internals/design-principles.md`):

> **Events are the contract.** The agent communicates progress through a stream
> of provider-neutral events. Frontends render from those events, never from
> provider-specific chunks or internal control flow.

Look at `tau/src/tau_coding/rendering/` - `plain.py`, `json.py`,
`transcript.py` - plus the Textual TUI in `tau/src/tau_coding/tui/`. Four
frontends. The loop knows about none of them.

There is a second, less obvious payoff: `tau/src/tau_coding/rpc.py` exposes the
same event stream over stdin/stdout as JSON lines, so a completely external
program can drive the agent.

The tutor on this page is the same idea reached independently. It is a harness
in the browser, and the panel you type into renders from its event stream
alone - it never sees a provider chunk. You can read it in
`web-next/src/tutor/harness.js`: the architecture you are studying is the
architecture answering your questions.
""",
        transfer="""\
**Transferable:** when a core component formats, prints, or renders, it has
absorbed a decision belonging to its caller. Emitting structured events instead
is what makes one core serve a CLI, a TUI, a web app, a test harness, and an
external process. Ask of any agent codebase: *what is the contract between the
engine and the interface?* If the answer is "there isn't one", you have found
its ceiling.
""",
    )


def _l04() -> Level:
    return Level(
        id="l04-tools",
        title="The Tool Boundary",
        teaser="A tool is a schema and a function. Find out why that's enough.",
        question="Tools are where an agent touches the real world. What has to be true at that boundary?",
        minutes=25,
        requires=["l02-build-loop"],
        concepts=["tools", "isolation", "schema"],
        hook="""\
A tool is the only place an agent affects anything outside its own transcript.
Everything risky lives here: files get written, commands run, money gets spent.

Given that, you might expect an elaborate framework. Tau's is a dataclass with
five fields. This level is about why that is the right answer - and where the
real complexity hides instead.
""",
        steps=[
            Step(
                id="failure-modes",
                kind="predict",
                title="A tool raises. What should the loop do?",
                body="""\
Your `bash` tool runs a command that exits non-zero and raises
`CalledProcessError`. The model is mid-task and has made two other tool calls
in the same turn.
""",
                question="What is the right behavior?",
                choices=[
                    Choice(
                        id="catch-return",
                        label="Catch it, return an error result to the model, continue the loop.",
                        note="Correct. The model is often the best-placed component to recover - it can read the error, adjust, and retry. Crashing denies it that chance and loses the session.",
                    ),
                    Choice(
                        id="propagate",
                        label="Let it propagate and end the run.",
                        note="This throws away a recoverable situation. It also strands the tool call without a result, corrupting the transcript - the exact failure Level 7 covers.",
                    ),
                    Choice(
                        id="retry",
                        label="Retry the tool automatically a few times.",
                        note="The harness does not know whether the call is idempotent. Retrying `rm -rf` or a POST is worse than failing. Retry belongs at the transport layer, not here.",
                    ),
                    Choice(
                        id="skip",
                        label="Skip it silently and run the remaining calls.",
                        note="Silence is the worst option: the model sees a missing result and cannot tell whether it succeeded. An explicit error is strictly more useful than an absent one.",
                    ),
                ],
                answer="catch-return",
                hints=[
                    "Who in this system is capable of understanding 'permission denied' and trying something else?",
                    "Also consider the transcript: an unanswered tool call is a structural problem, not just a missing message.",
                ],
                after="""\
Tau states this directly in `loop.py`:

```python
except Exception as exc:  # noqa: BLE001 - tools are an isolation boundary
    return _error_result(str(exc)), True, updates
```

A blanket `except Exception` is usually a smell. Here it is the design: a tool
is untrusted code at the edge of the system, and the loop's job is to ensure a
tool can fail without taking the session with it.

Two invariants are preserved at once - the run survives, *and* every tool call
still gets exactly one result.
""",
                xp=20,
            ),
            Step(
                id="design-result",
                kind="explain",
                title="Design the result type before you look",
                body="""\
Here is a design question. Answer it before reading any specimen code.

Your `edit` tool just modified a file. Two different consumers need to know:

- **The model** needs enough to decide what to do next.
- **The UI** wants to show a syntax-highlighted diff with line numbers and a
  change count.

A naive `ToolResult` is just a string. That forces one of two bad outcomes:
either the UI has to parse prose back into structure, or you stuff the full
diff into the string and pay for it in tokens on every subsequent request.

{{diagram:tool-contract}}

Commit to a shape below, then say what it costs. The tutor will probe your
reasoning before you see Tau's answer.
""",
                stance_question="Which shape would you ship?",
                stances=[
                    Choice(
                        id="one-string",
                        label="One string. The UI parses what it needs out of it.",
                        note="Simplest, and it makes the UI depend on the exact wording of tool output. Change 'Edited 3 lines' to 'Changed 3 lines' and the diff viewer breaks.",
                    ),
                    Choice(
                        id="split",
                        label="Two fields: text for the model, structured data for the UI.",
                        note="This is Tau's answer. The split matters because the two have different costs - UI data is free, model data is paid for on every later request in the session.",
                    ),
                    Choice(
                        id="everything",
                        label="One rich object; send the whole thing to the model as JSON.",
                        note="The model does not need the syntax-highlighted diff, and you pay for those tokens on every subsequent turn of the session. Context is the scarce resource.",
                    ),
                    Choice(
                        id="callback",
                        label="The tool renders its own UI directly.",
                        note="This is the Level 3 mistake one layer down: the tool has absorbed a decision belonging to whoever is consuming it, and now cannot be used headlessly.",
                    ),
                ],
                writing_prompt=(
                    "Now defend it: what does your choice cost, and which "
                    "consumer pays?"
                ),
                specimen_paths=["tau/src/tau_agent/tools.py"],
                hints=[
                    "How many distinct audiences does a tool result have? Should one field serve both?",
                    "Consider the cost asymmetry: UI data is free, model data is paid for on every later request in the session.",
                ],
                after="""\
Tau's answer (`tau/src/tau_agent/tools.py`):

```python
class AgentToolResult(WireModel):
    content: list[TextContent | ImageContent]   # -> the model
    details: JSONValue = None                   # -> the UI only
    added_tool_names: list[str] | None = None
    terminate: bool | None = None
```

`content` is context, `details` is presentation. The split lets the TUI render
a full diff while the model sees "edited foo.py, 3 lines changed".

The two fields you likely did not invent are the interesting ones:

- `added_tool_names` - a tool can **add new tools** to the session. That is how
  skills and MCP work: a discovery tool returns new capabilities mid-run.
- `terminate` - a tool can end the run. For "I'm done" or approval-denied tools.

Both are small fields with large consequences. They turn the tool set from a
fixed list into something a run can modify as it goes.
""",
                xp=25,
            ),
            Step(
                id="write-tool",
                kind="implement",
                title="Write two real tools",
                body="""\
Implement `read` and `write` in the editor below.

Then handle the cases that make tools a security boundary rather than a
convenience:

- `read` on a nonexistent file must return an error result, not raise.
- `read` on a 5 MB file must truncate - an untruncated read can blow the
  context window in a single call.
- `write` must refuse paths that escape the working directory. The model may
  be acting on instructions from a file it just read; `../../.ssh/authorized_keys`
  is a real attack, not a hypothetical.

The tests cover all three.
""",
                target_file="tools_impl.py",
                test_file="tests/test_l04_tools.py",
                specimen_paths=["tau/src/tau_coding/tools.py"],
                starter='''\
"""Two real tools.

Notice how much of this file is about things going wrong. That ratio is
representative: tool implementations are mostly boundary conditions, because
this is where an agent meets a filesystem that does not care about its plans.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from harnesskit.tools import Tool, ToolResult

MAX_READ_BYTES = 64_000


def create_read_tool(cwd: str | Path) -> Tool:
    """A tool that reads a file, safely."""
    root = Path(cwd).resolve()

    async def execute(arguments: dict[str, Any]) -> ToolResult:
        # TODO
        #  - resolve arguments["path"] against root
        #  - missing file  -> ToolResult(content="Error: ...")  (do not raise)
        #  - large file    -> read at most MAX_READ_BYTES and say so in content
        #  - success       -> content is the text; details carries {"path", "bytes"}
        raise NotImplementedError

    return Tool(
        name="read",
        description="Read a file from disk.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        execute=execute,
    )


def create_write_tool(cwd: str | Path) -> Tool:
    """A tool that writes a file, refusing to escape the working directory."""
    root = Path(cwd).resolve()

    async def execute(arguments: dict[str, Any]) -> ToolResult:
        # TODO
        #  - resolve the target path
        #  - if it is not inside root, refuse with an error result
        #    hint: compare resolved paths, do not pattern-match on ".."
        #  - otherwise create parent dirs, write, and report bytes written
        raise NotImplementedError

    return Tool(
        name="write",
        description="Write a file to disk.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
        execute=execute,
    )
''',
                hints=[
                    "Resolve first, check second: `target = (root / path).resolve()`. Checking the raw string for '..' is defeated by symlinks and absolute paths.",
                    "`target.is_relative_to(root)` is the containment check you want (Python 3.9+).",
                    "For truncation, read bytes and compare length to MAX_READ_BYTES; append a clear marker like '... [truncated]' so the model knows it saw a partial file.",
                    "Return `ToolResult(content='Error: file not found: ...')` for missing files. The loop marks it as an error; your job is just not to raise.",
                ],
                after="""\
Compare with `tau/src/tau_coding/tools.py` - around 1,200 lines for four tools.

Almost none of it is the operation itself. It is truncation strategy (head vs.
tail), line-ending preservation, diff generation, image handling, cancellation
during long `bash` runs, and byte-accurate limits.

The *interface* is tiny and the *implementation* is large. That is the correct
shape, and it tells you where to look when evaluating an agent: the tool
contract shows you the architecture, the tool implementations show you how much
real-world experience the project has absorbed.
""",
                xp=40,
            ),
        ],
        reveal="""\
Tau's `AgentTool` is a frozen dataclass with a name, a label, a description, a
JSON schema, an async executor, and some optional prompt/render metadata. No
registry, no base class, no plugin system, no decorators.

From the design principles:

> **Tools are ordinary typed functions.** A tool is a name, a description, a
> JSON input schema, and an async executor that returns a structured result.
> There's no framework magic - which makes tools easy to read, test, and add.

The restraint is the design. Every piece of machinery you add here becomes
machinery every tool author must learn.
""",
        transfer="""\
**Transferable:** evaluate any agent's tool layer on three questions. (1) Can a
tool fail without killing the run? (2) Is model-facing content separated from
UI-facing data? (3) Can the tool set change during a run? Those three answers
tell you more about an agent's maturity than its model list does.
""",
    )


# --------------------------------------------------------------------------
# Act II - State
# --------------------------------------------------------------------------


def act_two() -> Act:
    return Act(
        id="act2",
        title="Act II - Memory",
        subtitle="The loop is stateless. Everything hard about agents is in the state around it.",
        levels=[_l05(), _l06(), _l07(), _l08()],
    )


def _l05() -> Level:
    return Level(
        id="l05-harness",
        title="The Harness",
        teaser="Three steps: hold state, publish events, guard against races.",
        question="Your loop takes a message list as an argument. Who owns that list?",
        minutes=40,
        requires=["l02-build-loop", "l03-events"],
        concepts=["harness", "state-ownership", "layering"],
        hook="""\
Your loop is a *function*. It receives `messages`, mutates it, and returns. It
owns nothing and remembers nothing.

That is deliberate - but it means somebody else has to hold the conversation.
This level builds that somebody, in three steps:

```
A. hold the transcript   prompt() twice and have the second remember the first
B. publish events        let something watch the run without consuming it
C. guard the run         make a second concurrent run impossible
```

Each step adds roughly one method and has its own tests. You edit the same
file throughout, so step C's version is the one Level 6 and your capstone use.
""",
        steps=[
            Step(
                id="who-owns",
                kind="predict",
                title="Two prompts in a row",
                body="""\
A user sends "read config.py", the run completes, and then they send "now
explain it".

For the second prompt to work, the transcript from the first must still exist.
Your `run_agent_loop` cannot provide that - it returned.
""",
                question="Where should the conversation transcript live?",
                choices=[
                    Choice(
                        id="harness",
                        label="In a stateful object that wraps the loop and calls it per prompt.",
                        note="Correct. This is the harness. The loop stays a pure function of its inputs; the harness supplies continuity.",
                    ),
                    Choice(
                        id="global",
                        label="In a module-level global the loop reads and writes.",
                        note="Works for exactly one conversation per process. It rules out multiple sessions, parallel agents, and most testing.",
                    ),
                    Choice(
                        id="ui",
                        label="In the UI, passed back in each time.",
                        note="Tempting since the UI already renders them. But then every frontend reimplements transcript management, and they will disagree about details like whether a failed turn is retained.",
                    ),
                    Choice(
                        id="loop",
                        label="The loop should keep its own state between calls.",
                        note="This makes the loop stateful, which costs you testability and the ability to run several agents at once. The split exists precisely to avoid this.",
                    ),
                ],
                answer="harness",
                hints=[
                    "The loop is an async generator. What happens to its local variables when it finishes?",
                    "Think about running two conversations in one process. Which options survive?",
                ],
                after="""\
This is the split Tau puts at the top of its README:

```text
AgentHarness  = reusable brain      (stateful: owns the transcript)
CodingSession = coding environment  (tools, persistence, project context)
TUI           = one possible frontend
```

The loop is a *verb*; the harness is a *noun*. Keeping them separate means the
loop stays trivially testable - every test in Level 2 handed it a plain list.

{{diagram:loop-vs-harness}}
""",
                xp=20,
            ),
            Step(
                id="hold-state",
                kind="implement",
                title="Step A - hold the transcript",
                body="""\
Start with the smallest harness that is actually useful: one that remembers.

In the editor below, implement:

- `prompt(text)` - append a `UserMessage` to `self._messages`, then return
  `self._run(...)`
- `continue_()` - same, but add no user message
- `_run(...)` - call `run_agent_loop` and yield everything it yields

Ignore listeners, guards and cancellation for now; step B and C add those.

**What `_run` must pass through**

`_run` must pass `self._messages` to the loop. Your loop mutates that list in
place (Level 2, step 3), so after the run the harness's transcript already
contains the new messages. You do not append them yourself.

Four tests.
""",
                target_file="harness.py",
                test_file="tests/test_l05a_transcript.py",
                starter='''\
"""A stateful agent harness wrapping your loop.

The loop is a function; this is the object that gives it continuity.

You will edit this file three times - steps A, B and C of Level 5 - so leave
room for the parts you have not written yet.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from harnesskit.events import AgentEvent
from harnesskit.messages import AgentMessage, UserMessage
from harnesskit.tools import SimpleCancellationToken, Tool

from loop import run_agent_loop


@dataclass
class AgentHarnessConfig:
    provider: Any
    model: str = "scripted"
    system: str = ""
    tools: list[Tool] = field(default_factory=list)
    max_turns: int | None = None


class AgentHarness:
    """Owns a transcript; delegates execution to the pure loop."""

    def __init__(
        self,
        config: AgentHarnessConfig,
        *,
        messages: Sequence[AgentMessage] = (),
    ) -> None:
        self._config = config
        self._messages: list[AgentMessage] = list(messages)
        self._listeners: list[Callable[[AgentEvent], Any]] = []   # step B
        self._running = False                                     # step C
        self._signal: SimpleCancellationToken | None = None       # step C

    @property
    def messages(self) -> tuple[AgentMessage, ...]:
        return tuple(self._messages)

    @property
    def config(self) -> AgentHarnessConfig:
        return self._config

    @property
    def is_running(self) -> bool:
        return self._running

    def replace_messages(self, messages: Sequence[AgentMessage]) -> None:
        self._messages = list(messages)

    # ---------------------------------------------------------- step A

    def prompt(self, text: str) -> AsyncIterator[AgentEvent]:
        """Append a user message and run."""
        # TODO: append UserMessage(content=text) to self._messages,
        #       then `return self._run()`
        raise NotImplementedError

    def continue_(self) -> AsyncIterator[AgentEvent]:
        """Run without a new user message."""
        # TODO
        raise NotImplementedError

    async def _run(self) -> AsyncIterator[AgentEvent]:
        """Shared execution path."""
        # TODO
        #   async for event in run_agent_loop(
        #       provider=self._config.provider,
        #       model=self._config.model,
        #       system=self._config.system,
        #       messages=self._messages,
        #       tools=self._config.tools,
        #       max_turns=self._config.max_turns,
        #   ):
        #       yield event
        raise NotImplementedError
        yield  # pragma: no cover - keeps this an async generator
''',
                hints=[
                    "`prompt` is NOT async. It appends the message, then `return self._run()` - returning the generator object.",
                    "`_run` IS an async generator: `async for event in run_agent_loop(...): yield event`.",
                    "Pass `messages=self._messages` (the list itself, not a copy). The loop appends to it, which is how the harness ends up holding the new messages.",
                    "Once your `_run` has a real `yield`, delete the trailing `raise NotImplementedError` and bare `yield` placeholder.",
                ],
                after="""\
That is already a useful object: it remembers. Two prompts in a row now share
a conversation, and the provider can see the earlier exchange.

Notice how little code it took. The harness is not complicated - it is just
the thing that holds the list.
""",
                xp=25,
            ),
            Step(
                id="add-listeners",
                kind="implement",
                title="Step B - publish events to listeners",
                body="""\
Right now the only way to see events is to consume the generator. That is
fine for a UI, but other things need to watch too - a persistence layer, a
logger, a metrics counter.

Add to the same file:

- `subscribe(listener)` - register a callback, **return a function that
  removes it**
- in `_run`, call every listener for each event

**The ordering rule, and why it matters later**

Notify listeners *before* you `yield` the event:

```python
async for event in run_agent_loop(...):
    await self._notify(event)   # first
    yield event                 # then
```

It looks arbitrary. It is not. If the consumer is cancelled mid-run, the code
after `yield` never resumes - but a listener that already ran has already done
its work. Level 9 is an entire level about a real data-loss bug caused by
getting this backwards.

Four tests, and the last one checks exactly this ordering.
""",
                target_file="harness.py",
                test_file="tests/test_l05b_listeners.py",
                specimen_paths=["tau/src/tau_agent/harness.py"],
                hints=[
                    "Add a `_notify` helper: `for listener in list(self._listeners): result = listener(event)`.",
                    "Listeners may be sync or async. Use `from inspect import isawaitable` and `if isawaitable(result): await result`.",
                    "subscribe: append to the list, then return a closure that removes it. Wrap the removal in `contextlib.suppress(ValueError)` in case it is called twice.",
                    "Iterate `list(self._listeners)` rather than the list itself, so a listener that unsubscribes during delivery cannot corrupt the iteration.",
                ],
                after="""\
A subscriber is now structurally different from a consumer: it runs on the
harness's own call stack.

Hold on to that distinction. It is the single most useful idea in Act III.
""",
                xp=25,
            ),
            Step(
                id="add-guards",
                kind="implement",
                title="Step C - guard the run, support cancel",
                body="""\
Last step. Two runs mutating one transcript from two coroutines would produce
interleavings that providers reject - intermittently, under load. Make it
structurally impossible instead of debugging it later.

Add:

- `_running` set to `True` in `prompt()`/`continue_()`, cleared in a
  `finally` inside `_run`
- `RuntimeError` if `prompt()` is called while already running
- `cancel()` setting a `SimpleCancellationToken` that `_run` passes to the loop

**One ordering detail that decides whether this works**

`prompt()` must stay a *normal* function, not `async def`.

If it were `async def`, `_running` would only flip when someone starts
iterating. Two calls to `prompt()` would both succeed and you would get the
race you were trying to prevent. One test checks this specifically by calling
`prompt()` twice without awaiting either.

(What *should* happen when a user types mid-run is a real question. Hold it -
that is Level 6.)

Five tests.
""",
                target_file="harness.py",
                test_file="tests/test_l05c_guards.py",
                specimen_paths=["tau/src/tau_agent/harness.py"],
                hints=[
                    "In `prompt()`: check the guard, set `self._running = True`, THEN return `self._run()`. All three before any iteration happens.",
                    "In `_run`, wrap the whole `async for` in try/finally and clear `self._running = False` in the finally.",
                    "`cancel()` just calls `self._signal.cancel()` if a signal exists. Create the token at the top of `_run` and store it on self.",
                    "Pass `signal=signal` through to `run_agent_loop` so a cancelled token actually stops tool execution.",
                    "Tau does exactly this - read `prompt_message` in tau/src/tau_agent/harness.py: `_ensure_not_running()`, then `self._running = True`, then `return self._run(...)`.",
                ],
                after="""\
One detail worth dwelling on: you set `_running = True` inside `prompt()`
rather than inside `_run()`.

Had you set it in `_run`, the flag would only flip when someone started
*iterating* the generator - and the guard would never fire in time. Tau does
exactly this, for exactly this reason.

Small ordering decisions like this are most of what separates a harness that
works from one that works under load.
""",
                xp=30,
            ),
        ],
        reveal="""\
Read `tau/src/tau_agent/harness.py` (259 lines). Beyond what you built:

- **Queues** (`_steering_queue`, `_follow_up_queue`) - Level 6.
- **`_append_interrupted_tool_results`** - Level 7.
- **Listener notification before yield**, with a comment explaining that the
  consumer is usually gone during cancellation - Level 9.

Also note what is *absent*: no file paths, no provider configuration, no slash
commands, no rendering. The harness is the portable brain. Everything
application-specific lives one layer up in `CodingSession`.

That boundary is testable, and Tau tests it: `tau_agent` must not import
`tau_coding`. An architectural rule that is not enforced is a wish.
""",
        transfer="""\
**Transferable:** separating the pure loop from the stateful harness is near
universal, because they have genuinely different lifetimes - a loop lives for
one run, a harness for a conversation. When reading a new agent codebase, find
these two things first. If they are fused, expect difficulty in testing,
multi-session support, and cancellation.
""",
    )
def _l06() -> Level:
    return Level(
        id="l06-steering",
        title="Interruption",
        teaser="The user types while the agent is working. Now what?",
        question="A run is mid-flight and the user has more to say. Where does it go?",
        minutes=20,
        requires=["l05-harness"],
        concepts=["steering", "queues", "concurrency"],
        hook="""\
The agent is six tool calls into a refactor. The user notices it is editing the
wrong module and types: *"wait, that's the generated file - don't touch it"*.

Your harness raises `RuntimeError: already running`.

Technically correct. Completely useless. This level is about the design space
that opens up here, which is larger and more interesting than it first appears.
""",
        steps=[
            Step(
                id="design-space",
                kind="predict",
                title="Four options",
                body="""\
The user submits text during an active run. Consider each option as a real
product decision - each one is shipped by some agent somewhere.
""",
                question="Which single approach best handles the 'wrong file' correction above?",
                choices=[
                    Choice(
                        id="queue-turn",
                        label="Queue it and inject it after the current turn, before the next model call.",
                        note="Correct for a correction. The in-flight tool batch finishes (so no half-applied state), but the model sees the correction before deciding what to do next. Pi and Tau call this steering.",
                    ),
                    Choice(
                        id="reject",
                        label="Reject it and ask the user to wait.",
                        note="Safe and honest, but it means the user watches a known mistake unfold. Correction is the single most valuable interaction in a coding agent.",
                    ),
                    Choice(
                        id="abort",
                        label="Cancel the run immediately and start a new one with the new message.",
                        note="Loses all progress, and cancels mid-tool-call - which strands tool calls without results. Sometimes right (Esc), but too destructive to be the default for typed input.",
                    ),
                    Choice(
                        id="parallel",
                        label="Start a second run in parallel.",
                        note="Two runs mutating one transcript. This is the exact race your harness forbids in Level 5.",
                    ),
                ],
                answer="queue-turn",
                hints=[
                    "What is the earliest moment the model could act on the correction? What is the latest moment the harness can safely insert a message?",
                    "Those two are the same point: the boundary between turns.",
                ],
                after="""\
{{diagram:steering-timing}}

The turn boundary is the natural injection point: the transcript is in a
consistent state, every tool call has its result, and the next provider request
has not yet been built.

Tau distinguishes two queues with different timing:

- **steering** - injected after the current turn, before the next model call.
  *"Stop, change direction."*
- **follow-up** - injected only when the run would otherwise end.
  *"When you're done, also update the changelog."*

Same mechanism, different urgency. Notice this is a *product* decision
expressed in *architecture*: deciding when a message becomes visible to the
model is a UX question that the loop must structurally support.
""",
                xp=20,
            ),
            Step(
                id="implement-steering",
                kind="implement",
                title="Step A - add the queues",
                body="""\
Two steps. This one is pure bookkeeping on the harness; the loop stays
untouched until step B.

In the editor below, add:

- `steer(text)` - append a `UserMessage` to a steering queue
- `follow_up(text)` - append to a separate follow-up queue
- `has_queued_messages()` - is either queue non-empty?
- `_drain(queue)` - return **one** message as a tuple, removing it

Use `collections.deque` and `popleft()`, so messages come out in the order
they were typed.

**Queuing is not saying**

Queuing is not saying. A queued message must not appear in `self._messages`
until the loop actually injects it. If the run ends first, that message was
never part of the conversation - and the transcript must reflect that
honestly.

One test checks exactly this.

Four tests.
""",
                target_file="harness.py",
                test_file="tests/test_l06a_queues.py",
                specimen_paths=["tau/src/tau_agent/harness.py"],
                hints=[
                    "In `__init__`: `self._steering = deque()` and `self._follow_up = deque()`. Import deque from collections.",
                    "`steer(text)` is one line: `self._steering.append(UserMessage(content=text))`.",
                    "`_drain(queue)` returns a tuple: `return (queue.popleft(),) if queue else ()`. Returning a tuple keeps the loop's call site uniform whether or not anything was queued.",
                    "Do NOT touch self._messages in steer() or follow_up(). That is the point of the fourth test.",
                ],
                after="""\
The queues exist. Nothing reads them yet - which is fine, and worth noticing:
you have added a feature's *state* without touching its *control flow*.

Step B is where the control flow gets interesting.
""",
                xp=25,
            ),
            Step(
                id="inject-steering",
                kind="implement",
                title="Step B - inject them at the right moment",
                body="""\
Now the loop has to actually use the queues, and this is the genuinely tricky
part of Level 6: a loop that can resume *after it has decided to stop*.

Your `run_agent_loop` gains two optional parameters, each a zero-argument
callable returning a sequence of messages:

```python
get_steering_messages=None,
get_follow_up_messages=None,
```

and the harness passes `self._drain` closures for both.

**The control flow**

Sketch it before writing it. The outer loop exists purely so a follow-up can
restart a finished run:

```
pending = get_steering_messages()
while True:
    has_more_tools = True
    while has_more_tools or pending:
        <inject pending into the transcript, emitting message events>
        pending = ()
        <provider call, tool execution, as before>
        has_more_tools = bool(tool_calls)
        pending = get_steering_messages()
    follow_ups = get_follow_up_messages()
    if follow_ups:
        pending = follow_ups
        continue          # resurrect the run
    break
```

Two things this shape buys you:

- `while has_more_tools or pending` means a steering message continues a run
  that had no tool calls left.
- The outer `while True` with `continue` means a follow-up can restart one
  that had genuinely finished.

**Injection point**

Drain steering at the *end* of a turn, after tool results are appended. A
message injected mid-batch would sit before tool results that logically
precede it, and the model would reason about a world that never existed.

Five tests.
""",
                target_file="harness.py",
                test_file="tests/test_l06_steering.py",
                specimen_paths=["tau/src/tau_agent/loop.py", "tau/src/tau_agent/harness.py"],
                hints=[
                    "You are editing BOTH files: `loop.py` gains the two parameters and the nested loop; `harness.py` passes `get_steering_messages=lambda: self._drain(self._steering)` and the follow-up equivalent.",
                    "When injecting a pending message: append it to both `messages` and `new_messages`, then yield MessageStartEvent and MessageEndEvent for it, exactly as the loop does for a prompt.",
                    "Set `pending = ()` immediately after injecting, or you will inject the same message forever.",
                    "The `break` on max_turns now sits inside the inner while - make sure it does not accidentally skip the follow-up check.",
                    "Tau's version is at tau/src/tau_agent/loop.py around line 98. Read it if your control flow will not converge - but sketch yours first, because the shape IS the lesson.",
                ],
                after="""\
You built the mechanism behind "type while it works" in every good coding
agent.

Note the ordering guarantee you preserved: steering lands *after* the current
tool batch completes. The alternative would mean tool results arriving after a
message that logically precedes them.
""",
                xp=35,
            ),
        ],
        reveal="""\
`tau/src/tau_agent/harness.py` adds a detail worth copying: `QueueUpdateEvent`.

When you queue a message, the harness *emits an event* so the UI can show a
pending badge. The queue is internal state, but its existence is public
information the user needs - otherwise typing during a run feels like typing
into a void.

Also see `queue_mode` in `AgentHarnessConfig`: `"one_at_a_time"` (default)
drains a single message per boundary; `"all"` drains the whole queue. Both are
defensible; making it configurable rather than deciding for the user is a
reasonable call at a library boundary.
""",
        transfer="""\
**Transferable:** any long-running agent needs a story for mid-flight input.
The question "where is it safe to inject a message?" has one good answer -
a turn boundary - and recognizing that immediately tells you where to look in
an unfamiliar codebase. If a system has no such mechanism, its users are stuck
watching mistakes complete.
""",
    )


def _l07() -> Level:
    return Level(
        id="l07-invariant",
        title="The Invariant",
        teaser="Break a rule you didn't know existed. Watch a provider reject you.",
        question="Which transcript shapes are illegal, and who is responsible for preventing them?",
        minutes=30,
        requires=["l05-harness"],
        concepts=["invariants", "tool-pairing", "cancellation", "repair"],
        hook="""\
Everything works. Then a user presses Ctrl-C during a tool call, and the next
message in that session fails with:

```
400 Bad Request: messages.3: `tool_use` ids were found without `tool_result`
blocks immediately after
```

Not a crash in your code. A *provider rejection* - and the session is now
permanently broken, because the bad shape is saved on disk.

This level is about an invariant you have been maintaining accidentally, and
what it takes to maintain it on purpose.
""",
        steps=[
            Step(
                id="break-it",
                kind="implement",
                title="Break it deliberately",
                body="""\
Reproduce the bug before you fix it.

In the editor below, write `make_broken_transcript()` returning a
message list where an assistant message has a tool call with **no matching
tool result**. Exactly what a cancelled tool execution leaves behind.

Then write `validate(messages)` returning a list of problems. It must detect
four distinct shapes:

1. a tool call with no result
2. a tool result with no call
3. a result not immediately after its call
4. duplicate results for one call id

The tests check that your validator catches all four, and - importantly - that
it does *not* flag a healthy transcript. A validator that cries wolf is worse
than none.
""",
                target_file="break_invariant.py",
                test_file="tests/test_l07_invariant.py",
                specimen_paths=["tau/src/tau_agent/tool_history.py"],
                starter='''\
"""Break the tool-pairing invariant, then detect the breakage.

The invariant, stated precisely:

    Every tool call in an assistant message is followed IMMEDIATELY by exactly
    one tool result message carrying the same tool_call_id, in call order.

"Immediately" is doing real work in that sentence. A result that appears two
messages later still fails on several providers.
"""

from __future__ import annotations

from harnesskit.messages import (
    AgentMessage,
    AssistantMessage,
    TextContent,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)


def make_broken_transcript() -> list[AgentMessage]:
    """Return a transcript with a dangling tool call.

    Shape to produce:
        user       "read config.py"
        assistant  [ToolCall(id="call_1", name="read")]
        user       "actually never mind"      <- no tool result!
    """
    # TODO
    raise NotImplementedError


def validate(messages: list[AgentMessage]) -> list[str]:
    """Return a list of invariant violations; empty means healthy.

    Detect:
      - "dangling call: <id>"      a call with no result
      - "orphan result: <id>"      a result with no call
      - "misplaced result: <id>"   a result not immediately after its call
      - "duplicate result: <id>"   more than one result for a call
    """
    problems: list[str] = []
    # TODO
    return problems
''',
                hints=[
                    "Walk the list with an index. When you see an AssistantMessage with tool calls, the next N messages should be its results, in order.",
                    "Collect all call ids and all result ids first; set differences give you dangling and orphan cases directly.",
                    "For 'misplaced', compare the position where a result *is* against where it *should* be (assistant index + call offset).",
                    "For duplicates, count results per tool_call_id with a Counter and flag any count > 1.",
                ],
                after="""\
{{diagram:transcript-pairing}}

You can now detect the corruption. The harder question is who prevents it.

Tau answers at three layers, which is itself the lesson:

1. **Prevention** - the harness appends a synthetic "Tool call interrupted by
   user" result in its `finally` block when a run is cancelled.
2. **Repair at load** - `repair_tool_history()` fixes transcripts loaded from
   disk, because older versions already wrote bad ones.
3. **Repair at send** - `_provider_context()` repairs in memory on every
   request, as a final backstop for callers who built a harness directly.

Defense in depth, because the cost of a broken transcript is an unusable
session, and the repair is cheap and deterministic.
""",
                xp=40,
            ),
            Step(
                id="repair-policy",
                kind="explain",
                title="What would you do with an orphan result?",
                body="""\
You are writing the repair function. You hit a `ToolResultMessage` whose
`tool_call_id` matches no call in the transcript.

Your options:

- **Drop it.** Loses information that a tool actually ran.
- **Synthesize a matching call.** Keeps the result, but you must invent the
  call's name and arguments - and you do not know them.
- **Convert it to a user message** so the content survives as context.
- **Refuse to load the session** and tell the user it is corrupt.

Pick one, then say what it costs. Then the harder question: does your answer
change if that orphan holds the output of a ten-minute test run?
""",
                stance_question="What do you do with the orphan result?",
                stances=[
                    Choice(
                        id="drop",
                        label="Drop it.",
                        note="Tau's answer, and it is a real loss - not a free one. The argument is not that dropping is harmless but that every alternative requires inventing data the model will then treat as fact.",
                    ),
                    Choice(
                        id="synthesize",
                        label="Synthesize a matching call so the pair is complete.",
                        note="You would have to invent the call's name and arguments. The model cannot distinguish your invention from something it actually did, which is the worst failure mode available here.",
                    ),
                    Choice(
                        id="convert",
                        label="Convert it to a user message so the content survives.",
                        note="Defensible, and it changes the meaning: the model now believes the user said this. For a ten-minute test run that may be the right trade - which is why the second question is in the brief.",
                    ),
                    Choice(
                        id="refuse",
                        label="Refuse to load the session and tell the user it is corrupt.",
                        note="Honest, and it strands exactly the long sessions where the most work has accumulated. Repair exists because prevention arrived too late for sessions already on disk.",
                    ),
                ],
                writing_prompt=(
                    "Why that one - and what would change your mind?"
                ),
                specimen_paths=["tau/src/tau_agent/tool_history.py"],
                hints=[
                    "A repair's worst failure mode is being *plausible but wrong*. Which option risks fabricating something the model will then trust?",
                    "Consider who the repair is for. Is it protecting the user's data, or protecting the provider request from rejection?",
                ],
                after="""\
Tau drops it, and documents the reason in the docstring:

> Results with no call are omitted because a missing call's arguments cannot be
> reconstructed safely.

Note the shape of the argument. Not "dropping is harmless" - it plainly is not -
but "every alternative requires inventing data the model will treat as fact."

Read the whole policy in `tau/src/tau_agent/tool_history.py`:

1. Existing results move to sit directly after their calls, in call order.
2. A call with no result gets a deterministic interruption error.
3. A result with no call is omitted.
4. Duplicates collapse; a real result beats a synthetic interruption.

And `ToolHistoryRepair` returns *counters* for what it changed, which get
written to the session as a diagnostic entry. The repair is observable rather
than silent - you can tell, later, that it happened.
""",
                xp=30,
            ),
        ],
        reveal="""\
Read `tau/dev-notes/tool-history-recovery.md`. It is a short document and it
shows you the actual sequence: prevention shipped first, then real user
sessions were already corrupt, so recovery had to be added.

> Prevention stops new corruption, but it does not make existing user sessions
> usable.

That sentence is the whole justification for the second mechanism. It is also a
good example of the kind of reasoning you will not find by reading source code
alone - which is why, when evaluating an unfamiliar project, its design notes
are often worth more than its code.
""",
        transfer="""\
**Transferable:** every agent has transcript invariants enforced by *providers*
rather than by its own type system - which means violations surface as remote
400s, often long after the code that caused them. When you meet a new agent
codebase, ask: what shapes are illegal? What enforces them? What happens to
sessions that were corrupted before the fix? The answers locate most of the
genuinely hard bugs in the system.
""",
    )


def _l08() -> Level:
    return Level(
        id="l08-context",
        title="Running Out of Room",
        teaser="The context window fills. Something has to give.",
        question="A long session exceeds the model's context window. What do you throw away?",
        minutes=30,
        requires=["l07-invariant"],
        concepts=["compaction", "context-window", "summarization"],
        hook="""\
Two hours into a refactor. Forty tool calls, several large file reads. The next
request returns:

```
400: prompt is too long: 213,041 tokens > 200,000 maximum
```

The session is not finished and the user does not want to start over. Something
must be removed from the context - and whatever you choose, you are choosing
what the agent forgets.
""",
        steps=[
            Step(
                id="what-to-drop",
                kind="predict",
                title="Choose your loss",
                body="""\
Four strategies. Each loses something different.

{{diagram:compaction-tradeoff}}

Pick the one that best preserves the agent's ability to *continue the task*.
Note that the widest bar is not the answer: how much survives matters less
than whether the surviving part is the part the agent still needs.
""",
                question="Which strategy is the best default?",
                choices=[
                    Choice(
                        id="summarize",
                        label="Ask the model to summarize the old messages, then replace them with the summary.",
                        note="Correct as a default. It is the only option that preserves decisions and constraints from early in the session - usually the most load-bearing context there is.",
                    ),
                    Choice(
                        id="sliding",
                        label="Drop the oldest messages until it fits.",
                        note="Cheap and predictable, but it deletes the original task description and every constraint the user set at the start. The agent keeps working and quietly drifts.",
                    ),
                    Choice(
                        id="tool-results",
                        label="Drop old tool results, keep all the prose.",
                        note="A genuinely good heuristic - stale file contents are the bulk of the tokens. Worth combining with summarization, but alone it breaks the pairing invariant from Level 7.",
                    ),
                    Choice(
                        id="fail",
                        label="Stop and tell the user to start a new session.",
                        note="Honest, and some tools do this. But long sessions are exactly where an agent has accumulated the most useful context - abandoning them is the costliest moment to give up.",
                    ),
                ],
                answer="summarize",
                hints=[
                    "What was said at the very start of a session that nothing later restates? Usually: the actual goal.",
                    "Which strategies would let the agent silently forget a constraint like 'don't touch the generated files'?",
                ],
                after="""\
Summarization wins because the information density of a session is wildly
uneven. A 40,000-token file read may be worth one line now. The user's opening
constraint is worth keeping verbatim forever.

Note the third option is not wrong, just incomplete - and watch how Tau
combines ideas: it summarizes *and* keeps recent messages intact, because the
last few turns are where precise detail still matters.
""",
                xp=20,
            ),
            Step(
                id="implement-compaction",
                kind="implement",
                title="Step A - measure, and find a safe split point",
                body="""\
Compaction is two jobs. This step is the first: decide *where* to cut. The
next one does the summarizing.

In the editor below, write:

- `estimate_tokens(messages)` - roughly how big is this transcript?
- `find_split_point(messages, keep_recent_tokens)` - the index where "recent"
  begins

**Measuring**

`len(text) // 4` is the standard rough estimate and is what Tau uses. It is
not tokenization - it is deliberately approximate, and Step C explains what
you do about being wrong.

**The split point and the pairing invariant**

The split point must **not** land between an assistant message holding tool
calls and its tool results.

If it does, you have just recreated Level 7's bug inside the fix for a
different problem: the summary half keeps the call, the retained half keeps an
orphan result, and the next request gets rejected.

So after you find the boundary by token budget, walk it **earlier** until it
is not a `ToolResultMessage`. That pulls the whole call-plus-results group
into the half being summarized.

Five tests. The last one tries several budgets to make sure you did not just
get lucky.
""",
                target_file="compaction.py",
                test_file="tests/test_l08a_split.py",
                specimen_paths=["tau/src/tau_coding/context_window.py"],
                starter='''\
"""Context compaction.

Compaction is the clearest case in the whole system of durable history and
model context being different things. The JSONL record on disk never shrinks;
what the model sees does.

You will edit this file twice - steps A and B of Level 8.
"""

from __future__ import annotations

from collections.abc import Sequence

from harnesskit.messages import (
    AgentMessage,
    AssistantMessage,
    ToolResultMessage,
    UserMessage,
)

CHARS_PER_TOKEN = 4
SUMMARY_PREFIX = "Previous conversation summary:\\n"


# ------------------------------------------------------------- step A

def estimate_tokens(messages: Sequence[AgentMessage]) -> int:
    """Roughly estimate the token cost of a transcript."""
    # TODO: for each message, add len(text) // CHARS_PER_TOKEN plus a small
    #       per-message overhead (4 is fine). Use getattr(m, "text", "").
    raise NotImplementedError


def find_split_point(messages: Sequence[AgentMessage], keep_recent_tokens: int) -> int:
    """Return the index where 'recent' begins.

    Walk backwards accumulating tokens until keep_recent_tokens is reached.

    THEN adjust: the returned index must not be a ToolResultMessage, because
    that would separate a result from the call that produced it. Move the
    boundary EARLIER until it is not.
    """
    # TODO
    raise NotImplementedError


# ------------------------------------------------------------- step B

async def compact(
    messages: Sequence[AgentMessage],
    *,
    provider,
    model: str = "scripted",
    threshold_tokens: int = 100_000,
    keep_recent_tokens: int = 20_000,
) -> list[AgentMessage]:
    """Compact a transcript if it exceeds the threshold."""
    raise NotImplementedError
''',
                hints=[
                    "estimate_tokens: `sum(len(getattr(m, 'text', '')) // CHARS_PER_TOKEN + 4 for m in messages)`.",
                    "find_split_point: iterate `range(len(messages) - 1, -1, -1)`, accumulate the same per-message cost, remember the index, and break once you pass keep_recent_tokens.",
                    "Then the safety walk: `while index > 0 and isinstance(messages[index], ToolResultMessage): index -= 1`.",
                    "Think about why you move EARLIER rather than later: moving later would leave the assistant's tool call in the summarized half and its result in the kept half - exactly backwards.",
                ],
                after="""\
You can now measure a transcript and cut it in a place that will not break the
next request.

The boundary rule is a good example of how invariants compound. Level 7's
pairing rule is not a local concern of the loop - it constrains compaction,
persistence, branching, and resume. Every component that reorders or drops
messages has to respect it.
""",
                xp=30,
            ),
            Step(
                id="summarize",
                kind="implement",
                title="Step B - summarize and rebuild",
                body="""\
Now the other half: turn the old messages into a summary and assemble the new
transcript.

Add `compact(...)` to the same file:

1. If `estimate_tokens(messages) <= threshold_tokens`, return them unchanged
   and **do not call the provider**. Compaction is not free.
2. Otherwise split at `find_split_point`.
3. Ask the provider to summarize the old half.
4. Return `[UserMessage(SUMMARY_PREFIX + summary), *recent]`.

**Calling the provider directly**

You are not using the loop here - just one request. Same shape as Level 2
step 1: iterate `provider.stream_response(...)` and take the text off the
`AssistantDoneEvent`.

**What makes a good summary prompt**

Before you write one, look at Tau's `SUMMARIZATION_PROMPT` in
`tau/src/tau_coding/context_window.py`. It demands rigid structure - Goal,
Constraints, Progress, Key Decisions, Next Steps - and says explicitly:

> Preserve exact file paths, function names, and error messages.

That line exists because free-form summaries lose precisely the tokens hardest
to recover. "I fixed the auth bug" is useless; `src/auth/session.py:142` lets
work continue. A summary is not a description of the conversation - it is a
handoff document to a future instance of the model.

Six tests.
""",
                target_file="compaction.py",
                test_file="tests/test_l08_compaction.py",
                specimen_paths=["tau/src/tau_coding/context_window.py"],
                hints=[
                    "Guard first: `if estimate_tokens(messages) <= threshold_tokens: return list(messages)`. One test checks the provider was never called.",
                    "`split = find_split_point(messages, keep_recent_tokens)`, then `old, recent = messages[:split], messages[split:]`.",
                    "To summarize: `async for ev in provider.stream_response(model=model, system='Summarize.', messages=old, tools=[]): if isinstance(ev, AssistantDoneEvent): summary = ev.message.text`.",
                    "Import AssistantDoneEvent from harnesskit.provider_events.",
                    "Return `[UserMessage(content=SUMMARY_PREFIX + summary), *recent]` - the prefix is what tells the model it is reading a compaction rather than a user instruction.",
                ],
                after="""\
Compaction works. Note what the tests verified: the transcript shrank, recent
messages survived *verbatim*, the summary is labelled, and no tool result was
orphaned.

That last one is why Step A existed separately. The interesting part of
compaction is not the summarizing - it is not breaking everything else while
you do it.
""",
                xp=30,
            ),
            Step(
                id="durable-vs-active",
                kind="predict",
                title="What does the disk remember?",
                multi=True,
                body="""\
Compaction replaced messages in the *active context*. Now: what happened to the
session file on disk?

Read `tau/src/tau_agent/session/entries.py` (the `CompactionEntry` class) and
`tau/src/tau_agent/session/memory.py` (the `_apply_compaction` function), then
answer. The file is append-only; that one fact constrains every option below.
""",
                question=(
                    "A session is compacted twice, then loaded from disk. "
                    "Which of these are true? Select all that apply."
                ),
                choices=[
                    Choice(
                        id="kept",
                        label="The original pre-compaction messages are still in the JSONL file.",
                        note=(
                            "True. Nothing is ever deleted. A `CompactionEntry` "
                            "is appended recording the summary and a pointer to "
                            "where retained context begins."
                        ),
                    ),
                    Choice(
                        id="replay",
                        label="The model sees the summary, because the swap happens when entries are replayed.",
                        note=(
                            "True, and this is the mechanism. "
                            "`SessionState.from_entries()` walks the entries, "
                            "and when it meets a compaction it substitutes the "
                            "summary for the messages before it. The effect is "
                            "produced at read time, not at write time."
                        ),
                    ),
                    Choice(
                        id="inspect",
                        label="You could still read exactly what was compacted away.",
                        note=(
                            "True, and it is the practical payoff. Branching to "
                            "a pre-compaction point still has the full history, "
                            "and a bug in compaction loses nothing permanently."
                        ),
                    ),
                    Choice(
                        id="rewritten",
                        label="The file was rewritten to drop the replaced messages and save space.",
                        note=(
                            "False, and it is the tempting answer, because it is "
                            "what you would do with a mutable store. Rewriting "
                            "an append-only file is exactly the operation the "
                            "format exists to forbid: it would break every "
                            "entry id that points into the region being removed."
                        ),
                    ),
                ],
                answer=["kept", "replay", "inspect"],
                specimen_paths=[
                    "tau/src/tau_agent/session/entries.py",
                    "tau/src/tau_agent/session/memory.py",
                ],
                hints=[
                    "Look at what `CompactionEntry` stores. Is it a deletion instruction, or something else?",
                    "The file is append-only. What can you append that *changes how a replay turns out* without removing anything?",
                ],
                after="""\
{{diagram:compaction}}

Nothing is deleted. A `CompactionEntry` is appended, recording the summary and
a pointer (`first_kept_entry_id`) to where retained context begins.

The effect is produced at **replay time**: `SessionState.from_entries()` walks
the entries, and when it meets a compaction, it replaces the preceding messages
with the summary. The file still holds everything.

This is the Act II thesis in its clearest form:

> **The durable record and the model's context are two different things.**

The consequences are large. You can inspect what was compacted away. Branching
to an earlier point still has the full history. A bug in compaction loses
nothing permanently. And `/tree` can navigate to a pre-compaction state.

This is event sourcing, applied to a conversation - the same reasoning as a
database write-ahead log or a git object store. Nothing is mutated; new facts
are appended, and current state is a fold over them.
""",
                xp=25,
            ),
        ],
        reveal="""\
Tau's compaction has three triggers, which is worth noting as a product design:

1. **Manual** - `/compact`, optionally with instructions.
2. **Automatic** - crossing a token threshold before a request.
3. **Overflow recovery** - the provider rejected the request for length, so
   compact and retry *once*.

The third is the interesting one. Estimation is approximate (chars/4 is not
tokenization), so a system relying only on prediction will sometimes be wrong.
The recovery path turns a fatal error into a recoverable one.

The general principle: when you cannot measure a limit exactly, handle the
failure as well as predicting it.
""",
        transfer="""\
**Transferable:** every agent hits the context limit, and how it responds is
one of the most user-visible architectural choices it makes. Ask: is history
append-only or mutated? Is compaction summarization or truncation? Is there
overflow recovery, or does the session just die? These answers predict how a
tool behaves in exactly the long sessions where it matters most.
""",
    )
