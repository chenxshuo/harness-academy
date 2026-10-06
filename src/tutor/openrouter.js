/* OpenRouter provider: streaming chat completions with tool calling.
 *
 * Why OpenRouter rather than a vendor SDK: it has an OAuth PKCE flow designed
 * for browser apps, so the learner connects their own account in one click and
 * their key never touches our server (there is no server). Rate limits and
 * spend are per-user, which is what makes a public deployment viable.
 */

const BASE = "https://openrouter.ai/api/v1";

/* OpenRouter caps the routing array at 3 entries, counting the primary model.
 * Keep the candidate list longer than that for model selection, but never
 * send more than MAX_ROUTING_MODELS on a request. */
const MAX_ROUTING_MODELS = 3;

/* Free model IDs churn - endpoints appear, move behind payment, and vanish.
 * A hardcoded list goes stale and fails in front of the learner with a
 * message about a model they never chose. So the real list is fetched from
 * /models at startup; this is only the fallback for when that fetch fails,
 * and for the very first render before it resolves.
 *
 * Verified live on 2026-10-05. Treat as a hint, not a source of truth.
 */
export const FALLBACK_FREE_MODELS = [
  "google/gemma-4-31b-it:free",
  "nvidia/nemotron-3.5-lightning:free",
  "thinkingmachines/inkling-small:free",
];

/** Mutable catalogue, replaced once /models responds. */
export let FREE_MODELS = [...FALLBACK_FREE_MODELS];
export let DEFAULT_MODEL = FREE_MODELS[0];

let catalogue = null;

/**
 * Fetch the live free-model list, preferring models that support tool calling.
 *
 * The tutor is an agent: a model that cannot call tools degrades it into a
 * chatbot that cannot read the specimen. So tool-capable models sort first,
 * and larger context wins among those.
 */
export async function loadFreeModels({ force = false } = {}) {
  if (catalogue && !force) return catalogue;
  try {
    const response = await fetch(`${BASE}/models`);
    if (!response.ok) throw new Error(String(response.status));
    const { data } = await response.json();

    const free = data
      .filter((m) => m.id.endsWith(":free"))
      .map((m) => ({
        id: m.id,
        name: m.name || m.id,
        context: m.context_length || 0,
        tools: (m.supported_parameters || []).includes("tools"),
      }))
      .sort((a, b) => Number(b.tools) - Number(a.tools) || b.context - a.context);

    if (free.length) {
      catalogue = free;
      FREE_MODELS = free.map((m) => m.id);
      DEFAULT_MODEL = FREE_MODELS[0];
    }
    return catalogue || [];
  } catch {
    // Offline, or OpenRouter is down. The fallback list may itself be stale,
    // but an attempt is better than refusing to start.
    return (catalogue = FALLBACK_FREE_MODELS.map((id) => ({
      id,
      name: id,
      context: 0,
      tools: true,
    })));
  }
}

/** The catalogue as last fetched, without triggering a fetch. */
export function freeModelCatalogue() {
  return catalogue || [];
}

export class OpenRouterProvider {
  constructor({ apiKey, model = DEFAULT_MODEL, fallbacks = FREE_MODELS, referer, title }) {
    this.apiKey = apiKey;
    this.model = model;
    this.fallbacks = fallbacks;
    this.referer = referer || location.origin;
    this.title = title || "Harness Academy";
  }

