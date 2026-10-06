"""Inline diagrams for the curriculum.

The course had none, and several of its central ideas are spatial: a loop that
feeds itself, two event vocabularies meeting at a seam, a history that branches,
a transcript being cut in a place that must not break a pairing.

Each diagram is hand-written SVG using the site's palette, referenced from
curriculum prose as ``{{diagram:name}}``. They use ``currentColor`` and CSS
variables where possible so they stay correct if the theme changes.

Kept deliberately plain: a diagram here is an orientation device placed *before*
the explanation, not decoration after it.
"""

from __future__ import annotations

INK = "#151515"
MID = "#5f594f"
SOFT = "#8a8275"
LINE = "rgba(35,31,25,.22)"
TERRA = "#8f4b2e"
TERRA_L = "#d79b77"
SAGE = "#7f9b92"
CRIMSON = "#a33a2c"
AMBER_LINE = "#a07d32"
PAPER = "#fffcf3"
SUNK = "#f3efe5"

_FONT = 'font-family="Inter, Helvetica Neue, Arial, sans-serif"'
_MONO = 'font-family="JetBrains Mono, ui-monospace, Menlo, monospace"'


def _wrap(body: str, *, width: int, height: int, caption: str = "") -> str:
    figure = (
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet" '
        f'style="width:100%;max-width:{width}px;aspect-ratio:{width}/{height};'
        f'height:auto;display:block;margin:0 auto">{body}</svg>'
    )
    cap = f'<figcaption>{caption}</figcaption>' if caption else ""
    return f'<figure class="diagram">{figure}{cap}</figure>'


def _arrow_defs() -> str:
    """Arrowhead markers, referenced as ``url(#ah)`` and ``url(#ah-t)``.

    The ids are rewritten per diagram by ``render`` - see the note there.
    Figures keep writing the short names so the drawing code stays readable.
    """
    return (
        '<defs>'
        f'<marker id="ah" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto">'
        f'<path d="M0,0 L9,3.5 L0,7 z" fill="{MID}"/></marker>'
        f'<marker id="ah-t" markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto">'
        f'<path d="M0,0 L9,3.5 L0,7 z" fill="{TERRA}"/></marker>'
        '</defs>'
    )


def _box(x, y, w, h, label, *, sub="", accent=False, mono=False):
    stroke = TERRA if accent else LINE
    fill = "rgba(143,75,46,.07)" if accent else PAPER
    font = _MONO if mono else _FONT
    size = 13 if mono else 14
    text_y = y + h / 2 + (0 if not sub else -6)
    out = (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>'
        f'<text x="{x + w / 2}" y="{text_y}" {font} font-size="{size}" '
        f'font-weight="600" fill="{INK}" text-anchor="middle" '
        f'dominant-baseline="middle">{label}</text>'
    )
    if sub:
        out += (
            f'<text x="{x + w / 2}" y="{y + h / 2 + 12}" {_FONT} font-size="11.5" '
            f'fill="{SOFT}" text-anchor="middle" dominant-baseline="middle">{sub}</text>'
        )
    return out


def _label(x, y, text, *, size=11.5, fill=SOFT, anchor="middle", weight="500", mono=False):
    font = _MONO if mono else _FONT
    return (
        f'<text x="{x}" y="{y}" {font} font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}" dominant-baseline="middle">{text}</text>'
    )


# ------------------------------------------------------------- vocabulary
#
# A shared set of marks, so the same idea looks the same in every level.
#
# Before this, each diagram invented its own shapes: the model was a box in
# one figure and a circle in another, and a reader had to re-learn the
# notation at every level. Recurring marks are what let a diagram in Level 8
# build on one from Level 2 instead of starting over.
#
# The vocabulary is deliberately tiny, because an invented notation is only
# worth its learning cost if it is used often:
#
#   model      terracotta disc    the thing that decides, and cannot act
#   harness    square, ink        your code, the thing that acts
#   tool       sage square        the boundary where the world gets touched
#   message    rounded bar        one entry in the transcript
#   boundary   dashed rule        a line that data crosses deliberately
#
# Colour follows the same rule everywhere: terracotta is the model and the
# things it causes, sage is the world outside the process, ink is your code.


def _model(cx, cy, r=26, *, label="model"):
    """The model: a disc, because it is a black box you call, not a part you open."""
    out = (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="rgba(143,75,46,.12)" '
        f'stroke="{TERRA}" stroke-width="1.4"/>'
    )
    if label:
        out += _label(cx, cy, label, size=10.5, fill=TERRA, weight="600")
    return out


def _harness(x, y, w, h, label, *, sub=""):
    """Your code: a square-cornered box in ink. Deliberately the plainest mark."""
    return _box(x, y, w, h, label, sub=sub)


def _tool(x, y, w, h, label):
    """A tool: sage, the colour reserved for everything outside the process."""
    out = (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" '
        f'fill="rgba(127,155,146,.14)" stroke="{SAGE}" stroke-width="1.3"/>'
    )
    out += _label(x + w / 2, y + h / 2, label, size=11.5, fill=INK, weight="600")
    return out


def _message(x, y, w, role, text, *, hot=False, h=30):
    """One transcript entry. The same bar shape in every level that shows history."""
    stroke = TERRA if hot else LINE
    fill = "rgba(143,75,46,.07)" if hot else PAPER
    out = (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="7" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="1.2"/>'
    )
    out += _label(x + 13, y + h / 2, role, size=10.5, fill=MID, anchor="start", mono=True)
    if text:
        out += _label(x + w - 13, y + h / 2, text, size=10.5, fill=INK,
                      anchor="end", mono=True)
    return out


