export const STATE_VERSION = 8;

export const palette = {
  yellow: {
    name: { "zh-CN": "淡黄", en: "Yellow" },
    background: "#fff1a8",
    header: "#fff0a0",
    input: "#fff7c8",
    border: "#d9c45c",
    text: "#111111",
    muted: "#8f875f",
  },
  offwhite: {
    name: { "zh-CN": "黯白", en: "Off white" },
    background: "#f0f0ec",
    header: "#f2f2ee",
    input: "#f8f8f5",
    border: "#c9c9c2",
    text: "#111111",
    muted: "#898982",
  },
  lime: {
    name: { "zh-CN": "青柠", en: "Lime" },
    background: "#dceeb1",
    header: "#d7e9aa",
    input: "#edf7d5",
    border: "#b3ca77",
    text: "#111111",
    muted: "#738057",
  },
  lilac: {
    name: { "zh-CN": "丁香", en: "Lilac" },
    background: "#c5b0f4",
    header: "#bea8ee",
    input: "#dfd4fb",
    border: "#9f83dd",
    text: "#111111",
    muted: "#74648f",
  },
  cream: {
    name: { "zh-CN": "奶油", en: "Cream" },
    background: "#f4ecd6",
    header: "#f0e6cc",
    input: "#fbf6ea",
    border: "#d3c398",
    text: "#111111",
    muted: "#8d8169",
  },
  pink: {
    name: { "zh-CN": "淡粉", en: "Pink" },
    background: "#efd4d4",
    header: "#ebcaca",
    input: "#fae8e8",
    border: "#d4a7a7",
    text: "#111111",
    muted: "#947171",
  },
  mint: {
    name: { "zh-CN": "薄荷", en: "Mint" },
    background: "#c8e6cd",
    header: "#c1dfc6",
    input: "#e0f2e3",
    border: "#9ac7a2",
    text: "#111111",
    muted: "#667e6b",
  },
  coral: {
    name: { "zh-CN": "珊瑚", en: "Coral" },
    background: "#f3c9b6",
    header: "#efc1ad",
    input: "#fae0d3",
    border: "#d69d82",
    text: "#111111",
    muted: "#926b5b",
  },
  navy: {
    name: { "zh-CN": "深蓝", en: "Navy" },
    background: "#1f1d3d",
    header: "#29264b",
    input: "#302d53",
    border: "#514c78",
    text: "#ffffff",
    muted: "#a6a1c4",
  },
};

export const copy = {
  "zh-CN": {
    appName: "桌面便利贴",
    settings: "设置",
    close: "关闭",
    newNote: "新建便签",
    general: "常规",
    about: "关于",
    language: "语言",
    startAtLogin: "登录后自动启动",
    startAtLoginHint: "随系统启动，保持便签无感常驻。",
    stayLightweight: "轻量约束",
    stayLightweightHint: "单窗口承载多张便签，设置页按需显示，避免多渲染进程常驻。",
    version: "当前版本",
    source: "开源地址",
    update: "检查更新",
    checkNow: "立即检查",
    updateChecking: "正在检查 GitHub Releases…",
    updateIdle: "尚未检查更新。",
    updateCurrent: "已是最新版本。",
    updateAvailable: "发现新版本。",
    updateDownloading: "发现新版本，正在下载并准备安装：",
    updateInstalling: "更新已下载，正在启动安装程序…",
    updateInstallFailed: "下载或启动安装程序失败，请稍后重试。",
    updateFailed: "暂时无法检查更新，请稍后重试。",
    addTodo: "添加待办",
    notes: "便签",
    todoText: "待办内容",
    markDone: "标记完成",
    markOpen: "标记未完成",
    collapse: "收起",
    expand: "展开",
    pin: "置顶",
    unpin: "取消置顶",
    delete: "删除",
    resize: "调整便签大小",
    languageHint: "选择界面显示语言。",
  },
  en: {
    appName: "My Sticky Notes",
    settings: "Settings",
    close: "Close",
    newNote: "New note",
    general: "General",
    about: "About",
    language: "Language",
    startAtLogin: "Start at login",
    startAtLoginHint: "Launch with the system and keep notes lightweight.",
    stayLightweight: "Lightweight budget",
    stayLightweightHint: "One renderer owns all notes; Settings opens only when needed.",
    version: "Current version",
    source: "Open source",
    update: "Check update",
    checkNow: "Check now",
    updateChecking: "Checking GitHub Releases…",
    updateIdle: "No update check yet.",
    updateCurrent: "You are up to date.",
    updateAvailable: "An update is available.",
    updateDownloading: "An update is available. Downloading and preparing installation:",
    updateInstalling: "Update downloaded. Starting the installer…",
    updateInstallFailed: "Unable to download or start the update installer.",
    updateFailed: "Unable to check for updates right now.",
    addTodo: "Add todo",
    notes: "Notes",
    todoText: "Todo text",
    markDone: "Mark complete",
    markOpen: "Mark incomplete",
    collapse: "Collapse",
    expand: "Expand",
    pin: "Pin",
    unpin: "Unpin",
    delete: "Delete",
    resize: "Resize note",
    languageHint: "Choose the interface language.",
  },
};

