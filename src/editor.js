/* CodeMirror 6, themed to match the course.
 *
 * Vite bundles this now, so there is no hand-run esbuild step. The Tab
 * handling and comment binding resolve conflicts the learner hit: Tab only
 * accepts a completion while the popup is open, and Cmd+/ is left to the
 * tutor panel. */

import { EditorView, keymap, lineNumbers, highlightActiveLine,
         highlightActiveLineGutter, drawSelection, rectangularSelection,
         highlightSpecialChars } from "@codemirror/view";
import { EditorState, Compartment, Prec } from "@codemirror/state";
import { python } from "@codemirror/lang-python";
import { defaultKeymap, history, historyKeymap, indentWithTab,
         toggleComment, indentMore, indentLess } from "@codemirror/commands";
import { indentUnit, syntaxHighlighting, HighlightStyle,
         bracketMatching, foldGutter, indentOnInput } from "@codemirror/language";
import { closeBrackets, closeBracketsKeymap, autocompletion,
         completionKeymap, acceptCompletion, completionStatus,
         startCompletion } from "@codemirror/autocomplete";
import { searchKeymap, highlightSelectionMatches } from "@codemirror/search";
import { indentationMarkers } from "@replit/codemirror-indentation-markers";
import { tags as t } from "@lezer/highlight";

// Warm-ink palette matching the course's paper theme.
const highlight = HighlightStyle.define([
  { tag: t.keyword,                         color: "#d79b77", fontWeight: "600" },
  { tag: [t.name, t.deleted, t.character],  color: "#e8e2d6" },
  { tag: [t.function(t.variableName), t.labelName], color: "#9fc4ba" },
  { tag: [t.definition(t.variableName)],    color: "#e8e2d6" },
  { tag: [t.className, t.definition(t.propertyName)], color: "#c8d8d2", fontWeight: "600" },
  { tag: [t.typeName, t.namespace],         color: "#c8d8d2" },
  { tag: t.string,                          color: "#c3b183" },
  { tag: [t.number, t.bool, t.null],        color: "#d79b77" },
  { tag: t.comment,                         color: "#8a8275", fontStyle: "italic" },
  { tag: t.operator,                        color: "#bdb5aa" },
  { tag: t.self,                            color: "#d79b77", fontStyle: "italic" },
  { tag: [t.propertyName],                  color: "#dcd4c6" },
  { tag: t.invalid,                         color: "#e86a5a" },
]);

const theme = EditorView.theme({
  "&": {
    color: "#e8e2d6",
    backgroundColor: "#2c2823",
    fontSize: "13px",
  },
  ".cm-content": {
    fontFamily: '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace',
    padding: "12px 0",
    caretColor: "#d79b77",
  },
  ".cm-cursor, .cm-dropCursor": { borderLeftColor: "#d79b77", borderLeftWidth: "2px" },
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection": {
    backgroundColor: "rgba(215, 155, 119, 0.22)",
  },
  ".cm-gutters": {
    backgroundColor: "#24211d",
    color: "#6f685c",
    border: "none",
    borderRight: "1px solid rgba(255,255,255,.06)",
  },
  ".cm-activeLineGutter": { backgroundColor: "rgba(255,255,255,.04)", color: "#bdb5aa" },
  ".cm-activeLine": { backgroundColor: "rgba(255,255,255,.028)" },
  ".cm-matchingBracket, &.cm-focused .cm-matchingBracket": {
    backgroundColor: "rgba(215,155,119,.2)",
    outline: "1px solid rgba(215,155,119,.4)",
  },
  ".cm-selectionMatch": { backgroundColor: "rgba(200,216,210,.14)" },
  ".cm-tooltip": {
    backgroundColor: "#24211d",
    border: "1px solid rgba(255,255,255,.12)",
    borderRadius: "6px",
  },
  ".cm-tooltip-autocomplete ul li[aria-selected]": {
    backgroundColor: "rgba(215,155,119,.2)",
    color: "#f3efe5",
  },
  ".cm-scroller": { lineHeight: "1.6", overflow: "auto" },
  // Indentation guides. The library paints these as a background gradient on
  // .cm-indent-markers, so do NOT set `background` here - it erases them.
}, { dark: true });

