import { palette } from "./state.js";

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

function iconPath(note, name) {
  const light = note.color === "navy" ? "-light" : "";
  return `./assets/icons/${name}${light}.png`;
}

function noteIcon(note, name, label) {
  return `<img src="${iconPath(note, name)}" alt="" aria-hidden="true" data-icon="${name}" /><span class="sr-only">${escapeHtml(label)}</span>`;
}

function renderTodo(note, todo, tr) {
  const checkbox = todo.completed ? "checkbox-on" : "checkbox-off";
  return `
    <div class="todo ${todo.completed ? "done" : ""}">
      <button class="todo-check" data-action="toggle-todo" data-note-id="${note.id}" data-todo-id="${todo.id}" aria-pressed="${todo.completed}" title="${escapeHtml(todo.completed ? tr("markOpen") : tr("markDone"))}">
        ${noteIcon(note, checkbox, todo.completed ? tr("markOpen") : tr("markDone"))}
      </button>
      <span contenteditable="true" role="textbox" aria-label="${escapeHtml(tr("todoText"))}" data-edit-todo="${todo.id}" data-note-id="${note.id}">${escapeHtml(todo.text)}</span>
      <button class="todo-delete" data-action="delete-todo" data-note-id="${note.id}" data-todo-id="${todo.id}" title="${escapeHtml(tr("delete"))}">
        ${noteIcon(note, "delete", tr("delete"))}
      </button>
    </div>
  `;
}

export function renderNotes(state, { language, tr, previewCollapsed, previewPalette }) {
  return `
    <main class="notes-workspace" aria-label="${escapeHtml(tr("appName"))}">
      <section class="notes-layer" aria-label="${escapeHtml(tr("notes"))}">
        ${state.notes.map((note, index) => renderNote(note, index, { language, tr, previewCollapsed, previewPalette })).join("")}
      </section>
    </main>
  `;
}

function renderNote(note, index, { language, tr, previewCollapsed, previewPalette }) {
  const theme = palette[note.color];
  const collapsed = Boolean(note.collapsed || (previewCollapsed && index === 0));
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
    note.bodyHeight ? `--note-body-height:${note.bodyHeight}px` : "",
  ].filter(Boolean).join(";");
  const collapseIcon = collapsed ? "add" : "minus";
  const collapseLabel = collapsed ? tr("expand") : tr("collapse");
  return `
    <article class="note ${collapsed ? "collapsed" : ""} ${note.pinned ? "pinned" : ""}" style="${style}" data-note-id="${note.id}">
      <header class="note-bar" data-drag-note="${note.id}">
        <button class="color-dot" data-action="palette" data-note-id="${note.id}" aria-haspopup="true" aria-expanded="${previewPalette && index === 0}" title="${escapeHtml(palette[note.color].name[language])}">
          <span aria-hidden="true"></span><span class="sr-only">${escapeHtml(palette[note.color].name[language])}</span>
        </button>
        <div class="drag-space" aria-hidden="true"></div>
        <button class="note-action" data-action="new-from-note" data-note-id="${note.id}" title="${escapeHtml(tr("newNote"))}">
          ${noteIcon(note, "add", tr("newNote"))}
        </button>
        <button class="note-action" data-action="delete-note" data-note-id="${note.id}" title="${escapeHtml(tr("delete"))}">
          ${noteIcon(note, "delete", tr("delete"))}
        </button>
        <button class="note-action ${note.pinned ? "active" : ""}" data-action="pin-note" data-note-id="${note.id}" aria-pressed="${note.pinned}" title="${escapeHtml(tr(note.pinned ? "unpin" : "pin"))}">
          ${noteIcon(note, "pin", tr(note.pinned ? "unpin" : "pin"))}
        </button>
        <button class="note-action" data-action="collapse-note" data-note-id="${note.id}" title="${escapeHtml(collapseLabel)}">
          ${noteIcon(note, collapseIcon, collapseLabel)}
        </button>
      </header>
      <div class="palette-popover" ${previewPalette && index === 0 ? "" : "hidden"}>
        ${Object.keys(palette).map((key) => `
          <button data-action="set-color" data-note-id="${note.id}" data-color="${key}" class="${key === note.color ? "active" : ""}" aria-pressed="${key === note.color}">
            <span style="background:${palette[key].background}"></span>${escapeHtml(palette[key].name[language])}
          </button>
        `).join("")}
      </div>
      <section class="note-body">
        <div class="todos">
          ${note.todos.map((todo) => renderTodo(note, todo, tr)).join("")}
        </div>
        <form class="add-todo" data-note-id="${note.id}">
          <input name="todo" placeholder="${escapeHtml(tr("addTodo"))}" aria-label="${escapeHtml(tr("addTodo"))}" autocomplete="off" />
        </form>
      </section>
      <button class="note-resize" data-resize-note="${note.id}" title="${escapeHtml(tr("resize"))}">
        ${noteIcon(note, "resize-corner", tr("resize"))}
      </button>
    </article>
  `;
}

