"""Level 3 - two frontends over one event stream."""

from __future__ import annotations

import json

import pytest

from harnesskit import (
    AgentEndEvent,
    AgentStartEvent,
    MessageEndEvent,
    MessageStartEvent,
    ScriptedProvider,
    Tool,
    ToolCall,
    ToolResult,
    UserMessage,
    turn,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def build_events():
    """Produce a realistic event stream: one tool call, then an answer."""
    from loop import run_agent_loop

    async def execute(arguments):
        return ToolResult(content="line one\nline two")

    tool = Tool(name="read", description="Read.", execute=execute)
    call = ToolCall(id="c1", name="read", arguments={"path": "notes.txt"})
    provider = ScriptedProvider([turn(tool_calls=[call]), turn("The file has 2 lines.")])
    messages = [UserMessage(content="how many lines?")]
    return [
        event
        async for event in run_agent_loop(
            provider=provider, model="m", system="s", messages=messages, tools=[tool]
        )
    ]


async def test_text_renderer_shows_assistant_and_tool_output():
    from renderers import render_text

    output = render_text(await build_events())

    assert "The file has 2 lines." in output, (
        "render_text must include the assistant's final text. "
        "Look at MessageEndEvent for assistant messages."
    )
    assert "read" in output, "render_text should name the tool that ran"
    assert "line one" in output, "render_text should include the tool's result content"


async def test_json_renderer_is_serializable():
    from renderers import render_json

    records = render_json(await build_events())

    assert isinstance(records, list) and records, "render_json must return a non-empty list"
    assert all(isinstance(r, dict) for r in records), "every record must be a dict"
    assert all("type" in r for r in records), "every record needs a 'type' key"
    try:
        json.dumps(records)
    except (TypeError, ValueError) as exc:
        pytest.fail(
            f"render_json output must be JSON-serializable, but json.dumps failed: {exc}. "
            f"Do not put dataclass instances in the records."
        )


async def test_both_renderers_consume_the_same_stream():
    """The architectural claim: one stream, many consumers, no coupling."""
    from renderers import render_json, render_text

    events = await build_events()
    before = list(events)

    text = render_text(events)
    records = render_json(events)

    assert events == before, (
        "A renderer must not mutate the event list. Frontends are read-only "
        "consumers of the event stream."
    )
    assert text and records, "Both renderers must produce output from the same events"


async def test_renderers_do_not_touch_the_provider_or_tools():
    """Renderers receive events. They must not re-run anything."""
    import inspect

    import renderers

    source = inspect.getsource(renderers)
    for forbidden in ("stream_response", "run_agent_loop", "ScriptedProvider", ".run("):
        assert forbidden not in source, (
            f"renderers.py references {forbidden!r}. A frontend must consume events "
            f"only - it cannot call the provider, run the loop, or execute tools. "
            f"That separation is the entire point of the event contract."
        )


async def test_adding_a_renderer_requires_no_loop_change():
    """A third consumer works with zero changes anywhere else."""
    events = await build_events()

    # A brand new 'frontend', written here, with no cooperation from the loop.
    tool_names = [e.tool_name for e in events if e.type == "tool_execution_end"]

    assert tool_names == ["read"], (
        "Any new consumer should be able to extract what it needs from the "
        "event stream alone."
    )
