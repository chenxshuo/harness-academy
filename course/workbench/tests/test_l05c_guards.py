"""Level 5, step C - the overlap guard and cancellation.

Four tests. The subtle one is that `prompt()` must not be `async def` - the
guard has to fire when called, not when iterated.
"""

from __future__ import annotations

import asyncio

import pytest

from harnesskit import ScriptedProvider, Tool, ToolCall, ToolResult, turn

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


async def test_overlapping_prompt_is_rejected():
    """Two runs mutating one transcript is a race, not a feature."""
    harness = make_harness(ScriptedProvider([turn("a"), turn("b")]))

    stream = harness.prompt("one")
    await stream.__anext__()  # start the run

    with pytest.raises(RuntimeError):
        harness.prompt("two")

    await drain(stream)


async def test_the_guard_fires_on_call_not_on_iteration():
    """prompt() must NOT be `async def`.

    If it is, `_running` only flips when someone starts iterating, so two
    calls to prompt() both succeed and you get the race anyway.
    """
    harness = make_harness(ScriptedProvider([turn("a"), turn("b")]))

    first = harness.prompt("one")
    try:
        with pytest.raises(RuntimeError):
            harness.prompt("two")   # not awaited, not iterated - must still raise
    finally:
        await drain(first)


async def test_running_flag_clears_after_a_run():
    harness = make_harness(ScriptedProvider([turn("a")]))

    await drain(harness.prompt("one"))

    assert not harness.is_running, (
        "is_running must be cleared when a run ends - use try/finally, "
        "otherwise one exception wedges the harness permanently."
    )


async def test_running_flag_clears_even_on_provider_error():
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
        "That needs a finally block, not just a line after the loop."
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
