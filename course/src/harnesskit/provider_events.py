"""Events a *provider* emits while streaming one assistant turn.

Note the layering, it is the point of this file: the provider speaks
``ProviderEvent``; the agent loop speaks ``AgentEvent`` (see ``events.py``).
One of the course's recurring questions is why a harness needs both.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from harnesskit.messages import AssistantMessage, ToolCall


@dataclass(slots=True)
class AssistantStartEvent:
    """The provider has begun producing an assistant message."""

    partial: AssistantMessage = field(default_factory=AssistantMessage)
    type: Literal["assistant_start"] = "assistant_start"


@dataclass(slots=True)
class TextDeltaEvent:
    """One incremental chunk of assistant text."""

    delta: str
    partial: AssistantMessage = field(default_factory=AssistantMessage)
    content_index: int = 0
    type: Literal["text_delta"] = "text_delta"


@dataclass(slots=True)
class ToolCallEndEvent:
    """A complete, parsed tool call is now available."""

    tool_call: ToolCall
    partial: AssistantMessage = field(default_factory=AssistantMessage)
    content_index: int = 0
    type: Literal["tool_call_end"] = "tool_call_end"


@dataclass(slots=True)
class AssistantDoneEvent:
    """The assistant turn completed normally."""

    message: AssistantMessage
    type: Literal["assistant_done"] = "assistant_done"


@dataclass(slots=True)
class AssistantErrorEvent:
    """The assistant turn failed (HTTP error, overflow, refusal to continue)."""

    error: AssistantMessage
    type: Literal["assistant_error"] = "assistant_error"


ProviderEvent = (
    AssistantStartEvent
    | TextDeltaEvent
    | ToolCallEndEvent
    | AssistantDoneEvent
    | AssistantErrorEvent
)
