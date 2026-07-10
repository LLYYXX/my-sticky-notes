import {
  addTodoToNote,
  copy,
  createDefaultNote,
  createId,
  findNote,
  normalizeState,
  sanitizeState,
  toggleNoteCollapsed,
} from "./state.js";
import { renderNotes, renderSettings } from "./views.js";
import { checkGithubRelease } from "./updates.js";

const app = document.querySelector("#app");
const params = new URLSearchParams(window.location.search);
const isSettingsWindow = params.get("settings") === "1";
const previewCollapsed = params.get("collapsed") === "1";
const previewPalette = params.get("palette") === "1";
const APP_VERSION = "v0.3.0-alpha.0";

let state = normalizeState();
let activeSettingsPage = params.get("settingsPage") === "about" ? "about" : "general";
let updateStatus = "";
let updateReleaseUrl = "";
let pointerSession = null;
let pointerEventsBound = false;

function language() {
  return state.settings.language === "en" ? "en" : "zh-CN";
}

function tr(key) {
  return copy[language()][key] ?? copy["zh-CN"][key] ?? key;
}

async function invoke(command, payload) {
  const tauri = window.__TAURI__?.core;
  if (!tauri?.invoke) return null;
  try {
    return await tauri.invoke(command, payload);
  } catch (error) {
    console.warn(`Tauri command failed: ${command}`, error);
    return null;
  }
}

async function load() {
  const remoteState = await invoke("load_state");
  if (remoteState) {
    state = normalizeState(remoteState);
  } else {
    const local = localStorage.getItem("my-sticky-notes-tauri-state");
    state = normalizeState(local ? JSON.parse(local) : {});
  }
  const nativeOpenAtLogin = await invoke("is_open_at_login_enabled");
  if (typeof nativeOpenAtLogin === "boolean") {
    state.settings.openAtLogin = nativeOpenAtLogin;
  }
  render();
}

function persist() {
  state = sanitizeState(state);
  localStorage.setItem("my-sticky-notes-tauri-state", JSON.stringify(state));
  void invoke("save_state", { state });
}

function update(mutator) {
  mutator(state);
  persist();
  render();
}

function render() {
  app.innerHTML = isSettingsWindow
    ? renderSettings(state, {
      activePage: activeSettingsPage,
      language: language(),
      tr,
      updateStatus,
      updateReleaseUrl,
      version: APP_VERSION,
    })
    : renderNotes(state, {
      language: language(),
      tr,
      previewCollapsed,
      previewPalette,
    });
  document.body.classList.toggle("settings-context", isSettingsWindow);
  bind();
  if (!isSettingsWindow) syncNoteWindow();
}

function bind() {
  app.querySelectorAll("[data-settings-page]").forEach((button) => {
    button.addEventListener("click", () => {
      activeSettingsPage = button.dataset.settingsPage;
      render();
    });
  });
  app.querySelectorAll("[data-language]").forEach((button) => {
    button.addEventListener("click", () => update((draft) => {
      draft.settings.language = button.dataset.language;
    }));
  });
  app.querySelectorAll("[data-toggle]").forEach((button) => {
    button.addEventListener("click", () => toggleSetting(button.dataset.toggle));
  });
  app.querySelectorAll("[data-action]").forEach((element) => {
    element.addEventListener("click", handleAction);
  });
  app.querySelectorAll(".add-todo").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const value = String(new FormData(form).get("todo") || "").trim();
      if (value) update((draft) => addTodoToNote(draft, form.dataset.noteId, value));
    });
  });
  app.querySelectorAll("[data-edit-todo]").forEach((span) => {
    span.addEventListener("blur", () => updateTodoText(span));
    span.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        span.blur();
      }
    });
  });
  app.querySelectorAll("[data-drag-note]").forEach((bar) => {
    bar.addEventListener("pointerdown", startDrag);
  });
  app.querySelectorAll("[data-resize-note]").forEach((button) => {
    button.addEventListener("pointerdown", startResize);
  });
  bindPointerEvents();
}

async function toggleSetting(key) {
  if (key !== "openAtLogin") return;
  const requested = !Boolean(state.settings.openAtLogin);
  const applied = await invoke("set_open_at_login", { enabled: requested });
  update((draft) => {
    draft.settings.openAtLogin = typeof applied === "boolean" ? applied : requested;
  });
}

function updateTodoText(span) {
  const nextText = span.textContent.trim();
  update((draft) => {
    const note = findNote(draft, span.dataset.noteId);
    const todo = note.todos.find((item) => item.id === span.dataset.editTodo);
    if (todo) todo.text = nextText;
  });
}

