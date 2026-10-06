"""Compute Level 1's expected answer by actually running an agent.

The point: the course does not hardcode "the answer is 2". It runs a loop and
counts. If the substrate ever changed, this would change with it.

Prints one JSON line.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from harnesskit import (  # noqa: E402
    AssistantDoneEvent,
    ScriptedProvider,
    TextContent,
    Tool,
    ToolCall,
    ToolResult,
    ToolResultMessage,
    UserMessage,
    turn,
)


async def main() -> None:
    async def read_file(arguments: dict) -> ToolResult:
        return ToolResult(content="alpha\nbeta\ngamma\ndelta\n")

    tool = Tool(name="read", description="Read.", execute=read_file)
    call = ToolCall(id="call_1", name="read", arguments={"path": "notes.txt"})
    provider = ScriptedProvider(
        [turn(tool_calls=[call]), turn("notes.txt has 4 lines.")]
    )

    messages: list = [UserMessage(content="How many lines are in notes.txt?")]
    stop_reason = ""

    while True:
        assistant = None
        async for event in provider.stream_response(
            model="scripted", system="s", messages=messages, tools=[tool]
        ):
            if isinstance(event, AssistantDoneEvent):
                assistant = event.message
        assert assistant is not None
        messages.append(assistant)
        if not assistant.tool_calls:
            stop_reason = "assistant message contained no tool calls"
            break
        for tool_call in assistant.tool_calls:
            result = await tool.run(tool_call.id, tool_call.arguments)
            messages.append(
                ToolResultMessage(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    content=[TextContent(text=result.content)],
                )
            )

    print(
        json.dumps(
            {
                "provider_calls": provider.call_count,
                "answer": str(provider.call_count),
                "stop_reason": stop_reason,
                "transcript": [type(m).__name__ for m in messages],
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
