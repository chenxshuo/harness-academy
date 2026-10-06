/* A coding-agent harness, in the browser, in about 200 lines.
 *
 * This is the course's own subject matter running in the same tab the course
 * runs in. Everything Act I and II teach is here: a loop whose stop condition
 * is "the assistant asked for no tools", tools as a schema plus a function,
 * a typed event stream the UI renders from, and a harness that owns the
 * transcript between prompts.
 *
 * It is deliberately readable. A learner who opens this file should recognise
 * the shape they are being asked to build.
 */

/** @typedef {{role: string, content: any}} Message */

export class TutorHarness {
  /**
   * @param {object} options
   * @param {object} options.provider  something with .stream({messages, tools, signal})
   * @param {string} options.system    the system prompt
   * @param {Array}  options.tools     [{name, description, parameters, execute}]
   * @param {number} options.maxTurns  safety cap on tool round-trips
   */
  constructor({ provider, system, tools = [], maxTurns = 8 }) {
    this.provider = provider;
    this.system = system;
    this.tools = tools;
    this.maxTurns = maxTurns;
    this.messages = [];
    this.running = false;
    this.controller = null;
  }

  get toolsByName() {
    return Object.fromEntries(this.tools.map((t) => [t.name, t]));
  }

  cancel() {
    this.controller?.abort();
  }

  reset() {
    this.messages = [];
  }

  /**
   * Run one prompt to completion, yielding events as it goes.
   *
   * The loop is the same six lines the course asks you to write: call the
   * model, and if it asked for tools, run them, append the results, and call
   * again. Otherwise stop.
   */
  async *prompt(text) {
    if (this.running) throw new Error("Tutor is already answering.");
    this.running = true;
    this.controller = new AbortController();
    const signal = this.controller.signal;

    this.messages.push({ role: "user", content: text });
    yield { type: "agent_start" };

    try {
      const byName = this.toolsByName;

      for (let turn = 0; turn < this.maxTurns; turn++) {
        yield { type: "turn_start", turn };

        let assistant = null;
        for await (const event of this.provider.stream({
          system: this.system,
          messages: this.messages,
          tools: this.tools,
          signal,
        })) {
          if (event.type === "text_delta") {
            yield { type: "message_update", delta: event.delta };
          } else if (event.type === "done") {
            assistant = event.message;
          } else if (event.type === "error") {
            yield { type: "error", message: event.message };
            return;
          }
        }

        if (!assistant) {
          yield { type: "error", message: "The model returned nothing." };
          return;
        }

        this.messages.push(assistant);
        const calls = assistant.tool_calls || [];

        // The stop condition. This single line is Level 1's answer.
        if (!calls.length) {
          yield { type: "turn_end", message: assistant };
          break;
        }

        for (const call of calls) {
          yield { type: "tool_execution_start", name: call.name, args: call.arguments };
          const tool = byName[call.name];
          let content;
          let isError = false;
          if (!tool) {
            content = `Tool ${call.name} not found`;
            isError = true;
          } else {
            try {
              // A tool is an isolation boundary: it may fail without taking
              // the run with it, because the model can often recover.
              content = await tool.execute(call.arguments || {});
            } catch (exc) {
              content = String(exc && exc.message ? exc.message : exc);
              isError = true;
            }
          }
          const text = typeof content === "string" ? content : JSON.stringify(content);
          yield { type: "tool_execution_end", name: call.name, isError };

          // The result must sit immediately after the call that produced it.
          this.messages.push({
            role: "tool",
            tool_call_id: call.id,
            name: call.name,
            content: text.slice(0, 20000),
            is_error: isError,
          });
        }

        yield { type: "turn_end", message: assistant };
      }
      yield { type: "agent_end" };
    } finally {
      this.running = false;
      this.controller = null;
    }
  }
}

/**
 * Tools the tutor can use.
 *
 * Three of them, matching what the Python tutor could do: read the specimen,
 * read the learner's code, and run Python to settle a question empirically.
 */
export function createTutorTools({ specimen, readLearnerFile, runPython }) {
  return [
    {
      name: "read_specimen",
      description:
        "Read a file from the Tau specimen. Use this to ground an answer in " +
        "the real implementation rather than recalling it.",
      parameters: {
        type: "object",
        properties: {
          path: {
            type: "string",
            description: "Repo-relative path, e.g. tau/src/tau_agent/loop.py",
          },
        },
        required: ["path"],
      },
      async execute({ path }) {
        const entry = specimen[path];
        if (!entry) {
          const available = Object.keys(specimen).slice(0, 25).join("\n");
          return `No bundled file at ${path}. Available:\n${available}`;
        }
        return entry.content;
      },
    },
    {
      name: "list_specimen",
      description: "List the specimen files available to read.",
      parameters: { type: "object", properties: {} },
      async execute() {
        return Object.keys(specimen).join("\n");
      },
    },
    {
      name: "read_my_code",
      description:
        "Read the learner's current code for one of their workbench files, " +
        "e.g. loop.py or harness.py. Read before commenting on their code.",
      parameters: {
        type: "object",
        properties: { file: { type: "string" } },
        required: ["file"],
      },
      async execute({ file }) {
        const content = readLearnerFile(file);
        return content ?? `The learner has not written ${file} yet.`;
      },
    },
    {
      name: "run_python",
      description:
        "Run a short Python snippet in the course runtime to check a claim. " +
        "harnesskit and the learner's modules are importable. Prefer this " +
        "over asserting what the code does.",
      parameters: {
        type: "object",
        properties: { code: { type: "string" } },
        required: ["code"],
      },
      async execute({ code }) {
        const result = await runPython(code);
        return result.output || result.error || "(no output)";
      },
    },
  ];
}
