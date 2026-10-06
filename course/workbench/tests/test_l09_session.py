"""Level 9 - append-only, branchable session storage."""

from __future__ import annotations

import json

import pytest


def test_append_and_read_round_trip(tmp_path):
    from session_store import Entry, SessionStore

    store = SessionStore(tmp_path / "session.jsonl")
    store.append(Entry(type="message", role="user", text="hello"))
    store.append(Entry(type="message", role="assistant", text="hi"))

    entries = store.read_all()

    assert len(entries) == 2
    assert entries[0].text == "hello"
    assert entries[1].role == "assistant"


def test_storage_is_jsonl(tmp_path):
    """One JSON object per line - readable by hand, appendable without parsing."""
    from session_store import Entry, SessionStore

    path = tmp_path / "session.jsonl"
    store = SessionStore(path)
    store.append(Entry(type="message", role="user", text="a"))
    store.append(Entry(type="message", role="user", text="b"))

    lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 2, f"Expected 2 JSON lines, found {len(lines)}"
    for line in lines:
        json.loads(line)  # must parse individually


def test_read_all_on_missing_file_is_empty(tmp_path):
    from session_store import SessionStore

    assert SessionStore(tmp_path / "nope.jsonl").read_all() == [], (
        "A session file that does not exist yet is an empty session, not an error"
    )


def test_append_never_rewrites_existing_entries(tmp_path):
    """Append-only is the property everything else depends on."""
    from session_store import Entry, SessionStore

    path = tmp_path / "session.jsonl"
    store = SessionStore(path)
    first = store.append(Entry(type="message", role="user", text="original"))
    before = path.read_text()

    store.append(Entry(type="message", role="assistant", text="reply", parent_id=first.id))
    after = path.read_text()

    assert after.startswith(before), (
        "Appending must not modify bytes already on disk. The new entry goes "
        "at the end; everything before it stays byte-identical."
    )


def test_path_to_walks_parent_pointers(tmp_path):
    from session_store import Entry, SessionStore

    store = SessionStore(tmp_path / "s.jsonl")
    a = store.append(Entry(type="message", role="user", text="a"))
    b = store.append(Entry(type="message", role="assistant", text="b", parent_id=a.id))
    c = store.append(Entry(type="message", role="user", text="c", parent_id=b.id))

    path = store.path_to(c.id)

    assert [e.text for e in path] == ["a", "b", "c"], (
        f"path_to must return root-to-entry order, got {[e.text for e in path]}"
    )


def test_branching_produces_two_independent_histories(tmp_path):
    """The reason history is a tree rather than a list."""
    from session_store import Entry, SessionStore

    store = SessionStore(tmp_path / "s.jsonl")
    root = store.append(Entry(type="message", role="user", text="original question"))
    branch_a = store.append(
        Entry(type="message", role="assistant", text="answer A", parent_id=root.id)
    )
    branch_b = store.append(
        Entry(type="message", role="assistant", text="answer B", parent_id=root.id)
    )

    path_a = [e.text for e in store.path_to(branch_a.id)]
    path_b = [e.text for e in store.path_to(branch_b.id)]

    assert path_a == ["original question", "answer A"]
    assert path_b == ["original question", "answer B"], (
        "Two entries sharing a parent must yield two independent histories. "
        "This needs no special branching code - it falls out of parent pointers."
    )


def test_replay_builds_messages_from_a_path(tmp_path):
    from session_store import Entry, SessionStore

    store = SessionStore(tmp_path / "s.jsonl")
    a = store.append(Entry(type="message", role="user", text="hello"))
    b = store.append(Entry(type="message", role="assistant", text="hi", parent_id=a.id))

    messages = store.replay(store.path_to(b.id))

    assert len(messages) == 2
    assert messages[0].text == "hello"
    assert type(messages[1]).__name__ == "AssistantMessage"


def test_replay_applies_compaction_without_deleting_entries(tmp_path):
    """The Act II thesis, made concrete."""
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

    assert "Earlier: user asked" in texts, "The summary must appear in replayed context"
    assert "old answer" not in texts, (
        "Messages before first_kept_entry_id must be replaced by the summary "
        "in the active context"
    )
    assert "recent question" in texts, "Retained messages must survive compaction"

    assert len(store.read_all()) == 4, (
        "Compaction must NOT delete entries from disk. It appends a compaction "
        "record; the effect happens at replay time. This is what makes "
        "compaction reversible and auditable."
    )
