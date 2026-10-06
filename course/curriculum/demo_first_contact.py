"""Level 1's demo: a complete working agent, in one readable file.

This runs before the learner has been told anything. The point is for them to
*see* two provider calls happen, and to notice the gap between them.

It is intentionally not imported by anything else. It is a thing to run.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from harnesskit import (  # noqa: E402
    AssistantDoneEvent,
    AssistantMessage,
    ScriptedProvider,
    TextContent,
    Tool,
    ToolCall,
    ToolResult,
    ToolResultMessage,
    UserMessage,
    turn,
)

BLUE, GREEN, DIM, YELLOW, RESET = "\033[94m", "\033[92m", "\033[2m", "\033[93m", "\033[0m"


async def main() -> None:
    workdir = Path(__file__).parent / "_scratch"
    workdir.mkdir(exist_ok=True)
    notes = workdir / "notes.txt"
    notes.write_text("alpha\nbeta\ngamma\ndelta\n")

    # --- the tool ------------------------------------------------------
    async def read_file(arguments: dict) -> ToolResult:
        target = workdir / str(arguments["path"])
        text = target.read_text()
        print(f"{YELLOW}  [the harness actually opens {target.name} here]{RESET}")
        return ToolResult(content=text)

    read_tool = Tool(
        name="read",
        description="Read a file from disk.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        execute=read_file,
    )

    # A scripted model: first it asks for the tool, then it answers.
    call = ToolCall(id="call_1", name="read", arguments={"path": "notes.txt"})
    provider = ScriptedProvider(
        [
            turn(tool_calls=[call]),
            turn("notes.txt has 4 lines: alpha, beta, gamma, delta."),
        ]
    )

    messages: list = [UserMessage(content="How many lines are in notes.txt?")]
    tools = [read_tool]

    print(f"\n{BLUE}user:{RESET} How many lines are in notes.txt?\n")

    # --- the loop ------------------------------------------------------
    # This is the whole algorithm. Twenty lines.
    call_number = 0
    while True:
        call_number += 1
        print(f"{DIM}--- provider call {call_number} ---{RESET}")

        assistant: AssistantMessage | None = None
        async for event in provider.stream_response(
            model="scripted", system="You are a coding assistant.",
            messages=messages, tools=tools,
        ):
            if isinstance(event, AssistantDoneEvent):
                assistant = event.message

        assert assistant is not None
        messages.append(assistant)

        if assistant.text:
            print(f"{GREEN}assistant:{RESET} {assistant.text}")

        if not assistant.tool_calls:
            print(f"{DIM}--- no tool calls, so the loop stops ---{RESET}")
            break

        for tool_call in assistant.tool_calls:
            print(
                f"{DIM}  model requests:{RESET} {tool_call.name}"
                f"({tool_call.arguments})"
            )
            tool = next(t for t in tools if t.name == tool_call.name)
            result = await tool.run(tool_call.id, tool_call.arguments)
            messages.append(
                ToolResultMessage(
                    tool_call_id=tool_call.id,
                    tool_name=tool_call.name,
                    content=[TextContent(text=result.content)],
                )
            )
            preview = result.content.replace("\n", "\\n")[:40]
            print(f"{DIM}  result appended to transcript:{RESET} {preview}...")
        print()

    # --- what just happened --------------------------------------------
    print(f"\n{DIM}{'=' * 62}{RESET}")
    print(f"provider calls: {BLUE}{provider.call_count}{RESET}")
    print(f"final transcript ({len(messages)} messages):")
    for index, message in enumerate(messages):
        kind = type(message).__name__
        text = getattr(message, "text", "").replace("\n", " ")[:46]
        print(f"  {index}. {kind:20} {DIM}{text}{RESET}")
    print(f"{DIM}{'=' * 62}{RESET}")
    print(
        f"\n{YELLOW}Question to sit with:{RESET} the model never opened a file.\n"
        f"So where did the agent's ability to read one come from?\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
