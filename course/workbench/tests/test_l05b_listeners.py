"""Level 5, step B - event listeners.

Four tests. One idea: something can watch the event stream without consuming
it. The ordering test here is the seed of Level 9's data-loss bug.
"""

from __future__ import annotations

import pytest

from harnesskit import ScriptedProvider, turn

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_harness(provider):
    from harness import AgentHarness, AgentHarnessConfig

    return AgentHarness(AgentHarnessConfig(provider=provider, model="m", system="s"))


async def drain(stream):
    return [event async for event in stream]


async def test_subscriber_sees_every_event():
    harness = make_harness(ScriptedProvider([turn("hi")]))
    seen = []
    harness.subscribe(lambda e: seen.append(e.type))

    events = await drain(harness.prompt("one"))

    assert len(seen) == len(events), (
        f"The subscriber saw {len(seen)} events but the consumer saw "
        f"{len(events)}. Every event must reach listeners."
    )


async def test_unsubscribe_stops_delivery():
    harness = make_harness(ScriptedProvider([turn("a"), turn("b")]))
    seen = []
    unsubscribe = harness.subscribe(lambda e: seen.append(e))

    await drain(harness.prompt("one"))
    after_first = len(seen)
    unsubscribe()
    await drain(harness.prompt("two"))

    assert len(seen) == after_first, (
        "subscribe() must return a callable that removes the listener. Nothing "
        "should be delivered after it is called."
    )


async def test_several_listeners_all_fire():
    harness = make_harness(ScriptedProvider([turn("hi")]))
    a, b = [], []
    harness.subscribe(lambda e: a.append(e))
    harness.subscribe(lambda e: b.append(e))

    await drain(harness.prompt("one"))

    assert a and b and len(a) == len(b), (
        "All registered listeners must receive all events"
    )


async def test_listeners_fire_before_the_consumer_sees_the_event():
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
        "cancelled mid-run, a listener that already ran has still done its "
        "work - which is exactly how durable persistence survives an "
        "interrupted run. Put the notify call above the yield."
    )
