"""Level 9, step A - append-only JSONL storage.

Four tests. One idea: write one JSON object per line, never modify what is
already on disk.
"""

from __future__ import annotations

import json

import pytest


def test_append_and_read_round_trip(tmp_path):
    from session_store import Entry, SessionStore

    store = SessionStore(tmp_path / "session.jsonl")
    store.append(Entry(type="message", role="user", text="hello"))
    store.append(Entry(type="message", role="assistant", text="hi"))

    entries = store.read_all()

    assert len(entries) == 2, f"Expected 2 entries, got {len(entries)}"
    assert entries[0].text == "hello"
    assert entries[1].role == "assistant"


def test_storage_is_one_json_object_per_line(tmp_path):
    """JSONL: readable by hand, appendable without re-parsing the file."""
    from session_store import Entry, SessionStore

    path = tmp_path / "session.jsonl"
    store = SessionStore(path)
    store.append(Entry(type="message", role="user", text="a"))
    store.append(Entry(type="message", role="user", text="b"))

    lines = [ln for ln in path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 2, f"Expected 2 JSON lines, found {len(lines)}"
    for line in lines:
        json.loads(line)  # each line must parse on its own


def test_read_all_on_missing_file_is_empty(tmp_path):
    from session_store import SessionStore

    assert SessionStore(tmp_path / "nope.jsonl").read_all() == [], (
        "A session file that does not exist yet is an empty session, not an "
        "error. Return [] rather than raising."
    )


def test_append_never_rewrites_existing_bytes(tmp_path):
    """Append-only is the property everything else in this level depends on."""
    from session_store import Entry, SessionStore

    path = tmp_path / "session.jsonl"
    store = SessionStore(path)
    first = store.append(Entry(type="message", role="user", text="original"))
    before = path.read_text()

    store.append(Entry(type="message", role="assistant", text="reply", parent_id=first.id))
    after = path.read_text()

    assert after.startswith(before), (
        "Appending must not modify bytes already on disk. The new entry goes "
        "at the end; everything before it stays byte-identical. Open the file "
        "in 'a' mode."
    )


def test_append_returns_the_entry(tmp_path):
    """The caller needs the generated id to use as the next entry's parent."""
    from session_store import Entry, SessionStore

    store = SessionStore(tmp_path / "s.jsonl")
    entry = store.append(Entry(type="message", role="user", text="x"))

    assert entry is not None and entry.id, (
        "append() must return the entry it wrote, so the caller can chain "
        "parent_id on the next one."
    )
