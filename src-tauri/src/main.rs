#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod direct_update;
mod single_instance;

use serde::{Deserialize, Serialize};
use std::{
    collections::HashSet,
    env,
    fs::{self, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
    sync::atomic::{AtomicU64, Ordering},
};
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, LogicalSize, Manager, PhysicalPosition, PhysicalSize, WebviewUrl,
    WebviewWindowBuilder,
};
use tauri_plugin_autostart::{MacosLauncher, ManagerExt};

const STATE_VERSION: u16 = 8;
const NOTES_HOST_MAX_WIDTH: f64 = 1120.0;
const NOTES_HOST_MAX_HEIGHT: f64 = 760.0;
const NOTES_HOST_MARGIN: i32 = 24;
const LEGACY_APP_DIRECTORY: &str = "MyStickyNotes";
const LEGACY_MIGRATION_MARKER: &str = ".legacy-tk-state-v1";
static STATE_WRITE_SEQUENCE: AtomicU64 = AtomicU64::new(0);

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AppState {
    #[serde(default = "state_version")]
    version: u16,
    #[serde(default)]
    settings: AppSettings,
    #[serde(default)]
    notes: Vec<Note>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AppSettings {
    #[serde(default, alias = "open_at_login")]
    open_at_login: bool,
    #[serde(default = "default_language")]
    language: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Note {
    #[serde(default = "default_note_id")]
    id: String,
    #[serde(default = "default_color")]
    color: String,
    #[serde(default)]
    pinned: bool,
    #[serde(default)]
    collapsed: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    x: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    y: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    width: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    body_height: Option<f64>,
    #[serde(default)]
    todos: Vec<Todo>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Todo {
    #[serde(default = "default_todo_id")]
    id: String,
    #[serde(default)]
    text: String,
    #[serde(default)]
    completed: bool,
    #[serde(default)]
    order: usize,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            open_at_login: false,
            language: default_language(),
        }
    }
}

fn state_version() -> u16 {
    STATE_VERSION
}

fn default_language() -> String {
    "zh-CN".to_string()
}

fn default_color() -> String {
    "yellow".to_string()
}

fn default_note_id() -> String {
    "note-default".to_string()
}

fn default_todo_id() -> String {
    "todo-default".to_string()
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            version: STATE_VERSION,
            settings: AppSettings::default(),
            notes: vec![],
        }
    }
}

#[tauri::command]
fn load_state(app: AppHandle) -> Result<AppState, String> {
    let path = state_path(&app)?;
    let legacy_path = configured_data_dir().is_none().then(legacy_state_path).flatten();
    let (state, migrated) = load_or_migrate_state(&path, legacy_path.as_deref())?;
    if migrated && state.settings.open_at_login {
        let _ = app.autolaunch().enable();
    }
    Ok(state)
}

#[tauri::command]
fn save_state(app: AppHandle, state: AppState) -> Result<(), String> {
    let path = state_path(&app)?;
    let payload = serde_json::to_vec_pretty(&state).map_err(|error| error.to_string())?;
    write_json_atomically(&path, &payload)
}

#[tauri::command]
fn is_open_at_login_enabled(app: AppHandle) -> Result<bool, String> {
    app.autolaunch()
        .is_enabled()
        .map_err(|error| error.to_string())
}

#[tauri::command]
fn set_open_at_login(app: AppHandle, enabled: bool) -> Result<bool, String> {
    let autostart = app.autolaunch();
    if enabled {
        autostart.enable().map_err(|error| error.to_string())?;
    } else {
        autostart.disable().map_err(|error| error.to_string())?;
    }
    autostart.is_enabled().map_err(|error| error.to_string())
}

#[tauri::command]
fn set_always_on_top(app: AppHandle, pinned: bool) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window
            .set_always_on_top(pinned)
            .map_err(|error| error.to_string())?;
    }
    Ok(())
}

fn read_json(path: &Path) -> Result<Option<AppState>, String> {
    if !path.exists() {
        return Ok(None);
    }
    let payload = fs::read_to_string(path).map_err(|error| error.to_string())?;
    let mut state: AppState = serde_json::from_str(&payload).map_err(|error| error.to_string())?;
    state.version = STATE_VERSION;
    Ok(Some(state))
}

