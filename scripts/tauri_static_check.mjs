import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const requiredFiles = [
  "package.json", "pnpm-lock.yaml", "src/index.html", "src/app.js", "src/views.js",
  "src/updates.js", "src/state.js", "src/styles.css", "src/assets/icons/add.png",
  "src/assets/icons/checkbox-on.png", "src/assets/icons/delete.png", "src/assets/icons/pin.png",
  "src/assets/icons/LICENSE-lucide.txt", "src/assets/app-icon.png", "src-tauri/Cargo.toml",
  "src-tauri/tauri.conf.json", "src-tauri/nsis-hooks.nsh", "src-tauri/capabilities/default.json",
  "src-tauri/src/main.rs", "src-tauri/src/direct_update.rs", "src-tauri/src/single_instance.rs",
  "scripts/tauri_runtime_probe.py", "scripts/tauri_single_instance_probe.py", "scripts/tauri_update_test.mjs",
];
for (const relative of requiredFiles) {
  if (!fs.existsSync(path.join(root, relative))) throw new Error(`Missing ${relative}`);
}

const read = (relative) => fs.readFileSync(path.join(root, relative), "utf8");
const app = read("src/app.js");
const views = read("src/views.js");
const updates = read("src/updates.js");
const state = read("src/state.js");
const styles = read("src/styles.css");
const rust = read("src-tauri/src/main.rs");
const directUpdate = read("src-tauri/src/direct_update.rs");
const singleInstance = read("src-tauri/src/single_instance.rs");
const cargoToml = read("src-tauri/Cargo.toml");
const config = JSON.parse(read("src-tauri/tauri.conf.json"));
const capabilities = JSON.parse(read("src-tauri/capabilities/default.json"));
const nsisHooks = read("src-tauri/nsis-hooks.nsh");
const runtimeProbe = read("scripts/tauri_runtime_probe.py");
const singleInstanceProbe = read("scripts/tauri_single_instance_probe.py");
const updateTest = read("scripts/tauri_update_test.mjs");
const tauriBuild = fs.existsSync(path.join(root, ".github/workflows/tauri-build.yml")) ? read(".github/workflows/tauri-build.yml") : "";
const release = fs.existsSync(path.join(root, ".github/workflows/release.yml")) ? read(".github/workflows/release.yml") : "";
const packageJson = JSON.parse(read("package.json"));
const noteChromeOrder = [
  'data-action="new-from-note"', 'data-action="delete-note"',
  'data-action="pin-note"', 'data-action="collapse-note"',
].map((needle) => views.indexOf(needle));

