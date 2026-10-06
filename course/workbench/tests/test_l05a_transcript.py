"""Level 5, step A - the harness holds the transcript.

Three tests. One idea: a stateful object that remembers the conversation
between runs. No listeners, no guards, no cancellation yet.
"""

from __future__ import annotations

import pytest

from harnesskit import ScriptedProvider, turn

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


async def test_a_single_prompt_runs():
    from harness import AgentHarness  # noqa: F401

    harness = make_harness(ScriptedProvider([turn("hello")]))

    events = await drain(harness.prompt("hi"))

    assert events, (
        "prompt() produced no events. It should append a UserMessage and then "
        "delegate to run_agent_loop."
    )
    assert events[0].type == "agent_start"


async def test_transcript_survives_between_prompts():
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
        f"After two prompts the transcript should hold all four messages, got "
        f"{kinds}. The harness must accumulate state across runs - a loop "
        f"cannot, because it returns."
    )


async def test_second_prompt_sends_the_earlier_exchange():
    """Continuity is observable in what the provider receives."""
    provider = ScriptedProvider([turn("first"), turn("second")])
    harness = make_harness(provider)

    await drain(harness.prompt("one"))
    await drain(harness.prompt("two"))

    sent = provider.calls[1]["messages"]
    assert len(sent) >= 3, (
        f"The second provider call received {len(sent)} message(s). It should "
        f"include the first exchange, otherwise the model has no memory of it."
    )


async def test_continue_adds_no_user_message():
    from harness import AgentHarness  # noqa: F401

    harness = make_harness(ScriptedProvider([turn("a"), turn("b")]))

    await drain(harness.prompt("one"))
    before = len(harness.messages)
    await drain(harness.continue_())

    added = harness.messages[before:]
    assert all(type(m).__name__ != "UserMessage" for m in added), (
        "continue_() must not append a UserMessage. It resumes the existing "
        "conversation - used after compaction, or to recover from a cancel."
    )