export function renderSettings(state, { activePage, language, tr, updateStatus, updateInFlight, version }) {
  const status = updateStatus || tr("updateIdle");
  return `
    <main class="settings-window" aria-label="${escapeHtml(tr("settings"))}">
      <header class="settings-nav">
        <div class="settings-brand">
          <img class="brand-mark" src="./assets/app-icon.png" alt="" aria-hidden="true" />
          <span>${escapeHtml(tr("appName"))}</span>
        </div>
        <nav class="settings-tabs" aria-label="${escapeHtml(tr("settings"))}">
          ${settingsTab("general", tr("general"), activePage)}
          ${settingsTab("about", tr("about"), activePage)}
        </nav>
      </header>
      <section class="settings-content">
        ${activePage === "about"
          ? renderAbout({ tr, status, updateInFlight, version })
          : renderGeneral(state, { language, tr })}
      </section>
    </main>
  `;
}

function settingsTab(page, label, activePage) {
  return `<button class="settings-tab ${activePage === page ? "active" : ""}" data-settings-page="${page}" aria-current="${activePage === page ? "page" : "false"}">${escapeHtml(label)}</button>`;
}

function renderGeneral(state, { language, tr }) {
  const enabled = Boolean(state.settings.openAtLogin);
  return `
    <section class="settings-panel">
      <h1>${escapeHtml(tr("general"))}</h1>
      <div class="settings-row">
        <div>
          <strong>${escapeHtml(tr("startAtLogin"))}</strong>
          <p>${escapeHtml(tr("startAtLoginHint"))}</p>
        </div>
        <button class="switch ${enabled ? "on" : ""}" data-toggle="openAtLogin" aria-pressed="${enabled}"><span></span></button>
      </div>
      <div class="settings-row">
        <div>
          <strong>${escapeHtml(tr("language"))}</strong>
          <p>${escapeHtml(tr("languageHint"))}</p>
        </div>
        <div class="segmented" role="group" aria-label="${escapeHtml(tr("language"))}">
          <button class="${language === "zh-CN" ? "active" : ""}" data-language="zh-CN">中文</button>
          <button class="${language === "en" ? "active" : ""}" data-language="en">English</button>
        </div>
      </div>
    </section>
  `;
}

function renderAbout({ tr, status, updateInFlight, version }) {
  return `
    <section class="settings-panel">
      <h1>${escapeHtml(tr("about"))}</h1>
      <div class="settings-row about-version">
        <div>
          <strong>${escapeHtml(tr("version"))}</strong>
          <p>${escapeHtml(version)}</p>
        </div>
      </div>
      <div class="settings-row update-row">
        <div>
          <strong>${escapeHtml(tr("update"))}</strong>
          <p data-update-status>${escapeHtml(status)}</p>
        </div>
        <button class="primary" data-action="check-update" ${updateInFlight ? "disabled" : ""}>${escapeHtml(tr("checkNow"))}</button>
      </div>
      <p class="source-link"><a href="https://github.com/LLYYXX/my-sticky-notes" target="_blank" rel="noreferrer">github.com/LLYYXX/my-sticky-notes</a></p>
    </section>
  `;
}
