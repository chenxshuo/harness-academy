/* Tutor facade: wires the harness, the provider, auth, and mode selection.
 *
 * Mode matters because free models vary a lot in tool-calling reliability.
 * We start with tools, and fall back to stuffed context if a model turns out
 * not to call them - a tutor that cannot read the specimen is the "generic
 * chatbot next to the course" the project explicitly rules out.
 */

import { TutorHarness, createTutorTools } from "./harness.js";
import {
  FALLBACK_FREE_MODELS,
  OpenRouterProvider,
  beginAuth,
  completeAuth,
  freeModelCatalogue,
  keyStatus,
  loadFreeModels,
} from "./openrouter.js";
import {
  TUTOR_SYSTEM_STUFFED,
  TUTOR_SYSTEM_TOOLS,
  renderContext,
  stuffedFilesFor,
} from "./context.js";
import { loadSettings, saveSettings } from "../store.js";
import { ready, runScript } from "../runtime.js";

export function createTutor({ specimen, readLearnerFile }) {
  let apiKey = "";
  let model = "";
  let models = [];     // live catalogue, fetched from OpenRouter
  let mode = "tools";  // tools | stuffed
  let toolFailures = 0;
  let harness = null;

  const tools = createTutorTools({
    specimen,
    readLearnerFile,
    runPython: async (code) => {
      try {
        await ready(null);
      } catch {
        return { error: "Python runtime unavailable." };
      }
      // Wrap the snippet so stdout is captured rather than streamed.
      const path = "_tutor_snippet.py";
      return runScript({ path, files: { [path]: code } })
        .then((r) => ({ output: r.lines.join("\n"), error: r.error }))
        .catch((e) => ({ error: String(e.message || e) }));
    },
  });

  function build() {
    // Route only among tool-capable models, so a fallback cannot silently
    // land on one that breaks the tutor's ability to read the specimen.
    const fallbacks = models.filter((m) => m.tools).map((m) => m.id);
    const provider = new OpenRouterProvider({
      apiKey,
      model,
      fallbacks: fallbacks.length ? fallbacks : FALLBACK_FREE_MODELS,
    });
    harness = new TutorHarness({
      provider,
      system: mode === "tools" ? TUTOR_SYSTEM_TOOLS : TUTOR_SYSTEM_STUFFED,
      tools: mode === "tools" ? tools : [],
    });
  }

  return {
    /** Pick up a saved key, or finish an OAuth round-trip. */
    async restore() {
      const settings = loadSettings();
      if (settings.tutorMode === "stuffed") mode = "stuffed";

      // Free model IDs churn, so always take the live list. A model saved
      // last week may have been retired since.
      models = await loadFreeModels();
      const ids = new Set(models.map((m) => m.id));
      model = ids.has(settings.tutorModel) ? settings.tutorModel : models[0]?.id || "";
      if (model !== settings.tutorModel) saveSettings({ tutorModel: model });

      try {
        const fresh = await completeAuth();
        if (fresh) {
          apiKey = fresh;
          saveSettings({ tutorKey: fresh });
        }
      } catch (err) {
        console.warn("OpenRouter auth failed:", err.message);
      }
      if (!apiKey) apiKey = settings.tutorKey || "";
      if (apiKey) build();
      return Boolean(apiKey);
    },

    isConnected: () => Boolean(apiKey),
    modelLabel: () => `${(model || "?").split("/").pop()} · ${mode}`,
    currentModel: () => model,
    availableModels: () => freeModelCatalogue(),
    async refreshModels() {
      models = await loadFreeModels({ force: true });
      return models;
    },

    beginConnect: () => beginAuth(),

    async connectWithKey(key) {
      const status = await keyStatus(key);
      if (!status.valid) throw new Error("That key was rejected by OpenRouter.");
      apiKey = key;
      saveSettings({ tutorKey: key });
      build();
      return status;
    },

    setModel(next) {
      model = next;
      saveSettings({ tutorModel: next });
      build();
    },

    setMode(next) {
      mode = next;
      saveSettings({ tutorMode: next });
      build();
    },

    /** Ask a question. Yields harness events. */
    async *ask(message, context) {
      if (!harness) build();

      const ctx = { ...context };
      if (mode === "stuffed") {
        ctx.stuffedFiles = stuffedFilesFor(ctx, specimen);
      }
      const payload = `${renderContext(ctx)}\n\n${message}`;

      let usedTools = false;
      let produced = false;
      for await (const event of harness.prompt(payload)) {
        if (event.type === "tool_execution_start") usedTools = true;
        if (event.type === "message_update") produced = true;
        yield event;
      }

      // A model that never calls tools in tools-mode is probably unable to.
      // Switch after two such turns rather than degrading silently.
      if (mode === "tools" && produced && !usedTools) {
        toolFailures += 1;
        if (toolFailures >= 2) {
          mode = "stuffed";
          saveSettings({ tutorMode: "stuffed" });
          build();
          yield {
            type: "message_update",
            delta:
              "\n\n_(This model does not seem to call tools. Switched to " +
              "pre-loaded context so I can still see the specimen.)_",
          };
        }
      } else if (usedTools) {
        toolFailures = 0;
      }
    },

    cancel: () => harness?.cancel(),
    reset: () => harness?.reset(),
  };
}
