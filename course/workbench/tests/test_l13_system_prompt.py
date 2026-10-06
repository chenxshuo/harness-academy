"""Level 13 - system prompt assembly with provenance."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FakeTool:
    name: str
    description: str


def test_preamble_is_the_first_source():
    from system_prompt import build_system_prompt

    result = build_system_prompt(preamble="You are an agent.")

    assert result.sources, "the preamble must produce a source record"
    assert result.sources[0].kind == "default"
    assert "You are an agent." in result.text


def test_tools_are_listed_and_attributed():
    from system_prompt import build_system_prompt

    result = build_system_prompt(
        preamble="P",
        tools=[FakeTool("read", "Read a file."), FakeTool("bash", "Run a command.")],
    )

    assert "read" in result.text and "Read a file." in result.text
    kinds = [s.kind for s in result.sources]
    assert "tools" in kinds, (
        f"the tool list needs its own source record, got {kinds}. Provenance is "
        f"the point: a section nobody can attribute is a section nobody can debug."
    )


def test_no_tools_means_no_tools_section():
    from system_prompt import build_system_prompt

    result = build_system_prompt(preamble="P", tools=[])

    assert "tools" not in [s.kind for s in result.sources], (
        "an empty tool section is worse than none - it tells the model it has "
        "tools and then lists nothing"
    )


def test_each_context_file_is_its_own_source():
    from system_prompt import build_system_prompt

    result = build_system_prompt(
        preamble="P",
        context_files=[("AGENTS.md", "Use tabs."), ("sub/AGENTS.md", "Use spaces.")],
    )

    context = [s for s in result.sources if s.kind == "context"]
    assert len(context) == 2, (
        f"expected one source per context file, got {len(context)}. Merging them "
        f"means you cannot tell the user which file contributed a rule."
    )
    assert any("AGENTS.md" in s.label for s in context), "label with the path"


def test_text_matches_the_sources():
    """Provenance that disagrees with the text is worse than none."""
    from system_prompt import build_system_prompt

    result = build_system_prompt(
        preamble="P",
        tools=[FakeTool("read", "Read.")],
        context_files=[("AGENTS.md", "CONTEXT_MARKER")],
        extra_sections=[("Runtime", "EXTRA_MARKER")],
    )

    for source in result.sources:
        assert source.content in result.text, (
            f"source {source.label!r} claims content that is not in the final "
            f"text. Build the text from the sources, not alongside them."
        )
    assert "CONTEXT_MARKER" in result.text
    assert "EXTRA_MARKER" in result.text


def test_section_order_is_stable():
    from system_prompt import build_system_prompt

    result = build_system_prompt(
        preamble="PREAMBLE",
        tools=[FakeTool("read", "Read.")],
        context_files=[("AGENTS.md", "CONTEXT")],
        extra_sections=[("Runtime", "EXTRA")],
    )

    order = [s.kind for s in result.sources]
    assert order == ["default", "tools", "context", "extra"], (
        f"order is part of the contract, got {order}. A prompt whose section "
        f"order varies between runs is not reproducible."
    )
