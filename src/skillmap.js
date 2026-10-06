/* The skill map: the course as a connected region map, in an overlay.
 *
 * The curriculum list answers "what is in this course". It does not answer
 * "where am I, and what does this unlock" - a list cannot show that, because
 * the levels are a dependency graph and a list is a line. l04 and l13 both
 * hang off l02; the capstone needs three separate branches finished first.
 * On the list those facts are invisible.
 *
 * So: nodes grouped into their acts, edges drawn from `requires`, and three
 * visual states - done, open, locked. A locked node is greyed and says what
 * it is waiting on. This is the game-map convention, used here for the same
 * reason games use it: it makes "what have I got, and what is next" a glance
 * instead of a search.
 *
 * It floats above the page rather than replacing it. Opening the map from
 * inside a level should not throw away the level you are reading.
 *
 * Columns are acts rather than dependency depth. Depth was the first
 * attempt and it laid out correctly, but the longest path through this
 * curriculum is eight levels, so the graph came out eight columns wide and
 * had to render at 0.62 scale to fit a dialog - small enough that the
 * titles clipped. Acts give five columns, which fits near 1:1, and they are
 * a grouping the course already teaches.
 *
 * The cost is that half the edges (9 of 18) are now within an act rather
 * than across one, and a straight line between two stacked boxes would be
 * hidden behind them. Those are drawn as loops out of the right edge,
 * fanned by how far apart their endpoints are, so that concentric loops in
 * one column nest instead of landing on top of each other.
 *
 * Positions are computed, never hand-placed. Hand-placed coordinates rot the
 * moment a level is added, and this course has grown from 12 to 16 already.
 */

import { esc } from "./markdown.js";

const NODE_W = 166;
/* Tall enough for the worst case: a three-line title plus a "needs 08, 13,
   15" subtitle. That is level 12's card, and sizing to it keeps every node
   the same height, which matters because unequal boxes in a grid read as
   meaning something. */
const NODE_H = 72;
const COL_GAP = 52;
const ROW_GAP = 20;
const HEAD_H = 38; // room above the first row for the act label
const PAD = 22;

/** Lay the acts out as columns, levels as rows within their act. */
function layout(acts) {
  const tallest = Math.max(...acts.map((a) => a.levels.length));
  const bodyH = tallest * NODE_H + (tallest - 1) * ROW_GAP;

  const nodes = {};
  acts.forEach((act, col) => {
    const x = PAD + col * (NODE_W + COL_GAP);
    act.levels.forEach((level, row) => {
      nodes[level.id] = { level, act, col, x, y: PAD + HEAD_H + row * (NODE_H + ROW_GAP) };
    });
  });

  return {
    nodes,
    columns: acts.map((act, col) => ({
      act,
      x: PAD + col * (NODE_W + COL_GAP),
    })),
    width: PAD * 2 + acts.length * NODE_W + (acts.length - 1) * COL_GAP,
    height: PAD * 2 + HEAD_H + bodyH,
  };
}

/**
 * An edge from one node to another.
 *
 * Across columns: a cubic with horizontal control points, so it leaves and
 * enters flat. A straight line between non-adjacent columns passes through
 * whatever sits between them; a flat-entry curve still reads as a route when
 * it crosses one.
 *
 * Within a column: out of the right side and back into the right side,
 * bulging into the gap between columns. Nine of the eighteen edges are of
 * this kind, several in the same column, so the bulge scales with how far
 * apart the two nodes are. Without that, a neighbour hop and a three-row
 * reach draw the same arc and overlap into a smear. ROW_GAP/2 is subtracted
 * so a single-row hop still clears the boxes.
 */
/* How far an edge stops short of the node it points at, leaving room for
   the arrowhead to sit in the gap rather than under the box. */
const ARROW_GAP = 7;

function edgePath(from, to) {
  const y1 = from.y + NODE_H / 2;
  const y2 = to.y + NODE_H / 2;

  if (from.col === to.col) {
    const x = from.x + NODE_W;
    const span = Math.abs(y2 - y1);
    // Cap below COL_GAP so a loop never reaches the next column.
    const bulge = x + Math.min(COL_GAP - 10, 14 + span * 0.22);
    return `M${x},${y1} C${bulge},${y1} ${bulge},${y2} ${x + ARROW_GAP},${y2}`;
  }

  const x1 = from.x + NODE_W;
  const x2 = to.x - ARROW_GAP;
  const bend = Math.max(26, (x2 - x1) * 0.42);
  return `M${x1},${y1} C${x1 + bend},${y1} ${x2 - bend},${y2} ${x2},${y2}`;
}

/**
 * Wrap a title onto at most `maxLines` lines, breaking on spaces.
 *
 * SVG text does not wrap and has no ellipsis. The longest title here is 45
 * characters ("Changing the Agent Without Changing the Agent"), which needs
 * three lines at this box width; at two it was still being cut mid-phrase.
 * Greedy fill, and only the final line is clipped.
 */
