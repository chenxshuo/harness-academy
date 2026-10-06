"""Level 2, step 2 - translate provider events into agent events.

Four tests. The new idea is `yield` instead of `return`, and the fact that
your harness publishes its own event vocabulary rather than the vendor's.
"""

from __future__ import annotations

import pytest

from harnesskit import ScriptedProvider, UserMessage, event_names, turn

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def collect(stream):
    return [event async for event in stream]


async def test_yields_start_update_end_in_order():
    from step2_events import stream_one_turn

    provider = ScriptedProvider([turn("abcd", chunk=2)])

    events = await collect(
        stream_one_turn(provider=provider, messages=[UserMessage(content="hi")])
    )
    names = event_names(events)

    assert names, (
        "No events were yielded. Did you delete the placeholder "
        "`raise NotImplementedError` and add real yields?"
    )
    assert names[0] == "message_start", (
        f"The first event should be message_start (from AssistantStartEvent), "
        f"got {names[0]!r}"
    )
    assert names[-1] == "message_end", (
        f"The last event should be message_end (from AssistantDoneEvent), "
        f"got {names[-1]!r}"
    )


async def test_one_update_per_text_delta():
    from step2_events import stream_one_turn

    provider = ScriptedProvider([turn("abcdefgh", chunk=2)])

    events = await collect(
        stream_one_turn(provider=provider, messages=[UserMessage(content="hi")])
    )
    updates = [e for e in events if e.type == "message_update"]

    assert len(updates) == 4, (
        f"Expected 4 message_update events (8 chars at chunk=2), got "
        f"{len(updates)}. Each TextDeltaEvent becomes one MessageUpdateEvent."
    )


async def test_final_message_is_on_the_last_event():
    """This is how step 3 will recover the assistant message."""
    from step2_events import stream_one_turn

    provider = ScriptedProvider([turn("Hello")])

    events = await collect(
        stream_one_turn(provider=provider, messages=[UserMessage(content="hi")])
    )
    end = [e for e in events if e.type == "message_end"]

    assert end, "There must be a message_end event carrying the final message"
    assert end[-1].message.text == "Hello", (
        "The message_end event must carry the provider's finished message "
        "(`event.message` from AssistantDoneEvent)."
    )


async def test_error_turn_still_ends_the_stream():
    from step2_events import stream_one_turn

    provider = ScriptedProvider([turn(error="provider exploded")])

    events = await collect(
        stream_one_turn(provider=provider, messages=[UserMessage(content="hi")])
    )
    names = event_names(events)

    assert "message_end" in names, (
        "An AssistantErrorEvent must also produce a message_end, carrying "
        "`event.error`. Otherwise a failed turn never terminates cleanly for "
        "whoever is consuming your events."
    )
