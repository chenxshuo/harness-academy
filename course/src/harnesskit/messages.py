"""Provider-neutral transcript messages.

These are the objects that flow between the provider, the loop, the tools, and
persistence. They are deliberately plain dataclasses: a harness's message types
are data, not behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(slots=True)
class TextContent:
    text: str
    type: Literal["text"] = "text"


@dataclass(slots=True)
class ToolCall:
    """An assistant's request to run one named tool."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    type: Literal["tool_call"] = "tool_call"


Content = TextContent | ToolCall


@dataclass(slots=True)
class UserMessage:
    content: str
    role: Literal["user"] = "user"

    @property
    def text(self) -> str:
        return self.content


@dataclass(slots=True)
class AssistantMessage:
    """One assistant turn: text, tool calls, and why it stopped.

    ``stop_reason`` matters more than it looks. A harness must distinguish
    "the model finished talking" from "the model wants tools" from "this turn
    failed", because each leads somewhere different in the loop.
    """

    model: str = "scripted"
    content: list[Content] = field(default_factory=list)
    stop_reason: Literal["stop", "tool_use", "length", "error", "aborted", "pending"] = "pending"
    error_message: str | None = None
    role: Literal["assistant"] = "assistant"

    def __post_init__(self) -> None:
        # Convenience: AssistantMessage(content="hi") is common in exercises.
        if isinstance(self.content, str):
            self.content = [TextContent(text=self.content)] if self.content else []

    @property
    def text(self) -> str:
        return "".join(c.text for c in self.content if isinstance(c, TextContent))

    @property
    def tool_calls(self) -> list[ToolCall]:
        return [c for c in self.content if isinstance(c, ToolCall)]


@dataclass(slots=True)
class ToolResultMessage:
    """The result of exactly one tool call, tied back by ``tool_call_id``.

    That id is the whole reason this is a separate message type. Providers
    match results to calls by id, and reject a transcript where the pairing
    is broken.
    """

    tool_call_id: str
    tool_name: str
    content: list[TextContent] = field(default_factory=list)
    is_error: bool = False
    role: Literal["tool"] = "tool"

    def __post_init__(self) -> None:
        if isinstance(self.content, str):
            self.content = [TextContent(text=self.content)]

    @property
    def text(self) -> str:
        return "".join(c.text for c in self.content)


AgentMessage = UserMessage | AssistantMessage | ToolResultMessage


def message_text(message: AgentMessage) -> str:
    """Return the readable text of any transcript message."""
    return message.text


def describe(message: AgentMessage) -> str:
    """Return a compact one-line description, useful when printing traces."""
    match message:
        case UserMessage():
            return f"user({message.text[:40]!r})"
        case AssistantMessage():
            calls = ",".join(c.name for c in message.tool_calls)
            suffix = f" tools=[{calls}]" if calls else ""
            return f"assistant({message.text[:40]!r}{suffix}) stop={message.stop_reason}"
        case ToolResultMessage():
            flag = "!" if message.is_error else ""
            return f"tool_result{flag}({message.tool_name}, id={message.tool_call_id})"
    return repr(message)
