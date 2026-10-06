/* Linking specimen references back to the source repository.
 *
 * The course names real files constantly - "read tau/src/tau_agent/loop.py",
 * "line ~185". A bare path string is a dead end; the learner has to go and
 * find it. Every reference should be one click from the actual file, at a
 * pinned revision so a line number still means something later.
 */

const REPO = "https://github.com/huggingface/tau";
/* Pinned so line references stay meaningful. The specimen bundled with the
   course is this revision; `main` would drift away from the prose. */
const REF = "v0.4.7";

/** Turn a repo-relative path (with optional #L123) into a GitHub URL. */
export function specimenUrl(path, line = null) {
  const clean = String(path).replace(/^\.?\//, "");
  // Paths in the curriculum are written with the `tau/` prefix the local
  // checkout uses; GitHub paths start inside the repository.
  const inRepo = clean.startsWith("tau/") ? clean.slice(4) : clean;
  const anchor = line ? `#L${line}` : "";
  return `${REPO}/blob/${REF}/${inRepo}${anchor}`;
}

/** A short label for a path: the filename, or the last two segments. */
export function specimenLabel(path) {
  const parts = String(path).split("/");
  return parts.length > 1 ? parts.slice(-2).join("/") : parts[0];
}

const PATH_PATTERN =
  /\btau\/[A-Za-z0-9_./-]+\.(?:py|md|toml|json|ts|sh|ps1|html)\b(?::(\d+))?/g;

/**
 * Link every specimen path inside already-rendered HTML.
 *
 * Runs on the output of the markdown renderer, so it sees `<code>` spans
 * rather than raw text. Only paths inside `<code>` are linked: prose
 * mentions are usually mid-sentence and would read badly as links.
 */
export function linkSpecimenPaths(html) {
  if (!html || !html.includes("tau/")) return html;

  return html.replace(
    /<code>([^<]*tau\/[^<]*)<\/code>/g,
    (whole, inner) => {
      // Skip anything already inside a link.
      const linked = inner.replace(PATH_PATTERN, (match, line) => {
        const path = line ? match.slice(0, -(line.length + 1)) : match;
        const url = specimenUrl(path, line);
        return (
          `<a class="specimen-link" href="${url}" target="_blank" ` +
          `rel="noopener noreferrer" title="Open on GitHub">${match}` +
          `<svg viewBox="0 0 24 24" width="11" height="11" fill="none" ` +
          `stroke="currentColor" stroke-width="2.4" stroke-linecap="round" ` +
          `stroke-linejoin="round" aria-hidden="true">` +
          `<path d="M7 17 17 7"/><path d="M8 7h9v9"/></svg></a>`
        );
      });
      return linked === inner ? whole : `<code>${linked}</code>`;
    }
  );
}
