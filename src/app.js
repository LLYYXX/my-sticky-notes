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
import { renderNoteWindow, renderSettings } from "./views.js";
import { checkGithubRelease } from "./updates.js";

const app = document.querySelector("#app");
const params = new URLSearchParams(window.location.search);
const noteId = params.get("note");
const isSettingsWindow = params.get("settings") === "1";
const APP_VERSION = "v0.3.1";

let state = normalizeState();
let activeSettingsPage = params.get("settingsPage") === "about" ? "about" : "general";
let updateStatus = "";
let updateInFlight = false;
let paletteOpen = false;
let resizeSession = null;
let resizeFrame = null;

function language() {
  return state.settings.language === "en" ? "en" : "zh-CN";
}

function tr(key) {
  return copy[language()][key] ?? copy["zh-CN"][key] ?? key;
}

function currentNote() {
  return noteId ? state.notes.find((note) => note.id === noteId) ?? null : null;
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

function applySnapshot(snapshot) {
  if (snapshot?.notes && snapshot?.settings) {
    state = normalizeState(snapshot);
  }
}

async function load() {
  const remoteState = await invoke("load_state");
  if (remoteState) {
    applySnapshot(remoteState);
  } else {
    const local = localStorage.getItem("my-sticky-notes-tauri-state");
    state = normalizeState(local ? JSON.parse(local) : {});
  }
  const nativeOpenAtLogin = await invoke("is_open_at_login_enabled");
  if (typeof nativeOpenAtLogin === "boolean") state.settings.openAtLogin = nativeOpenAtLogin;
  render();
}

function saveFallback() {
  localStorage.setItem("my-sticky-notes-tauri-state", JSON.stringify(sanitizeState(state)));
}

async function saveCurrentNote() {
  const note = currentNote();
  if (!note) return;
  saveFallback();
  const snapshot = await invoke("save_note", { note });
  applySnapshot(snapshot);
}

async function updateCurrentNote(mutator) {
  const note = currentNote();
  if (!note) return;
  mutator(note, state);
  await saveCurrentNote();
  render();
}

async function updateSettings(mutator) {
  mutator(state.settings);
  saveFallback();
  const snapshot = await invoke("save_settings", { settings: state.settings });
  applySnapshot(snapshot);
  render();
}

function render() {
  const note = currentNote();
  app.innerHTML = isSettingsWindow
    ? renderSettings(state, {
      activePage: activeSettingsPage,
      language: language(),
      tr,
      updateStatus,
      updateInFlight,
      version: APP_VERSION,
    })
    : note
      ? renderNoteWindow(note, { language: language(), tr, paletteOpen })
      : "";
  document.body.classList.toggle("settings-context", isSettingsWindow);
  document.body.classList.toggle("note-context", Boolean(note) && !isSettingsWindow);
  bind();
  if (note && !isSettingsWindow) queueFitNoteWindow();
}

function bind() {
  app.querySelectorAll("[data-settings-page]").forEach((button) => {
    button.addEventListener("click", () => {
      activeSettingsPage = button.dataset.settingsPage;
      render();
    });
  });
  app.querySelectorAll("[data-language]").forEach((button) => {
    button.addEventListener("click", () => {
      void updateSettings((settings) => {
        settings.language = button.dataset.language;
      });
    });
  });
  app.querySelectorAll("[data-toggle]").forEach((button) => {
    button.addEventListener("click", () => void toggleSetting(button.dataset.toggle));
  });
  app.querySelectorAll("[data-action]").forEach((element) => {
    element.addEventListener("click", handleAction);
  });
  app.querySelectorAll(".add-todo").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const value = String(new FormData(form).get("todo") || "").trim();
      if (value) {
        void updateCurrentNote((note) => addTodoToNote({ notes: [note] }, note.id, value));
      }
    });
  });
  app.querySelectorAll("[data-edit-todo]").forEach((span) => {
    span.addEventListener("blur", () => void updateTodoText(span));
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
  window.onpointermove = moveResize;
  window.onpointerup = stopResize;
}

async function toggleSetting(key) {
  if (key !== "openAtLogin") return;
  const requested = !Boolean(state.settings.openAtLogin);
  const applied = await invoke("set_open_at_login", { enabled: requested });
  state.settings.openAtLogin = typeof applied === "boolean" ? applied : requested;
  saveFallback();
  render();
}

async function updateTodoText(span) {
  const nextText = span.textContent.trim();
  await updateCurrentNote((note) => {
    const todo = note.todos.find((item) => item.id === span.dataset.editTodo);
    if (todo) todo.text = nextText;
  });
}

async function handleAction(event) {
  const action = event.currentTarget.dataset.action;
  if (action === "palette") {
    paletteOpen = !paletteOpen;
    render();
    return;
  }
  if (action === "check-update") {
    void checkForUpdate();
    return;
  }
  if (action === "new-from-note") {
    const source = currentNote();
    if (!source) return;
    const note = createDefaultNote(state.notes.length, createId);
    note.x = Number.isFinite(source.x) ? source.x + 28 : null;
    note.y = Number.isFinite(source.y) ? source.y + 32 : null;
    const snapshot = await invoke("create_note", { note });
    applySnapshot(snapshot);
    return;
  }
  if (action === "delete-note") {
    const snapshot = await invoke("delete_note", { noteId });
    applySnapshot(snapshot);
    return;
  }
  await updateCurrentNote((note) => {
    if (action === "collapse-note") toggleNoteCollapsed({ notes: [note] }, note.id);
    if (action === "pin-note") note.pinned = !note.pinned;
    if (action === "set-color") {
      note.color = event.currentTarget.dataset.color;
      paletteOpen = false;
    }
    if (action === "toggle-todo") {
      const todo = note.todos.find((item) => item.id === event.currentTarget.dataset.todoId);
      if (todo) todo.completed = !todo.completed;
    }
    if (action === "delete-todo") {
      note.todos = note.todos.filter((todo) => todo.id !== event.currentTarget.dataset.todoId);
    }
  });
}

async function checkForUpdate() {
  if (updateInFlight) return;
  updateInFlight = true;
  updateStatus = tr("updateChecking");
  render();
  try {
    const result = await checkGithubRelease(APP_VERSION);
    if (result.updateAvailable) {
      updateStatus = `${tr("updateDownloading")} v${result.latestVersion}`;
      render();
      const started = await invoke("download_and_install_update", {
        request: { tag: result.releaseTag, assetNames: result.assetNames },
      });
      updateStatus = started === true ? tr("updateInstalling") : tr("updateInstallFailed");
    } else {
      updateStatus = tr("updateCurrent");
    }
  } catch (error) {
    console.warn("GitHub release check failed", error);
    updateStatus = tr("updateFailed");
  } finally {
    updateInFlight = false;
    render();
  }
}

function startDrag(event) {
  if (event.target.closest("button, input, [contenteditable='true']")) return;
  void invoke("start_note_dragging");
}

function startResize(event) {
  event.preventDefault();
  event.stopPropagation();
  const note = currentNote();
  const element = app.querySelector("[data-note-id]");
  if (!note || !element) return;
  resizeSession = {
    startX: event.clientX,
    startY: event.clientY,
    width: note.width,
    bodyHeight: note.bodyHeight ?? element.querySelector(".note-body")?.offsetHeight ?? 164,
  };
  event.currentTarget.setPointerCapture(event.pointerId);
}

function moveResize(event) {
  if (!resizeSession) return;
  const note = currentNote();
  const element = app.querySelector("[data-note-id]");
  if (!note || !element) return;
  note.width = clamp(resizeSession.width + event.clientX - resizeSession.startX, 280, 720);
  note.bodyHeight = Math.max(128, resizeSession.bodyHeight + event.clientY - resizeSession.startY);
  element.style.setProperty("--note-body-height", `${note.bodyHeight}px`);
  queueResizePreview();
}

function queueResizePreview() {
  if (resizeFrame !== null) return;
  resizeFrame = requestAnimationFrame(() => {
    resizeFrame = null;
    const note = currentNote();
    if (note) {
      void invoke("resize_note_preview", {
        noteId: note.id,
        width: note.width,
        bodyHeight: note.bodyHeight,
      });
    }
  });
}

function stopResize() {
  if (!resizeSession) return;
  resizeSession = null;
  void saveCurrentNote();
}

function queueFitNoteWindow() {
  requestAnimationFrame(() => {
    const note = currentNote();
    const element = app.querySelector("[data-note-id]");
    if (note && element) {
      void invoke("fit_note_window", {
        noteId: note.id,
        height: Math.ceil(element.getBoundingClientRect().height),
      });
    }
  });
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

load();
