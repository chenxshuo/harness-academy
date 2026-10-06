"""Level 9, step C - replay a path into messages.

Four tests. The payoff: compaction changes what the model sees without
deleting anything from disk.
"""

from __future__ import annotations

import pytest


def test_replay_builds_messages_from_a_path(tmp_path):
    from session_store import Entry, SessionStore

    store = SessionStore(tmp_path / "s.jsonl")
    a = store.append(Entry(type="message", role="user", text="hello"))
    b = store.append(Entry(type="message", role="assistant", text="hi", parent_id=a.id))

    messages = store.replay(store.path_to(b.id))

    assert len(messages) == 2, f"Expected 2 messages, got {len(messages)}"
    assert messages[0].text == "hello"
    assert type(messages[1]).__name__ == "AssistantMessage", (
        "The `role` field decides which message class to build"
    )


def test_replay_restores_tool_results(tmp_path):
    from session_store import Entry, SessionStore

    store = SessionStore(tmp_path / "s.jsonl")
    a = store.append(Entry(type="message", role="user", text="go"))
    b = store.append(
        Entry(
            type="message", role="tool", text="file contents",
            tool_call_id="c1", tool_name="read", parent_id=a.id,
        )
    )

    messages = store.replay(store.path_to(b.id))
    result = messages[-1]

    assert type(result).__name__ == "ToolResultMessage"
    assert result.tool_call_id == "c1", (
        "A tool result must round-trip its tool_call_id, or the pairing "
        "invariant from Level 7 breaks on resume."
    )


def test_replay_applies_compaction(tmp_path):
    from session_store import Entry, SessionStore

    store = SessionStore(tmp_path / "s.jsonl")
    a = store.append(Entry(type="message", role="user", text="old question"))
    b = store.append(Entry(type="message", role="assistant", text="old answer", parent_id=a.id))
    c = store.append(Entry(type="message", role="user", text="recent question", parent_id=b.id))
    comp = store.append(
        Entry(
            type="compaction",
            summary="Earlier: user asked a question, got an answer.",
            first_kept_entry_id=c.id,
            parent_id=c.id,
        )
    )

    messages = store.replay(store.path_to(comp.id))
    texts = " ".join(getattr(m, "text", "") for m in messages)

    assert "Earlier: user asked" in texts, (
        "The summary must appear in the replayed context"
    )
    assert "old answer" not in texts, (
        "Messages before first_kept_entry_id must be replaced by the summary"
    )
    assert "recent question" in texts, (
        "Entries from first_kept_entry_id onward must survive"
    )


def test_compaction_deletes_nothing_from_disk(tmp_path):
    """The Act II thesis, made concrete."""
    from session_store import Entry, SessionStore

    store = SessionStore(tmp_path / "s.jsonl")
    a = store.append(Entry(type="message", role="user", text="old question"))
    b = store.append(Entry(type="message", role="assistant", text="old answer", parent_id=a.id))
    c = store.append(Entry(type="message", role="user", text="recent", parent_id=b.id))
    store.append(
        Entry(type="compaction", summary="summary", first_kept_entry_id=c.id, parent_id=c.id)
    )

    assert len(store.read_all()) == 4, (
        "Compaction must NOT delete entries. It appends a compaction record; "
        "the effect happens at replay time. That is what makes compaction "
        "reversible, auditable, and safe to get wrong."
    )
