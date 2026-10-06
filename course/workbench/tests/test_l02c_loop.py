"""Level 2, step 3 - the loop, without tool execution.

Five tests. The new ideas are the stop condition and the fact that `messages`
is mutated in place, which is how the next turn remembers the previous one.
"""

from __future__ import annotations

import pytest

from harnesskit import (
    AssistantMessage,
    ScriptedProvider,
    ToolCall,
    UserMessage,
    event_names,
    turn,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def collect(stream):
    return [event async for event in stream]


async def test_stops_when_there_are_no_tool_calls():
    from step3_loop import run_loop

    provider = ScriptedProvider([turn("Done"), turn("should not be reached")])
    messages = [UserMessage(content="hi")]

    await collect(run_loop(provider=provider, messages=messages))

    assert provider.call_count == 1, (
        f"The provider was called {provider.call_count} times. An assistant "
        f"message with no tool calls must end the loop: "
        f"`if not assistant.tool_calls: break`."
    )


async def test_continues_when_the_model_asks_for_a_tool():
    from step3_loop import run_loop

    call = ToolCall(id="c1", name="read", arguments={})
    provider = ScriptedProvider([turn(tool_calls=[call]), turn("Done")])
    messages = [UserMessage(content="hi")]

    await collect(run_loop(provider=provider, messages=messages))

    assert provider.call_count == 2, (
        f"The provider was called {provider.call_count} time(s). A tool call "
        f"means the model wants to continue, so the loop should go round again."
    )


async def test_appends_assistant_messages_to_the_transcript():
    """`messages` is mutated in place - that list IS the conversation."""
    from step3_loop import run_loop

    call = ToolCall(id="c1", name="read", arguments={})
    provider = ScriptedProvider([turn(tool_calls=[call]), turn("Done")])
    messages = [UserMessage(content="hi")]

    await collect(run_loop(provider=provider, messages=messages))

    kinds = [type(m).__name__ for m in messages]
    assert kinds == ["UserMessage", "AssistantMessage", "AssistantMessage"], (
        f"Expected the two assistant messages to be appended, got {kinds}. "
        f"The caller's list must be mutated - that is how turn 2 sees turn 1."
    )


async def test_second_call_receives_the_first_turn():
    from step3_loop import run_loop

    call = ToolCall(id="c1", name="read", arguments={})
    provider = ScriptedProvider([turn(tool_calls=[call]), turn("Done")])
    messages = [UserMessage(content="hi")]

    await collect(run_loop(provider=provider, messages=messages))

    sent = provider.calls[1]["messages"]
    assert len(sent) >= 2, (
        f"The second provider call received {len(sent)} message(s). It should "
        f"include the first assistant turn, otherwise the model has no memory "
        f"of what it just said."
    )


async def test_event_envelope_is_correct():
    from step3_loop import run_loop

    provider = ScriptedProvider([turn("Done")])
    messages = [UserMessage(content="hi")]

    events = await collect(run_loop(provider=provider, messages=messages))
    names = event_names(events)

    assert names[0] == "agent_start", f"Run must open with agent_start, got {names[:1]}"
    assert names[-1] == "agent_end", f"Run must close with agent_end, got {names[-1:]}"
    assert "turn_start" in names and "turn_end" in names, (
        f"Each provider round-trip needs turn_start and turn_end. Got: {names}"
    )


async def test_max_turns_caps_a_runaway_loop():
    from step3_loop import run_loop

    call = ToolCall(id="c1", name="read", arguments={})
    # A provider that always asks for another tool: infinite without a cap.
    provider = ScriptedProvider([turn(tool_calls=[call]) for _ in range(20)])
    messages = [UserMessage(content="hi")]

    await collect(run_loop(provider=provider, messages=messages, max_turns=3))

    assert provider.call_count <= 3, (
        f"max_turns=3 must cap provider calls, but there were "
        f"{provider.call_count}. Check it at the top of the while body."
    )