def _boundary(x, y1, y2, label="", *, colour=None):
    """A line data crosses on purpose. Always dashed, always vertical."""
    colour = colour or SOFT
    out = (
        f'<path d="M{x},{y1} L{x},{y2}" stroke="{colour}" stroke-width="1.4" '
        f'stroke-dasharray="5 4" fill="none"/>'
    )
    if label:
        out += _label(x, y1 - 11, label, size=10, fill=colour, weight="600")
    return out



# ---------------------------------------------------------------- diagrams


def agent_loop() -> str:
    """The central loop: model -> tool request -> execution -> back to model.

    The first diagram in the course, so it establishes the vocabulary every
    later figure reuses: terracotta disc for the model, plain box for your
    code, sage for the tool that touches the world.
    """
    b = _arrow_defs()
    b += _model(85, 87, 34)
    # "decides" sits to the right of the disc, not under it: the return
    # arrow comes up the left edge at x=85 and used to strike the word.
    b += _label(128, 112, "decides", size=11, fill=SOFT, anchor="start")
    b += _harness(250, 60, 130, 54, "Harness", sub="executes")
    b += _tool(480, 60, 130, 54, "Tool")
    b += _label(545, 136, "touches the world", size=11, fill=SAGE)

    # left to right
    b += f'<path d="M123,87 L244,87" stroke="{MID}" stroke-width="1.4" marker-end="url(#ah)" fill="none"/>'
    b += _label(184, 74, '"call read"')
    b += f'<path d="M380,87 L474,87" stroke="{MID}" stroke-width="1.4" marker-end="url(#ah)" fill="none"/>'
    b += _label(427, 74, "run it")

    # Return path, below both captions rather than through them: at y=152
    # it used to cut the "touches the world" label in half.
    b += (
        f'<path d="M545,160 L545,176 L85,176 L85,125" stroke="{TERRA}" stroke-width="1.4" '
        f'marker-end="url(#ah-t)" fill="none" stroke-dasharray="4 3"/>'
    )
    b += _label(315, 192, "result appended to the transcript, model called again", fill=TERRA)

    b += _label(315, 24, "while the model keeps asking for tools", size=12.5, fill=INK, weight="600")
    return _wrap(b, width=630, height=210,
                 caption="One round-trip. The loop repeats until a reply contains no tool calls.")


def event_seam() -> str:
    """Why there are two event vocabularies."""
    b = _arrow_defs()
    b += f'<rect x="12" y="46" width="180" height="128" rx="11" fill="{SUNK}" stroke="{LINE}"/>'
    b += _label(102, 30, "vendor-shaped", size=11, fill=SOFT, weight="600")
    for i, name in enumerate(["AssistantStartEvent", "TextDeltaEvent", "AssistantDoneEvent"]):
        b += _label(102, 78 + i * 32, name, size=10.5, fill=MID, mono=True)

    b += f'<rect x="398" y="46" width="180" height="128" rx="11" fill="rgba(143,75,46,.07)" stroke="{TERRA}"/>'
    b += _label(488, 30, "yours", size=11, fill=TERRA, weight="600")
    for i, name in enumerate(["MessageStartEvent", "MessageUpdateEvent", "MessageEndEvent"]):
        b += _label(488, 78 + i * 32, name, size=10.5, fill=INK, mono=True)

    b += _box(232, 82, 126, 56, "translate", sub="your code")
    b += f'<path d="M196,110 L226,110" stroke="{MID}" stroke-width="1.4" marker-end="url(#ah)" fill="none"/>'
    b += f'<path d="M360,110 L392,110" stroke="{TERRA}" stroke-width="1.4" marker-end="url(#ah-t)" fill="none"/>'

    b += _label(295, 196, "Every frontend reads only the right-hand column.",
                size=12, fill=INK, weight="600")
    b += _label(295, 214, "Swapping vendors changes the left column and nothing else.", size=11.5)
    return _wrap(b, width=590, height=232)


def async_timeline() -> str:
    """Why the loop is an async generator: when output becomes visible.

    The prose for this step already has a keyword table, which says what
    ``await`` and ``yield`` mean. What a table cannot show is the thing the
    distinction is actually about - time. Both lanes below do the same work
    and take the same total, and that is the point: the difference is purely
    when the caller gets to see any of it.
    """
    b = _arrow_defs()
    x0, x1 = 118, 578

    b += _label(348, 24, "Same work, same total time.", size=13, fill=INK, weight="700")
    b += _label(348, 44, "The difference is when you see any of it.", size=12, fill=SOFT)

    # --- lane 1: return. One long opaque stretch, everything at the end.
    y = 104
    b += _label(108, y + 15, "return", size=12, fill=MID, anchor="end", mono=True)
    b += (f'<rect x="{x0}" y="{y}" width="{518 - x0}" height="30" rx="7" '
          f'fill="{SUNK}" stroke="{LINE}" stroke-width="1.2"/>')
    b += _label((x0 + 518) / 2, y + 15, "working, nothing observable", size=11.5, fill=SOFT)
    b += (f'<rect x="518" y="{y}" width="{x1 - 518}" height="30" rx="7" '
          f'fill="rgba(143,75,46,.14)" stroke="{TERRA}" stroke-width="1.2"/>')
    b += _label((518 + x1) / 2, y + 15, "all of it", size=11, fill=TERRA, weight="600")
    b += (f'<path d="M548,{y - 4} L548,74" stroke="{TERRA}" stroke-width="1.4" '
          f'marker-end="url(#ah-t)" fill="none"/>')
    b += _label(548, 64, "first output", size=11, fill=TERRA, weight="600")

    # --- lane 2: yield. Same span, cut into turns, each one emitting.
    y2 = 206
    b += _label(108, y2 + 15, "yield", size=12, fill=MID, anchor="end", mono=True)
    seg = (x1 - x0) / 4
    for i in range(4):
        sx = x0 + i * seg
        b += (f'<rect x="{sx}" y="{y2}" width="{seg - 6}" height="30" rx="7" '
              f'fill="{PAPER}" stroke="{LINE}" stroke-width="1.2"/>')
        b += _label(sx + (seg - 6) / 2, y2 + 15, "await", size=11, fill=SOFT, mono=True)
        # The emit sits on the segment's trailing edge, where the await ends.
        edge = sx + seg - 3
        b += f'<circle cx="{edge}" cy="{y2 + 15}" r="5" fill="{TERRA}"/>'
        b += (f'<path d="M{edge},{y2 - 4} L{edge},176" stroke="{TERRA}" '
              f'stroke-width="1.4" marker-end="url(#ah-t)" fill="none"/>')
    b += _label(348, 166, "output, four times, during the run",
                size=11.5, fill=TERRA, weight="600")

    # --- shared time axis, so "same total" is visible rather than asserted.
    b += (f'<path d="M{x0},262 L{x1},262" stroke="{SOFT}" stroke-width="1.2" '
          f'marker-end="url(#ah)" fill="none" stroke-dasharray="3 3"/>')
    b += _label(348, 278, "time", size=11, fill=SOFT)

    return _wrap(b, width=660, height=292,
                 caption="An agent loop has to await the model and show progress "
                         "before the run ends. Those two needs together are what "
                         "an async generator is for.")


