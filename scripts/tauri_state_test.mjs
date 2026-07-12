import assert from "assert";
import {
  addTodoToNote,
  createDefaultNote,
  normalizeState,
  palette,
  sanitizeState,
  toggleNoteCollapsed,
} from "../src/state.js";

let sequence = 0;
const ids = (prefix) => `${prefix}-${++sequence}`;

{
  const state = normalizeState({}, ids);
  assert.equal(state.version, 9);
  assert.equal(state.settings.language, "zh-CN");
  assert.equal(state.notes.length, 1);
  assert.equal(state.notes[0].color, "yellow");
  assert.equal(state.notes[0].collapsed, false);
  assert.deepEqual(state.notes[0].todos, []);
}

{
  const note = createDefaultNote(0, ids);
  assert.equal(note.x, null);
  assert.equal(note.y, null);
  assert.deepEqual(note.todos, []);
  const normalized = normalizeState({ notes: [{ id: "n", x: null, todos: [] }] }, ids);
  assert.equal(normalized.notes[0].x, null);
}

{
  const normalized = normalizeState({
    notes: [{ id: "legacy-offscreen", x: 2109, y: -9, width: 446, height: 584, todos: [] }],
  }, ids);
  assert.equal(normalized.notes[0].x, 2109);
  assert.equal(normalized.notes[0].y, -9);
}

{
  const state = normalizeState({
    settings: { open_at_login: true, language: "en" },
    notes: [{ id: "old", color: "missing", width: 10, height: 10, todos: [] }],
  }, ids);
  assert.equal(state.settings.openAtLogin, true);
  assert.equal(state.settings.language, "en");
  assert.equal(state.notes[0].color, "yellow");
  assert.equal(state.notes[0].width, 280);
  assert.equal(state.notes[0].bodyHeight, null);
}

{
  const state = normalizeState({ notes: [createDefaultNote(0, ids)] }, ids);
  const noteId = state.notes[0].id;
  assert.equal(toggleNoteCollapsed(state, noteId), true);
  assert.equal(sanitizeState(state, ids).notes[0].collapsed, true);
  assert.equal(toggleNoteCollapsed(state, noteId), false);
}

{
  const state = normalizeState({ notes: [{ id: "n", todos: [] }] }, ids);
  assert.equal(addTodoToNote(state, "n", "  long todo wraps at the edge  ", ids).text, "long todo wraps at the edge");
  assert.equal(addTodoToNote(state, "n", "   ", ids), null);
  assert.equal(sanitizeState(state, ids).notes[0].todos.length, 1);
}

assert.deepEqual(Object.keys(palette), [
  "yellow",
  "offwhite",
  "lime",
  "lilac",
  "cream",
  "pink",
  "mint",
  "coral",
  "navy",
]);

console.log(JSON.stringify({ result: "passed", tests: 7 }));
