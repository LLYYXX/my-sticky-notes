import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const requiredFiles = [
  "package.json",
  "pnpm-lock.yaml",
  "src/index.html",
  "src/app.js",
  "src/views.js",
  "src/updates.js",
  "src/state.js",
  "src/styles.css",
  "src/assets/icons/add.png",
  "src/assets/icons/checkbox-on.png",
  "src/assets/icons/delete.png",
  "src/assets/icons/pin.png",
  "src/assets/app-icon.png",
  "src-tauri/Cargo.toml",
  "src-tauri/tauri.conf.json",
  "src-tauri/capabilities/default.json",
  "src-tauri/src/main.rs",
  "src-tauri/src/direct_update.rs",
  "src-tauri/src/single_instance.rs",
  "scripts/tauri_runtime_probe.py",
  "scripts/tauri_single_instance_probe.py",
  "scripts/tauri_update_test.mjs",
];

for (const relative of requiredFiles) {
  if (!fs.existsSync(path.join(root, relative))) {
    throw new Error(`Missing ${relative}`);
  }
}

const app = fs.readFileSync(path.join(root, "src/app.js"), "utf8");
const views = fs.readFileSync(path.join(root, "src/views.js"), "utf8");
const updates = fs.readFileSync(path.join(root, "src/updates.js"), "utf8");
const state = fs.readFileSync(path.join(root, "src/state.js"), "utf8");
const styles = fs.readFileSync(path.join(root, "src/styles.css"), "utf8");
const rust = fs.readFileSync(path.join(root, "src-tauri/src/main.rs"), "utf8");
const directUpdate = fs.readFileSync(path.join(root, "src-tauri/src/direct_update.rs"), "utf8");
const singleInstance = fs.readFileSync(path.join(root, "src-tauri/src/single_instance.rs"), "utf8");
const cargoToml = fs.readFileSync(path.join(root, "src-tauri/Cargo.toml"), "utf8");
const capabilities = JSON.parse(
  fs.readFileSync(path.join(root, "src-tauri/capabilities/default.json"), "utf8"),
);
const config = JSON.parse(
  fs.readFileSync(path.join(root, "src-tauri/tauri.conf.json"), "utf8"),
);
const tauriBuild = fs.existsSync(path.join(root, ".github/workflows/tauri-build.yml"))
  ? fs.readFileSync(path.join(root, ".github/workflows/tauri-build.yml"), "utf8")
  : "";
const release = fs.existsSync(path.join(root, ".github/workflows/release.yml"))
  ? fs.readFileSync(path.join(root, ".github/workflows/release.yml"), "utf8")
  : "";
const packageJson = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
const runtimeProbe = fs.readFileSync(path.join(root, "scripts/tauri_runtime_probe.py"), "utf8");
const singleInstanceProbe = fs.readFileSync(path.join(root, "scripts/tauri_single_instance_probe.py"), "utf8");
const updateTest = fs.readFileSync(path.join(root, "scripts/tauri_update_test.mjs"), "utf8");
const noteChromeOrder = [
  'data-action="new-from-note"',
  'data-action="delete-note"',
  'data-action="pin-note"',
  'data-action="collapse-note"',
].map((needle) => views.indexOf(needle));
const noteChromeControlsOrdered = noteChromeOrder.every((index) => index >= 0)
  && noteChromeOrder.every((index, indexInArray) => indexInArray === 0 || index > noteChromeOrder[indexInArray - 1]);

