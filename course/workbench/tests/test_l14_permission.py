"""Level 14 - the permission decision point."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@dataclass
class FakeCall:
    id: str
    name: str
    arguments: dict


def test_read_inside_cwd_is_allowed(tmp_path):
    from permission import ALLOW, classify

    assert classify("read", {"path": "notes.txt"}, tmp_path) == ALLOW


def test_write_inside_cwd_is_allowed(tmp_path):
    from permission import ALLOW, classify

    assert classify("write", {"path": "out/new.txt", "content": "x"}, tmp_path) == ALLOW


def test_write_escaping_cwd_is_denied_not_asked(tmp_path):
    """A question nobody can evaluate should be a rule instead."""
    from permission import DENY, classify

    verdict = classify("write", {"path": "../../.ssh/authorized_keys"}, tmp_path)
    assert verdict == DENY, (
        f"expected DENY, got {verdict!r}. Asking here trains people to click "
        f"through prompts: mid-refactor, nobody can evaluate this path."
    )


def test_absolute_path_outside_cwd_is_denied(tmp_path):
    from permission import DENY, classify

    outside = tmp_path.parent / "elsewhere.txt"
    assert classify("write", {"path": str(outside)}, tmp_path) == DENY, (
        "an absolute path escape must be caught too, not just '..'"
    )


def test_shell_asks(tmp_path):
    from permission import ASK, classify

    assert classify("bash", {"command": "ls"}, tmp_path) == ASK


def test_unknown_tool_defaults_to_asking(tmp_path):
    """Default closed: a tool nobody classified is not automatically safe."""
    from permission import ASK, classify

    assert classify("send_email", {"to": "x@y.z"}, tmp_path) == ASK


async def test_gate_blocks_a_denied_call(tmp_path):
    from permission import PermissionGate

    gate = PermissionGate(cwd=tmp_path)
    blocked, reason = await gate.before_tool_call(
        FakeCall("c1", "write", {"path": "../escape.txt"})
    )

    assert blocked is True
    assert reason, "a blocked call must explain itself - the model sees this"


async def test_gate_consults_the_frontend_for_ask(tmp_path):
    from permission import PermissionGate

    answers = []

    def ask(call, verdict):
        answers.append(call.name)
        return True  # user approves

    gate = PermissionGate(cwd=tmp_path, ask_fn=ask)
    blocked, _ = await gate.before_tool_call(FakeCall("c1", "bash", {"command": "ls"}))

    assert answers == ["bash"], "ASK must reach the frontend"
    assert blocked is False, "an approved call proceeds"


async def test_gate_blocks_when_there_is_nobody_to_ask(tmp_path):
    """No frontend means no approval. Default closed."""
    from permission import PermissionGate

    gate = PermissionGate(cwd=tmp_path, ask_fn=None)
    blocked, reason = await gate.before_tool_call(FakeCall("c1", "bash", {"command": "ls"}))

    assert blocked is True, (
        "with no way to ask, the safe answer is no - a headless run must not "
        "silently gain permissions an interactive one would prompt for"
    )
    assert reason


async def test_always_allow_skips_the_question(tmp_path):
    from permission import PermissionGate

    asked = []
    gate = PermissionGate(
        cwd=tmp_path,
        ask_fn=lambda call, verdict: asked.append(call.name) or True,
        always_allow={"bash"},
    )
    blocked, _ = await gate.before_tool_call(FakeCall("c1", "bash", {"command": "ls"}))

    assert blocked is False
    assert asked == [], "a remembered decision must not be re-asked"