def memory_vs_disk() -> str:
    """Level 9: the same run, held correctly in memory and corrupt on disk.

    The bug is a divergence between two sequences, which prose has to
    enumerate step by step. Side by side it is one look: the interrupted
    tool result exists on the left and is missing on the right, and the gap
    is exactly where the write never happened.

    Reuses the transcript bars from Level 2 and 7, so the "what a valid
    transcript looks like" shape is already familiar by the time it breaks.
    """
    b = _arrow_defs()
    rows = [
        ("assistant", "tool_call id=c1", True),
        ("tool_result", "interrupted", True),
        ("user", '"never mind"', False),
    ]

    b += _label(150, 26, "in memory", size=12, fill=INK, weight="700")
    b += _label(150, 44, "valid", size=10.5, fill=SAGE, weight="600")
    for i, (role, text, hot) in enumerate(rows):
        b += _message(24, 62 + i * 40, 252, role, text, hot=hot)

    b += _boundary(316, 56, 196, "the write")

    b += _label(482, 26, "on disk", size=12, fill=INK, weight="700")
    b += _label(482, 44, "rejected on reload", size=10.5, fill=CRIMSON, weight="600")
    # The same sequence minus one row: the gap is the whole point, so it is
    # drawn as an empty slot rather than closed up.
    b += _message(356, 62, 252, "assistant", "tool_call id=c1", hot=True)
    b += (f'<rect x="356" y="102" width="252" height="30" rx="7" fill="none" '
          f'stroke="{CRIMSON}" stroke-width="1.3" stroke-dasharray="5 4"/>')
    b += _label(482, 117, "never written", size=10.5, fill=CRIMSON, weight="600")
    b += _message(356, 142, 252, "user", '"never mind"', hot=False)

    b += (f'<path d="M286,117 L348,117" stroke="{MID}" stroke-width="1.3" '
          f'marker-end="url(#ah)" fill="none" stroke-dasharray="3 3"/>')

    b += _label(316, 212,
                "A tool call with no result: the provider rejects the whole transcript.",
                size=11.5, fill=INK, weight="600")
    return _wrap(b, width=632, height=232,
                 caption="The in-memory repair ran in a finally block. "
                         "The persistence layer never saw it.")


def compaction_tradeoff() -> str:
    """Level 8: four compaction strategies, and what each one destroys.

    The step asks which strategy best preserves the ability to continue the
    task. The four rows are the step's four options, in its own order, so the
    figure is a view of the question rather than a different question.

    Nothing is marked correct here: this diagram sits in the step body, and
    pre-announcing the answer would make the prediction pointless. What it
    shows is that "how much survives" and "what survives" are different
    axes, which is the distinction the question turns on.
    """
    b = ""
    b += _label(336, 24, "Every strategy loses something. Which loss can the agent survive?",
                size=12, fill=INK, weight="600")

    # The step's four options, in the step's order. `kept` is the rough
    # fraction of the transcript still in context afterwards.
    rows = [
        ("summarize old", 0.26, "all of it, compressed and approximate"),
        ("drop oldest", 0.58, "recent turns exact; the original goal gone"),
        ("drop tool results", 0.46, "prose intact; call/result pairs broken"),
        ("refuse to continue", 0.00, "nothing - the session ends instead"),
    ]
    bar_x, bar_w = 190, 250
    for i, (name, kept, note) in enumerate(rows):
        y = 58 + i * 42
        b += _label(176, y + 9, name, size=11, fill=MID, anchor="end")
        kw = bar_w * kept
        if kw:
            b += (f'<rect x="{bar_x}" y="{y}" width="{kw}" height="18" rx="4" '
                  f'fill="rgba(143,75,46,.22)" stroke="{TERRA}" stroke-width="1"/>')
        b += (f'<rect x="{bar_x + kw}" y="{y}" width="{bar_w - kw}" height="18" rx="4" '
              f'fill="{SUNK}" stroke="{LINE}" stroke-width="1"/>')
        b += _label(bar_x + bar_w + 14, y + 9, note, size=10.5, fill=SOFT,
                    anchor="start")

    b += _label(bar_x + 28, 236, "kept in context", size=10, fill=TERRA, weight="600")
    b += _label(bar_x + 186, 236, "lost", size=10, fill=SOFT, weight="600")
    return _wrap(b, width=688, height=252,
                 caption="Bar width is how much of the transcript survives. "
                         "The question is about the column on the right.")