const checks = [
  ["renderer responsibilities are separated", app.includes('from "./views.js"') && views.includes("renderNotes") && views.includes("renderSettings")],
  ["note and settings use dedicated window contexts", app.includes("isSettingsWindow") && rust.includes("show_settings_window") && rust.includes('WebviewUrl::App("index.html?settings=1"')],
  ["settings webview is created only on demand", rust.includes('get_webview_window("settings")') && rust.includes("WebviewWindowBuilder::new") && !config.app.windows.some((window) => window.label === "settings")],
  ["preview states are available for visual QA", app.includes("previewCollapsed") && app.includes("previewPalette")],
  ["note chrome uses bundled raster icons", views.includes("./assets/icons/") && !views.includes(">＋</button>") && !views.includes(">×</button>")],
  ["note chrome keeps requested button order", noteChromeControlsOrdered],
  ["nine independent note colors remain available", ["yellow", "offwhite", "lime", "lilac", "cream", "pink", "mint", "coral", "navy"].every((color) => state.includes(`${color}: {`))],
  ["default note placement is viewport-relative", state.includes("globalThis.innerWidth") && state.includes("defaultNoteX") && rust.includes("x: Option<f64>")],
  ["legacy note height is not restored", !state.includes("note.height") && state.includes("bodyHeight")],
  ["note content height follows its todo list by default", views.includes("note.bodyHeight ?") && styles.includes("var(--note-body-height, 0px)") && !views.includes("min-height:${note.collapsed")],
  ["long todos wrap inside their note", styles.includes("overflow-wrap: anywhere") && styles.includes("word-break: break-word")],
  ["collapse action is implemented", views.includes('data-action="collapse-note"') && state.includes("toggleNoteCollapsed")],
  ["collapsed state is persisted", state.includes("collapsed: Boolean")],
  ["per-note resize is persisted", app.includes("startResize") && app.includes("bodyHeight") && views.includes("note-resize")],
  ["Tauri state commands are wired", app.includes('invoke("load_state"') && app.includes('invoke("save_state"')],
  ["state persistence replaces JSON atomically", rust.includes("write_json_atomically") && rust.includes("create_new(true)") && rust.includes("sync_all()") && rust.includes("fs::rename")],
  ["Tauri command failures degrade safely", app.includes("console.warn(`Tauri command failed:") && app.includes("return null;")],
  ["global pointer listeners are bound once", app.includes("pointerEventsBound") && app.includes("bindPointerEvents()")],
  ["note host stays out of the taskbar", config.app.windows[0].skipTaskbar === true && rust.includes("ensure_notes_taskbar_style")],
  ["settings is the only normal taskbar window", rust.includes("WebviewWindowBuilder::new") && rust.includes('.title("桌面便利贴设置")')],
  ["window shell is sticky-layer styled", config.app.windows[0].decorations === false && config.app.windows[0].transparent === true && config.app.windows[0].resizable === false && styles.includes("background: transparent;")],
  ["host window uses monitor work area and scale factor", rust.includes("position_notes_window") && rust.includes("top_right_position") && rust.includes("notes_host_logical_size") && rust.includes("monitor.work_area()") && !Object.prototype.hasOwnProperty.call(config.app.windows[0], "minWidth") && !Object.prototype.hasOwnProperty.call(config.app.windows[0], "minHeight")],
  ["QA can use isolated Tauri state directory", rust.includes("configured_data_dir") && rust.includes("MY_STICKY_NOTES_DATA_DIR") && rust.includes("app.path().app_data_dir()")],
  ["pin state reaches host window", app.includes('invoke("set_always_on_top"') && rust.includes("set_always_on_top")],
  ["autostart setting reaches native plugin", app.includes('invoke("set_open_at_login"') && app.includes('invoke("is_open_at_login_enabled"') && cargoToml.includes("tauri-plugin-autostart") && rust.includes("ManagerExt")],
  ["tray is implemented once in Rust", !('trayIcon' in config.app) && rust.includes("TrayIconBuilder::new()")],
  ["tray left click restores notes", rust.includes(".show_menu_on_left_click(false)") && rust.includes("MouseButton::Left") && rust.includes("show_main_window(tray.app_handle())")],
  ["tray opens the independent settings window", rust.includes('"settings" =>') && rust.includes("show_settings_window(app)")],
  ["single-instance guard is owned before the Tauri shell", rust.includes("single_instance::acquire()") && rust.includes("single_instance::begin_listening") && singleInstance.includes("TcpListener::bind") && singleInstance.includes("focus_main_window")],
  ["single-instance probe asserts the duplicate-launch symptom", singleInstanceProbe.includes("second.poll() is not None") && singleInstanceProbe.includes("firstWindowsAfterDuplicate")],
  ["GitHub release checks include prerelease assets", updates.includes("releases?per_page=20") && updates.includes("selectNewestRelease") && updates.includes("assetNames") && app.includes("checkGithubRelease") && updateTest.includes("no published release available")],
  ["direct updates are fixed-source and parent-exit safe", rust.includes("direct_update::download_and_install_update") && directUpdate.includes("RELEASE_DOWNLOAD_BASE") && directUpdate.includes("--proto") && directUpdate.includes("WaitForExit") && directUpdate.includes("-ArgumentList @('/S')") && directUpdate.includes("$installer.WaitForExit()") && directUpdate.includes("asset_matches_current_platform")],
  ["direct updates add no signed-updater runtime", !cargoToml.includes("tauri-plugin-updater") && !directUpdate.includes("tauri_plugin_updater")],
  ["runtime probe covers settings, autostart, and runtime budgets", runtimeProbe.includes("MENU_SETTINGS = 1001") && runtimeProbe.includes("APP_REG_NAMES") && runtimeProbe.includes("matching_autostart_values") && runtimeProbe.includes("settingsWindow") && runtimeProbe.includes("working_set_mb") && runtimeProbe.includes("assert_memory_budget")],
  ["Tauri v2 capability file covers both views", capabilities.identifier === "default" && capabilities.windows.includes("main") && capabilities.windows.includes("settings") && capabilities.permissions.includes("core:default") && capabilities.permissions.includes("autostart:default")],
  ["settings page exists without a note settings section", views.includes("settings-window") && !views.includes("stayLightweight")],
  ["color palette exists", views.includes("palette-popover")],
  ["hidden popovers stay hidden", styles.includes("[hidden]")],
  ["Windows and macOS bundle targets exist", JSON.stringify(config.bundle.targets) === JSON.stringify(["nsis", "dmg"])],
  ["CI uses stable GitHub action majors", tauriBuild.includes("actions/checkout@v4") && tauriBuild.includes("actions/setup-node@v4") && tauriBuild.includes("actions/upload-artifact@v4")],
  ["Tauri CI validates both supported desktop platforms", tauriBuild.includes("push:") && tauriBuild.includes("pull_request:") && tauriBuild.includes("windows-latest") && tauriBuild.includes("macos-latest") && tauriBuild.includes("cargo test --locked")],
  ["Tauri build workflow uses locked pnpm install", tauriBuild.includes("corepack enable") && tauriBuild.includes("pnpm install --frozen-lockfile") && tauriBuild.includes("pnpm run tauri:build")],
  ["frontend package manager and Tauri CLI are pinned", packageJson.packageManager === "pnpm@11.7.0" && packageJson.devDependencies?.["@tauri-apps/cli"] === "2.11.4"],
  ["manual release publishes both native bundles", release.includes("workflow_dispatch") && release.includes("windows-latest") && release.includes("macos-latest") && release.includes("cargo test --locked") && release.includes("gh release upload") && !release.includes("build.ps1")],
];

const failures = checks.filter(([, passed]) => !passed).map(([name]) => name);
if (failures.length > 0) {
  throw new Error(`Static Tauri checks failed: ${failures.join(", ")}`);
}

console.log(JSON.stringify({ result: "passed", checks: checks.map(([name]) => name) }));
