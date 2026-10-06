"""Run the learner's capstone agent against a real model.

Everything in the course up to this point used a scripted provider, because
determinism is what makes the exercises teachable. This script removes that
scaffolding. It is the moment the architecture stops being an exercise.

It adapts whatever provider credentials are already configured in the
environment. No new keys, no new accounts.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.request
from collections.abc import AsyncIterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, os.environ.get("ACADEMY_WORKBENCH", str(ROOT / "workbench")))

from harnesskit.messages import (  # noqa: E402
    AssistantMessage,
    TextContent,
    ToolCall,
    ToolResultMessage,
)
from harnesskit.provider_events import (  # noqa: E402
    AssistantDoneEvent,
    AssistantErrorEvent,
    AssistantStartEvent,
    ProviderEvent,
    TextDeltaEvent,
    ToolCallEndEvent,
)


class AnthropicProvider:
    """A minimal real provider speaking the Anthropic Messages API.

    Note how small this is. The provider layer's whole job is translating one
    vendor's wire format into the harness's neutral events - which is exactly
    the boundary Level 10 asked you to place.
    """

    def __init__(self, *, base_url: str, api_key: str, max_tokens: int = 4096) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.max_tokens = max_tokens

    def stream_response(
        self, *, model, system, messages, tools=(), signal=None, **_
    ) -> AsyncIterator[ProviderEvent]:
        payload = {
            "model": model,
            "max_tokens": self.max_tokens,
            "stream": True,
            "system": system or "You are a helpful coding assistant.",
            "messages": _to_anthropic(messages),
        }
        if tools:
            payload["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": dict(t.parameters)}
                for t in tools
            ]

        async def iterator() -> AsyncIterator[ProviderEvent]:
            queue: asyncio.Queue = asyncio.Queue()
            loop = asyncio.get_running_loop()

            def pump() -> None:
                try:
                    request = urllib.request.Request(
                        f"{self.base_url}/v1/messages",
                        data=json.dumps(payload).encode(),
                        headers={
                            "content-type": "application/json",
                            "x-api-key": self.api_key,
                            "anthropic-version": "2023-06-01",
                        },
                    )
                    with urllib.request.urlopen(request, timeout=180) as response:
                        for raw in response:
                            line = raw.decode().strip()
                            if line.startswith("data: "):
                                loop.call_soon_threadsafe(queue.put_nowait, line[6:])
                except Exception as exc:  # surfaced as an assistant error below
                    loop.call_soon_threadsafe(queue.put_nowait, {"__error__": str(exc)})
                loop.call_soon_threadsafe(queue.put_nowait, None)

            asyncio.get_running_loop().run_in_executor(None, pump)

            yield AssistantStartEvent()
            text_parts: list[str] = []
            content: list = []
            tool_blocks: dict[int, dict] = {}

            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, dict) and "__error__" in item:
                    yield AssistantErrorEvent(
                        error=AssistantMessage(stop_reason="error", error_message=item["__error__"])
                    )
                    return
                if item.strip() == "[DONE]":
                    continue
                try:
                    event = json.loads(item)
                except json.JSONDecodeError:
                    continue

                kind = event.get("type")
                if kind == "content_block_start":
                    block = event.get("content_block", {})
                    if block.get("type") == "tool_use":
                        tool_blocks[event["index"]] = {
                            "id": block["id"], "name": block["name"], "json": "",
                        }
                elif kind == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text_parts.append(delta["text"])
                        yield TextDeltaEvent(
                            delta=delta["text"],
                            partial=AssistantMessage(content=[TextContent(text="".join(text_parts))]),
                        )
                    elif delta.get("type") == "input_json_delta":
                        block = tool_blocks.get(event["index"])
                        if block is not None:
                            block["json"] += delta.get("partial_json", "")
                elif kind == "content_block_stop":
                    block = tool_blocks.get(event.get("index"))
                    if block is not None:
                        try:
                            args = json.loads(block["json"]) if block["json"].strip() else {}
                        except json.JSONDecodeError:
                            args = {}
                        call = ToolCall(id=block["id"], name=block["name"], arguments=args)
                        content.append(call)
                        yield ToolCallEndEvent(
                            tool_call=call, partial=AssistantMessage(content=list(content))
                        )

            text = "".join(text_parts)
            final_content = ([TextContent(text=text)] if text else []) + content
            yield AssistantDoneEvent(
                message=AssistantMessage(
                    model=model,
                    content=final_content,
                    stop_reason="tool_use" if content else "stop",
                )
            )

        return iterator()


def _to_anthropic(messages) -> list[dict]:
    """Translate harness messages into Anthropic's wire shape."""
    out: list[dict] = []
    for message in messages:
        role = getattr(message, "role", "")
        if role == "user":
            out.append({"role": "user", "content": message.content})
        elif role == "assistant":
            blocks: list[dict] = []
            if message.text:
                blocks.append({"type": "text", "text": message.text})
            for call in message.tool_calls:
                blocks.append({
                    "type": "tool_use", "id": call.id,
                    "name": call.name, "input": dict(call.arguments),
                })
            if blocks:
                out.append({"role": "assistant", "content": blocks})
        elif role == "tool":
            out.append({
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": message.text or "(empty)",
                    "is_error": message.is_error,
                }],
            })
    return out


def resolve_provider() -> tuple[AnthropicProvider, str]:
    base = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not key:
        raise SystemExit(
            "No credentials found. Set ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN),\n"
            "optionally with ANTHROPIC_BASE_URL for a local or proxied endpoint."
        )
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
    return AnthropicProvider(base_url=base, api_key=key), model


async def main() -> None:
    try:
        from myagent import MyAgent
    except ImportError as exc:
        raise SystemExit(
            f"Could not import your capstone agent: {exc}\n"
            "Finish Level 12 first - this runs YOUR agent, not a reference one."
        ) from exc

    provider, model = resolve_provider()
    scratch = ROOT / "curriculum" / "_scratch" / "live"
    scratch.mkdir(parents=True, exist_ok=True)

    prompt = " ".join(sys.argv[1:]) or (
        "Create a file called hello.py containing a function that returns "
        "the string 'hello', then read it back to confirm what you wrote."
    )

    print(f"\n  model:  {model}")
    print(f"  cwd:    {scratch}")
    print(f"  prompt: {prompt}\n")

    agent = MyAgent(
        provider=provider,
        model=model,
        cwd=scratch,
        session_path=scratch / "session.jsonl",
        system=(
            "You are a coding assistant with read, write and bash tools. "
            "Use them to complete the task, then briefly report what you did."
        ),
    )

    answer = await agent.run(prompt)
    print(f"\n  {'-' * 56}")
    print(f"  {answer}")
    print(f"  {'-' * 56}")
    print(f"\n  files now in {scratch.name}/:")
    for path in sorted(scratch.iterdir()):
        print(f"    {path.name}")
    print("\n  That was your harness. Not a reference implementation - yours.\n")


if __name__ == "__main__":
    asyncio.run(main())