export function createId(prefix) {
  if (globalThis.crypto?.randomUUID) {
    return `${prefix}-${globalThis.crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now().toString(36)}-${Math.random()
    .toString(36)
    .slice(2)}`;
}

export function createDefaultTodo(index = 0, idFactory = createId) {
  const samples = [
    { text: "完成项目草稿", completed: false },
    { text: "晨跑 30 分钟", completed: true },
  ];
  const sample = samples[index] ?? { text: "", completed: false };
  return {
    id: idFactory("todo"),
    text: sample.text,
    completed: sample.completed,
    order: index,
  };
}

export function createDefaultNote(index = 0, idFactory = createId) {
  return {
    id: idFactory("note"),
    color: "yellow",
    pinned: false,
    collapsed: false,
    x: defaultNoteX(index),
    y: 38 + index * 32,
    width: 340,
    bodyHeight: null,
    todos: [createDefaultTodo(0, idFactory), createDefaultTodo(1, idFactory)],
  };
}

export function normalizeState(raw = {}, idFactory = createId) {
  const notes = Array.isArray(raw.notes) && raw.notes.length > 0
    ? raw.notes
    : [createDefaultNote(0, idFactory)];
  return {
    version: STATE_VERSION,
    settings: {
      openAtLogin: Boolean(raw.settings?.openAtLogin ?? raw.settings?.open_at_login),
      language: raw.settings?.language === "en" ? "en" : "zh-CN",
    },
    notes: notes.map((note, index) => normalizeNote(note, index, idFactory)),
  };
}

export function normalizeNote(note = {}, index = 0, idFactory = createId) {
  const color = palette[note.color] ? note.color : "yellow";
  const width = Math.max(280, numberOr(note.width, 340));
  const bodyHeight = Number.isFinite(note.bodyHeight)
    ? Math.max(128, Math.round(note.bodyHeight))
    : null;
  return {
    id: String(note.id || idFactory("note")),
    color,
    pinned: Boolean(note.pinned),
    collapsed: Boolean(note.collapsed),
    x: clampToViewportX(numberOr(note.x, defaultNoteX(index, width)), width),
    y: clampToViewportY(numberOr(note.y, 38 + index * 32), estimatedNoteHeight(bodyHeight)),
    width,
    bodyHeight,
    todos: Array.isArray(note.todos)
      ? note.todos
          .map((todo, todoIndex) => normalizeTodo(todo, todoIndex, idFactory))
          .filter((todo) => todo.text)
          .sort((a, b) => a.order - b.order)
          .map((todo, todoIndex) => ({ ...todo, order: todoIndex }))
      : [],
  };
}

export function normalizeTodo(todo = {}, order = 0, idFactory = createId) {
  return {
    id: String(todo.id || idFactory("todo")),
    text: String(todo.text || "").trim(),
    completed: Boolean(todo.completed),
    order: Number.isFinite(todo.order) ? todo.order : order,
  };
}

export function sanitizeState(state, idFactory = createId) {
  return normalizeState(state, idFactory);
}

export function toggleNoteCollapsed(state, noteId) {
  const note = findNote(state, noteId);
  note.collapsed = !note.collapsed;
  return note.collapsed;
}

export function addTodoToNote(state, noteId, text, idFactory = createId) {
  const cleanText = String(text || "").trim();
  if (!cleanText) return null;
  const note = findNote(state, noteId);
  const todo = {
    id: idFactory("todo"),
    text: cleanText,
    completed: false,
    order: note.todos.length,
  };
  note.todos.push(todo);
  return todo;
}

export function findNote(state, noteId) {
  return state.notes.find((note) => note.id === noteId) ?? state.notes[0];
}

function numberOr(value, fallback) {
  return Number.isFinite(value) ? value : fallback;
}

function defaultNoteX(index, width = 340) {
  const viewportWidth = Number.isFinite(globalThis.innerWidth) ? globalThis.innerWidth : 1120;
  return Math.max(24, viewportWidth - width - 20 - index * 28);
}

function clampToViewportX(value, width) {
  const viewportWidth = Number.isFinite(globalThis.innerWidth) ? globalThis.innerWidth : 1120;
  const maxX = Math.max(8, viewportWidth - width - 8);
  return clamp(value, 8, maxX);
}

function clampToViewportY(value, height) {
  const viewportHeight = Number.isFinite(globalThis.innerHeight) ? globalThis.innerHeight : 760;
  const visibleHeight = Math.min(height, 460);
  const maxY = Math.max(8, viewportHeight - visibleHeight - 8);
  return clamp(value, 8, maxY);
}

function estimatedNoteHeight(bodyHeight) {
  return 44 + (bodyHeight ?? 164) + 18;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}