const checks = [
  ["renderer separates a note window from Settings", app.includes("noteId") && app.includes("isSettingsWindow") && views.includes("renderNoteWindow") && views.includes("renderSettings")],
  ["each sticky note is a runtime native window", rust.includes("create_note_window") && rust.includes("WebviewWindowBuilder::new") && rust.includes("NOTE_LABEL_PREFIX") && rust.includes("index.html?note=")],
  ["no persistent transparent desktop host remains", Array.isArray(config.app.windows) && config.app.windows.length === 0 && !styles.includes("notes-workspace") && !rust.includes("position_notes_window")],
  ["only small note windows use transparent corners", rust.includes(".transparent(true)") && rust.includes(".inner_size(note_width(note), note_window_height(note))")],
  ["native note labels are safe and stable", rust.includes("fn note_label") && rust.includes("encode_query_component")],
  ["note positions are native coordinates", !state.includes("globalThis.innerWidth") && state.includes("x: Number.isFinite(note.x)") && rust.includes("remember_note_position")],
  ["previous host positions migrate once", rust.includes("migrate_legacy_host_coordinates") && rust.includes("legacy_host_origin") && rust.includes("STATE_VERSION: u16 = 9")],
  ["new notes still default to the screen top right", rust.includes("default_note_position") && rust.includes("NOTE_MARGIN")],
  ["settings is created only when requested", rust.includes('get_webview_window("settings")') && rust.includes("show_settings_window")],
  ["note controls keep the requested order", noteChromeOrder.every((index) => index >= 0) && noteChromeOrder.every((index, i) => i === 0 || index > noteChromeOrder[i - 1])],
  ["note chrome uses bundled raster icons", views.includes("./assets/icons/") && !views.includes(">+</button>")],
  ["nine independent note colors remain available", ["yellow", "offwhite", "lime", "lilac", "cream", "pink", "mint", "coral", "navy"].every((color) => state.includes(`${color}: {`))],
  ["long todos wrap inside each note", styles.includes("overflow-wrap: anywhere") && styles.includes("word-break: break-word")],
  ["collapse and resize stay per note", app.includes("collapse-note") && app.includes("resize_note_preview") && app.includes("bodyHeight") && views.includes("note-resize")],
  ["frontend mutates notes through focused commands", app.includes('invoke("save_note"') && app.includes('invoke("create_note"') && app.includes('invoke("delete_note"') && app.includes('invoke("save_settings"')],
  ["state has one backend authority and atomic writes", rust.includes("AppStateStore(Mutex<AppState>)") && rust.includes("mutate_state") && rust.includes("write_json_atomically") && rust.includes("create_new(true)")],
  ["legacy Tk state still migrates once", rust.includes("load_or_migrate_state") && rust.includes("legacy_state_path") && rust.includes("merge_legacy_state") && rust.includes("legacy_migration_marker_path")],
  ["per-note pin reaches native windows", rust.includes("set_always_on_top(note.pinned)")],
  ["tray restores every note window", rust.includes("show_note_windows") && rust.includes("MouseButton::Left") && rust.includes("show_menu_on_left_click(false)")],
  ["single instance focuses note windows rather than a host", singleInstance.includes("label.starts_with(\"note-\")") && singleInstance.includes("TcpListener::bind")],
  ["single-instance probe remains present", singleInstanceProbe.includes("second.poll() is not None") && singleInstanceProbe.includes("firstWindowsAfterDuplicate")],
  ["runtime probe checks native note mode and GUI subsystem", runtimeProbe.includes("find_note_window") && runtimeProbe.includes("assert_note_mode") && runtimeProbe.includes("assert_windows_gui_subsystem")],
  ["dynamic note windows are in the capability scope", capabilities.windows.includes("note-*") && capabilities.windows.includes("settings") && capabilities.permissions.includes("core:default")],
  ["settings page contains no obsolete note configuration", views.includes("settings-window") && !views.includes("stayLightweight")],
  ["about source link opens externally", views.includes('href="https://github.com/LLYYXX/my-sticky-notes" target="_blank"') && capabilities.permissions.includes("opener:default")],
  ["direct updates remain fixed-source and parent-exit safe", rust.includes("direct_update::download_and_install_update") && directUpdate.includes("RELEASE_DOWNLOAD_BASE") && directUpdate.includes("WaitForExit") && directUpdate.includes("-ArgumentList @('/S')")],
  ["direct updates add no signed-updater runtime", !cargoToml.includes("tauri-plugin-updater") && !directUpdate.includes("tauri_plugin_updater")],
  ["Windows release does not open a console window", rust.includes('#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]')],
  ["legacy installer closes the old application without a shell", config.bundle.windows.nsis.installerHooks === "nsis-hooks.nsh" && nsisHooks.includes("taskkill.exe") && nsisHooks.includes("MyStickyNotes.exe") && !nsisHooks.includes("cmd.exe")],
  ["Windows and macOS bundle targets exist", JSON.stringify(config.bundle.targets) === JSON.stringify(["nsis", "dmg"])],
  ["release versions stay aligned", packageJson.version === config.version && app.includes(`const APP_VERSION = "v${packageJson.version}"`)],
  ["CI validates Windows and both Mac architectures", tauriBuild.includes("windows-latest") && tauriBuild.includes("macos-latest") && tauriBuild.includes("macos-15-intel") && tauriBuild.includes("cargo test --locked")],
  ["build workflow uses locked pnpm and pinned Node", packageJson.engines?.node === ">=22.13" && tauriBuild.includes('node-version: "22"') && tauriBuild.includes("pnpm install --frozen-lockfile")],
  ["release publishes installers and legacy update metadata", release.includes("bundle/nsis/*.exe") && release.includes("bundle/dmg/*.dmg") && release.includes("My.Sticky.Notes.Setup.${version}.exe") && release.includes("SHA256SUMS.txt")],
  ["release builds both Mac architectures", release.includes("macos-latest") && release.includes("macos-15-intel")],
  ["GitHub release checks include prerelease assets", updates.includes("releases?per_page=20") && updates.includes("selectNewestRelease") && updateTest.includes("no published release available")],
];

const failures = checks.filter(([, passed]) => !passed).map(([name]) => name);
if (failures.length) throw new Error(`Static Tauri checks failed: ${failures.join(", ")}`);
console.log(JSON.stringify({ result: "passed", checks: checks.map(([name]) => name) }));
