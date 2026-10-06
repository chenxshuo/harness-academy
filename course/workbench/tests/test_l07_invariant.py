"""Level 7 - the tool-pairing invariant."""

from __future__ import annotations

import pytest

from harnesskit.messages import (
    AssistantMessage,
    TextContent,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)


def test_broken_transcript_has_a_dangling_call():
    from break_invariant import make_broken_transcript

    messages = make_broken_transcript()

    call_ids = {
        c.id for m in messages if isinstance(m, AssistantMessage) for c in m.tool_calls
    }
    result_ids = {m.tool_call_id for m in messages if isinstance(m, ToolResultMessage)}

    assert call_ids, "The transcript must contain at least one tool call"
    assert call_ids - result_ids, (
        "make_broken_transcript must leave a tool call with no matching result - "
        "exactly what a cancelled tool execution produces."
    )


def test_validate_accepts_a_healthy_transcript():
    """A validator that flags healthy input is worse than no validator."""
    from break_invariant import validate

    call = ToolCall(id="c1", name="read", arguments={})
    healthy = [
        UserMessage(content="go"),
        AssistantMessage(content=[call], stop_reason="tool_use"),
        ToolResultMessage(tool_call_id="c1", tool_name="read", content=[TextContent(text="ok")]),
        AssistantMessage(content=[TextContent(text="done")], stop_reason="stop"),
    ]

    assert validate(healthy) == [], (
        f"A valid transcript must produce no problems, got {validate(healthy)}"
    )


def test_validate_detects_dangling_call():
    from break_invariant import validate

    problems = validate(
        [
            UserMessage(content="go"),
            AssistantMessage(content=[ToolCall(id="c1", name="read")], stop_reason="tool_use"),
            UserMessage(content="never mind"),
        ]
    )

    assert any("dangling" in p for p in problems), (
        f"A tool call with no result must be reported. Got: {problems}"
    )


def test_validate_detects_orphan_result():
    from break_invariant import validate

    problems = validate(
        [
            UserMessage(content="go"),
            ToolResultMessage(tool_call_id="ghost", tool_name="read"),
        ]
    )

    assert any("orphan" in p for p in problems), (
        f"A result with no matching call must be reported. Got: {problems}"
    )


def test_validate_detects_misplaced_result():
    """Adjacency matters: a result two messages later still fails on providers."""
    from break_invariant import validate

    problems = validate(
        [
            AssistantMessage(content=[ToolCall(id="c1", name="read")], stop_reason="tool_use"),
            UserMessage(content="interrupting"),
            ToolResultMessage(tool_call_id="c1", tool_name="read"),
        ]
    )

    assert any("misplaced" in p for p in problems), (
        f"A result separated from its call must be reported - 'immediately "
        f"after' is a real requirement, not a style preference. Got: {problems}"
    )


def test_validate_detects_duplicate_results():
    from break_invariant import validate

    problems = validate(
        [
            AssistantMessage(content=[ToolCall(id="c1", name="read")], stop_reason="tool_use"),
            ToolResultMessage(tool_call_id="c1", tool_name="read"),
            ToolResultMessage(tool_call_id="c1", tool_name="read"),
        ]
    )

    assert any("duplicate" in p for p in problems), (
        f"Two results for one call must be reported. Got: {problems}"
    )


def test_validate_handles_parallel_calls_correctly():
    """Two calls in one message, two results after it, in order. This is legal."""
    from break_invariant import validate

    healthy = [
        AssistantMessage(
            content=[ToolCall(id="c1", name="read"), ToolCall(id="c2", name="read")],
            stop_reason="tool_use",
        ),
        ToolResultMessage(tool_call_id="c1", tool_name="read"),
        ToolResultMessage(tool_call_id="c2", tool_name="read"),
    ]

    assert validate(healthy) == [], (
        f"Parallel tool calls followed by their results in order are valid. "
        f"Got: {validate(healthy)}"
    )