def transcript_pairing() -> str:
    """The tool-call / tool-result adjacency invariant.

    Uses the same message bars as every other transcript figure, so a reader
    who met them in Level 2 does not re-learn them here. The only new mark is
    the bracket, which is the point of the diagram.
    """
    b = ""
    rows = [
        ("user", '"how many lines?"', False),
        ("assistant", "tool_call id=c1", True),
        ("tool_result", "id=c1", True),
        ("assistant", '"4 lines"', False),
    ]
    for i, (role, text, hot) in enumerate(rows):
        b += _message(90, 44 + i * 42, 300, role, text, hot=hot, h=32)

    b += (f'<path d="M404,102 L430,102 L430,144 L404,144" stroke="{TERRA}" '
          f'stroke-width="1.5" fill="none"/>')
    b += _label(442, 123, "must be", size=11, fill=TERRA, anchor="start", weight="600")
    b += _label(442, 138, "adjacent", size=11, fill=TERRA, anchor="start", weight="600")

    b += _label(240, 24, "A provider rejects any other arrangement",
                size=12, fill=INK, weight="600")
    return _wrap(b, width=540, height=232,
                 caption="Cancellation, compaction and replay all have to preserve this.")


def session_tree() -> str:
    """Append-only history as a tree, and why branching needs no code."""
    b = _arrow_defs()
    nodes = [
        (250, 40, "question", False),
        (250, 104, "answer A", False),
        (120, 168, "retry", True),
        (380, 168, "continue", False),
    ]
    for x, y, label, hot in nodes:
        stroke = TERRA if hot else LINE
        fill = "rgba(143,75,46,.07)" if hot else PAPER
        b += (f'<rect x="{x - 62}" y="{y}" width="124" height="34" rx="8" fill="{fill}" '
              f'stroke="{stroke}" stroke-width="1.2"/>')
        b += _label(x, y + 17, label, size=12, fill=INK, weight="600")

    b += f'<path d="M250,74 L250,98" stroke="{MID}" stroke-width="1.3" marker-end="url(#ah)" fill="none"/>'
    # Split below "answer A" so both children hang from the same elbow.
    b += f'<path d="M250,138 L250,152" stroke="{MID}" stroke-width="1.3" fill="none"/>'
    b += f'<path d="M250,152 L120,152 L120,162" stroke="{TERRA}" stroke-width="1.3" marker-end="url(#ah-t)" fill="none"/>'
    b += f'<path d="M250,152 L380,152 L380,162" stroke="{MID}" stroke-width="1.3" marker-end="url(#ah)" fill="none"/>'

    b += _label(250, 225, "Two entries share one parent_id. That is the whole feature.",
                size=12, fill=INK, weight="600")
    b += _label(250, 243, "Nothing is deleted; both paths stay replayable.", size=11.5)
    return _wrap(b, width=500, height=258)


def compaction() -> str:
    """Durable record vs. active context."""
    b = _arrow_defs()
    b += _label(140, 22, "on disk (append-only)", size=11.5, fill=SOFT, weight="600")
    for i in range(6):
        y = 40 + i * 26
        b += (f'<rect x="60" y="{y}" width="160" height="20" rx="4" fill="{PAPER}" '
              f'stroke="{LINE}" stroke-width="1"/>')
    b += (f'<rect x="60" y="196" width="160" height="20" rx="4" '
          f'fill="rgba(143,75,46,.12)" stroke="{TERRA}" stroke-width="1.2"/>')
    b += _label(140, 206, "compaction entry", size=10, fill=TERRA, mono=True)

    b += _label(420, 22, "what the model sees", size=11.5, fill=SOFT, weight="600")
    b += (f'<rect x="340" y="40" width="160" height="46" rx="6" '
          f'fill="rgba(143,75,46,.09)" stroke="{TERRA}" stroke-width="1.2"/>')
    b += _label(420, 63, "summary", size=11.5, fill=TERRA, weight="600")
    for i in range(3):
        y = 96 + i * 26
        b += (f'<rect x="340" y="{y}" width="160" height="20" rx="4" fill="{PAPER}" '
              f'stroke="{LINE}" stroke-width="1"/>')
    b += _label(420, 180, "recent turns, kept verbatim", size=11, fill=MID)

    b += (f'<path d="M232,118 L330,100" stroke="{MID}" stroke-width="1.4" '
          f'marker-end="url(#ah)" fill="none" stroke-dasharray="4 3"/>')
    b += _label(281, 130, "replay", size=11, fill=SOFT)

    b += _label(280, 240, "Nothing is deleted. Replay produces a smaller context.",
                size=12, fill=INK, weight="600")
    return _wrap(b, width=560, height=258)


def layers() -> str:
    """The three-layer boundary."""
    b = ""
    rows = [
        ("tau_coding", "CLI, TUI, tools, config, project context", "application"),
        ("tau_agent", "loop, harness, events, sessions", "portable brain"),
        ("tau_ai", "provider streaming", "vendor APIs"),
    ]
    for i, (name, detail, tag) in enumerate(rows):
        y = 38 + i * 62
        accent = i == 1
        stroke = TERRA if accent else LINE
        fill = "rgba(143,75,46,.07)" if accent else PAPER
        b += (f'<rect x="60" y="{y}" width="400" height="50" rx="9" fill="{fill}" '
              f'stroke="{stroke}" stroke-width="1.2"/>')
        b += _label(80, y + 19, name, size=13, fill=INK, anchor="start", weight="700", mono=True)
        b += _label(80, y + 36, detail, size=11, fill=MID, anchor="start")
        b += _label(440, y + 25, tag, size=10.5, fill=SOFT, anchor="end")

    for i in range(2):
        y = 88 + i * 62
        b += (f'<path d="M260,{y} L260,{y + 12}" stroke="{SOFT}" stroke-width="1.2" fill="none"/>')
        b += _label(276, y + 6, "depends on", size=10, fill=SOFT, anchor="start")

    b += _label(260, 238, "Dependencies point one way. The brain never reaches up.",
                size=12, fill=INK, weight="600")
    return _wrap(b, width=520, height=256)


