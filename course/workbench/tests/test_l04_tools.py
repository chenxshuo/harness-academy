"""Level 4 - real tools, and the boundary conditions that define them."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def test_read_returns_file_contents(tmp_path):
    from tools_impl import create_read_tool

    (tmp_path / "notes.txt").write_text("alpha\nbeta\n")
    tool = create_read_tool(tmp_path)

    result = await tool.run("c1", {"path": "notes.txt"})

    assert "alpha" in result.content and "beta" in result.content


async def test_read_missing_file_returns_error_not_raises(tmp_path):
    """A tool must not raise for an ordinary, expected failure."""
    from tools_impl import create_read_tool

    tool = create_read_tool(tmp_path)

    try:
        result = await tool.run("c1", {"path": "nope.txt"})
    except Exception as exc:
        pytest.fail(
            f"read raised {type(exc).__name__} for a missing file. Return a "
            f"ToolResult describing the error instead - the model can recover "
            f"from an error message, but not from a crash."
        )

    assert "error" in result.content.lower() or "not found" in result.content.lower(), (
        f"The result should explain what went wrong. Got: {result.content[:100]!r}"
    )


async def test_read_truncates_large_files(tmp_path):
    """An untruncated read can destroy the context window in one call."""
    from tools_impl import MAX_READ_BYTES, create_read_tool

    (tmp_path / "big.txt").write_text("x" * (MAX_READ_BYTES * 3))
    tool = create_read_tool(tmp_path)

    result = await tool.run("c1", {"path": "big.txt"})

    assert len(result.content) < MAX_READ_BYTES * 2, (
        f"read returned {len(result.content)} chars for a file of "
        f"{MAX_READ_BYTES * 3}. It must truncate - one unbounded read can "
        f"consume an entire context window."
    )
    assert "trunc" in result.content.lower(), (
        "Say that the content was truncated, so the model knows it saw a "
        "partial file rather than the whole thing."
    )


async def test_write_creates_a_file(tmp_path):
    from tools_impl import create_write_tool

    tool = create_write_tool(tmp_path)

    await tool.run("c1", {"path": "out/new.txt", "content": "hello"})

    assert (tmp_path / "out" / "new.txt").read_text() == "hello", (
        "write should create parent directories as needed"
    )


async def test_write_refuses_to_escape_the_working_directory(tmp_path):
    """The model may act on text it just read. Path escape is a real attack."""
    from tools_impl import create_write_tool

    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("original")

    tool = create_write_tool(root)
    result = await tool.run("c1", {"path": "../secret.txt", "content": "OVERWRITTEN"})

    assert outside.read_text() == "original", (
        "write escaped the working directory and modified a file outside it. "
        "Resolve the path first, then check containment with is_relative_to - "
        "string matching on '..' is not sufficient."
    )
    assert "error" in result.content.lower() or "refus" in result.content.lower(), (
        "Refusing is right, but say so clearly in the result."
    )


async def test_write_refuses_absolute_paths_outside_root(tmp_path):
    from tools_impl import create_write_tool

    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "abs.txt"
    outside.write_text("original")

    tool = create_write_tool(root)
    await tool.run("c1", {"path": str(outside), "content": "OVERWRITTEN"})

    assert outside.read_text() == "original", (
        "An absolute path pointing outside the working directory must also be "
        "refused, not just relative ones containing '..'."
    )


async def test_read_result_carries_structured_details(tmp_path):
    """content goes to the model; details goes to the UI."""
    from tools_impl import create_read_tool

    (tmp_path / "a.txt").write_text("hello")
    tool = create_read_tool(tmp_path)

    result = await tool.run("c1", {"path": "a.txt"})

    assert result.details is not None, (
        "Populate `details` with structured metadata (path, bytes). It is free - "
        "the UI can use it without spending any model tokens."
    )
