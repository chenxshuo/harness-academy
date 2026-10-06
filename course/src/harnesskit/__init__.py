"""Harness Academy workbench substrate.

This package gives you the *boring* parts of a coding-agent harness so your
effort goes into the architectural parts.

You get:
    - message types            (``messages.py``)
    - provider event types     (``provider_events.py``)
    - agent event types        (``events.py``)
    - a deterministic provider (``ScriptedProvider`` in ``scripted.py``)
    - tool types               (``tools.py``)

You write (in ``workbench/``):
    - the agent loop
    - the stateful harness
    - the session/persistence layer
    - context compaction
    - ...and whatever else the current level asks for.

Nothing in here is copied from the study specimen. It is deliberately smaller,
so that when you finally read Tau's version you are comparing two real designs
rather than checking your memory.
"""

from harnesskit.events import (
    AgentEndEvent,
    AgentEvent,
    AgentStartEvent,
    MessageEndEvent,
    MessageStartEvent,
    MessageUpdateEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    TurnEndEvent,
    TurnStartEvent,
    event_names,
)
from harnesskit.messages import (
    AgentMessage,
    AssistantMessage,
    TextContent,
    ToolCall,
    ToolResultMessage,
    UserMessage,
    message_text,
)
from harnesskit.provider_events import (
    AssistantDoneEvent,
    AssistantErrorEvent,
    AssistantStartEvent,
    ProviderEvent,
    TextDeltaEvent,
    ToolCallEndEvent,
)
from harnesskit.scripted import RecordingProvider, ScriptedProvider, turn
from harnesskit.tools import CancellationToken, SimpleCancellationToken, Tool, ToolResult

__all__ = [
    "AgentEndEvent",
    "AgentEvent",
    "AgentMessage",
    "AgentStartEvent",
    "AssistantDoneEvent",
    "AssistantErrorEvent",
    "AssistantMessage",
    "AssistantStartEvent",
    "CancellationToken",
    "MessageEndEvent",
    "MessageStartEvent",
    "MessageUpdateEvent",
    "ProviderEvent",
    "RecordingProvider",
    "ScriptedProvider",
    "SimpleCancellationToken",
    "TextContent",
    "TextDeltaEvent",
    "Tool",
    "ToolCall",
    "ToolCallEndEvent",
    "ToolExecutionEndEvent",
    "ToolExecutionStartEvent",
    "ToolResult",
    "ToolResultMessage",
    "TurnEndEvent",
    "TurnStartEvent",
    "UserMessage",
    "event_names",
    "message_text",
    "turn",
]