fn load_or_migrate_state(
    state_path: &Path,
    legacy_path: Option<&Path>,
) -> Result<(AppState, bool), String> {
    let current = read_json(state_path)?;
    let marker_path = legacy_migration_marker_path(state_path);
    if marker_path.exists() {
        return Ok((current.unwrap_or_default(), false));
    }
    if let Some(legacy_path) = legacy_path.filter(|path| *path != state_path) {
        if let Some(legacy) = read_json(legacy_path)? {
            let state = current
                .map(|current| merge_legacy_state(current, legacy.clone()))
                .unwrap_or(legacy);
            let payload = serde_json::to_vec_pretty(&state).map_err(|error| error.to_string())?;
            write_json_atomically(state_path, &payload)?;
            write_json_atomically(&marker_path, b"migrated\n")?;
            return Ok((state, true));
        }
    }
    Ok((current.unwrap_or_default(), false))
}

fn merge_legacy_state(mut current: AppState, legacy: AppState) -> AppState {
    let current_was_empty = current.notes.is_empty();
    let AppState {
        settings: legacy_settings,
        notes: legacy_notes,
        ..
    } = legacy;
    let mut note_ids = current
        .notes
        .iter()
        .map(|note| note.id.clone())
        .collect::<HashSet<_>>();
    for note in legacy_notes {
        if note_ids.insert(note.id.clone()) {
            current.notes.push(note);
        }
    }
    if current_was_empty {
        current.settings = legacy_settings;
    } else {
        current.settings.open_at_login |= legacy_settings.open_at_login;
        if current.settings.language == default_language()
            && legacy_settings.language != default_language()
        {
            current.settings.language = legacy_settings.language;
        }
    }
    current.version = STATE_VERSION;
    current
}

fn legacy_migration_marker_path(state_path: &Path) -> PathBuf {
    state_path.with_file_name(LEGACY_MIGRATION_MARKER)
}

fn write_json_atomically(path: &Path, payload: &[u8]) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| "state path has no parent directory".to_owned())?;
    let file_name = path
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| "state path has no file name".to_owned())?;
    fs::create_dir_all(parent).map_err(|error| error.to_string())?;

    let sequence = STATE_WRITE_SEQUENCE.fetch_add(1, Ordering::Relaxed);
    let temporary_path = parent.join(format!(".{file_name}.{}.{}.tmp", std::process::id(), sequence));
    let write_result = (|| -> Result<(), String> {
        let mut temporary_file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temporary_path)
            .map_err(|error| error.to_string())?;
        temporary_file
            .write_all(payload)
            .map_err(|error| error.to_string())?;
        temporary_file
            .sync_all()
            .map_err(|error| error.to_string())?;
        drop(temporary_file);
        fs::rename(&temporary_path, path).map_err(|error| error.to_string())
    })();
    if write_result.is_err() {
        let _ = fs::remove_file(&temporary_path);
    }
    write_result
}

fn state_path(app: &AppHandle) -> Result<PathBuf, String> {
    let data_dir = if let Some(path) = configured_data_dir() {
        path
    } else {
        app.path().app_data_dir().map_err(|error| error.to_string())?
    };
    Ok(data_dir.join("state.json"))
}

fn configured_data_dir() -> Option<PathBuf> {
    env::var_os("MY_STICKY_NOTES_DATA_DIR").map(PathBuf::from)
}

#[cfg(target_os = "windows")]
fn legacy_state_path() -> Option<PathBuf> {
    env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .map(|directory| directory.join(LEGACY_APP_DIRECTORY).join("state.json"))
}

#[cfg(not(target_os = "windows"))]
fn legacy_state_path() -> Option<PathBuf> {
    None
}

fn show_main_window(app: &AppHandle) {
    single_instance::focus_main_window(app);
}

fn show_settings_window(app: &AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("settings") {
        window.show().map_err(|error| error.to_string())?;
        window.set_focus().map_err(|error| error.to_string())?;
        return Ok(());
    }
    WebviewWindowBuilder::new(
        app,
        "settings",
        WebviewUrl::App("index.html?settings=1".into()),
    )
    .title("桌面便利贴设置")
    .inner_size(720.0, 560.0)
    .min_inner_size(520.0, 420.0)
    .resizable(true)
    .center()
    .build()
    .map(|_| ())
    .map_err(|error| error.to_string())
}

