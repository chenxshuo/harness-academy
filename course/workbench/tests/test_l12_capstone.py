"""Level 12 - the capstone.

These tests check *behavior*, not structure. Any design that genuinely works
passes. That is deliberate: the capstone is about whether you can build a
working agent, not whether you reproduced a reference implementation.
"""

from __future__ import annotations

import asyncio

import pytest

from harnesskit import ScriptedProvider, ToolCall, turn

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_agent(tmp_path, provider, **kwargs):
    from myagent import MyAgent

    return MyAgent(
        provider=provider,
        model="scripted",
        cwd=tmp_path,
        session_path=tmp_path / "session.jsonl",
        **kwargs,
    )


async def test_agent_answers_a_simple_prompt(tmp_path):
    agent = make_agent(tmp_path, ScriptedProvider([turn("Hello back")]))

    answer = await agent.run("hello")

    assert "Hello back" in answer, (
        f"run() must return the final assistant text, got {answer!r}"
    )


async def test_agent_uses_a_tool_to_answer(tmp_path):
    """The real test: the agent learns something it was not told."""
    (tmp_path / "notes.txt").write_text("alpha\nbeta\ngamma\n")
    call = ToolCall(id="c1", name="read", arguments={"path": "notes.txt"})
    provider = ScriptedProvider([turn(tool_calls=[call]), turn("The file has 3 lines.")])
    agent = make_agent(tmp_path, provider)

    await agent.run("how many lines in notes.txt?")

    assert provider.call_count == 2, "The tool result must go back to the model"
    sent = provider.calls[1]["messages"]
    combined = " ".join(getattr(m, "text", "") for m in sent)
    assert "alpha" in combined, (
        "The second provider call must include the file contents the tool read. "
        "This is the whole mechanism by which an agent 'reads' a file."
    )


async def test_agent_writes_a_file(tmp_path):
    call = ToolCall(
        id="c1", name="write", arguments={"path": "out.txt", "content": "written by agent"}
    )
    provider = ScriptedProvider([turn(tool_calls=[call]), turn("Done")])
    agent = make_agent(tmp_path, provider)

    await agent.run("create out.txt")

    assert (tmp_path / "out.txt").read_text() == "written by agent"


async def test_session_is_persisted(tmp_path):
    agent = make_agent(tmp_path, ScriptedProvider([turn("remembered")]))

    await agent.run("remember this")

    session = tmp_path / "session.jsonl"
    assert session.exists(), "The session file must be written"
    content = session.read_text()
    assert "remember this" in content, "The user message must be persisted"
    assert "remembered" in content, "The assistant message must be persisted"


async def test_resume_restores_the_conversation(tmp_path):
    first = make_agent(tmp_path, ScriptedProvider([turn("first answer")]))
    await first.run("first question")

    second = make_agent(tmp_path, ScriptedProvider([turn("second answer")]))
    second.resume()

    texts = " ".join(getattr(m, "text", "") for m in second.harness.messages)
    assert "first question" in texts and "first answer" in texts, (
        "resume() must rebuild the transcript from disk. Without it, every "
        "restart loses the session."
    )


async def test_resumed_agent_sends_prior_context_to_the_model(tmp_path):
    first = make_agent(tmp_path, ScriptedProvider([turn("first answer")]))
    await first.run("first question")

    provider = ScriptedProvider([turn("second answer")])
    second = make_agent(tmp_path, provider)
    second.resume()
    await second.run("follow up")

    sent = " ".join(getattr(m, "text", "") for m in provider.calls[0]["messages"])
    assert "first question" in sent, (
        "A resumed session must send the restored history to the model, not "
        "just hold it in memory."
    )


async def test_tool_failure_does_not_end_the_run(tmp_path):
    call = ToolCall(id="c1", name="read", arguments={"path": "missing.txt"})
    provider = ScriptedProvider([turn(tool_calls=[call]), turn("I could not read it.")])
    agent = make_agent(tmp_path, provider)

    answer = await agent.run("read missing.txt")

    assert provider.call_count == 2, (
        "A failing tool must feed its error back to the model, not kill the run"
    )
    assert answer, "The agent should still produce a final answer"


async def test_persistence_survives_cancellation(tmp_path):
    """Level 9's bug, as an end-to-end behavioral test."""
    import myagent

    slow_started = asyncio.Event()

    from harnesskit.tools import Tool, ToolResult

    async def slow(arguments):
        slow_started.set()
        await asyncio.sleep(10)
        return ToolResult(content="never")

    call = ToolCall(id="c1", name="slow", arguments={})
    provider = ScriptedProvider([turn(tool_calls=[call]), turn("done")])
    agent = make_agent(tmp_path, provider)
    agent.harness._config.tools.append(
        Tool(name="slow", description="Slow.", execute=slow)
    )

    task = asyncio.create_task(agent.run("go"))
    await asyncio.wait_for(slow_started.wait(), timeout=3)
    agent.harness.cancel()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await asyncio.sleep(0.1)

    session = tmp_path / "session.jsonl"
    assert session.exists() and "go" in session.read_text(), (
        "Messages emitted before cancellation must still be on disk. If they "
        "are not, persistence is a consumer of the event stream rather than a "
        "subscriber to it - see Level 9."
    )


async def test_transcript_stays_valid_after_cancellation(tmp_path):
    """Level 7's invariant, end to end."""
    from harnesskit.messages import AssistantMessage, ToolResultMessage
    from harnesskit.tools import Tool, ToolResult

    slow_started = asyncio.Event()

    async def slow(arguments):
        slow_started.set()
        await asyncio.sleep(10)
        return ToolResult(content="never")

    call = ToolCall(id="c1", name="slow", arguments={})
    provider = ScriptedProvider([turn(tool_calls=[call]), turn("done")])
    agent = make_agent(tmp_path, provider)
    agent.harness._config.tools.append(Tool(name="slow", description="S.", execute=slow))

    task = asyncio.create_task(agent.run("go"))
    await asyncio.wait_for(slow_started.wait(), timeout=3)
    agent.harness.cancel()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await asyncio.sleep(0.1)

    messages = list(agent.harness.messages)
    call_ids = {
        c.id for m in messages if isinstance(m, AssistantMessage) for c in m.tool_calls
    }
    result_ids = {m.tool_call_id for m in messages if isinstance(m, ToolResultMessage)}

    assert not (call_ids - result_ids), (
        f"After cancellation, tool call(s) {call_ids - result_ids} have no "
        f"result. The next provider request with this transcript would be "
        f"rejected. Append a synthetic interrupted result when a run is "
        f"cancelled - see Level 7."
    )
