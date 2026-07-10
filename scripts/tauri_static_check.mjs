import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const requiredFiles = [
  "package.json",
  "pnpm-lock.yaml",
  "src-tauri/Cargo.lock",
  "src/index.html",
  "src/app.js",
  "src/state.js",
  "src/styles.css",
  "scripts/tauri_runtime_probe.py",
  "src-tauri/Cargo.toml",
  "src-tauri/tauri.conf.json",
  "src-tauri/capabilities/default.json",
  "src-tauri/icons/32x32.png",
  "src-tauri/icons/128x128.png",
  "src-tauri/icons/128x128@2x.png",
  "src-tauri/icons/icon.icns",
  "src-tauri/icons/icon.ico",
  "src-tauri/src/main.rs",
];

for (const relative of requiredFiles) {
  const absolute = path.join(root, relative);
  if (!fs.existsSync(absolute)) {
    throw new Error(`Missing ${relative}`);
  }
}

const app = fs.readFileSync(path.join(root, "src/app.js"), "utf8");
const state = fs.readFileSync(path.join(root, "src/state.js"), "utf8");
const styles = fs.readFileSync(path.join(root, "src/styles.css"), "utf8");
const rust = fs.readFileSync(path.join(root, "src-tauri/src/main.rs"), "utf8");
const cargoToml = fs.readFileSync(path.join(root, "src-tauri/Cargo.toml"), "utf8");
const capabilities = JSON.parse(
  fs.readFileSync(path.join(root, "src-tauri/capabilities/default.json"), "utf8"),
);
const config = JSON.parse(
  fs.readFileSync(path.join(root, "src-tauri/tauri.conf.json"), "utf8"),
);
const ci = fs.existsSync(path.join(root, ".github/workflows/ci.yml"))
  ? fs.readFileSync(path.join(root, ".github/workflows/ci.yml"), "utf8")
  : "";
const tauriBuild = fs.existsSync(path.join(root, ".github/workflows/tauri-build.yml"))
  ? fs.readFileSync(path.join(root, ".github/workflows/tauri-build.yml"), "utf8")
  : "";
const release = fs.existsSync(path.join(root, ".github/workflows/release.yml"))
  ? fs.readFileSync(path.join(root, ".github/workflows/release.yml"), "utf8")
  : "";
const packageJson = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
const runtimeProbe = fs.readFileSync(path.join(root, "scripts/tauri_runtime_probe.py"), "utf8");
const noteChromeOrder = [
  'data-action="new-from-note"',
  'data-action="delete-note"',
  'data-action="pin-note"',
  'data-action="collapse-note"',
].map((needle) => app.indexOf(needle));
const noteChromeControlsOrdered = noteChromeOrder.every((index) => index >= 0)
  && noteChromeOrder.every((index, arrayIndex) => arrayIndex === 0 || index > noteChromeOrder[arrayIndex - 1]);

