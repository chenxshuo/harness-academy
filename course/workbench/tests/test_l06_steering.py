"""Level 6 - steering and follow-up queues."""

from __future__ import annotations

import pytest

from harnesskit import ScriptedProvider, Tool, ToolCall, ToolResult, UserMessage, turn

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_harness(provider, tools=()):
    from harness import AgentHarness, AgentHarnessConfig

    return AgentHarness(
        AgentHarnessConfig(provider=provider, model="m", system="s", tools=list(tools))
    )


async def drain(stream):
    return [event async for event in stream]


def echo() -> Tool:
    async def execute(arguments):
        return ToolResult(content="ok")

    return Tool(name="echo", description="Echo.", execute=execute)


async def test_steering_message_reaches_the_next_provider_call():
    """A correction typed mid-run must be visible to the model's next decision."""
    call = ToolCall(id="c1", name="echo", arguments={})
    provider = ScriptedProvider([turn(tool_calls=[call]), turn("adjusted")])
    harness = make_harness(provider, tools=[echo()])

    stream = harness.prompt("do the thing")
    await stream.__anext__()
    harness.steer("actually, stop touching that file")
    await drain(stream)

    assert provider.call_count >= 2, "The run should have continued after the tool call"
    second_call_texts = [
        getattr(m, "text", "") for m in provider.calls[1]["messages"]
    ]
    assert any("stop touching" in t for t in second_call_texts), (
        "The steering message must appear in the transcript sent to the model on "
        "the next call. That is the entire point: the model should act on the "
        "correction rather than finish the wrong work."
    )


async def test_steering_lands_after_the_tool_result():
    """Ordering guarantee: the in-flight batch completes first."""
    call = ToolCall(id="c1", name="echo", arguments={})
    provider = ScriptedProvider([turn(tool_calls=[call]), turn("done")])
    harness = make_harness(provider, tools=[echo()])

    stream = harness.prompt("go")
    # Advance until a tool is actually executing, so this really is a
    # mid-batch interruption rather than a message queued before the run began.
    async for event in stream:
        if event.type == "tool_execution_start":
            break
    harness.steer("correction")
    await drain(stream)

    kinds = [type(m).__name__ for m in harness.messages]
    tool_index = kinds.index("ToolResultMessage")
    steer_index = next(
        i
        for i, m in enumerate(harness.messages)
        if type(m).__name__ == "UserMessage" and "correction" in getattr(m, "text", "")
    )
    assert steer_index > tool_index, (
        "A steering message must be injected AFTER the current tool batch "
        "completes. Injecting mid-batch would place a message before tool "
        "results that logically precede it."
    )


async def test_follow_up_resurrects_a_finished_run():
    """A follow-up fires only when the run would otherwise stop."""
    provider = ScriptedProvider([turn("first answer"), turn("second answer")])
    harness = make_harness(provider)

    stream = harness.prompt("question")
    await stream.__anext__()
    harness.follow_up("also summarize it")
    await drain(stream)

    assert provider.call_count == 2, (
        f"The provider was called {provider.call_count} time(s). A queued "
        f"follow-up must restart a run that had no more tool calls - the inner "
        f"while loop is what makes this possible."
    )


async def test_queues_are_empty_after_draining():
    provider = ScriptedProvider([turn("a"), turn("b")])
    harness = make_harness(provider)

    stream = harness.prompt("q")
    await stream.__anext__()
    harness.follow_up("more")
    await drain(stream)

    assert not harness.has_queued_messages(), (
        "Queues must be empty once their messages have been injected"
    )


async def test_unused_queued_message_is_not_in_the_transcript():
    """Queued is not the same as said."""
    harness = make_harness(ScriptedProvider([turn("done")]))

    harness.steer("never injected")

    assert all(
        "never injected" not in getattr(m, "text", "") for m in harness.messages
    ), (
        "A queued message becomes a durable transcript message only when it is "
        "injected into the loop - not when it is queued."
    )
