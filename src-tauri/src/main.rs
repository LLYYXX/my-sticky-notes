use serde::{Deserialize, Serialize};
use std::{env, fs, path::PathBuf};
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Emitter, Manager, PhysicalPosition, PhysicalSize,
};
use tauri_plugin_autostart::{MacosLauncher, ManagerExt};

const STATE_VERSION: u16 = 7;

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
    height: Option<f64>,
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
    if let Some(state) = read_json(&state_path(&app)?)? {
        return Ok(state);
    }
    if configured_data_dir().is_none() {
        if let Some(state) = read_json(&legacy_state_path())? {
            return Ok(state);
        }
    }
    Ok(AppState::default())
}

#[tauri::command]
fn save_state(app: AppHandle, state: AppState) -> Result<(), String> {
    let path = state_path(&app)?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    let payload = serde_json::to_vec_pretty(&state).map_err(|error| error.to_string())?;
    fs::write(path, payload).map_err(|error| error.to_string())
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
fn set_settings_visibility(app: AppHandle, visible: bool) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window
            .set_skip_taskbar(!visible)
            .map_err(|error| error.to_string())?;
        if visible {
            window.show().map_err(|error| error.to_string())?;
            window.set_focus().map_err(|error| error.to_string())?;
        } else {
            position_notes_window(&app)?;
        }
    }
    Ok(())
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

fn read_json(path: &PathBuf) -> Result<Option<AppState>, String> {
    if !path.exists() {
        return Ok(None);
    }
    let payload = fs::read_to_string(path).map_err(|error| error.to_string())?;
    let mut state: AppState = serde_json::from_str(&payload).map_err(|error| error.to_string())?;
    state.version = STATE_VERSION;
    Ok(Some(state))
}

fn state_path(app: &AppHandle) -> Result<PathBuf, String> {
    let data_dir = if let Some(path) = configured_data_dir() {
        path
    } else {
        app.path().app_data_dir().map_err(|error| error.to_string())?
    };
    Ok(data_dir.join("state.json"))
}

fn legacy_state_path() -> PathBuf {
    env::var_os("LOCALAPPDATA")
        .map(|value| PathBuf::from(value).join("MyStickyNotes"))
        .unwrap_or_else(|| PathBuf::from("."))
        .join("state.json")
}

fn configured_data_dir() -> Option<PathBuf> {
    env::var_os("MY_STICKY_NOTES_DATA_DIR").map(PathBuf::from)
}

fn show_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.show();
        let _ = window.set_focus();
    }
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
    let window_size = window.outer_size().map_err(|error| error.to_string())?;
    let position = top_right_position(work_area.position, work_area.size, window_size, 24);
    window
        .set_position(position)
        .map_err(|error| error.to_string())
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

fn build_tray(app: &AppHandle) -> tauri::Result<()> {
    let show = MenuItem::with_id(app, "show", "显示全部", true, None::<&str>)?;
    let settings = MenuItem::with_id(app, "settings", "设置", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "退出应用", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &settings, &quit])?;
    let mut builder = TrayIconBuilder::new()
        .menu(&menu)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "quit" => app.exit(0),
            "show" => {
                show_main_window(app);
                let _ = app.emit("show-notes", ());
            }
            "settings" => {
                show_main_window(app);
                let _ = app.emit("open-settings", ());
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
                let _ = tray.app_handle().emit("show-notes", ());
            }
        });
    if let Some(icon) = app.default_window_icon() {
        builder = builder.icon(icon.clone());
    }
    builder.build(app)?;
    Ok(())
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            Some(vec![]),
        ))
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            build_tray(app.handle())?;
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
            set_settings_visibility,
            set_always_on_top
        ])
        .run(tauri::generate_context!())
        .expect("error while running My Sticky Notes");
}

fn main() {
    run();
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
}
