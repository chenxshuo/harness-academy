"""Level 6, step A - the queues themselves.

Four tests. No loop changes yet: just the harness-side bookkeeping.
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


def test_steer_queues_a_message():
    harness = make_harness(ScriptedProvider([turn("a")]))

    harness.steer("change direction")

    assert harness.has_queued_messages(), (
        "After steer(), has_queued_messages() should be True"
    )


def test_follow_up_queues_a_message():
    harness = make_harness(ScriptedProvider([turn("a")]))

    harness.follow_up("also do this afterwards")

    assert harness.has_queued_messages()


def test_queued_message_is_not_yet_in_the_transcript():
    """Queued is not the same as said."""
    harness = make_harness(ScriptedProvider([turn("done")]))

    harness.steer("never injected")

    assert all(
        "never injected" not in getattr(m, "text", "") for m in harness.messages
    ), (
        "A queued message becomes a durable transcript message only when it is "
        "injected into the loop - not when it is queued. If the run ends "
        "first, it was never part of the conversation."
    )


def test_draining_removes_one_message_at_a_time():
    """The drain callback is what the loop will call at a turn boundary."""
    harness = make_harness(ScriptedProvider([turn("a")]))

    harness.steer("first")
    harness.steer("second")

    drained = harness._drain(harness._steering)
    assert len(drained) == 1, (
        f"Draining should yield one message at a time by default, got "
        f"{len(drained)}. Use popleft() on a deque."
    )
    assert harness.has_queued_messages(), "The second message should still be queued"
