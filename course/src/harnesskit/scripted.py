"""A deterministic provider.

Real models are a terrible teaching instrument: they are slow, nondeterministic,
and they hide the harness behind the interesting text they produce. A scripted
provider makes the *harness* the only variable in the experiment.

Every exercise in this course runs against one of these. Same input, same
events, every time - so when something changes, it was your code.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterable, Sequence
from typing import Any

from harnesskit.messages import AgentMessage, AssistantMessage, TextContent, ToolCall
from harnesskit.provider_events import (
    AssistantDoneEvent,
    AssistantErrorEvent,
    AssistantStartEvent,
    ProviderEvent,
    TextDeltaEvent,
    ToolCallEndEvent,
)
from harnesskit.tools import CancellationToken, Tool


def turn(
    text: str = "",
    *,
    tool_calls: Sequence[ToolCall] = (),
    error: str | None = None,
    chunk: int = 4,
) -> list[ProviderEvent]:
    """Build the provider event stream for one assistant turn.

    This is the authoring helper for exercises::

        provider = ScriptedProvider([
            turn(tool_calls=[ToolCall(id="c1", name="read", arguments={"path": "x"})]),
            turn("All done."),
        ])

    Each ``turn(...)`` is one provider round-trip. A loop that stops early will
    simply never consume the later turns - which is exactly how several levels
    detect a wrong implementation.
    """
    if error is not None:
        return [
            AssistantStartEvent(),
            AssistantErrorEvent(
                error=AssistantMessage(stop_reason="error", error_message=error)
            ),
        ]

    events: list[ProviderEvent] = [AssistantStartEvent()]
    accumulated = ""
    for index in range(0, len(text), chunk):
        piece = text[index : index + chunk]
        accumulated += piece
        events.append(
            TextDeltaEvent(
                delta=piece,
                partial=AssistantMessage(content=[TextContent(text=accumulated)]),
            )
        )

    content: list[Any] = [TextContent(text=text)] if text else []
    for call in tool_calls:
        content.append(call)
        events.append(ToolCallEndEvent(tool_call=call, partial=AssistantMessage(content=list(content))))

    final = AssistantMessage(
        content=content,
        stop_reason="tool_use" if tool_calls else "stop",
    )
    events.append(AssistantDoneEvent(message=final))
    return events


class ScriptedProvider:
    """Replays a predetermined list of turns, one per ``stream_response`` call."""

    def __init__(self, turns: Iterable[Iterable[ProviderEvent]]) -> None:
        self._turns = [list(t) for t in turns]
        self.calls: list[dict[str, Any]] = []

    @property
    def call_count(self) -> int:
        """How many times the loop asked the provider for a response."""
        return len(self.calls)

    @property
    def exhausted(self) -> bool:
        return not self._turns

    def stream_response(
        self,
        *,
        model: str = "scripted",
        system: str = "",
        messages: Sequence[AgentMessage] = (),
        tools: Sequence[Tool] = (),
        signal: CancellationToken | None = None,
    ) -> AsyncIterator[ProviderEvent]:
        """Stream one scripted assistant turn.

        The call is recorded first. Inspecting ``provider.calls[n]["messages"]``
        is how several levels let you *see* what the loop actually sent, which
        is usually more informative than what you assumed it sent.
        """
        self.calls.append(
            {
                "model": model,
                "system": system,
                "messages": list(messages),
                "tools": list(tools),
            }
        )
        events = self._turns.pop(0) if self._turns else []

        async def iterator() -> AsyncIterator[ProviderEvent]:
            for event in events:
                if signal is not None and signal.is_cancelled():
                    return
                yield event

        return iterator()


class RecordingProvider(ScriptedProvider):
    """A ScriptedProvider that also exposes the last context it was sent."""

    @property
    def last_messages(self) -> list[AgentMessage]:
        return list(self.calls[-1]["messages"]) if self.calls else []

    @property
    def last_system(self) -> str:
        return self.calls[-1]["system"] if self.calls else ""