const readOnlyCompartment = new Compartment();

/**
 * Tab behaviour, resolving the conflict between "accept completion" and
 * "indent".
 *
 * The rule: Tab only accepts a completion when the popup is actually open.
 * Otherwise it indents. Previously both were bound and the completion
 * handler swallowed Tab whenever it thought a completion was available,
 * which made ordinary indenting unreliable.
 */
const tabKeymap = Prec.highest(keymap.of([
  {
    key: "Tab",
    run: (view) => {
      if (completionStatus(view.state) === "active") return acceptCompletion(view);
      return indentMore(view);
    },
    shift: indentLess,
  },
  // Explicit completion trigger, since Tab no longer opens the popup.
  { key: "Ctrl-Space", run: startCompletion },
  { key: "Alt-/", run: startCompletion },
]));

/**
 * Mount a Python editor into `parent`.
 * Returns { getValue, setValue, focus, destroy, view }.
 */
export function createEditor({ parent, doc = "", onChange = null, readOnly = false,
                               minHeight = "340px", maxHeight = "70vh" }) {
  const extensions = [
    lineNumbers(),
    highlightActiveLineGutter(),
    highlightSpecialChars(),
    history(),
    foldGutter(),
    drawSelection(),
    EditorState.allowMultipleSelections.of(true),
    // Re-indent as you type: `if x:` + Enter indents the next line.
    indentOnInput(),
    // Vertical guides showing the indentation block structure.
    indentationMarkers({
      highlightActiveBlock: true,
      hideFirstIndent: false,
      thickness: 1,
      colors: {
        light: "rgba(232,226,214,.14)",
        dark: "rgba(232,226,214,.14)",
        activeLight: "rgba(215,155,119,.5)",
        activeDark: "rgba(215,155,119,.5)",
      },
    }),
    syntaxHighlighting(highlight, { fallback: true }),
    bracketMatching(),
    closeBrackets(),
    autocompletion({ defaultKeymap: false }),
    rectangularSelection(),
    highlightActiveLine(),
    highlightSelectionMatches(),
    // Tab handling wins over everything else.
    tabKeymap,
    keymap.of([
      ...closeBracketsKeymap,
      // completionKeymap minus its Tab binding (tabKeymap owns Tab now).
      ...completionKeymap.filter((b) => b.key !== "Tab"),
      ...defaultKeymap,
      ...searchKeymap,
      ...historyKeymap,
      // Comment toggling: Cmd/Ctrl-' avoids the browser-level Cmd+/ that the
      // course uses for the tutor panel. Both are offered.
      { key: "Mod-'", run: toggleComment },
      { key: "Ctrl-Shift-/", run: toggleComment },
    ]),
    python(),
    indentUnit.of("    "),   // PEP 8
    theme,
    EditorView.lineWrapping,
    EditorView.theme({
      "&": { minHeight, maxHeight },
      ".cm-scroller": { minHeight, maxHeight },
    }),
    readOnlyCompartment.of(EditorState.readOnly.of(readOnly)),
  ];

  if (onChange) {
    extensions.push(
      EditorView.updateListener.of((update) => {
        if (update.docChanged) onChange(update.state.doc.toString());
      })
    );
  }

  const view = new EditorView({
    state: EditorState.create({ doc, extensions }),
    parent,
  });

  return {
    view,
    getValue: () => view.state.doc.toString(),
    setValue: (text) => {
      view.dispatch({
        changes: { from: 0, to: view.state.doc.length, insert: text },
      });
    },
    focus: () => view.focus(),
    destroy: () => view.destroy(),
  };
}