  headers() {
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${this.apiKey}`,
      // OpenRouter uses these for attribution on their leaderboards.
      "HTTP-Referer": this.referer,
      "X-Title": this.title,
    };
  }

  /**
   * Stream one assistant turn.
   *
   * Yields: {type:"text_delta", delta} | {type:"done", message} | {type:"error", message}
   * The `message` on done carries `tool_calls`, which is what the loop's stop
   * condition inspects.
   */
  async *stream({ system, messages, tools = [], signal }) {
    const body = {
      model: this.model,
      messages: [{ role: "system", content: system }, ...messages.map(toWire)],
      stream: true,
    };
    if (this.fallbacks?.length) {
      // The primary model counts toward the cap, so take at most two others.
      const others = this.fallbacks.filter((m) => m !== this.model);
      body.models = [this.model, ...others].slice(0, MAX_ROUTING_MODELS);
    }
    if (tools.length) {
      body.tools = tools.map((t) => ({
        type: "function",
        function: {
          name: t.name,
          description: t.description,
          parameters: t.parameters || { type: "object", properties: {} },
        },
      }));
    }

    let response;
    try {
      response = await fetch(`${BASE}/chat/completions`, {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify(body),
        signal,
      });
    } catch (exc) {
      if (signal?.aborted) return;
      yield { type: "error", message: `Network error: ${exc.message}` };
      return;
    }

    if (!response.ok) {
      yield { type: "error", message: await describeError(response) };
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let text = "";
    let reasoning = "";
    let refusal = "";
    let finishReason = "";
    const toolCalls = [];

    while (true) {
      let chunk;
      try {
        chunk = await reader.read();
      } catch {
        break; // aborted
      }
      if (chunk.done) break;
      buffer += decoder.decode(chunk.value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;
        const data = trimmed.slice(5).trim();
        if (data === "[DONE]") continue;

        let event;
        try {
          event = JSON.parse(data);
        } catch {
          continue;
        }
        // A mid-stream error arrives as a normal SSE frame.
        if (event.error) {
          yield { type: "error", message: event.error.message || "Provider error" };
          return;
        }
        const choice = event.choices?.[0];
        if (!choice) continue;
        if (choice.finish_reason) finishReason = choice.finish_reason;
        const delta = choice.delta;
        if (!delta) continue;

        if (delta.content) {
          text += delta.content;
          yield { type: "text_delta", delta: delta.content };
        }
        // Reasoning models stream their thinking separately. Most also emit
        // `content`, but some emit only `reasoning` - and ignoring it meant
        // the tutor rendered nothing at all. Keep it as a fallback answer
        // rather than showing the model's scratchpad as the reply.
        if (delta.reasoning) reasoning += delta.reasoning;
        if (delta.refusal) refusal += delta.refusal;

        // Tool calls arrive in fragments indexed by position.
        for (const part of delta.tool_calls || []) {
          const index = part.index ?? 0;
          toolCalls[index] ||= { id: "", name: "", argsText: "" };
          if (part.id) toolCalls[index].id = part.id;
          if (part.function?.name) toolCalls[index].name = part.function.name;
          if (part.function?.arguments) {
            toolCalls[index].argsText += part.function.arguments;
          }
        }
      }
    }

    const calls = toolCalls.filter(Boolean).map((call, i) => ({
      id: call.id || `call_${i}`,
      name: call.name,
      arguments: parseArgs(call.argsText),
    }));

    if (refusal && !text) {
      yield { type: "error", message: `The model declined: ${refusal}` };
      return;
    }

    // Fall back to reasoning text, so a reasoning-only model still answers.
    if (!text && !calls.length && reasoning) {
      text = reasoning;
      yield { type: "text_delta", delta: reasoning };
    }

    // Silence is a bug somewhere; say which kind rather than rendering nothing.
    if (!text && !calls.length) {
      yield {
        type: "error",
        message:
          finishReason === "length"
            ? "The model hit its output limit before saying anything. Try a shorter question."
            : `The model returned an empty response${
                finishReason ? ` (finish_reason: ${finishReason})` : ""
              }. Free endpoints are sometimes overloaded - retry, or switch model from the tutor header.`,
      };
      return;
    }

    yield {
      type: "done",
      message: { role: "assistant", content: text, tool_calls: calls },
    };
  }
}

function parseArgs(text) {
  if (!text?.trim()) return {};
  try {
    return JSON.parse(text);
  } catch {
    return {};
  }
}

/** Translate our message shape into OpenAI-compatible wire format. */
function toWire(message) {
  if (message.role === "tool") {
    return {
      role: "tool",
      tool_call_id: message.tool_call_id,
      content: message.content,
    };
  }
  if (message.role === "assistant" && message.tool_calls?.length) {
    return {
      role: "assistant",
      content: message.content || null,
      tool_calls: message.tool_calls.map((c) => ({
        id: c.id,
        type: "function",
        function: { name: c.name, arguments: JSON.stringify(c.arguments || {}) },
      })),
    };
  }
  return { role: message.role, content: message.content };
}

/** Turn an HTTP failure into something the learner can act on. */
async function describeError(response) {
  let detail = "";
  try {
    const body = await response.json();
    detail = body?.error?.message || JSON.stringify(body).slice(0, 200);
  } catch {
    detail = await response.text().catch(() => "");
  }

  switch (response.status) {
    case 401:
      return "Your OpenRouter key was rejected. Reconnect your account.";
    case 402:
      return "OpenRouter reports insufficient credits for this model. Try a free model.";
    case 404: {
      // Two very different causes share this status, and the old message
      // asserted the wrong one. OpenRouter's own text distinguishes them.
      const retired = /unavailable for free|use this slug/i.test(detail);
      if (retired) {
        return (
          "That free model has been retired by OpenRouter. Pick another in " +
          "the tutor's model list - the list is fetched live, so it is " +
          `current. (${detail})`
        );
      }
      return (
        "Model unavailable. Free models require 'Model training / prompt " +
        "logging' to be enabled in your OpenRouter privacy settings. " + detail
      );
    }
    case 429:
      return "Rate limited by OpenRouter. Wait a moment, or pick another model.";
    default:
      return `OpenRouter error ${response.status}: ${detail}`;
  }
}

// ----------------------------------------------------------------- PKCE auth

/**
 * OAuth PKCE: the learner connects their own OpenRouter account.
 *
 * PKCE means no client secret, which is what lets this work from a purely
 * static site. The resulting key is user-scoped: their rate limits, their
 * spend, their revocation.
 */

const VERIFIER_KEY = "harness-academy:pkce-verifier";

function randomString(length = 64) {
  const bytes = crypto.getRandomValues(new Uint8Array(length));
  return Array.from(bytes, (b) => "abcdefghijklmnopqrstuvwxyz0123456789"[b % 36]).join("");
}

async function challengeFor(verifier) {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

/** Send the learner to OpenRouter to approve access. */
export async function beginAuth(callbackUrl = location.origin + location.pathname) {
  const verifier = randomString();
  sessionStorage.setItem(VERIFIER_KEY, verifier);
  const challenge = await challengeFor(verifier);
  const url = new URL("https://openrouter.ai/auth");
  url.searchParams.set("callback_url", callbackUrl);
  url.searchParams.set("code_challenge", challenge);
  url.searchParams.set("code_challenge_method", "S256");
  location.href = url.toString();
}

/**
 * Complete the flow if we came back with ?code=.
 * Returns the key, or null when this is an ordinary page load.
 */
export async function completeAuth() {
  const params = new URLSearchParams(location.search);
  const code = params.get("code");
  if (!code) return null;

  const verifier = sessionStorage.getItem(VERIFIER_KEY);
  sessionStorage.removeItem(VERIFIER_KEY);

  // Clean the URL whatever happens, so a refresh does not retry a used code.
  history.replaceState({}, "", location.pathname);
  if (!verifier) throw new Error("Auth state was lost. Please connect again.");

  const response = await fetch(`${BASE}/auth/keys`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      code,
      code_verifier: verifier,
      code_challenge_method: "S256",
    }),
  });
  if (!response.ok) {
    throw new Error(`Could not exchange the code (${response.status}).`);
  }
  const data = await response.json();
  if (!data.key) throw new Error("OpenRouter did not return a key.");
  return data.key;
}

/** Check a key and report remaining free-tier allowance. */
export async function keyStatus(apiKey) {
  try {
    const response = await fetch(`${BASE}/key`, {
      headers: { Authorization: `Bearer ${apiKey}` },
    });
    if (!response.ok) return { valid: false };
    const { data } = await response.json();
    return {
      valid: true,
      label: data?.label || "",
      usage: data?.usage ?? null,
      limit: data?.limit ?? null,
      isFreeTier: data?.is_free_tier ?? null,
    };
  } catch {
    return { valid: false };
  }
}
