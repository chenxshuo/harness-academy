"""Level 9, step B - history as a tree.

Four tests. One idea: each entry names its parent, so two entries can share
one parent and you get branching for free.
"""

from __future__ import annotations

import pytest


def test_path_to_walks_parent_pointers(tmp_path):
    from session_store import Entry, SessionStore

    store = SessionStore(tmp_path / "s.jsonl")
    a = store.append(Entry(type="message", role="user", text="a"))
    b = store.append(Entry(type="message", role="assistant", text="b", parent_id=a.id))
    c = store.append(Entry(type="message", role="user", text="c", parent_id=b.id))

    path = store.path_to(c.id)

    assert [e.text for e in path] == ["a", "b", "c"], (
        f"path_to must return root-to-entry order, got "
        f"{[e.text for e in path]}. Walk parents up, then reverse."
    )


def test_path_to_a_root_entry_is_just_itself(tmp_path):
    from session_store import Entry, SessionStore

    store = SessionStore(tmp_path / "s.jsonl")
    root = store.append(Entry(type="message", role="user", text="only"))

    assert [e.text for e in store.path_to(root.id)] == ["only"]


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
        "This needs no special branching code - it falls out of parent "
        "pointers. That is the whole point of the design."
    )


def test_an_abandoned_branch_is_still_on_disk(tmp_path):
    from session_store import Entry, SessionStore

    store = SessionStore(tmp_path / "s.jsonl")
    root = store.append(Entry(type="message", role="user", text="q"))
    store.append(Entry(type="message", role="assistant", text="first try", parent_id=root.id))
    store.append(Entry(type="message", role="assistant", text="second try", parent_id=root.id))

    assert len(store.read_all()) == 3, (
        "Branching away from an answer must not delete it. Append-only means "
        "the abandoned branch is still there and still reachable."
    )
