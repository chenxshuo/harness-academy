"""Events the *agent loop* emits. This is the harness's public contract.

Everything downstream - a terminal renderer, a TUI, a web UI, a JSON log, the
course's own trace viewer - consumes these and nothing else. That is what lets
one core drive many frontends.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from harnesskit.messages import AgentMessage, ToolResultMessage
from harnesskit.provider_events import ProviderEvent
from harnesskit.tools import ToolResult


@dataclass(slots=True)
class AgentStartEvent:
    """One whole run began (one call to prompt())."""

    type: str = "agent_start"


@dataclass(slots=True)
class AgentEndEvent:
    """The run finished and will make no further provider calls."""

    messages: list[AgentMessage] = field(default_factory=list)
    type: str = "agent_end"


@dataclass(slots=True)
class TurnStartEvent:
    """One provider round-trip began."""

    type: str = "turn_start"


@dataclass(slots=True)
class TurnEndEvent:
    """One provider round-trip finished, including any tool results."""

    message: AgentMessage
    tool_results: list[ToolResultMessage] = field(default_factory=list)
    type: str = "turn_end"


@dataclass(slots=True)
class MessageStartEvent:
    message: AgentMessage
    type: str = "message_start"


@dataclass(slots=True)
class MessageUpdateEvent:
    """A streaming update to the message currently being produced."""

    message: AgentMessage
    provider_event: ProviderEvent | None = None
    type: str = "message_update"


@dataclass(slots=True)
class MessageEndEvent:
    """A message is final.

    This event is the durability boundary in most harnesses: when it fires,
    the message is complete and safe to persist.
    """

    message: AgentMessage
    type: str = "message_end"


@dataclass(slots=True)
class ToolExecutionStartEvent:
    tool_call_id: str
    tool_name: str
    args: dict[str, Any] = field(default_factory=dict)
    type: str = "tool_execution_start"


@dataclass(slots=True)
class ToolExecutionEndEvent:
    tool_call_id: str
    tool_name: str
    result: ToolResult
    is_error: bool = False
    type: str = "tool_execution_end"


AgentEvent = (
    AgentStartEvent
    | AgentEndEvent
    | TurnStartEvent
    | TurnEndEvent
    | MessageStartEvent
    | MessageUpdateEvent
    | MessageEndEvent
    | ToolExecutionStartEvent
    | ToolExecutionEndEvent
)


def event_names(events: list[AgentEvent]) -> list[str]:
    """Return just the ``type`` of each event.

    Most prediction exercises compare against this, because the *shape* of the
    stream is the architectural claim; the payloads are detail.
    """
    return [event.type for event in events]
