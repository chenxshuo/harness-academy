"""Level 16 - skills (knowledge) and extensions (capability)."""

from __future__ import annotations


def _skill(name, body, *triggers):
    from extensions import Skill

    return Skill(name=name, description=f"{name} skill", body=body, triggers=tuple(triggers))


def test_registry_holds_skills():
    from extensions import SkillRegistry

    registry = SkillRegistry()
    registry.add(_skill("django", "Use migrations.", "django", "migration"))

    assert len(registry.skills) == 1


def test_only_relevant_skills_are_returned():
    """Loading every skill into every session is what 'relevant' prevents."""
    from extensions import SkillRegistry

    registry = SkillRegistry()
    registry.add(_skill("django", "Use migrations.", "django"))
    registry.add(_skill("rust", "Use cargo.", "rust", "cargo"))

    names = [s.name for s in registry.relevant_to("fix the django model")]
    assert names == ["django"], f"expected only the django skill, got {names}"


def test_matching_is_case_insensitive():
    from extensions import SkillRegistry

    registry = SkillRegistry()
    registry.add(_skill("django", "Use migrations.", "Django"))

    assert registry.relevant_to("DJANGO models") , "trigger matching must ignore case"


def test_a_skill_without_triggers_is_always_relevant():
    from extensions import SkillRegistry

    registry = SkillRegistry()
    registry.add(_skill("house-style", "Two spaces."))

    assert len(registry.relevant_to("anything at all")) == 1, (
        "no triggers is how a user says 'this one is general'"
    )


def test_prompt_sections_carry_the_body():
    from extensions import SkillRegistry

    registry = SkillRegistry()
    registry.add(_skill("django", "MIGRATION_RULE", "django"))

    sections = registry.prompt_sections("django work")
    assert sections and sections[0][1] == "MIGRATION_RULE"


def test_extension_can_register_a_tool():
    from extensions import ExtensionHost

    host = ExtensionHost()

    def setup(h):
        h.register_tool({"name": "file_ticket"})

    assert host.load("tickets", setup) is True
    assert len(host.tools) == 1


def test_extension_can_register_a_prompt_section():
    from extensions import ExtensionHost

    host = ExtensionHost()
    host.load("style", lambda h: h.register_prompt_section("Style", "Two spaces."))

    assert host.sections and host.sections[0][0] == "Style"


def test_a_broken_extension_does_not_take_the_agent_down():
    """Third-party code failing is expected, not exceptional."""
    from extensions import ExtensionHost

    host = ExtensionHost()

    def broken(h):
        raise RuntimeError("bad import")

    ok = host.load("broken", broken)

    assert ok is False, "load() reports failure rather than raising"
    assert host.diagnostics, "the failure must be recorded, not swallowed"
    assert "broken" in host.diagnostics[0].source, "name the extension that failed"


def test_one_broken_extension_does_not_block_the_others():
    from extensions import ExtensionHost

    host = ExtensionHost()
    host.load("broken", lambda h: (_ for _ in ()).throw(RuntimeError("nope")))
    host.load("good", lambda h: h.register_tool({"name": "works"}))

    assert len(host.tools) == 1, "a later extension must still load"
    assert len(host.diagnostics) == 1