def _level_count() -> int:
    """How many levels the curriculum actually has, spelled out."""
    from academy.curriculum import all_levels, load_curriculum

    words = {
        12: "Twelve", 13: "Thirteen", 14: "Fourteen", 15: "Fifteen",
        16: "Sixteen", 17: "Seventeen", 18: "Eighteen", 19: "Nineteen",
        20: "Twenty",
    }
    n = len(all_levels(load_curriculum()))
    return words.get(n, str(n))


def course_map() -> str:
    """The whole course in one picture, shown above the level list.

    Four acts on a spine, plus Act II-and-a-half hanging below it. The half
    act is genuinely off-spine - its four levels branch from Act I and II
    rather than continuing the sequence - but an earlier version left it out
    of the drawing entirely while the subhead beside it said "5 acts". That
    was invisible while the figure sat at the top of the page, and obvious
    once it moved next to the curriculum heading.
    """
    b = _arrow_defs()

    # Geometry kept explicit: the arrow spans the gap between boxes exactly,
    # so widening a box cannot make an arrow overlap the next one.
    box_w, box_h = 190, 84
    gap = 56
    top = 86
    left = 40

    acts = [
        ("I", "The Engine", "loop, events, tools"),
        ("II", "Memory", "state, context, systems"),
        ("III", "The Application", "persistence, boundaries"),
        ("IV", "Reconstruction", "build your own"),
    ]
    for i, (numeral, title, detail) in enumerate(acts):
        x = left + i * (box_w + gap)
        last = i == len(acts) - 1
        stroke = TERRA if last else LINE
        fill = "rgba(143,75,46,.09)" if last else PAPER
        b += (f'<rect x="{x}" y="{top}" width="{box_w}" height="{box_h}" rx="12" '
              f'fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>')
        b += _label(x + box_w / 2, top + 22, f"ACT {numeral}", size=11.5,
                    fill=TERRA, weight="700")
        b += _label(x + box_w / 2, top + 46, title, size=16, fill=INK, weight="700")
        b += _label(x + box_w / 2, top + 66, detail, size=12, fill=SOFT)

        if not last:
            # Start at the box edge, stop short of the next one so the
            # arrowhead sits in the gap rather than on top of the box.
            start = x + box_w + 8
            end = x + box_w + gap - 10
            b += (f'<path d="M{start},{top + box_h / 2} L{end},{top + box_h / 2}" '
                  f'stroke="{MID}" stroke-width="1.6" marker-end="url(#ah)" fill="none"/>')

    # Act II-and-a-half, below the spine between Acts I and II, because that
    # is where its prerequisites are. Dashed, to say "branch, not sequence".
    half_w = box_w + gap + box_w  # spans the first two acts
    half_y = top + box_h + 44
    b += (f'<rect x="{left}" y="{half_y}" width="{half_w}" height="56" rx="12" '
          f'fill="{PAPER}" stroke="{LINE}" stroke-width="1.4" stroke-dasharray="6 4"/>')
    b += _label(left + half_w / 2, half_y + 19, "ACT II½", size=11.5,
                fill=TERRA, weight="700")
    b += _label(left + half_w / 2, half_y + 38,
                "Around the Loop - prompts, permissions, recovery, extensions",
                size=12, fill=SOFT)
    # Two short droppers from the acts it hangs off.
    for i in (0, 1):
        x = left + i * (box_w + gap) + box_w / 2
        b += (f'<path d="M{x},{top + box_h} L{x},{half_y}" stroke="{LINE}" '
              f'stroke-width="1.4" stroke-dasharray="4 4" fill="none"/>')

    centre = left + (len(acts) * box_w + (len(acts) - 1) * gap) / 2
    total_levels = _level_count()
    b += _label(centre, 40,
                f"{total_levels} levels, each one a mechanism you build yourself",
                size=16, fill=INK, weight="700")
    b += _label(centre, 62, "From a thirty-line loop to a working agent",
                size=13, fill=SOFT)
    width = int(left * 2 + len(acts) * box_w + (len(acts) - 1) * gap)
    # Height follows the half act, which now sits below the spine.
    return _wrap(b, width=width, height=half_y + 56 + 28)