const checks = [
  ["settings opens on demand", app.includes("settingsOpen") && app.includes('data-action="open-settings"')],
  ["preview states are available for visual QA", app.includes("previewCollapsed") && app.includes("previewPalette")],
  ["note chrome keeps compact text controls", app.includes('title="${tr("newNote")}">＋</button>') && app.includes('title="${tr("delete")}">×</button>') && app.includes('title="${tr("pin")}">⌾</button>') && styles.includes("border-radius: 999px;")],
  ["note chrome keeps requested button order", noteChromeControlsOrdered],
  ["default note placement is viewport-relative", state.includes("globalThis.innerWidth") && state.includes("defaultNoteX") && !rust.includes("default_x") && rust.includes("x: Option<f64>")],
  ["legacy note coordinates are clamped into viewport", state.includes("clampToViewportX") && state.includes("clampToViewportY") && state.includes("viewportWidth - width")],
  ["collapse action is implemented", app.includes('data-action="collapse-note"') && state.includes("toggleNoteCollapsed")],
  ["collapsed state is persisted", state.includes("collapsed: Boolean")],
  ["Tauri commands are wired", app.includes('invoke("load_state"') && app.includes('invoke("save_state"')],
  ["Tauri command failures degrade safely", app.includes("console.warn(`Tauri command failed:") && app.includes("return null;")],
  ["global pointer listeners are bound once", app.includes("pointerEventsBound") && app.includes("bindPointerEvents()")],
  ["taskbar visibility is settings-driven", app.includes('invoke("set_settings_visibility"') && rust.includes("set_settings_visibility") && config.app.windows[0].skipTaskbar === true],
  ["window shell is sticky-layer styled", config.app.windows[0].decorations === false && config.app.windows[0].transparent === true && styles.includes("background: transparent;")],
  ["host window is positioned from monitor work area", rust.includes("position_notes_window") && rust.includes("top_right_position") && rust.includes("monitor.work_area()")],
  ["QA can use isolated Tauri state directory", rust.includes("configured_data_dir") && rust.includes("MY_STICKY_NOTES_DATA_DIR") && rust.includes("app.path().app_data_dir()")],
  ["pin state reaches host window", app.includes('invoke("set_always_on_top"') && rust.includes("set_always_on_top")],
  ["autostart setting reaches native plugin", app.includes('invoke("set_open_at_login"') && app.includes('invoke("is_open_at_login_enabled"') && cargoToml.includes("tauri-plugin-autostart") && rust.includes("ManagerExt")],
  ["tray is implemented once in Rust", !("trayIcon" in config.app) && rust.includes("TrayIconBuilder::new()")],
  ["tray left click restores notes without opening the menu", rust.includes(".show_menu_on_left_click(false)") && rust.includes("MouseButton::Left") && rust.includes('emit("show-notes"')],
  ["tray can open settings through frontend event", rust.includes('emit("open-settings"') && app.includes('listen("open-settings"')],
  ["runtime probe covers tray commands and reversible autostart", runtimeProbe.includes("MENU_SETTINGS = 1001") && runtimeProbe.includes("MENU_QUIT = 1002") && runtimeProbe.includes("APP_REG_NAMES") && runtimeProbe.includes("matching_autostart_values") && runtimeProbe.includes("autostartDisabled")],
  ["Tauri v2 capability file is present", capabilities.identifier === "default" && capabilities.permissions.includes("core:default") && capabilities.permissions.includes("autostart:default")],
  ["Tauri bundle icons cover Windows and macOS", Array.isArray(config.bundle.icon) && config.bundle.icon.includes("icons/icon.ico") && config.bundle.icon.includes("icons/icon.icns")],
  ["settings page exists", app.includes("settings-shell")],
  ["color palette exists", app.includes("palette-popover")],
  ["collapsed content is visually hidden", styles.includes(".note.collapsed .note-body")],
  ["hidden popovers stay hidden", styles.includes("[hidden]")],
  ["Windows and macOS bundle targets exist", JSON.stringify(config.bundle.targets) === JSON.stringify(["nsis", "dmg"])],
  ["CI uses stable GitHub action majors", ci.includes("actions/checkout@v4") && ci.includes("actions/setup-node@v4") && tauriBuild.includes("actions/upload-artifact@v4")],
  ["Tauri build workflow uses locked pnpm install", tauriBuild.includes("corepack enable") && tauriBuild.includes("pnpm install --frozen-lockfile") && tauriBuild.includes("pnpm run tauri:build")],
  ["frontend package manager and Tauri CLI are pinned", packageJson.packageManager === "pnpm@11.7.0" && packageJson.devDependencies?.["@tauri-apps/cli"] === "2.11.4"],
  ["legacy Python release is paused", release.includes("workflow_dispatch") && release.includes("legacy Python release workflow is disabled") && !release.includes("build.ps1")],
];

const failures = checks.filter(([, passed]) => !passed).map(([name]) => name);
if (failures.length > 0) {
  throw new Error(`Static Tauri checks failed: ${failures.join(", ")}`);
}

console.log(JSON.stringify({ result: "passed", checks: checks.map(([name]) => name) }));
