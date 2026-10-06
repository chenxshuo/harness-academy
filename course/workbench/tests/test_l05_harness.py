"""Level 5 - the stateful harness."""

from __future__ import annotations

import asyncio

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


async def test_harness_keeps_transcript_between_prompts():
    """The whole reason the harness exists."""
    harness = make_harness(ScriptedProvider([turn("first"), turn("second")]))

    await drain(harness.prompt("one"))
    await drain(harness.prompt("two"))

    kinds = [type(m).__name__ for m in harness.messages]
    assert kinds == [
        "UserMessage",
        "AssistantMessage",
        "UserMessage",
        "AssistantMessage",
    ], (
        f"After two prompts the transcript should hold all four messages, got {kinds}. "
        f"The harness must accumulate state across runs - that is its job."
    )


async def test_second_prompt_sees_the_first_exchange():
    """Continuity is observable in what the provider receives."""
    provider = ScriptedProvider([turn("first"), turn("second")])
    harness = make_harness(provider)

    await drain(harness.prompt("one"))
    await drain(harness.prompt("two"))

    sent = provider.calls[1]["messages"]
    assert len(sent) >= 3, (
        f"The second provider call received {len(sent)} message(s). It should "
        f"include the earlier exchange, otherwise the model has no memory."
    )


async def test_overlapping_prompt_is_rejected():
    """Two runs mutating one transcript is a race, not a feature."""
    harness = make_harness(ScriptedProvider([turn("a"), turn("b")]))

    stream = harness.prompt("one")
    await stream.__anext__()  # start the run

    with pytest.raises(RuntimeError):
        harness.prompt("two")

    await drain(stream)


async def test_running_flag_clears_after_a_run():
    harness = make_harness(ScriptedProvider([turn("a")]))

    await drain(harness.prompt("one"))

    assert not harness.is_running, (
        "is_running must be cleared when a run ends. Use try/finally - otherwise "
        "one exception permanently wedges the harness."
    )


async def test_running_flag_clears_even_on_error():
    class Exploding:
        def stream_response(self, **kwargs):
            async def it():
                raise RuntimeError("provider down")
                yield  # pragma: no cover

            return it()

    harness = make_harness(Exploding())

    with pytest.raises(RuntimeError):
        await drain(harness.prompt("one"))

    assert not harness.is_running, (
        "After a provider exception the harness must still clear is_running. "
        "This needs a finally block, not just a line after the loop."
    )


async def test_subscribers_receive_every_event():
    harness = make_harness(ScriptedProvider([turn("hi")]))
    seen = []
    harness.subscribe(lambda e: seen.append(e.type))

    events = await drain(harness.prompt("one"))

    assert len(seen) == len(events), (
        f"Subscriber saw {len(seen)} events but the consumer saw {len(events)}. "
        f"Every event must reach listeners."
    )


async def test_unsubscribe_stops_delivery():
    harness = make_harness(ScriptedProvider([turn("a"), turn("b")]))
    seen = []
    unsubscribe = harness.subscribe(lambda e: seen.append(e))

    await drain(harness.prompt("one"))
    count_after_first = len(seen)
    unsubscribe()
    await drain(harness.prompt("two"))

    assert len(seen) == count_after_first, (
        "subscribe() must return a callable that removes the listener"
    )


async def test_listeners_are_notified_before_the_consumer_yields():
    """This ordering is what makes persistence survive cancellation (Level 9)."""
    harness = make_harness(ScriptedProvider([turn("hi")]))
    order = []
    harness.subscribe(lambda e: order.append(("listener", e.type)))

    async for event in harness.prompt("one"):
        order.append(("consumer", event.type))

    first_listener = next(i for i, (who, _) in enumerate(order) if who == "listener")
    first_consumer = next(i for i, (who, _) in enumerate(order) if who == "consumer")
    assert first_listener < first_consumer, (
        "Notify listeners BEFORE yielding to the consumer. If the consumer is "
        "cancelled mid-run, a listener that already ran has still done its work - "
        "which is exactly how durable persistence survives an interrupted run."
    )


async def test_continue_runs_without_adding_a_user_message():
    harness = make_harness(ScriptedProvider([turn("a"), turn("b")]))

    await drain(harness.prompt("one"))
    before = len(harness.messages)
    await drain(harness.continue_())

    added = harness.messages[before:]
    assert all(type(m).__name__ != "UserMessage" for m in added), (
        "continue_() must not append a UserMessage. It resumes the existing "
        "conversation - used after compaction or to recover from a cancel."
    )


async def test_cancel_stops_the_run():
    slow_started = asyncio.Event()

    async def slow(arguments):
        slow_started.set()
        await asyncio.sleep(5)
        return ToolResult(content="never")

    tool = Tool(name="slow", description="Slow.", execute=slow)
    call = ToolCall(id="c1", name="slow", arguments={})
    harness = make_harness(
        ScriptedProvider([turn(tool_calls=[call]), turn("done")]), tools=[tool]
    )

    async def run():
        return await drain(harness.prompt("go"))

    task = asyncio.create_task(run())
    await asyncio.wait_for(slow_started.wait(), timeout=2)
    harness.cancel()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert not harness.is_running, "A cancelled run must still clear is_running"