def prompt_assembly() -> str:
    """Where the system prompt comes from."""
    b = _arrow_defs()
    parts = [
        ("default preamble", "tau_coding"),
        ("tool list", "from loaded tools"),
        ("project AGENTS.md", "from the repo"),
        ("skills", "when relevant"),
        ("extension sections", "third party"),
    ]
    for i, (label, origin) in enumerate(parts):
        y = 46 + i * 36
        b += (f'<rect x="40" y="{y}" width="190" height="28" rx="6" fill="{PAPER}" '
              f'stroke="{LINE}" stroke-width="1.1"/>')
        b += _label(135, y + 14, label, size=11, fill=INK, weight="600")
        b += _label(248, y + 14, origin, size=10, fill=SOFT, anchor="start")
        b += (f'<path d="M232,{y + 14} L236,{y + 14}" stroke="{LINE}" stroke-width="1"/>')

    b += (f'<path d="M380,110 L420,110" stroke="{TERRA}" stroke-width="1.4" '
          f'marker-end="url(#ah-t)" fill="none"/>')
    b += (f'<rect x="428" y="72" width="150" height="76" rx="10" '
          f'fill="rgba(143,75,46,.08)" stroke="{TERRA}" stroke-width="1.2"/>')
    b += _label(503, 100, "system prompt", size=12.5, fill=INK, weight="700")
    b += _label(503, 120, "+ provenance", size=11, fill=TERRA)

    b += _label(300, 24, "Assembled per run, never a literal string",
                size=12.5, fill=INK, weight="600")
    b += _label(300, 240, "Every section is attributable, which is the only way to explain behaviour",
                size=11, fill=SOFT)
    return _wrap(b, width=620, height=258)


def permission_gate() -> str:
    """The decision point between the loop and the world."""
    b = _arrow_defs()
    b += _box(30, 70, 120, 50, "loop", sub="wants to act")
    b += _box(240, 62, 140, 66, "gate", sub="classify", accent=True)
    b += _box(470, 70, 120, 50, "the world", sub="files, shell")

    b += f'<path d="M152,95 L234,95" stroke="{MID}" stroke-width="1.4" marker-end="url(#ah)" fill="none"/>'
    b += f'<path d="M382,95 L464,95" stroke="{SAGE}" stroke-width="1.4" marker-end="url(#ah)" fill="none"/>'
    b += _label(423, 83, "allow", size=10.5, fill="#4a6a60")

    verdicts = [("allow", SAGE, "read inside cwd"), ("ask", AMBER_LINE, "bash"), ("deny", CRIMSON, "escapes cwd")]
    for i, (name, colour, example) in enumerate(verdicts):
        y = 162 + i * 26
        b += f'<rect x="240" y="{y}" width="56" height="20" rx="10" fill="{colour}" opacity=".16"/>'
        b += _label(268, y + 10, name, size=10.5, fill=colour, weight="700")
        b += _label(306, y + 10, example, size=10.5, fill=SOFT, anchor="start")

    b += _label(310, 28, "Policy lives outside the loop", size=12.5, fill=INK, weight="600")
    b += _label(310, 252, "so a TUI can ask, CI can refuse, and a test can allow everything",
                size=11, fill=SOFT)
    return _wrap(b, width=620, height=268)


def failure_taxonomy() -> str:
    """Three kinds of failure, three responses."""
    b = _arrow_defs()
    rows = [
        ("transient", "429, 500, timeouts", "retry with backoff", SAGE),
        ("terminal", "401, malformed request", "stop, tell the user", CRIMSON),
        ("recoverable", "context overflow", "change something, retry once", TERRA),
    ]
    for i, (kind, example, response, colour) in enumerate(rows):
        y = 50 + i * 60
        b += (f'<rect x="40" y="{y}" width="130" height="44" rx="8" '
              f'fill="{colour}" opacity=".10"/>')
        b += (f'<rect x="40" y="{y}" width="130" height="44" rx="8" '
              f'fill="none" stroke="{colour}" stroke-width="1.2" opacity=".55"/>')
        b += _label(105, y + 17, kind, size=12, fill=colour, weight="700")
        b += _label(105, y + 32, example, size=9.5, fill=SOFT)
        b += (f'<path d="M174,{y + 22} L232,{y + 22}" stroke="{MID}" stroke-width="1.3" '
              f'marker-end="url(#ah)" fill="none"/>')
        b += _label(240, y + 22, response, size=11.5, fill=INK, anchor="start", weight="600")

    b += _label(260, 24, "The harness cannot tell these apart by exception type",
                size=12.5, fill=INK, weight="600")
    b += _label(260, 248, "It has to read the status and the message, which is heuristic - so fail safe",
                size=11, fill=SOFT)
    return _wrap(b, width=620, height=266)


def extension_points() -> str:
    """Knowledge versus capability."""
    b = _arrow_defs()
    b += (f'<rect x="30" y="54" width="250" height="120" rx="11" '
          f'fill="{SUNK}" stroke="{LINE}"/>')
    b += _label(155, 76, "SKILLS", size=10.5, fill=SAGE, weight="700")
    b += _label(155, 100, "knowledge", size=14, fill=INK, weight="700")
    b += _label(155, 122, "markdown, loaded when relevant", size=10.5, fill=SOFT)
    b += _label(155, 146, "worst case: wasted tokens", size=10.5, fill="#4a6a60")

    b += (f'<rect x="340" y="54" width="250" height="120" rx="11" '
          f'fill="rgba(143,75,46,.07)" stroke="{TERRA}"/>')
    b += _label(465, 76, "EXTENSIONS", size=10.5, fill=TERRA, weight="700")
    b += _label(465, 100, "capability", size=14, fill=INK, weight="700")
    b += _label(465, 122, "python, runs in your process", size=10.5, fill=SOFT)
    b += _label(465, 146, "worst case: anything", size=10.5, fill=CRIMSON)

    b += _label(310, 28, "Two extension points, because the blast radius differs",
                size=12.5, fill=INK, weight="600")
    b += _label(310, 198, "This is why loading one needs a trust decision and the other mostly does not",
                size=11, fill=SOFT)
    return _wrap(b, width=620, height=216)


