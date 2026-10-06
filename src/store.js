/* Local persistence: everything the server used to hold.
 *
 * Three stores, all in localStorage:
 *   files     the learner's workbench code
 *   progress  step records, concept mastery, achievements
 *   settings  tutor key, panel width, model choice
 *
 * Progress is exportable as JSON, which is strictly better than the old
 * server-side file: you can move between machines, and back up before a
 * risky experiment.
 */

const NS = "harness-academy";
const FILES_KEY = `${NS}:files`;
const PROGRESS_KEY = `${NS}:progress`;
const SETTINGS_KEY = `${NS}:settings`;

function read(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : structuredClone(fallback);
  } catch {
    return structuredClone(fallback);
  }
}

function write(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (err) {
    // Quota exceeded is the realistic failure. Tell the caller rather than
    // silently losing the learner's code.
    console.error("storage write failed", err);
    return false;
  }
}

// ------------------------------------------------------------------- files

/** Learner code, keyed by filename, with the starter version it came from. */
export function loadFiles() {
  return read(FILES_KEY, {});
}

export function readFile(name) {
  const entry = loadFiles()[name];
  return entry ? entry.content : null;
}

export function saveFile(name, content, starterHash = null) {
  const files = loadFiles();
  files[name] = {
    content,
    starterHash: starterHash ?? files[name]?.starterHash ?? null,
    savedAt: Date.now(),
  };
  return write(FILES_KEY, files);
}

export function fileStarterHash(name) {
  return loadFiles()[name]?.starterHash ?? null;
}

export function resetFile(name) {
  const files = loadFiles();
  delete files[name];
  write(FILES_KEY, files);
}

/** Cheap, stable hash so we can notice when a starter has changed upstream. */
export function hashString(text) {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(36);
}

// ---------------------------------------------------------------- progress

const EMPTY_PROGRESS = {
  version: 1,
  startedAt: null,
  steps: {},      // "levelId/stepId" -> record
  concepts: {},   // concept -> mastery counters
  achievements: [],
  notes: [],
};

export function loadProgress() {
  const data = read(PROGRESS_KEY, EMPTY_PROGRESS);
  if (!data.startedAt) data.startedAt = Date.now();
  return data;
}

export function saveProgress(progress) {
  return write(PROGRESS_KEY, progress);
}

export function resetProgress() {
  const fresh = structuredClone(EMPTY_PROGRESS);
  fresh.startedAt = Date.now();
  write(PROGRESS_KEY, fresh);
  return fresh;
}

/** Export both progress and code, so a learner can move machines. */
export function exportAll() {
  return JSON.stringify(
    {
      kind: "harness-academy-export",
      version: 1,
      exportedAt: new Date().toISOString(),
      progress: loadProgress(),
      files: loadFiles(),
    },
    null,
    2
  );
}

export function importAll(json) {
  const data = JSON.parse(json);
  if (data.kind !== "harness-academy-export") {
    throw new Error("Not a Harness Academy export file");
  }
  if (data.progress) write(PROGRESS_KEY, data.progress);
  if (data.files) write(FILES_KEY, data.files);
  return true;
}

// ---------------------------------------------------------------- settings

const EMPTY_SETTINGS = {
  tutorKey: "",
  tutorModel: "",
  tutorWidth: "",
  tutorMode: "auto", // auto | tools | stuffed
};

export function loadSettings() {
  return read(SETTINGS_KEY, EMPTY_SETTINGS);
}

export function saveSettings(patch) {
  const next = { ...loadSettings(), ...patch };
  write(SETTINGS_KEY, next);
  return next;
}

export function clearTutorKey() {
  return saveSettings({ tutorKey: "" });
}