function wrapTitle(text, perLine, maxLines = 3) {
  const words = text.split(" ");
  const lines = [];
  let line = "";
  for (let i = 0; i < words.length; i++) {
    const next = line ? `${line} ${words[i]}` : words[i];
    if (next.length <= perLine) {
      line = next;
      continue;
    }
    if (line) lines.push(line);
    if (lines.length === maxLines - 1) {
      // Last available line: everything remaining goes here, clipped.
      // Indexed by position, not indexOf - "Changing the Agent Without
      // Changing the Agent" repeats every word in it.
      lines.push(clip(words.slice(i).join(" "), perLine));
      return lines;
    }
    line = words[i];
  }
  if (line) lines.push(clip(line, perLine));
  return lines;
}

function clip(text, max) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

/**
 * Build the map SVG.
 *
 * `status(level)` returns "done" | "open" | "locked". Passed in rather than
 * imported so this module needs to know nothing about progress storage.
 */
export function skillMapSvg(acts, status, { activeId = "" } = {}) {
  const { nodes, columns, width, height } = layout(acts);
  const levels = acts.flatMap((a) => a.levels);
  const index = Object.fromEntries(levels.map((l, i) => [l.id, i + 1]));

  // Edges first, so nodes paint over them rather than being crossed. An
  // edge is "live" when what it leads to is reachable, which makes the lit
  // routes a path through the map rather than scattered colour.
  //
  // The arrowhead points at the level being unlocked, not at the
  // prerequisite. Without one the graph shows which levels are related but
  // not which way the dependency runs, and that is the whole question.
  const edges = levels
    .flatMap((level) =>
      (level.requires || [])
        .filter((r) => nodes[r])
        .map((r) => {
          const live = status(level) !== "locked";
          return `<path class="map-edge${live ? " live" : ""}"
                        marker-end="url(#map-ah${live ? "-live" : ""})"
                        d="${edgePath(nodes[r], nodes[level.id])}"/>`;
        })
    )
    .join("");

  const heads = columns
    .map(
      ({ act, x }) => `
      <text class="map-act" x="${x}" y="${PAD + 14}">${esc(
        act.title.replace(/^Act\s+/i, "").replace(/^([IVX½]+)\s*-\s*/, "$1 · ")
      )}</text>`
    )
    .join("");

  const cards = levels
    .map((level) => {
      const n = nodes[level.id];
      const state = status(level);
      const active = level.id === activeId;

      // A locked node names its blocker. "Locked" alone does not answer the
      // question the map exists for, which is what to do next.
      const blockers = (level.requires || [])
        .filter((r) => nodes[r] && status(nodes[r].level) !== "done")
        .map((r) => String(index[r]).padStart(2, "0"));
      const sub = state === "locked" && blockers.length ? `needs ${blockers.join(", ")}` : "";

      const lines = wrapTitle(level.title, 20);
      // Block of title lines, vertically centred in whatever space the
      // subtitle leaves. Computed rather than tabulated so adding a line
      // cannot push text out of the box.
      const bodyTop = 26;
      const bodyBottom = sub ? NODE_H - 20 : NODE_H - 8;
      const lineH = 13;
      const top =
        bodyTop + (bodyBottom - bodyTop - (lines.length - 1) * lineH) / 2;

      return `
      <g class="map-node ${state}${active ? " active" : ""}"
         data-map-level="${esc(level.id)}"
         transform="translate(${n.x},${n.y})"
         role="${state === "locked" ? "img" : "button"}"
         tabindex="${state === "locked" ? -1 : 0}"
         aria-label="${esc(`Level ${index[level.id]}, ${level.title}, ${state}`)}">
        <rect class="map-node-box" width="${NODE_W}" height="${NODE_H}" rx="10"/>
        <text class="map-node-num" x="12" y="19">${
          state === "done" ? "&#10003;" : String(index[level.id]).padStart(2, "0")
        }</text>
        ${lines
          .map(
            (line, i) =>
              `<text class="map-node-title" x="12" y="${top + i * lineH}">${esc(line)}</text>`
          )
          .join("")}
        ${sub ? `<text class="map-node-sub" x="12" y="${NODE_H - 9}">${esc(sub)}</text>` : ""}
      </g>`;
    })
    .join("");

  return `
    <svg class="map-svg" viewBox="0 0 ${width} ${height}"
         preserveAspectRatio="xMidYMid meet" role="img"
         aria-label="Course map: levels, and what unlocks them">
      <defs>
        <marker id="map-ah" markerWidth="7" markerHeight="6" refX="6.4" refY="3"
                orient="auto" markerUnits="userSpaceOnUse">
          <path class="map-ah" d="M0,0 L7,3 L0,6 Z"/>
        </marker>
        <marker id="map-ah-live" markerWidth="7" markerHeight="6" refX="6.4" refY="3"
                orient="auto" markerUnits="userSpaceOnUse">
          <path class="map-ah live" d="M0,0 L7,3 L0,6 Z"/>
        </marker>
      </defs>
      <g class="map-edges">${edges}</g>
      ${heads}
      ${cards}
    </svg>`;
}