def frontend_fanout() -> str:
    """One event stream, many consumers. Level 3."""
    b = _arrow_defs()
    b += _box(30, 92, 130, 52, "the loop", sub="emits events", accent=True)
    for i, (name, detail) in enumerate(
        [("terminal", "text"), ("TUI", "widgets"), ("JSON log", "scripting"), ("tests", "assertions")]
    ):
        y = 34 + i * 54
        b += (f'<rect x="330" y="{y}" width="150" height="40" rx="8" fill="{PAPER}" '
              f'stroke="{LINE}" stroke-width="1.1"/>')
        b += _label(405, y + 15, name, size=12, fill=INK, weight="650")
        b += _label(405, y + 29, detail, size=10, fill=SOFT)
        b += (f'<path d="M224,118 C270,118 275,{y + 20} 324,{y + 20}" '
              f'stroke="{MID}" stroke-width="1.2" marker-end="url(#ah)" fill="none" opacity=".75"/>')

    b += _label(192, 100, "events", size=10.5, fill=TERRA, weight="600")
    b += _label(255, 24, "Adding a fifth needs no change to the loop",
                size=12.5, fill=INK, weight="600")
    b += _label(255, 272, "The loop decided nothing about format, destination or timing",
                size=11, fill=SOFT)
    return _wrap(b, width=520, height=290)


def tool_contract() -> str:
    """What a tool returns, and who reads which half. Level 4."""
    b = _arrow_defs()
    b += (f'<rect x="200" y="46" width="200" height="74" rx="10" '
          f'fill="rgba(143,75,46,.08)" stroke="{TERRA}" stroke-width="1.2"/>')
    b += _label(300, 68, "ToolResult", size=13, fill=INK, weight="700", mono=True)
    b += _label(300, 90, "content   details", size=11, fill=TERRA, mono=True)
    b += _label(300, 106, "terminate  added_tools", size=9.5, fill=SOFT, mono=True)

    b += f'<path d="M248,124 L150,164" stroke="{MID}" stroke-width="1.3" marker-end="url(#ah)" fill="none"/>'
    b += _box(40, 168, 180, 50, "the model", sub="paid for, every turn")
    b += f'<path d="M352,124 L450,164" stroke="{MID}" stroke-width="1.3" marker-end="url(#ah)" fill="none"/>'
    b += _box(380, 168, 180, 50, "the UI", sub="free, rendered once")

    b += _label(300, 24, "One result, two audiences with different costs",
                size=12.5, fill=INK, weight="600")
    b += _label(300, 244, "Collapsing them means paying tokens for a syntax-highlighted diff",
                size=11, fill=SOFT)
    return _wrap(b, width=600, height=262)


def loop_vs_harness() -> str:
    """A verb and a noun. Level 5."""
    b = _arrow_defs()
    b += (f'<rect x="30" y="50" width="250" height="150" rx="11" fill="{SUNK}" stroke="{LINE}"/>')
    b += _label(155, 72, "run_agent_loop()", size=12.5, fill=INK, weight="700", mono=True)
    b += _label(155, 94, "a verb", size=11, fill=SOFT)
    for i, line in enumerate(["lives for one run", "holds no state", "trivially testable"]):
        b += _label(155, 122 + i * 22, line, size=10.5, fill=MID)

    b += (f'<rect x="340" y="50" width="250" height="150" rx="11" '
          f'fill="rgba(143,75,46,.07)" stroke="{TERRA}"/>')
    b += _label(465, 72, "AgentHarness", size=12.5, fill=INK, weight="700", mono=True)
    b += _label(465, 94, "a noun", size=11, fill=TERRA)
    for i, line in enumerate(["lives for a conversation", "owns the transcript", "guards against overlap"]):
        b += _label(465, 122 + i * 22, line, size=10.5, fill=MID)

    b += (f'<path d="M284,125 L334,125" stroke="{MID}" stroke-width="1.4" '
          f'marker-end="url(#ah)" fill="none"/>')
    b += _label(309, 112, "calls", size=10, fill=SOFT)

    b += _label(310, 26, "Different lifetimes, so different objects",
                size=12.5, fill=INK, weight="600")
    b += _label(310, 224, "Fuse them and you lose testing, multiple sessions, and cancellation",
                size=11, fill=SOFT)
    return _wrap(b, width=620, height=242)


def steering_timing() -> str:
    """Where a mid-run message can safely be injected. Level 6."""
    b = _arrow_defs()
    events = [
        (40, "provider\ncall"), (150, "tool\ncall"), (260, "tool\nresult"),
        (370, "turn\nends"), (480, "next\ncall"),
    ]
    for x, label in events:
        b += (f'<rect x="{x}" y="70" width="86" height="46" rx="8" fill="{PAPER}" '
              f'stroke="{LINE}" stroke-width="1.1"/>')
        for i, part in enumerate(label.split("\n")):
            b += _label(x + 43, 87 + i * 14, part, size=10.5, fill=INK, weight="600")
        if x < 480:
            b += (f'<path d="M{x + 88},93 L{x + 146},93" stroke="{MID}" '
                  f'stroke-width="1.2" marker-end="url(#ah)" fill="none"/>')

    # the safe injection point
    b += f'<path d="M458,60 L458,126" stroke="{TERRA}" stroke-width="2" stroke-dasharray="4 3"/>'
    b += _label(458, 44, "inject here", size=11, fill=TERRA, weight="700")
    b += _label(458, 148, "transcript is consistent;", size=10, fill=TERRA)
    b += _label(458, 162, "next request not yet built", size=10, fill=TERRA)

    b += f'<path d="M205,60 L205,126" stroke="{CRIMSON}" stroke-width="1.6" stroke-dasharray="3 3" opacity=".6"/>'
    b += _label(205, 44, "not here", size=10.5, fill=CRIMSON, weight="600")
    b += _label(205, 148, "a call without its result", size=10, fill=CRIMSON)

    b += _label(300, 200, "The turn boundary is the only safe moment",
                size=12.5, fill=INK, weight="600")
    return _wrap(b, width=600, height=216)


