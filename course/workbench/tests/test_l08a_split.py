"""Level 8, step A - estimate tokens and find a safe split point.

Five tests. Two small functions, no provider calls, no summarization yet.
"""

from __future__ import annotations

import pytest

from harnesskit.messages import (
    AssistantMessage,
    TextContent,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)


def long_transcript(turns: int = 20, size: int = 4000):
    """A transcript with interleaved tool calls, like a real session."""
    messages = [UserMessage(content="Refactor auth. Do not touch generated files.")]
    for i in range(turns):
        call = ToolCall(id=f"c{i}", name="read", arguments={"path": f"f{i}.py"})
        messages.append(AssistantMessage(content=[call], stop_reason="tool_use"))
        messages.append(
            ToolResultMessage(
                tool_call_id=f"c{i}", tool_name="read",
                content=[TextContent(text="x" * size)],
            )
        )
    return messages


def test_estimate_scales_with_content():
    from compaction import estimate_tokens

    small = estimate_tokens([UserMessage(content="hi")])
    large = estimate_tokens([UserMessage(content="x" * 4000)])

    assert large > small * 10, (
        f"Token estimate should scale with text length. small={small}, "
        f"large={large}. Use len(text) // 4 plus a small per-message overhead."
    )


def test_estimate_counts_every_message():
    from compaction import estimate_tokens

    one = estimate_tokens([UserMessage(content="x" * 400)])
    three = estimate_tokens([UserMessage(content="x" * 400)] * 3)

    assert three > one * 2, (
        "Every message in the list must contribute to the estimate"
    )


def test_split_point_is_in_range():
    from compaction import find_split_point

    messages = long_transcript(turns=10)
    index = find_split_point(messages, keep_recent_tokens=2000)

    assert 0 <= index <= len(messages), f"split index {index} is out of range"


def test_split_keeps_roughly_the_requested_recent_budget():
    from compaction import estimate_tokens, find_split_point

    messages = long_transcript(turns=20, size=4000)
    index = find_split_point(messages, keep_recent_tokens=5000)

    kept = estimate_tokens(messages[index:])
    assert kept >= 4000, (
        f"The retained tail holds about {kept} tokens but keep_recent_tokens "
        f"was 5000. Walk backwards accumulating until you reach the budget."
    )
    assert index > 0, (
        "With a long transcript and a small budget, some messages must be "
        "split off for summarization."
    )


def test_split_never_lands_on_a_tool_result():
    """This is the rule that keeps Level 7's invariant intact."""
    from compaction import find_split_point

    messages = long_transcript(turns=10)

    for budget in (1000, 2000, 5000, 9000, 15000):
        index = find_split_point(messages, keep_recent_tokens=budget)
        if index >= len(messages):
            continue
        assert not isinstance(messages[index], ToolResultMessage), (
            f"With keep_recent_tokens={budget}, find_split_point returned "
            f"index {index}, which is a ToolResultMessage. Splitting there "
            f"orphans the result from the assistant message that called it. "
            f"Move the boundary EARLIER until it is not a tool result."
        )