fn position_notes_window(app: &AppHandle) -> Result<(), String> {
    let Some(window) = app.get_webview_window("main") else {
        return Ok(());
    };
    let monitor = window
        .current_monitor()
        .map_err(|error| error.to_string())?
        .or(window.primary_monitor().map_err(|error| error.to_string())?);
    let Some(monitor) = monitor else {
        return Ok(());
    };
    let work_area = monitor.work_area();
    let (target_width, target_height) = notes_host_logical_size(
        work_area.size,
        monitor.scale_factor(),
        NOTES_HOST_MARGIN,
    );
    window
        .set_size(LogicalSize::new(target_width, target_height))
        .map_err(|error| error.to_string())?;
    let window_size = window.outer_size().map_err(|error| error.to_string())?;
    let position = top_right_position(
        work_area.position,
        work_area.size,
        window_size,
        NOTES_HOST_MARGIN,
    );
    window
        .set_position(position)
        .map_err(|error| error.to_string())
}

fn notes_host_logical_size(
    work_area_size: PhysicalSize<u32>,
    scale_factor: f64,
    margin: i32,
) -> (f64, f64) {
    let safe_width = work_area_size
        .width
        .saturating_sub((margin.max(0) as u32).saturating_mul(2)) as f64;
    let safe_height = work_area_size
        .height
        .saturating_sub((margin.max(0) as u32).saturating_mul(2)) as f64;
    let scale = scale_factor.max(0.01);
    (
        (safe_width / scale).min(NOTES_HOST_MAX_WIDTH),
        (safe_height / scale).min(NOTES_HOST_MAX_HEIGHT),
    )
}

fn top_right_position(
    work_area_position: PhysicalPosition<i32>,
    work_area_size: PhysicalSize<u32>,
    window_size: PhysicalSize<u32>,
    margin: i32,
) -> PhysicalPosition<i32> {
    let work_area_right = work_area_position.x + work_area_size.width as i32;
    let max_x = work_area_right - window_size.width as i32 - margin;
    PhysicalPosition::new(max_x.max(work_area_position.x + margin), work_area_position.y + margin)
}

#[cfg(windows)]
fn ensure_notes_taskbar_style(window: &tauri::WebviewWindow) -> Result<(), String> {
    use windows::Win32::UI::WindowsAndMessaging::{
        GetWindowLongPtrW, SetWindowLongPtrW, SetWindowPos, GWL_EXSTYLE, SWP_FRAMECHANGED,
        SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER, WS_EX_APPWINDOW, WS_EX_TOOLWINDOW,
    };

    let hwnd = window.hwnd().map_err(|error| error.to_string())?;
    unsafe {
        let current = GetWindowLongPtrW(hwnd, GWL_EXSTYLE);
        let next = (current | WS_EX_TOOLWINDOW.0 as isize) & !(WS_EX_APPWINDOW.0 as isize);
        if next != current {
            SetWindowLongPtrW(hwnd, GWL_EXSTYLE, next);
            SetWindowPos(
                hwnd,
                None,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
            )
            .map_err(|error| error.to_string())?;
        }
    }
    Ok(())
}

#[cfg(not(windows))]
fn ensure_notes_taskbar_style(_window: &tauri::WebviewWindow) -> Result<(), String> {
    Ok(())
}

fn build_tray(app: &AppHandle) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, "show", "显示全部", true, None::<&str>)?;
    let settings = MenuItem::with_id(app, "settings", "设置", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "退出应用", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &settings, &quit])?;
    let mut builder = TrayIconBuilder::new()
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "quit" => app.exit(0),
            "show" => {
                show_main_window(app);
            }
            "settings" => {
                if let Err(error) = show_settings_window(app) {
                    eprintln!("Unable to show Settings: {error}");
                }
            }
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = event
            {
                show_main_window(tray.app_handle());
            }
        });
    if let Some(icon) = app.default_window_icon() {
        builder = builder.icon(icon.clone());
    }
    builder.build(app)?;
    Ok(())
}

pub fn run(instance: single_instance::InstanceGuard) {
    tauri::Builder::default()
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            Some(vec![]),
        ))
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            single_instance::begin_listening(instance, app.handle().clone());
            build_tray(app.handle())?;
            if let Some(window) = app.handle().get_webview_window("main") {
                let _ = window.set_skip_taskbar(true);
                if let Err(error) = ensure_notes_taskbar_style(&window) {
                    eprintln!("Unable to hide notes window from taskbar: {error}");
                }
            }
            if let Err(error) = position_notes_window(app.handle()) {
                eprintln!("Unable to position notes window: {error}");
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            load_state,
            save_state,
            is_open_at_login_enabled,
            set_open_at_login,
            set_always_on_top,
            direct_update::download_and_install_update
        ])
        .run(tauri::generate_context!())
        .expect("error while running My Sticky Notes");
}