def convergence() -> str:
    """The same abstractions in two independent implementations. Level 11."""
    b = _arrow_defs()
    rows = [
        ("the loop", "run_agent_loop", "agent-loop.ts", True),
        ("events", "agent_start, turn_end", "agent_start, turn_end", True),
        ("persistence", "on message_end", "on message_end", True),
        ("language", "Python", "TypeScript", False),
        ("queue mode", "configurable", "fixed", False),
    ]
    b += _label(170, 40, "tau", size=12, fill=INK, weight="700", mono=True)
    b += _label(400, 40, "pi", size=12, fill=INK, weight="700", mono=True)
    for i, (concept, left, right, same) in enumerate(rows):
        y = 64 + i * 34
        colour = SAGE if same else TERRA
        b += _label(78, y + 12, concept, size=11, fill=MID, anchor="end", weight="600")
        b += (f'<rect x="92" y="{y}" width="156" height="24" rx="5" '
              f'fill="{colour}" opacity=".10"/>')
        b += _label(170, y + 12, left, size=10, fill=INK, mono=True)
        b += (f'<rect x="322" y="{y}" width="156" height="24" rx="5" '
              f'fill="{colour}" opacity=".10"/>')
        b += _label(400, y + 12, right, size=10, fill=INK, mono=True)
        mark = "=" if same else "\u2260"
        b += _label(285, y + 12, mark, size=13, fill=colour, weight="700")

    b += _label(285, 22, "Two teams, two languages, same abstractions",
                size=12.5, fill=INK, weight="600")
    b += _label(285, 252, "What both do under different constraints is forced. What differs was decided.",
                size=11, fill=SOFT)
    return _wrap(b, width=580, height=268)


def capstone_assembly() -> str:
    """Everything you built, assembled. Level 12."""
    b = _arrow_defs()
    pieces = [
        (40, "loop.py", "L2"), (160, "harness.py", "L5"),
        (280, "tools_impl.py", "L4"), (400, "session_store.py", "L9"),
        (520, "compaction.py", "L8"),
    ]
    for x, name, level in pieces:
        b += (f'<rect x="{x}" y="44" width="104" height="44" rx="8" fill="{PAPER}" '
              f'stroke="{LINE}" stroke-width="1.1"/>')
        b += _label(x + 52, 60, name, size=9.5, fill=INK, mono=True, weight="600")
        b += _label(x + 52, 76, level, size=9.5, fill=TERRA, weight="700")
        b += (f'<path d="M{x + 52},90 L{x + 52},110 L322,110 L322,130" '
              f'stroke="{MID}" stroke-width="1" fill="none" opacity=".5"/>')

    b += (f'<rect x="232" y="134" width="180" height="52" rx="10" '
          f'fill="rgba(143,75,46,.08)" stroke="{TERRA}" stroke-width="1.3"/>')
    b += _label(322, 152, "MyAgent", size=13.5, fill=INK, weight="700", mono=True)
    b += _label(322, 170, "a working coding agent", size=10, fill=TERRA)

    b += (f'<path d="M322,188 L322,210" stroke="{TERRA}" stroke-width="1.4" '
          f'marker-end="url(#ah-t)" fill="none"/>')
    b += _label(322, 224, "real model, real files", size=11, fill=INK, weight="600")

    b += _label(322, 24, "Nothing new to learn - only assembly",
                size=12.5, fill=INK, weight="600")
    return _wrap(b, width=660, height=244)


DIAGRAMS = {
    "course-map": course_map,
    "agent-loop": agent_loop,
    "async-timeline": async_timeline,
    "memory-vs-disk": memory_vs_disk,
    "compaction-tradeoff": compaction_tradeoff,
    "event-seam": event_seam,
    "transcript-pairing": transcript_pairing,
    "session-tree": session_tree,
    "compaction": compaction,
    "layers": layers,
    "convergence": convergence,
    "capstone-assembly": capstone_assembly,
    "frontend-fanout": frontend_fanout,
    "tool-contract": tool_contract,
    "loop-vs-harness": loop_vs_harness,
    "steering-timing": steering_timing,
    "prompt-assembly": prompt_assembly,
    "permission-gate": permission_gate,
    "failure-taxonomy": failure_taxonomy,
    "extension-points": extension_points,
}


def render(name: str) -> str:
    """Return the SVG figure for ``name``, or an empty string.

    Marker ids are namespaced here, because SVG ids live in the *document*,
    not in the <svg> that declares them. Every figure writes `id="ah"`, so
    two figures on one page gave two elements the same id and both
    `url(#ah)` references resolved to whichever came first. In practice the
    arrowheads on the second diagram silently vanished, which is how this
    was found: the loop in Level 1 had no arrows once the level also showed
    the async timeline.

    Rewriting at render time keeps the drawing code readable - each figure
    still refers to `ah` and `ah-t` - and makes the ids unique by
    construction rather than by every author remembering to.
    """
    builder = DIAGRAMS.get(name)
    if not builder:
        return ""
    svg = builder()
    for marker in ("ah-t", "ah"):  # longest first: "ah" is a prefix of "ah-t"
        svg = svg.replace(f'id="{marker}"', f'id="{name}-{marker}"')
        svg = svg.replace(f"url(#{marker})", f"url(#{name}-{marker})")
    return svg


def expand(text: str) -> str:
    """Replace every ``{{diagram:name}}`` marker in ``text``."""
    if "{{diagram:" not in text:
        return text
    import re

    return re.sub(
        r"\{\{diagram:([a-z0-9-]+)\}\}",
        lambda m: render(m.group(1)),
        text,
    )
