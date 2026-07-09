import {
  addTodoToNote,
  copy,
  createDefaultNote,
  createId,
  findNote,
  normalizeState,
  palette,
  sanitizeState,
  toggleNoteCollapsed,
} from "./state.js";

const app = document.querySelector("#app");
let state = normalizeState();
const initialParams = new URLSearchParams(window.location.search);
let activeSettingsPage = initialParams.get("settingsPage") === "about" ? "about" : "general";
let settingsOpen = initialParams.get("settings") === "1";
const previewCollapsed = initialParams.get("collapsed") === "1";
const previewPalette = initialParams.get("palette") === "1";
let dragging = null;
let tauriEventsBound = false;
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
  if (previewCollapsed && state.notes[0]) {
    state.notes[0].collapsed = true;
  }
  render();
}

function persist() {
  state = sanitizeState(state);
  localStorage.setItem("my-sticky-notes-tauri-state", JSON.stringify(state));
  invoke("save_state", { state });
}

function update(mutator) {
  mutator(state);
  persist();
  render();
}

function render() {
  app.innerHTML = `
    <main class="workspace">
      <div class="top-rail">
        <button class="rail-button" data-action="open-settings">${tr("settings")}</button>
        <button class="rail-button primary-rail" data-action="new-note">${tr("newNote")}</button>
      </div>
      ${settingsOpen ? renderSettingsShell() : ""}
      <section class="notes-layer" aria-label="${tr("appName")}">
        ${state.notes.map((note, index) => renderNote(note, index)).join("")}
      </section>
    </main>
  `;
  bind();
  syncWindowChrome();
}

function renderSettingsShell() {
  return `
    <section class="settings-shell" aria-label="${tr("settings")}">
      <header class="settings-topbar">
        <div>
          <span class="eyebrow">SETTINGS</span>
          <h1>${tr("appName")}</h1>
        </div>
        <nav class="settings-tabs">
          ${settingsTab("general", tr("general"))}
          ${settingsTab("about", tr("about"))}
          <button class="tab close-tab" data-action="close-settings">${tr("close")}</button>
        </nav>
      </header>
      <div class="settings-page">${renderSettingsPage()}</div>
    </section>
  `;
}

function settingsTab(page, label) {
  return `
    <button class="tab ${activeSettingsPage === page ? "active" : ""}" data-settings-page="${page}">
      ${label}
    </button>
  `;
}

function renderSettingsPage() {
  if (activeSettingsPage === "about") {
    return `
      <div class="settings-card warm">
        <h2>${tr("about")}</h2>
        <p>${tr("version")}: <strong>v0.3.0-alpha.0</strong></p>
        <p>${tr("source")}: <a href="https://github.com/LLYYXX/my-sticky-notes">github.com/LLYYXX/my-sticky-notes</a></p>
        <button class="primary" data-action="check-update">${tr("update")}</button>
      </div>
    `;
  }
  return `
    <div class="settings-card fresh">
      <h2>${tr("general")}</h2>
      ${toggleRow("openAtLogin", tr("startAtLogin"), tr("startAtLoginHint"))}
      <div class="row">
        <div>
          <strong>${tr("language")}</strong>
          <p>中文 / English</p>
        </div>
        <div class="segmented">
          <button class="${language() === "zh-CN" ? "active" : ""}" data-language="zh-CN">中文</button>
          <button class="${language() === "en" ? "active" : ""}" data-language="en">English</button>
        </div>
      </div>
      <div class="row no-control">
        <div>
          <strong>${tr("stayLightweight")}</strong>
          <p>${tr("stayLightweightHint")}</p>
        </div>
      </div>
    </div>
  `;
}

function toggleRow(key, title, hint) {
  const value = Boolean(state.settings[key]);
  return `
    <div class="row">
      <div>
        <strong>${title}</strong>
        <p>${hint}</p>
      </div>
      <button class="switch ${value ? "on" : ""}" data-toggle="${key}" aria-pressed="${value}">
        <span></span>
      </button>
    </div>
  `;
}

function renderNote(note, index) {
  const theme = palette[note.color];
  const style = [
    `--note-bg:${theme.background}`,
    `--note-header:${theme.header}`,
    `--note-input:${theme.input}`,
    `--note-border:${theme.border}`,
    `--note-text:${theme.text}`,
    `--note-muted:${theme.muted}`,
    `left:${note.x}px`,
    `top:${note.y}px`,
    `width:${note.width}px`,
    `min-height:${note.collapsed ? 44 : note.height}px`,
  ].join(";");
  return `
    <article class="note ${note.collapsed ? "collapsed" : ""} ${note.pinned ? "pinned" : ""}" style="${style}" data-note-id="${note.id}">
      <header class="note-bar" data-drag-note="${note.id}">
        <button class="color-dot" data-action="palette" data-note-id="${note.id}" title="${palette[note.color].name[language()]}">
          <span></span>
        </button>
        <div class="drag-space"></div>
        <button data-action="new-from-note" data-note-id="${note.id}" title="${tr("newNote")}">＋</button>
        <button data-action="collapse-note" data-note-id="${note.id}" title="${note.collapsed ? tr("expand") : tr("collapse")}">${note.collapsed ? "⌄" : "−"}</button>
        <button data-action="pin-note" data-note-id="${note.id}" class="${note.pinned ? "active" : ""}" title="${tr("pin")}">⌾</button>
        <button data-action="delete-note" data-note-id="${note.id}" title="${tr("delete")}">×</button>
      </header>
      <div class="palette-popover" ${previewPalette && index === 0 ? "" : "hidden"}>
        ${Object.keys(palette).map((key) => `
          <button data-action="set-color" data-note-id="${note.id}" data-color="${key}" class="${key === note.color ? "active" : ""}">
            <span style="background:${palette[key].background}"></span>${palette[key].name[language()]}
          </button>
        `).join("")}
      </div>
      <section class="note-body">
        <div class="todos">
          ${note.todos.length === 0 ? `<p class="empty">${tr("empty")}</p>` : ""}
          ${note.todos.map((todo) => renderTodo(note, todo)).join("")}
        </div>
        <form class="add-todo" data-note-id="${note.id}">
          <input name="todo" placeholder="${tr("addTodo")}" autocomplete="off" />
        </form>
      </section>
    </article>
  `;
}

