"""Level 2, step 1 - consume one provider stream.

Three tests. This step is deliberately small: the only new idea is that the
final message arrives inside the last event, so you need a variable outside
the loop to catch it.
"""

from __future__ import annotations

import pytest

from harnesskit import ScriptedProvider, UserMessage, turn

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_returns_the_finished_message():
    from step1_one_call import get_one_response

    provider = ScriptedProvider([turn("Hello there")])

    message = await get_one_response(
        provider=provider, messages=[UserMessage(content="hi")]
    )

    assert message is not None, (
        "get_one_response returned None. You need to save event.message when "
        "you see an AssistantDoneEvent, and return it after the loop."
    )
    assert message.text == "Hello there", (
        f"Expected the assistant's text, got {message.text!r}"
    )


async def test_calls_the_provider_exactly_once():
    from step1_one_call import get_one_response

    provider = ScriptedProvider([turn("a"), turn("b")])

    await get_one_response(provider=provider, messages=[UserMessage(content="hi")])

    assert provider.call_count == 1, (
        f"The provider was called {provider.call_count} times. This step asks "
        f"for exactly one call - looping comes in step 3."
    )


async def test_handles_an_error_turn():
    """A failed turn arrives as AssistantErrorEvent, with its message on .error."""
    from step1_one_call import get_one_response

    provider = ScriptedProvider([turn(error="rate limited")])

    message = await get_one_response(
        provider=provider, messages=[UserMessage(content="hi")]
    )

    assert message is not None, (
        "An error turn still produces a message - but it arrives on an "
        "AssistantErrorEvent as `event.error`, not `event.message`. Handle "
        "that case too."
    )
    assert message.stop_reason == "error"
