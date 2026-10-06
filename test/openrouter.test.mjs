/* Request-shape checks for the OpenRouter provider.
 *
 * These exist because a malformed request fails only at runtime, in front of
 * the learner, with a message that tells them nothing useful.
 */
import assert from "node:assert/strict";

globalThis.location = { origin: "http://localhost:5273" };

const mod = await import("../src/tutor/openrouter.js");
const { OpenRouterProvider, FALLBACK_FREE_MODELS } = mod;
const FREE_MODELS = FALLBACK_FREE_MODELS;
const DEFAULT_MODEL = FALLBACK_FREE_MODELS[0];

/** Capture the body of the request the provider would send. */
async function capture(provider, opts = {}) {
  let sent = null;
  globalThis.fetch = async (_url, init) => {
    sent = JSON.parse(init.body);
    return {
      ok: true,
      body: { getReader: () => ({ read: async () => ({ done: true }) }) },
    };
  };
  // Drain the stream so the request actually goes out.
  for await (const _ of provider.stream({ system: "s", messages: [], ...opts })) {
    /* drain */
  }
  return sent;
}

// OpenRouter rejects a routing array longer than 3, counting the primary.
{
  const provider = new OpenRouterProvider({
    apiKey: "k",
    model: DEFAULT_MODEL,
    fallbacks: FREE_MODELS,
  });
  const body = await capture(provider);
  assert.ok(body.models.length <= 3, `models must be <= 3, got ${body.models.length}`);
  assert.equal(body.models[0], DEFAULT_MODEL, "primary model must come first");
  assert.equal(new Set(body.models).size, body.models.length, "no duplicates");
}

// Even with a long fallback list.
{
  const many = Array.from({ length: 10 }, (_, i) => `vendor/model-${i}:free`);
  const provider = new OpenRouterProvider({ apiKey: "k", model: many[0], fallbacks: many });
  const body = await capture(provider);
  assert.ok(body.models.length <= 3, `models must be <= 3, got ${body.models.length}`);
}

// A model not in the fallback list is still routed first.
{
  const provider = new OpenRouterProvider({
    apiKey: "k",
    model: "anthropic/claude-sonnet-4.5",
    fallbacks: FREE_MODELS,
  });
  const body = await capture(provider);
  assert.equal(body.models[0], "anthropic/claude-sonnet-4.5");
  assert.ok(body.models.length <= 3);
}

// With no fallbacks, omit the array entirely rather than sending a 1-item one.
{
  const provider = new OpenRouterProvider({ apiKey: "k", model: DEFAULT_MODEL, fallbacks: [] });
  const body = await capture(provider);
  assert.equal(body.models, undefined, "no routing array when there is nothing to fall back to");
  assert.equal(body.model, DEFAULT_MODEL);
}

// Tools are sent in OpenAI function shape.
{
  const provider = new OpenRouterProvider({ apiKey: "k", model: DEFAULT_MODEL, fallbacks: [] });
  const body = await capture(provider, {
    tools: [{ name: "probe", description: "d", parameters: { type: "object" } }],
  });
  assert.equal(body.tools[0].type, "function");
  assert.equal(body.tools[0].function.name, "probe");
}

console.log("openrouter: 10 assertions passed");

/* The live catalogue. Hardcoding free model IDs is what broke the tutor:
   all four shipped IDs were retired within a day. */
{
  const catalogueResponse = {
    data: [
      { id: "paid/thing", context_length: 1000, supported_parameters: ["tools"] },
      { id: "small/no-tools:free", context_length: 8000, supported_parameters: [] },
      { id: "big/with-tools:free", context_length: 256000, supported_parameters: ["tools"] },
      { id: "mid/with-tools:free", context_length: 64000, supported_parameters: ["tools"] },
    ],
  };
  globalThis.fetch = async () => ({ ok: true, json: async () => catalogueResponse });

  const list = await mod.loadFreeModels({ force: true });
  assert.equal(list.length, 3, "paid models must be excluded");
  assert.equal(list[0].id, "big/with-tools:free", "tool-capable first, then widest context");
  assert.equal(list[2].id, "small/no-tools:free", "models without tools sort last");
  assert.equal(mod.DEFAULT_MODEL, "big/with-tools:free", "default follows the catalogue");
}

// A failed fetch must not leave the tutor with nothing to call.
{
  globalThis.fetch = async () => {
    throw new Error("offline");
  };
  const list = await mod.loadFreeModels({ force: true });
  assert.ok(list.length > 0, "fallback list is used when OpenRouter is unreachable");
}