function renderTodo(note, todo) {
  return `
    <label class="todo ${todo.completed ? "done" : ""}">
      <input type="checkbox" data-action="toggle-todo" data-note-id="${note.id}" data-todo-id="${todo.id}" ${todo.completed ? "checked" : ""} />
      <span contenteditable="true" data-edit-todo="${todo.id}" data-note-id="${note.id}">${escapeHtml(todo.text)}</span>
      <button data-action="delete-todo" data-note-id="${note.id}" data-todo-id="${todo.id}" title="${tr("delete")}">×</button>
    </label>
  `;
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
    button.addEventListener("click", async () => {
      const key = button.dataset.toggle;
      if (key === "openAtLogin") {
        const requested = !Boolean(state.settings.openAtLogin);
        const applied = await invoke("set_open_at_login", { enabled: requested });
        update((draft) => {
          draft.settings.openAtLogin = typeof applied === "boolean" ? applied : requested;
        });
        return;
      }
      update((draft) => {
        draft.settings[key] = !draft.settings[key];
      });
    });
  });
  app.querySelectorAll("[data-action]").forEach((element) => {
    element.addEventListener("click", handleAction);
  });
  app.querySelectorAll(".add-todo").forEach((form) => {
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const value = String(new FormData(form).get("todo") || "").trim();
      if (!value) return;
      update((draft) => addTodoToNote(draft, form.dataset.noteId, value));
    });
  });
  app.querySelectorAll("[data-edit-todo]").forEach((span) => {
    span.addEventListener("blur", () => update((draft) => {
      const note = findNote(draft, span.dataset.noteId);
      const todo = note.todos.find((item) => item.id === span.dataset.editTodo);
      if (todo) todo.text = span.textContent.trim();
    }));
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
  bindPointerEvents();
}

function handleAction(event) {
  const action = event.currentTarget.dataset.action;
  const noteId = event.currentTarget.dataset.noteId;
  if (action === "open-settings") {
    setSettingsOpen(true);
    return;
  }
  if (action === "close-settings") {
    setSettingsOpen(false);
    return;
  }
  if (action === "palette") {
    const note = app.querySelector(`[data-note-id="${noteId}"]`);
    note.querySelector(".palette-popover").hidden = !note.querySelector(".palette-popover").hidden;
    return;
  }
  if (action === "check-update") {
    alert("更新检查会在 Tauri 主进程接入 GitHub Releases 后启用。");
    return;
  }
  update((draft) => {
    if (action === "new-note") draft.notes.push(createDefaultNote(draft.notes.length, createId));
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
      if (todo) todo.completed = event.currentTarget.checked;
    }
    if (action === "delete-todo") {
      const note = findNote(draft, noteId);
      note.todos = note.todos.filter((todo) => todo.id !== event.currentTarget.dataset.todoId);
    }
  });
}

function startDrag(event) {
  if (event.target.closest("button")) return;
  const note = findNote(state, event.currentTarget.dataset.dragNote);
  dragging = {
    id: note.id,
    startX: event.clientX,
    startY: event.clientY,
    noteX: note.x,
    noteY: note.y,
  };
  event.currentTarget.setPointerCapture(event.pointerId);
}

function moveDrag(event) {
  if (!dragging) return;
  const note = findNote(state, dragging.id);
  note.x = Math.max(8, dragging.noteX + event.clientX - dragging.startX);
  note.y = Math.max(8, dragging.noteY + event.clientY - dragging.startY);
  const element = app.querySelector(`[data-note-id="${note.id}"]`);
  if (element) {
    element.style.left = `${note.x}px`;
    element.style.top = `${note.y}px`;
  }
}

function stopDrag() {
  if (!dragging) return;
  dragging = null;
  persist();
}

function setSettingsOpen(open) {
  settingsOpen = open;
  render();
}

function syncWindowChrome() {
  invoke("set_settings_visibility", { visible: settingsOpen });
  invoke("set_always_on_top", {
    pinned: state.notes.some((note) => note.pinned),
  });
}

async function bindTauriEvents() {
  if (tauriEventsBound) return;
  const listen = window.__TAURI__?.event?.listen;
  if (!listen) return;
  tauriEventsBound = true;
  await listen("open-settings", () => setSettingsOpen(true));
  await listen("show-notes", () => setSettingsOpen(false));
}

function bindPointerEvents() {
  if (pointerEventsBound) return;
  pointerEventsBound = true;
  window.addEventListener("pointermove", moveDrag);
  window.addEventListener("pointerup", stopDrag);
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#039;",
  }[char]));
}

bindTauriEvents();
load();
