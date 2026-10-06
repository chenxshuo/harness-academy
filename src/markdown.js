/* Markdown rendering.
 *
 * Deliberately minimal: the curriculum text is authored in-repo, so we only
 * support what it uses.
 *
 * SECURITY. `md()` is called on two very different kinds of input: trusted
 * curriculum prose (which may embed server-rendered <figure> diagrams) and
 * untrusted model output from the tutor. Those must not share a code path,
 * because a model can emit the literal diagram wrapper - directly, or via
 * prompt injection from a file it was asked to read - and with an API key in
 * localStorage that is an exploitable XSS.
 *
 * So raw HTML passthrough is opt-in and off by default:
 *   md(text)                        safe: everything is escaped
 *   md(text, { trusted: true })     curriculum only: diagrams pass through
 */

const esc = (s) =>
  String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

export { esc };

export function md(src, { trusted = false } = {}) {
  if (!src) return "";

  const blocks = [];
  let text = String(src).replace(/```(\w*)\n([\s\S]*?)```/g, (_m, _lang, code) => {
    blocks.push(code);
    return `\u0000CODE${blocks.length - 1}\u0000`;
  });

  // Only curriculum content may carry pre-rendered SVG.
  const figures = [];
  if (trusted) {
    text = text.replace(/<figure class="diagram">[\s\S]*?<\/figure>/g, (m) => {
      figures.push(m);
      return `\u0000FIG${figures.length - 1}\u0000`;
    });
  }

  text = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/`([^`\n]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s("'‘“])\*([^*]{1,200}?)\*/g, "$1<em>$2</em>");

  const lines = text.split("\n");
  const out = [];
  let mode = null;
  let para = [];

  const flushPara = () => {
    if (para.length) {
      out.push(`<p>${para.join(" ")}</p>`);
      para = [];
    }
  };
  const close = () => {
    flushPara();
    if (mode === "ul") out.push("</ul>");
    if (mode === "ol") out.push("</ol>");
    if (mode === "quote") out.push("</blockquote>");
    if (mode === "table") out.push("</tbody></table>");
    mode = null;
  };

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (!line.trim()) {
      close();
      continue;
    }

    let m;
    if ((m = line.match(/^(#{1,4})\s+(.*)$/))) {
      close();
      out.push(`<h4>${m[2]}</h4>`);
      continue;
    }
    if (line.startsWith("&gt; ")) {
      if (mode !== "quote") {
        close();
        out.push("<blockquote>");
        mode = "quote";
      }
      out.push(`<p>${line.slice(5)}</p>`);
      continue;
    }
    if (/^\|/.test(line)) {
      if (/^\|[\s:|-]+\|$/.test(line)) continue;
      const cells = line.split("|").slice(1, -1).map((c) => c.trim());
      if (mode !== "table") {
        close();
        out.push(
          `<table><thead><tr>${cells.map((c) => `<th>${c}</th>`).join("")}</tr></thead><tbody>`
        );
        mode = "table";
      } else {
        out.push(`<tr>${cells.map((c) => `<td>${c}</td>`).join("")}</tr>`);
      }
      continue;
    }
    if ((m = line.match(/^\s*[-*]\s+(.*)$/))) {
      flushPara();
      if (mode !== "ul") {
        close();
        out.push("<ul>");
        mode = "ul";
      }
      out.push(`<li>${m[1]}</li>`);
      continue;
    }
    if ((m = line.match(/^\s*(\d+)\.\s+(.*)$/))) {
      flushPara();
      if (mode !== "ol") {
        close();
        out.push(m[1] === "1" ? "<ol>" : `<ol start="${m[1]}">`);
        mode = "ol";
      }
      out.push(`<li>${m[2]}</li>`);
      continue;
    }
    if (/^\u0000(CODE|FIG)\d+\u0000$/.test(line.trim())) {
      close();
      out.push(line.trim());
      continue;
    }
    // A continuation line inside a list item stays with that item.
    if ((mode === "ul" || mode === "ol") && /^\s{2,}\S/.test(raw)) {
      const last = out.pop();
      out.push(last.replace(/<\/li>$/, ` ${line.trim()}</li>`));
      continue;
    }
    if (mode === "quote" || mode === "table") close();
    para.push(line.trim());
  }
  close();

  return out
    .join("\n")
    .replace(/<p>\u0000FIG(\d+)\u0000<\/p>|\u0000FIG(\d+)\u0000/g, (_m, a, b) => {
      const figure = figures[Number(a ?? b)];
      return figure ?? "";
    })
    .replace(/\u0000CODE(\d+)\u0000/g, (_m, i) => {
      const code = esc(blocks[Number(i)]);
      return `<pre><code>${code}</code></pre>`;
    });
}