// The retired-model 404 is reported as retirement, not as a privacy setting.
{
  globalThis.fetch = async () => ({
    ok: false,
    status: 404,
    json: async () => ({
      error: { message: "This model is unavailable for free. use this slug instead: x/y" },
    }),
  });
  const provider = new OpenRouterProvider({ apiKey: "k", model: "x/y:free", fallbacks: [] });
  let message = "";
  for await (const ev of provider.stream({ system: "s", messages: [] })) {
    if (ev.type === "error") message = ev.message;
  }
  assert.match(message, /retired/i, "must name the real cause");
  assert.doesNotMatch(message, /privacy settings/i, "must not blame the wrong thing");
}

console.log("openrouter catalogue: 7 assertions passed");

/* Streaming shapes. The tutor went silent because the parser only read
   delta.content, and every free model it offers is a reasoning model. */

/** Build a fake SSE response body from a list of chunk objects. */
function sseResponse(chunks) {
  const encoder = new TextEncoder();
  const frames = chunks.map((c) => `data: ${JSON.stringify(c)}\n\n`).concat("data: [DONE]\n\n");
  let i = 0;
  return {
    ok: true,
    body: {
      getReader: () => ({
        read: async () =>
          i < frames.length
            ? { done: false, value: encoder.encode(frames[i++]) }
            : { done: true },
      }),
    },
  };
}

async function drain(provider, opts = {}) {
  const out = { text: "", events: [], error: null, done: null };
  for await (const ev of provider.stream({ system: "s", messages: [], ...opts })) {
    out.events.push(ev.type);
    if (ev.type === "text_delta") out.text += ev.delta;
    if (ev.type === "error") out.error = ev.message;
    if (ev.type === "done") out.done = ev.message;
  }
  return out;
}

const mk = () => new OpenRouterProvider({ apiKey: "k", model: "m:free", fallbacks: [] });

// Ordinary content still works.
{
  globalThis.fetch = async () =>
    sseResponse([{ choices: [{ delta: { content: "he" } }] }, { choices: [{ delta: { content: "llo" } }] }]);
  const r = await drain(mk());
  assert.equal(r.text, "hello");
  assert.equal(r.done.content, "hello");
}

// A reasoning-only model must still produce an answer, not silence.
{
  globalThis.fetch = async () =>
    sseResponse([
      { choices: [{ delta: { reasoning: "thinking..." } }] },
      { choices: [{ delta: { reasoning: " the answer is 2" }, finish_reason: "stop" }] },
    ]);
  const r = await drain(mk());
  assert.ok(r.text.includes("the answer is 2"), "reasoning must be used when content is empty");
  assert.equal(r.error, null, "a reasoning-only reply is not an error");
}

// When both arrive, content wins and reasoning is not shown as the reply.
{
  globalThis.fetch = async () =>
    sseResponse([
      { choices: [{ delta: { reasoning: "scratchpad" } }] },
      { choices: [{ delta: { content: "real answer" } }] },
    ]);
  const r = await drain(mk());
  assert.equal(r.text, "real answer", "the model's scratchpad must not become the reply");
}

// Genuinely empty: report it rather than rendering nothing.
{
  globalThis.fetch = async () => sseResponse([{ choices: [{ delta: {}, finish_reason: "stop" }] }]);
  const r = await drain(mk());
  assert.ok(r.error, "an empty response must surface as an error");
  assert.match(r.error, /empty response/i);
  assert.match(r.error, /switch model/i, "and say what to do about it");
}

// Truncation has its own cause and its own advice.
{
  globalThis.fetch = async () => sseResponse([{ choices: [{ delta: {}, finish_reason: "length" }] }]);
  const r = await drain(mk());
  assert.match(r.error, /output limit/i);
}

// A refusal is reported as such.
{
  globalThis.fetch = async () =>
    sseResponse([{ choices: [{ delta: { refusal: "I can't help with that" } }] }]);
  const r = await drain(mk());
  assert.match(r.error, /declined/i);
}

// A mid-stream error frame must not be read as an empty reply.
{
  globalThis.fetch = async () =>
    sseResponse([{ error: { message: "upstream exploded" } }]);
  const r = await drain(mk());
  assert.match(r.error, /upstream exploded/);
}

// Tool calls with no text are a valid, non-empty turn.
{
  globalThis.fetch = async () =>
    sseResponse([
      { choices: [{ delta: { tool_calls: [{ index: 0, id: "c1", function: { name: "probe", arguments: '{"q"' } }] } }] },
      { choices: [{ delta: { tool_calls: [{ index: 0, function: { arguments: ':"x"}' } }] } }] },
    ]);
  const r = await drain(mk());
  assert.equal(r.error, null, "a tool-only turn is not empty");
  assert.equal(r.done.tool_calls[0].name, "probe");
  assert.deepEqual(r.done.tool_calls[0].arguments, { q: "x" });
}

console.log("openrouter streaming: 12 assertions passed");
