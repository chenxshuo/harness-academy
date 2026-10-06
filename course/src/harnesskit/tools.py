"""Tools: a schema plus an async function. No framework.

The course argues that this minimalism is a real architectural choice, not an
omission. Keep it in mind when you reach the level on tool isolation.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


class CancellationToken(Protocol):
    def is_cancelled(self) -> bool:
        """Return whether in-flight work should stop."""
        ...


class SimpleCancellationToken:
    """The entire cancellation mechanism. Deliberately this small."""

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled


@dataclass(slots=True)
class ToolResult:
    """What a tool returns.

    ``content`` goes back to the model. ``details`` does not: it is structured
    data for the UI (a diff to render, a row count, a file path). Separating
    them is why a harness can show a rich tool card without spending tokens.
    """

    content: str = ""
    details: dict[str, Any] | None = None

    @property
    def text(self) -> str:
        return self.content


ToolExecutor = Callable[..., Awaitable[ToolResult]]


@dataclass(slots=True)
class Tool:
    """A tool exposed to the agent loop."""

    name: str
    description: str
    parameters: Mapping[str, Any] = field(default_factory=lambda: {"type": "object"})
    execute: ToolExecutor = None  # type: ignore[assignment]

    async def run(
        self,
        tool_call_id: str,
        arguments: Mapping[str, Any],
        signal: CancellationToken | None = None,
    ) -> ToolResult:
        """Invoke the executor, tolerating several common signatures."""
        import inspect

        params = inspect.signature(self.execute).parameters
        kwargs: dict[str, Any] = {}
        if "tool_call_id" in params:
            kwargs["tool_call_id"] = tool_call_id
        if "signal" in params:
            kwargs["signal"] = signal
        return await self.execute(dict(arguments), **kwargs)


def tool(name: str, description: str = "", **parameters: Any) -> Callable[..., Tool]:
    """Decorator building a :class:`Tool` from an async function."""

    def wrap(fn: ToolExecutor) -> Tool:
        schema = parameters.get("parameters") or {"type": "object"}
        return Tool(
            name=name,
            description=description or (fn.__doc__ or "").strip(),
            parameters=schema,
            execute=fn,
        )

    return wrap
