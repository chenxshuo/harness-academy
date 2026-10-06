/* The tutor harness, against a scripted provider.
 *
 * The same trick the course itself uses: a deterministic provider makes the
 * harness the only variable. This proves the loop's stop condition, tool
 * execution, error isolation, and message ordering without a network call.
 */
import assert from "node:assert/strict";
import { TutorHarness, createTutorTools } from "../src/tutor/harness.js";

/** A provider that replays scripted turns. */
class ScriptedProvider {
  constructor(turns) { this.turns = [...turns]; this.calls = []; }
  async *stream({ messages }) {
    this.calls.push(structuredClone(messages));
    const turn = this.turns.shift() || { content: "", tool_calls: [] };
    for (const chunk of (turn.content || "").match(/.{1,4}/g) || []) {
      yield { type: "text_delta", delta: chunk };
    }
    yield { type: "done", message: { role: "assistant", content: turn.content || "", tool_calls: turn.tool_calls || [] } };
  }
}

const tool = (name, fn) => ({ name, description: "t", parameters: { type: "object" }, execute: fn });

// 1. No tool calls -> exactly one provider call. The stop condition.
{
  const provider = new ScriptedProvider([{ content: "hello" }, { content: "unreached" }]);
  const h = new TutorHarness({ provider, system: "s" });
  const events = [];
  for await (const e of h.prompt("hi")) events.push(e.type);
  assert.equal(provider.calls.length, 1, "a reply with no tool calls must end the loop");
  assert.ok(events.includes("agent_end"));
}

// 2. A tool call continues the loop and the result reaches the next call.
{
  const provider = new ScriptedProvider([
    { content: "", tool_calls: [{ id: "c1", name: "probe", arguments: { q: "x" } }] },
    { content: "done" },
  ]);
  const h = new TutorHarness({ provider, system: "s", tools: [tool("probe", async ({ q }) => `probed ${q}`)] });
  for await (const _ of h.prompt("go")) { /* drain */ }
  assert.equal(provider.calls.length, 2, "a tool call must cause another provider call");
  const second = provider.calls[1];
  assert.ok(second.some((m) => m.role === "tool" && m.content.includes("probed x")),
    "the tool result must be sent back to the model");
}

// 3. The result sits immediately after the call that produced it.
{
  const provider = new ScriptedProvider([
    { content: "", tool_calls: [{ id: "c1", name: "probe", arguments: {} }] },
    { content: "done" },
  ]);
  const h = new TutorHarness({ provider, system: "s", tools: [tool("probe", async () => "ok")] });
  for await (const _ of h.prompt("go")) { /* drain */ }
  const roles = h.messages.map((m) => m.role);
  assert.deepEqual(roles, ["user", "assistant", "tool", "assistant"]);
}

// 4. A throwing tool must not end the run - it is an isolation boundary.
{
  const provider = new ScriptedProvider([
    { content: "", tool_calls: [{ id: "c1", name: "boom", arguments: {} }] },
    { content: "recovered" },
  ]);
  const h = new TutorHarness({ provider, system: "s", tools: [tool("boom", async () => { throw new Error("kaboom"); })] });
  for await (const _ of h.prompt("go")) { /* drain */ }
  assert.equal(provider.calls.length, 2, "a failing tool must not kill the run");
  assert.ok(h.messages.some((m) => m.role === "tool" && m.is_error));
}

// 5. An unknown tool is reported, not thrown.
{
  const provider = new ScriptedProvider([
    { content: "", tool_calls: [{ id: "c1", name: "nope", arguments: {} }] },
    { content: "ok" },
  ]);
  const h = new TutorHarness({ provider, system: "s", tools: [] });
  for await (const _ of h.prompt("go")) { /* drain */ }
  assert.ok(h.messages.some((m) => m.role === "tool" && m.is_error));
}

// 6. maxTurns caps a model that keeps asking for tools forever.
{
  const turns = Array.from({ length: 20 }, () => ({ content: "", tool_calls: [{ id: "c", name: "probe", arguments: {} }] }));
  const provider = new ScriptedProvider(turns);
  const h = new TutorHarness({ provider, system: "s", tools: [tool("probe", async () => "ok")], maxTurns: 3 });
  for await (const _ of h.prompt("go")) { /* drain */ }
  assert.ok(provider.calls.length <= 3, `maxTurns must cap calls, got ${provider.calls.length}`);
}

// 7. Transcript survives between prompts.
{
  const provider = new ScriptedProvider([{ content: "first" }, { content: "second" }]);
  const h = new TutorHarness({ provider, system: "s" });
  for await (const _ of h.prompt("one")) {}
  for await (const _ of h.prompt("two")) {}
  assert.equal(h.messages.filter((m) => m.role === "user").length, 2);
  assert.ok(provider.calls[1].length > provider.calls[0].length, "second call carries history");
}

// 8. The specimen tool reports what is available rather than failing blankly.
{
  const tools = createTutorTools({
    specimen: { "tau/src/tau_agent/loop.py": { content: "# the loop" } },
    readLearnerFile: () => null,
    runPython: async () => ({ output: "" }),
  });
  const read = tools.find((t) => t.name === "read_specimen");
  assert.ok((await read.execute({ path: "tau/src/tau_agent/loop.py" })).includes("# the loop"));
  assert.ok((await read.execute({ path: "nope.py" })).includes("Available"));
  const mine = tools.find((t) => t.name === "read_my_code");
  assert.ok((await mine.execute({ file: "loop.py" })).includes("not written"));
}

console.log("tutor harness: 8 scenarios passed");
