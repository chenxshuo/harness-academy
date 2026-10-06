"""Level 2 - the agent loop.

These tests are the specification. If the brief is ambiguous, this file is the
authority. They are written to fail *informatively*: each assertion message
says what the loop should have done, not merely that something differed.
"""

from __future__ import annotations

import pytest

from harnesskit import (
    AssistantMessage,
    ScriptedProvider,
    TextContent,
    Tool,
    ToolCall,
    ToolResult,
    ToolResultMessage,
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


def echo_tool(name: str = "echo", *, fail: bool = False) -> Tool:
    async def execute(arguments):
        if fail:
            raise RuntimeError("tool exploded")
        return ToolResult(content=f"ran {name} with {arguments}")

    return Tool(name=name, description="Echo.", execute=execute)


async def test_simple_run_emits_canonical_event_order():
    """A no-tool run: start, one turn, one message, end."""
    from loop import run_agent_loop

    provider = ScriptedProvider([turn("Hello there")])
    messages = [UserMessage(content="hi")]

    events = await collect(
        run_agent_loop(
            provider=provider, model="m", system="s", messages=messages, tools=[]
        )
    )
    names = event_names(events)

    assert names[0] == "agent_start", f"Run must open with agent_start, got {names[:1]}"
    assert names[-1] == "agent_end", f"Run must close with agent_end, got {names[-1:]}"
    assert "turn_start" in names and "turn_end" in names, (
        f"Each provider round-trip needs turn_start/turn_end. Got: {names}"
    )
    assert "message_start" in names and "message_end" in names, (
        f"The assistant message needs message_start/message_end. Got: {names}"
    )
    assert names.index("turn_start") < names.index("message_start"), (
        "turn_start must come before the message it contains"
    )


async def test_streaming_deltas_become_message_updates():
    """Text deltas from the provider surface as message_update events."""
    from loop import run_agent_loop

    provider = ScriptedProvider([turn("abcdefgh", chunk=2)])
    messages = [UserMessage(content="hi")]

    events = await collect(
        run_agent_loop(provider=provider, model="m", system="s", messages=messages, tools=[])
    )
    updates = [e for e in events if e.type == "message_update"]
    assert len(updates) == 4, (
        f"Expected one message_update per text delta (4 for 8 chars at chunk=2), got {len(updates)}"
    )


async def test_assistant_message_is_appended_to_transcript():
    from loop import run_agent_loop

    provider = ScriptedProvider([turn("Hello")])
    messages = [UserMessage(content="hi")]

    await collect(
        run_agent_loop(provider=provider, model="m", system="s", messages=messages, tools=[])
    )

    assert len(messages) == 2, (
        f"The loop must append the assistant message to `messages`. "
        f"Expected 2 messages, found {len(messages)}: {[type(m).__name__ for m in messages]}"
    )
    assert isinstance(messages[1], AssistantMessage)
    assert messages[1].text == "Hello"


async def test_tool_call_triggers_second_provider_call():
    """The core behavior: tool calls continue the loop."""
    from loop import run_agent_loop

    call = ToolCall(id="c1", name="echo", arguments={"x": 1})
    provider = ScriptedProvider([turn(tool_calls=[call]), turn("Done")])
    messages = [UserMessage(content="go")]

    await collect(
        run_agent_loop(
            provider=provider, model="m", system="s", messages=messages, tools=[echo_tool()]
        )
    )

    assert provider.call_count == 2, (
        f"A tool call must cause another provider call. The provider was called "
        f"{provider.call_count} time(s). If it was 1, the loop stopped after the "
        f"tool instead of sending the result back to the model."
    )


async def test_tool_result_immediately_follows_its_call():
    """The pairing invariant - providers reject transcripts that violate it."""
    from loop import run_agent_loop

    call = ToolCall(id="c1", name="echo", arguments={})
    provider = ScriptedProvider([turn(tool_calls=[call]), turn("Done")])
    messages = [UserMessage(content="go")]

    await collect(
        run_agent_loop(
            provider=provider, model="m", system="s", messages=messages, tools=[echo_tool()]
        )
    )

    kinds = [type(m).__name__ for m in messages]
    assert kinds == [
        "UserMessage",
        "AssistantMessage",
        "ToolResultMessage",
        "AssistantMessage",
    ], (
        f"Transcript order is wrong: {kinds}\n"
        f"A ToolResultMessage must come IMMEDIATELY after the AssistantMessage "
        f"that requested it. Providers reject any other arrangement."
    )
    assert messages[2].tool_call_id == "c1", "The result must carry its call's id"


async def test_tool_execution_events_are_emitted():
    from loop import run_agent_loop

    call = ToolCall(id="c1", name="echo", arguments={})
    provider = ScriptedProvider([turn(tool_calls=[call]), turn("Done")])
    messages = [UserMessage(content="go")]

    events = await collect(
        run_agent_loop(
            provider=provider, model="m", system="s", messages=messages, tools=[echo_tool()]
        )
    )
    names = event_names(events)
    assert "tool_execution_start" in names, "Emit tool_execution_start before running a tool"
    assert "tool_execution_end" in names, "Emit tool_execution_end after running a tool"
    assert names.index("tool_execution_start") < names.index("tool_execution_end")


async def test_failing_tool_does_not_kill_the_run():
    """A tool is an isolation boundary."""
    from loop import run_agent_loop

    call = ToolCall(id="c1", name="boom", arguments={})
    provider = ScriptedProvider([turn(tool_calls=[call]), turn("Recovered")])
    messages = [UserMessage(content="go")]

    events = await collect(
        run_agent_loop(
            provider=provider,
            model="m",
            system="s",
            messages=messages,
            tools=[echo_tool("boom", fail=True)],
        )
    )

    assert provider.call_count == 2, (
        "A raising tool must not end the run. Catch the exception, return an "
        "error result, and let the model decide what to do next."
    )
    results = [m for m in messages if isinstance(m, ToolResultMessage)]
    assert results, "Even a failed tool must produce a ToolResultMessage"
    assert results[0].is_error, "A failed tool's result should set is_error=True"


async def test_unknown_tool_is_reported_not_raised():
    from loop import run_agent_loop

    call = ToolCall(id="c1", name="nonexistent", arguments={})
    provider = ScriptedProvider([turn(tool_calls=[call]), turn("ok")])
    messages = [UserMessage(content="go")]

    await collect(
        run_agent_loop(
            provider=provider, model="m", system="s", messages=messages, tools=[echo_tool()]
        )
    )

    results = [m for m in messages if isinstance(m, ToolResultMessage)]
    assert results, (
        "An unknown tool name must still produce a ToolResultMessage. "
        "Otherwise the tool call is left dangling and the transcript is invalid."
    )
    assert results[0].is_error


async def test_parallel_tool_calls_all_execute_in_order():
    from loop import run_agent_loop

    calls = [
        ToolCall(id="c1", name="echo", arguments={"n": 1}),
        ToolCall(id="c2", name="echo", arguments={"n": 2}),
    ]
    provider = ScriptedProvider([turn(tool_calls=calls), turn("Done")])
    messages = [UserMessage(content="go")]

    await collect(
        run_agent_loop(
            provider=provider, model="m", system="s", messages=messages, tools=[echo_tool()]
        )
    )

    results = [m for m in messages if isinstance(m, ToolResultMessage)]
    assert len(results) == 2, (
        f"Both tool calls need results; found {len(results)}. "
        f"An assistant message can request several tools at once."
    )
    assert [r.tool_call_id for r in results] == ["c1", "c2"], (
        "Results must appear in the same order the calls were made"
    )


async def test_max_turns_stops_a_runaway_loop():
    from loop import run_agent_loop

    call = ToolCall(id="c1", name="echo", arguments={})
    # A provider that always asks for another tool: an infinite loop without a cap.
    provider = ScriptedProvider([turn(tool_calls=[call]) for _ in range(20)])
    messages = [UserMessage(content="go")]

    await collect(
        run_agent_loop(
            provider=provider,
            model="m",
            system="s",
            messages=messages,
            tools=[echo_tool()],
            max_turns=3,
        )
    )

    assert provider.call_count <= 3, (
        f"max_turns=3 must cap provider calls, but there were {provider.call_count}. "
        f"Without this, a model that keeps requesting tools runs forever."
    )