function handleAction(event) {
  const action = event.currentTarget.dataset.action;
  const noteId = event.currentTarget.dataset.noteId;
  if (action === "palette") {
    const note = app.querySelector(`[data-note-id="${noteId}"]`);
    const popover = note?.querySelector(".palette-popover");
    if (popover) popover.hidden = !popover.hidden;
    return;
  }
  if (action === "check-update") {
    void checkForUpdate();
    return;
  }
  update((draft) => {
    if (action === "new-from-note") {
      const source = findNote(draft, noteId);
      draft.notes.push({
        ...createDefaultNote(draft.notes.length, createId),
        x: source.x + 28,
        y: source.y + 28,
      });
    }
    if (action === "collapse-note") toggleNoteCollapsed(draft, noteId);
    if (action === "pin-note") findNote(draft, noteId).pinned = !findNote(draft, noteId).pinned;
    if (action === "delete-note") {
      draft.notes = draft.notes.filter((note) => note.id !== noteId);
      if (draft.notes.length === 0) draft.notes.push(createDefaultNote(0, createId));
    }
    if (action === "set-color") findNote(draft, noteId).color = event.currentTarget.dataset.color;
    if (action === "toggle-todo") {
      const note = findNote(draft, noteId);
      const todo = note.todos.find((item) => item.id === event.currentTarget.dataset.todoId);
      if (todo) todo.completed = !todo.completed;
    }
    if (action === "delete-todo") {
      const note = findNote(draft, noteId);
      note.todos = note.todos.filter((todo) => todo.id !== event.currentTarget.dataset.todoId);
    }
  });
}

async function checkForUpdate() {
  updateStatus = tr("updateChecking");
  updateReleaseUrl = "";
  render();
  try {
    const result = await checkGithubRelease(APP_VERSION);
    if (result.updateAvailable) {
      updateStatus = `${tr("updateAvailable")} v${result.latestVersion}`;
      updateReleaseUrl = result.releaseUrl;
    } else {
      updateStatus = tr("updateCurrent");
    }
  } catch (error) {
    console.warn("GitHub release check failed", error);
    updateStatus = tr("updateFailed");
  }
  render();
}

function startDrag(event) {
  if (event.target.closest("button, input, [contenteditable='true']")) return;
  const note = findNote(state, event.currentTarget.dataset.dragNote);
  pointerSession = {
    kind: "drag",
    id: note.id,
    startX: event.clientX,
    startY: event.clientY,
    noteX: note.x,
    noteY: note.y,
  };
  event.currentTarget.setPointerCapture(event.pointerId);
}

function startResize(event) {
  event.preventDefault();
  event.stopPropagation();
  const note = findNote(state, event.currentTarget.dataset.resizeNote);
  const element = app.querySelector(`[data-note-id="${note.id}"]`);
  const bodyHeight = element?.querySelector(".note-body")?.offsetHeight ?? 164;
  pointerSession = {
    kind: "resize",
    id: note.id,
    startX: event.clientX,
    startY: event.clientY,
    width: note.width,
    bodyHeight,
  };
  event.currentTarget.setPointerCapture(event.pointerId);
}

function movePointer(event) {
  if (!pointerSession) return;
  const note = findNote(state, pointerSession.id);
  const element = app.querySelector(`[data-note-id="${note.id}"]`);
  if (!element) return;
  if (pointerSession.kind === "drag") {
    const maxX = Math.max(8, window.innerWidth - element.offsetWidth - 8);
    const maxY = Math.max(8, window.innerHeight - element.offsetHeight - 8);
    note.x = clamp(pointerSession.noteX + event.clientX - pointerSession.startX, 8, maxX);
    note.y = clamp(pointerSession.noteY + event.clientY - pointerSession.startY, 8, maxY);
    element.style.left = `${note.x}px`;
    element.style.top = `${note.y}px`;
    return;
  }
  note.width = clamp(pointerSession.width + event.clientX - pointerSession.startX, 260, Math.max(260, window.innerWidth - note.x - 8));
  note.bodyHeight = Math.max(128, pointerSession.bodyHeight + event.clientY - pointerSession.startY);
  element.style.width = `${note.width}px`;
  element.style.setProperty("--note-body-height", `${note.bodyHeight}px`);
}

function stopPointer() {
  if (!pointerSession) return;
  pointerSession = null;
  persist();
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function syncNoteWindow() {
  void invoke("set_always_on_top", { pinned: state.notes.some((note) => note.pinned) });
}

function bindPointerEvents() {
  if (pointerEventsBound || isSettingsWindow) return;
  pointerEventsBound = true;
  window.addEventListener("pointermove", movePointer);
  window.addEventListener("pointerup", stopPointer);
}

load();
