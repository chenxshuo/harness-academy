"""Level 8 - context compaction."""

from __future__ import annotations

import pytest

from harnesskit import ScriptedProvider, turn
from harnesskit.messages import (
    AssistantMessage,
    TextContent,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def long_transcript(turns: int = 20, size: int = 4000):
    """Build a transcript with interleaved tool calls, like a real session."""
    messages = [UserMessage(content="Refactor the auth module. Do not touch generated files.")]
    for i in range(turns):
        call = ToolCall(id=f"c{i}", name="read", arguments={"path": f"f{i}.py"})
        messages.append(AssistantMessage(content=[call], stop_reason="tool_use"))
        messages.append(
            ToolResultMessage(
                tool_call_id=f"c{i}",
                tool_name="read",
                content=[TextContent(text="x" * size)],
            )
        )
    return messages


def test_estimate_tokens_scales_with_content():
    from compaction import estimate_tokens

    small = estimate_tokens([UserMessage(content="hi")])
    large = estimate_tokens([UserMessage(content="x" * 4000)])

    assert large > small * 10, (
        f"Token estimate should scale with text length. "
        f"small={small}, large={large}"
    )


async def test_under_threshold_is_untouched():
    from compaction import compact

    messages = [UserMessage(content="hello"), AssistantMessage(content="hi")]
    provider = ScriptedProvider([turn("summary")])

    result = await compact(messages, provider=provider, threshold_tokens=100_000)

    assert len(result) == len(messages), (
        "A transcript under the threshold must be returned unchanged - "
        "compaction is not free, so do not do it needlessly."
    )
    assert provider.call_count == 0, (
        "Do not call the provider when no compaction is needed"
    )


async def test_over_threshold_shrinks_the_transcript():
    from compaction import compact, estimate_tokens

    messages = long_transcript()
    provider = ScriptedProvider([turn("A structured summary of the work so far.")])

    result = await compact(
        messages, provider=provider, threshold_tokens=1000, keep_recent_tokens=2000
    )

    assert len(result) < len(messages), (
        f"Compaction should reduce the message count "
        f"({len(messages)} -> {len(result)})"
    )
    assert estimate_tokens(result) < estimate_tokens(messages), (
        "The compacted transcript must be smaller in tokens, not just in count"
    )


async def test_summary_is_present_and_marked():
    from compaction import SUMMARY_PREFIX, compact

    provider = ScriptedProvider([turn("Goal: refactor auth. Constraint: no generated files.")])

    result = await compact(
        long_transcript(), provider=provider, threshold_tokens=1000, keep_recent_tokens=2000
    )

    texts = [getattr(m, "text", "") for m in result]
    assert any(SUMMARY_PREFIX.strip() in t for t in texts), (
        "The summary must be clearly labelled in the transcript so the model "
        "knows it is reading a compaction rather than a user instruction."
    )
    assert any("refactor auth" in t for t in texts), (
        "The model-generated summary content must appear in the result"
    )


async def test_recent_messages_are_preserved_verbatim():
    from compaction import compact

    messages = long_transcript()
    last_text = messages[-1].text
    provider = ScriptedProvider([turn("summary")])

    result = await compact(
        messages, provider=provider, threshold_tokens=1000, keep_recent_tokens=20_000
    )

    assert any(getattr(m, "text", "") == last_text for m in result), (
        "Recent messages must be kept exactly as they were. Summarizing the "
        "most recent turns loses the precise detail the model needs right now."
    )


async def test_split_never_separates_a_tool_call_from_its_result():
    """Compaction must not recreate Level 7's bug while fixing Level 8's."""
    from compaction import compact

    messages = long_transcript(turns=30)
    provider = ScriptedProvider([turn("summary")])

    result = await compact(
        messages, provider=provider, threshold_tokens=500, keep_recent_tokens=3000
    )

    # Every surviving result must still follow its call.
    call_ids = {
        c.id for m in result if isinstance(m, AssistantMessage) for c in m.tool_calls
    }
    for index, message in enumerate(result):
        if not isinstance(message, ToolResultMessage):
            continue
        assert message.tool_call_id in call_ids, (
            f"Compaction left an orphan tool result ({message.tool_call_id}) whose "
            f"call was summarized away. The split point must not fall between an "
            f"assistant message and its tool results - move the boundary earlier."
        )
        previous = result[index - 1]
        assert isinstance(previous, (AssistantMessage, ToolResultMessage)), (
            f"A tool result at index {index} is no longer adjacent to its call "
            f"after compaction."
        )


async def test_find_split_point_returns_a_valid_index():
    from compaction import find_split_point

    messages = long_transcript(turns=10)
    index = find_split_point(messages, keep_recent_tokens=2000)

    assert 0 <= index <= len(messages), f"split index {index} out of range"
    assert not isinstance(messages[index], ToolResultMessage), (
        f"find_split_point returned index {index}, which is a ToolResultMessage. "
        f"Splitting there orphans the result from its call - move the boundary "
        f"earlier so the owning assistant message goes with it."
    )