fn main() {
    match single_instance::acquire() {
        Ok(single_instance::AcquireResult::Primary(instance)) => run(instance),
        Ok(single_instance::AcquireResult::Existing) => {}
        Err(error) => eprintln!("Unable to start My Sticky Notes: {error}"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn deserializes_legacy_startup_and_collapsed_note() {
        let payload = r#"{
            "settings": {"open_at_login": true, "language": "en"},
            "notes": [{
                "id": "legacy-note",
                "color": "navy",
                "collapsed": true,
                "todos": [{"id": "todo-1", "text": "wrap long todo", "completed": true}]
            }]
        }"#;
        let state: AppState = serde_json::from_str(payload).expect("valid state");
        assert!(state.settings.open_at_login);
        assert_eq!(state.settings.language, "en");
        assert_eq!(state.notes[0].id, "legacy-note");
        assert!(state.notes[0].collapsed);
        assert_eq!(state.notes[0].x, None);
        assert!(state.notes[0].todos[0].completed);
    }

    #[test]
    fn read_json_keeps_layout_defaults_in_frontend_when_state_has_no_notes() {
        let path = std::env::temp_dir().join(format!(
            "my-sticky-notes-empty-{}.json",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("clock")
                .as_nanos()
        ));
        std::fs::write(&path, r#"{"version":1,"notes":[]}"#).expect("write state");
        let state = read_json(&path).expect("read state").expect("some state");
        std::fs::remove_file(&path).expect("cleanup");
        assert_eq!(state.version, STATE_VERSION);
        assert!(state.notes.is_empty());
    }

    #[test]
    fn migrates_legacy_tk_state_when_tauri_state_is_absent() {
        let directory = std::env::temp_dir().join(format!(
            "my-sticky-notes-migration-{}",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("clock")
                .as_nanos()
        ));
        let state_path = directory.join("tauri").join("state.json");
        let legacy_path = directory.join("MyStickyNotes").join("state.json");
        std::fs::create_dir_all(legacy_path.parent().expect("legacy parent"))
            .expect("create legacy directory");
        std::fs::write(
            &legacy_path,
            r#"{
              "version": 5,
              "settings": {"open_at_login": true, "language": "en"},
              "notes": [{
                "id": "old-note",
                "title": "old title",
                "color": "mint",
                "pinned": true,
                "x": 140,
                "y": 160,
                "width": 330,
                "height": 360,
                "todos": [{"id": "old-todo", "text": "keep this", "completed": true, "order": 0}]
              }]
            }"#,
        )
        .expect("write legacy state");

        let (state, migrated) = load_or_migrate_state(&state_path, Some(&legacy_path))
            .expect("migrate legacy state");

        assert!(migrated);
        assert_eq!(state.version, STATE_VERSION);
        assert!(state.settings.open_at_login);
        assert_eq!(state.settings.language, "en");
        assert_eq!(state.notes[0].id, "old-note");
        assert_eq!(state.notes[0].color, "mint");
        assert!(state.notes[0].pinned);
        assert_eq!(state.notes[0].todos[0].text, "keep this");
        assert!(state_path.exists());
        std::fs::remove_dir_all(&directory).expect("cleanup migration directory");
    }

    #[test]
    fn merges_legacy_tk_notes_once_when_tauri_state_already_exists() {
        let directory = std::env::temp_dir().join(format!(
            "my-sticky-notes-merge-migration-{}",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("clock")
                .as_nanos()
        ));
        let state_path = directory.join("tauri").join("state.json");
        let legacy_path = directory.join("MyStickyNotes").join("state.json");
        std::fs::create_dir_all(state_path.parent().expect("state parent"))
            .expect("create state directory");
        std::fs::create_dir_all(legacy_path.parent().expect("legacy parent"))
            .expect("create legacy directory");
        std::fs::write(
            &state_path,
            r#"{"version":8,"notes":[{"id":"new-note","todos":[]}],"settings":{"language":"zh-CN"}}"#,
        )
        .expect("write new state");
        std::fs::write(
            &legacy_path,
            r#"{"version":5,"settings":{"open_at_login":true,"language":"en"},"notes":[{"id":"old-note","color":"coral","todos":[{"id":"old-todo","text":"old task","completed":false,"order":0}]}]}"#,
        )
        .expect("write legacy state");

        let (merged, migrated) = load_or_migrate_state(&state_path, Some(&legacy_path))
            .expect("merge legacy state");
        let (reloaded, migrated_again) = load_or_migrate_state(&state_path, Some(&legacy_path))
            .expect("do not merge twice");

        assert!(migrated);
        assert!(merged.settings.open_at_login);
        assert_eq!(merged.notes.len(), 2);
        assert!(merged.notes.iter().any(|note| note.id == "new-note"));
        assert!(merged.notes.iter().any(|note| note.id == "old-note"));
        assert!(!migrated_again);
        assert_eq!(reloaded.notes.len(), 2);
        std::fs::remove_dir_all(&directory).expect("cleanup merge migration directory");
    }

    #[test]
    fn migration_marker_never_imports_legacy_state_a_second_time() {
        let directory = std::env::temp_dir().join(format!(
            "my-sticky-notes-migration-marker-{}",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("clock")
                .as_nanos()
        ));
        let state_path = directory.join("tauri").join("state.json");
        let legacy_path = directory.join("MyStickyNotes").join("state.json");
        std::fs::create_dir_all(legacy_path.parent().expect("legacy parent"))
            .expect("create legacy directory");
        std::fs::write(
            &legacy_path,
            r#"{"version":5,"notes":[{"id":"old-note","todos":[]}]}"#,
        )
        .expect("write legacy state");
        std::fs::create_dir_all(state_path.parent().expect("state parent"))
            .expect("create state directory");
        std::fs::write(legacy_migration_marker_path(&state_path), b"migrated\n")
            .expect("write migration marker");

        let (state, migrated) = load_or_migrate_state(&state_path, Some(&legacy_path))
            .expect("do not import legacy state twice");

        assert!(!migrated);
        assert!(state.notes.is_empty());
        assert!(!state_path.exists());
        std::fs::remove_dir_all(&directory).expect("cleanup marker directory");
    }

    #[test]
    fn atomic_state_write_replaces_existing_payload_without_temp_files() {
        let directory = std::env::temp_dir().join(format!(
            "my-sticky-notes-atomic-{}",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .expect("clock")
                .as_nanos()
        ));
        let path = directory.join("state.json");
        std::fs::create_dir_all(&directory).expect("create state directory");
        std::fs::write(&path, b"old").expect("write old payload");

        write_json_atomically(&path, b"new").expect("replace state payload");

        assert_eq!(std::fs::read(&path).expect("read new payload"), b"new");
        assert!(
            std::fs::read_dir(&directory)
                .expect("read state directory")
                .all(|entry| !entry
                    .expect("directory entry")
                    .file_name()
                    .to_string_lossy()
                    .ends_with(".tmp"))
        );
        std::fs::remove_dir_all(&directory).expect("cleanup state directory");
    }

    #[test]
    fn positions_window_at_work_area_top_right() {
        let position = top_right_position(
            PhysicalPosition::new(0, 0),
            PhysicalSize::new(1920, 1040),
            PhysicalSize::new(1120, 760),
            24,
        );
        assert_eq!(position, PhysicalPosition::new(776, 24));
    }

    #[test]
    fn positions_window_with_negative_monitor_origin() {
        let position = top_right_position(
            PhysicalPosition::new(-1920, 0),
            PhysicalSize::new(1920, 1040),
            PhysicalSize::new(1120, 760),
            24,
        );
        assert_eq!(position, PhysicalPosition::new(-1144, 24));
    }

    #[test]
    fn positions_oversized_window_inside_left_margin() {
        let position = top_right_position(
            PhysicalPosition::new(0, 0),
            PhysicalSize::new(900, 700),
            PhysicalSize::new(1120, 760),
            24,
        );
        assert_eq!(position, PhysicalPosition::new(24, 24));
    }

    #[test]
    fn sizes_notes_host_to_the_available_logical_work_area() {
        let size = notes_host_logical_size(PhysicalSize::new(1024, 560), 1.25, 24);
        assert!((size.0 - 780.8).abs() < 0.001);
        assert!((size.1 - 409.6).abs() < 0.001);
    }

    #[test]
    fn caps_notes_host_on_large_displays_without_using_fixed_dpi_pixels() {
        let size = notes_host_logical_size(PhysicalSize::new(1920, 1040), 1.0, 24);
        assert_eq!(size, (NOTES_HOST_MAX_WIDTH, NOTES_HOST_MAX_HEIGHT));
    }
}
