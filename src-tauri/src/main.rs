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
    sync::{
        atomic::{AtomicU64, Ordering},
        Mutex,
    },
};
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, LogicalSize, Manager, PhysicalPosition, PhysicalSize, WebviewUrl, WebviewWindow,
    WebviewWindowBuilder, WindowEvent,
};
use tauri_plugin_autostart::{MacosLauncher, ManagerExt};

const STATE_VERSION: u16 = 9;
const LEGACY_APP_DIRECTORY: &str = "MyStickyNotes";
const LEGACY_MIGRATION_MARKER: &str = ".legacy-tk-state-v1";
const NOTE_LABEL_PREFIX: &str = "note-";
const NOTE_MARGIN: i32 = 24;
const NOTE_CASCADE_X: i32 = 28;
const NOTE_CASCADE_Y: i32 = 32;
const NOTE_MIN_WIDTH: f64 = 280.0;
const NOTE_MAX_WIDTH: f64 = 720.0;
const NOTE_HEADER_HEIGHT: f64 = 42.0;
const NOTE_MIN_BODY_HEIGHT: f64 = 128.0;
const LEGACY_HOST_MAX_WIDTH: f64 = 1120.0;
const LEGACY_HOST_MAX_HEIGHT: f64 = 760.0;
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
    #[serde(default = "default_note_width")]
    width: f64,
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

struct AppStateStore(Mutex<AppState>);

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            open_at_login: false,
            language: default_language(),
        }
    }
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            version: STATE_VERSION,
            settings: AppSettings::default(),
            notes: vec![default_note()],
        }
    }
}

fn state_version() -> u16 {
    STATE_VERSION
}

fn default_language() -> String {
    "zh-CN".to_owned()
}

fn default_color() -> String {
    "yellow".to_owned()
}

fn default_note_id() -> String {
    "note-default".to_owned()
}

fn default_todo_id() -> String {
    "todo-default".to_owned()
}

fn default_note_width() -> f64 {
    340.0
}

fn default_note() -> Note {
    Note {
        id: default_note_id(),
        color: default_color(),
        pinned: false,
        collapsed: false,
        x: None,
        y: None,
        width: default_note_width(),
        body_height: None,
        todos: Vec::new(),
    }
}

#[tauri::command]
fn load_state(app: AppHandle) -> Result<AppState, String> {
    snapshot_state(&app)
}

#[tauri::command]
fn save_note(app: AppHandle, note: Note) -> Result<AppState, String> {
    mutate_state(&app, |state| {
        let note = normalize_note(note);
        if let Some(existing) = state.notes.iter_mut().find(|current| current.id == note.id) {
            *existing = note;
        } else {
            state.notes.push(note);
        }
        Ok(())
    })
}

#[tauri::command]
fn create_note(app: AppHandle, note: Note) -> Result<AppState, String> {
    save_note(app, note)
}

#[tauri::command]
fn delete_note(app: AppHandle, note_id: String) -> Result<AppState, String> {
    mutate_state(&app, |state| {
        state.notes.retain(|note| note.id != note_id);
        ensure_note_exists(state);
        Ok(())
    })
}

#[tauri::command]
fn save_settings(app: AppHandle, settings: AppSettings) -> Result<AppState, String> {
    let state = mutate_state(&app, |state| {
        state.settings = normalize_settings(settings);
        Ok(())
    })?;
    reload_note_windows(&app);
    Ok(state)
}

#[tauri::command]
fn resize_note_preview(
    app: AppHandle,
    note_id: String,
    width: f64,
    body_height: f64,
) -> Result<(), String> {
    let note = Note {
        id: note_id,
        width,
        body_height: Some(body_height),
        ..default_note()
    };
    let window = note_window(&app, &note.id)
        .ok_or_else(|| "note window is no longer available".to_owned())?;
    window
        .set_size(LogicalSize::new(note_width(&note), note_window_height(&note)))
        .map_err(|error| error.to_string())
}

#[tauri::command]
fn fit_note_window(app: AppHandle, note_id: String, height: f64) -> Result<(), String> {
    let state = snapshot_state(&app)?;
    let note = state
        .notes
        .iter()
        .find(|note| note.id == note_id)
        .ok_or_else(|| "note does not exist".to_owned())?;
    let window = note_window(&app, &note_id)
        .ok_or_else(|| "note window is no longer available".to_owned())?;
    window
        .set_size(LogicalSize::new(note_width(note), height.max(NOTE_HEADER_HEIGHT)))
        .map_err(|error| error.to_string())
}

#[tauri::command]
fn start_note_dragging(window: WebviewWindow) -> Result<(), String> {
    if !window.label().starts_with(NOTE_LABEL_PREFIX) {
        return Err("only sticky note windows can be dragged".to_owned());
    }
    window.start_dragging().map_err(|error| error.to_string())
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
    let applied = autostart.is_enabled().map_err(|error| error.to_string())?;
    mutate_state(&app, |state| {
        state.settings.open_at_login = applied;
        Ok(())
    })?;
    Ok(applied)
}

fn snapshot_state(app: &AppHandle) -> Result<AppState, String> {
    app.state::<AppStateStore>()
        .0
        .lock()
        .map_err(|_| "state lock is unavailable".to_owned())
        .map(|state| state.clone())
}

fn mutate_state(
    app: &AppHandle,
    change: impl FnOnce(&mut AppState) -> Result<(), String>,
) -> Result<AppState, String> {
    let snapshot = {
        let store = app.state::<AppStateStore>();
        let mut state = store
            .0
            .lock()
            .map_err(|_| "state lock is unavailable".to_owned())?;
        change(&mut state)?;
        normalize_state(&mut state);
        let snapshot = state.clone();
        write_state(app, &snapshot)?;
        snapshot
    };
    sync_note_windows(app, &snapshot)?;
    Ok(snapshot)
}

fn normalize_state(state: &mut AppState) {
    state.version = STATE_VERSION;
    state.settings = normalize_settings(state.settings.clone());
    state.notes = state
        .notes
        .drain(..)
        .map(normalize_note)
        .collect::<Vec<_>>();
    ensure_note_exists(state);
}

fn normalize_settings(mut settings: AppSettings) -> AppSettings {
    if settings.language != "en" {
        settings.language = default_language();
    }
    settings
}

fn normalize_note(mut note: Note) -> Note {
    if note.id.trim().is_empty() {
        note.id = default_note_id();
    }
    note.width = note.width.clamp(NOTE_MIN_WIDTH, NOTE_MAX_WIDTH);
    note.body_height = note.body_height.map(|height| height.max(NOTE_MIN_BODY_HEIGHT));
    note
}

fn ensure_note_exists(state: &mut AppState) {
    if state.notes.is_empty() {
        state.notes.push(default_note());
    }
}

fn read_json(path: &Path) -> Result<Option<AppState>, String> {
    if !path.exists() {
        return Ok(None);
    }
    let payload = fs::read_to_string(path).map_err(|error| error.to_string())?;
    serde_json::from_str(&payload)
        .map(Some)
        .map_err(|error| error.to_string())
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
            return Ok((current.map(|state| merge_legacy_state(state, legacy.clone())).unwrap_or(legacy), true));
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
    current
}

fn load_initial_state(app: &AppHandle) -> Result<(AppState, bool), String> {
    let path = state_path(app)?;
    let legacy_path = configured_data_dir().is_none().then(legacy_state_path).flatten();
    let (mut state, imported_legacy) = load_or_migrate_state(&path, legacy_path.as_deref())?;
    let previous_version = state.version;
    let migrated_host_layout = !imported_legacy && previous_version < STATE_VERSION;
    if migrated_host_layout {
        migrate_legacy_host_coordinates(app, &mut state)?;
    }
    assign_default_positions(app, &mut state)?;
    normalize_state(&mut state);
    if imported_legacy || migrated_host_layout || !path.exists() {
        write_state(app, &state)?;
    }
    if imported_legacy {
        write_json_atomically(&legacy_migration_marker_path(&path), b"migrated\n")?;
    }
    Ok((state, imported_legacy))
}

fn migrate_legacy_host_coordinates(app: &AppHandle, state: &mut AppState) -> Result<(), String> {
    let monitor = app
        .primary_monitor()
        .map_err(|error| error.to_string())?;
    let Some(monitor) = monitor else {
        return Ok(());
    };
    let work_area = monitor.work_area();
    let scale = monitor.scale_factor().max(0.01);
    let (host_width, host_height) = legacy_host_logical_size(work_area.size, scale);
    let host_width_physical = (host_width * scale).round() as i32;
    let host_height_physical = (host_height * scale).round() as i32;
    let host_origin = legacy_host_origin(work_area.position, work_area.size, host_width_physical, host_height_physical);
    for note in &mut state.notes {
        if let (Some(x), Some(y)) = (note.x, note.y) {
            note.x = Some(host_origin.x as f64 + x * scale);
            note.y = Some(host_origin.y as f64 + y * scale);
        }
    }
    Ok(())
}

fn assign_default_positions(app: &AppHandle, state: &mut AppState) -> Result<(), String> {
    let monitor = app
        .primary_monitor()
        .map_err(|error| error.to_string())?;
    let Some(monitor) = monitor else {
        return Ok(());
    };
    let work_area = monitor.work_area();
    let scale = monitor.scale_factor().max(0.01);
    for (index, note) in state.notes.iter_mut().enumerate() {
        if note.x.is_none() || note.y.is_none() {
            let position = default_note_position(work_area.position, work_area.size, scale, index, note);
            note.x = Some(position.x as f64);
            note.y = Some(position.y as f64);
        }
    }
    Ok(())
}

fn legacy_host_logical_size(work_area_size: PhysicalSize<u32>, scale_factor: f64) -> (f64, f64) {
    let safe_width = work_area_size.width.saturating_sub((NOTE_MARGIN * 2) as u32) as f64;
    let safe_height = work_area_size.height.saturating_sub((NOTE_MARGIN * 2) as u32) as f64;
    let scale = scale_factor.max(0.01);
    (
        (safe_width / scale).min(LEGACY_HOST_MAX_WIDTH),
        (safe_height / scale).min(LEGACY_HOST_MAX_HEIGHT),
    )
}

fn legacy_host_origin(
    work_area_position: PhysicalPosition<i32>,
    work_area_size: PhysicalSize<u32>,
    host_width: i32,
    _host_height: i32,
) -> PhysicalPosition<i32> {
    let right = work_area_position.x + work_area_size.width as i32;
    PhysicalPosition::new(
        (right - host_width - NOTE_MARGIN).max(work_area_position.x + NOTE_MARGIN),
        work_area_position.y + NOTE_MARGIN,
    )
}

fn default_note_position(
    work_area_position: PhysicalPosition<i32>,
    work_area_size: PhysicalSize<u32>,
    scale: f64,
    index: usize,
    note: &Note,
) -> PhysicalPosition<i32> {
    let width = (note_width(note) * scale).round() as i32;
    let offset_x = NOTE_CASCADE_X.saturating_mul(index as i32);
    let offset_y = NOTE_CASCADE_Y.saturating_mul(index as i32);
    let right = work_area_position.x + work_area_size.width as i32;
    PhysicalPosition::new(
        (right - width - NOTE_MARGIN - offset_x).max(work_area_position.x + NOTE_MARGIN),
        work_area_position.y + NOTE_MARGIN + offset_y,
    )
}

fn note_window_height(note: &Note) -> f64 {
    if note.collapsed {
        return NOTE_HEADER_HEIGHT;
    }
    let automatic_body_height = (note.todos.len() as f64 * 33.0 + 56.0).max(NOTE_MIN_BODY_HEIGHT);
    NOTE_HEADER_HEIGHT + note.body_height.unwrap_or(automatic_body_height)
}

fn note_width(note: &Note) -> f64 {
    note.width.clamp(NOTE_MIN_WIDTH, NOTE_MAX_WIDTH)
}

fn note_label(note_id: &str) -> String {
    let mut label = String::from(NOTE_LABEL_PREFIX);
    for byte in note_id.as_bytes() {
        use std::fmt::Write as _;
        let _ = write!(label, "{byte:02x}");
    }
    label
}

fn note_window(app: &AppHandle, note_id: &str) -> Option<WebviewWindow> {
    app.get_webview_window(&note_label(note_id))
}

fn encode_query_component(value: &str) -> String {
    value
        .bytes()
        .flat_map(|byte| match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'_' | b'.' | b'~' => {
                vec![byte as char]
            }
            _ => format!("%{byte:02X}").chars().collect(),
        })
        .collect()
}

fn sync_note_windows(app: &AppHandle, state: &AppState) -> Result<(), String> {
    let desired_labels = state
        .notes
        .iter()
        .map(|note| note_label(&note.id))
        .collect::<HashSet<_>>();
    for (label, window) in app.webview_windows() {
        if label.starts_with(NOTE_LABEL_PREFIX) && !desired_labels.contains(&label) {
            window.destroy().map_err(|error| error.to_string())?;
        }
    }
    for note in &state.notes {
        if let Some(window) = note_window(app, &note.id) {
            configure_note_window(&window, note)?;
        } else {
            create_note_window(app, note)?;
        }
    }
    Ok(())
}

fn create_note_window(app: &AppHandle, note: &Note) -> Result<(), String> {
    let note_id = note.id.clone();
    let position = PhysicalPosition::new(
        note.x.unwrap_or(NOTE_MARGIN as f64).round() as i32,
        note.y.unwrap_or(NOTE_MARGIN as f64).round() as i32,
    );
    let app_for_events = app.clone();
    let label = note_label(&note.id);
    let url = WebviewUrl::App(format!("index.html?note={}", encode_query_component(&note.id)).into());
    let window = WebviewWindowBuilder::new(app, label, url)
        .title("My Sticky Notes")
        .decorations(false)
        .transparent(true)
        .resizable(false)
        .skip_taskbar(true)
        .always_on_top(note.pinned)
        .inner_size(note_width(note), note_window_height(note))
        .build()
        .map_err(|error| error.to_string())?;
    window
        .set_position(position)
        .map_err(|error| error.to_string())?;
    window.on_window_event(move |event| {
        if let WindowEvent::Moved(position) = event {
            remember_note_position(&app_for_events, &note_id, position.clone());
        }
    });
    configure_note_window(&window, note)
}

fn configure_note_window(window: &WebviewWindow, note: &Note) -> Result<(), String> {
    window
        .set_skip_taskbar(true)
        .map_err(|error| error.to_string())?;
    window
        .set_always_on_top(note.pinned)
        .map_err(|error| error.to_string())?;
    ensure_notes_taskbar_style(window)
}

fn remember_note_position(app: &AppHandle, note_id: &str, position: PhysicalPosition<i32>) {
    let snapshot = {
        let store = app.state::<AppStateStore>();
        let Ok(mut state) = store.0.lock() else {
            return;
        };
        let Some(note) = state.notes.iter_mut().find(|note| note.id == note_id) else {
            return;
        };
        let next_x = position.x as f64;
        let next_y = position.y as f64;
        if note.x == Some(next_x) && note.y == Some(next_y) {
            return;
        }
        note.x = Some(next_x);
        note.y = Some(next_y);
        state.clone()
    };
    let _ = write_state(app, &snapshot);
}

fn reload_note_windows(app: &AppHandle) {
    for (label, window) in app.webview_windows() {
        if label.starts_with(NOTE_LABEL_PREFIX) {
            let _ = window.eval("window.location.reload()");
        }
    }
}

fn write_state(app: &AppHandle, state: &AppState) -> Result<(), String> {
    let payload = serde_json::to_vec_pretty(state).map_err(|error| error.to_string())?;
    write_json_atomically(&state_path(app)?, &payload)
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
        temporary_file.sync_all().map_err(|error| error.to_string())?;
        drop(temporary_file);
        fs::rename(&temporary_path, path).map_err(|error| error.to_string())
    })();
    if write_result.is_err() {
        let _ = fs::remove_file(&temporary_path);
    }
    write_result
}

fn state_path(app: &AppHandle) -> Result<PathBuf, String> {
    let data_dir = configured_data_dir()
        .unwrap_or(app.path().app_data_dir().map_err(|error| error.to_string())?);
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

#[cfg(windows)]
fn ensure_notes_taskbar_style(window: &WebviewWindow) -> Result<(), String> {
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
fn ensure_notes_taskbar_style(_window: &WebviewWindow) -> Result<(), String> {
    Ok(())
}

fn show_note_windows(app: &AppHandle) {
    let mut last_window = None;
    for (label, window) in app.webview_windows() {
        if label.starts_with(NOTE_LABEL_PREFIX) {
            let _ = window.unminimize();
            let _ = window.show();
            last_window = Some(window);
        }
    }
    if let Some(window) = last_window {
        let _ = window.set_focus();
    }
}

fn show_settings_window(app: &AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("settings") {
        window.show().map_err(|error| error.to_string())?;
        window.set_focus().map_err(|error| error.to_string())?;
        return Ok(());
    }
    WebviewWindowBuilder::new(app, "settings", WebviewUrl::App("index.html?settings=1".into()))
        .title("桌面便利贴设置")
        .inner_size(720.0, 560.0)
        .min_inner_size(520.0, 420.0)
        .resizable(true)
        .center()
        .build()
        .map(|_| ())
        .map_err(|error| error.to_string())
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
            "show" => show_note_windows(app),
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
                show_note_windows(tray.app_handle());
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
            let (state, imported_legacy) = load_initial_state(app.handle())?;
            if imported_legacy && state.settings.open_at_login {
                let _ = app.autolaunch().enable();
            }
            app.manage(AppStateStore(Mutex::new(state.clone())));
            build_tray(app.handle())?;
            sync_note_windows(app.handle(), &state)?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            load_state,
            save_note,
            create_note,
            delete_note,
            save_settings,
            resize_note_preview,
            fit_note_window,
            start_note_dragging,
            is_open_at_login_enabled,
            set_open_at_login,
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
    fn legacy_state_is_still_deserialized_without_a_title_or_height() {
        let payload = r#"{"version":5,"settings":{"open_at_login":true,"language":"en"},"notes":[{"id":"legacy-note","color":"navy","x":140,"y":160,"width":330,"height":360,"todos":[{"id":"todo-1","text":"wrap long todo","completed":true}]}]}"#;
        let state: AppState = serde_json::from_str(payload).expect("valid state");
        assert_eq!(state.version, 5);
        assert!(state.settings.open_at_login);
        assert_eq!(state.notes[0].id, "legacy-note");
        assert_eq!(state.notes[0].body_height, None);
        assert!(state.notes[0].todos[0].completed);
    }

    #[test]
    fn each_note_uses_a_stable_safe_native_window_label() {
        assert_eq!(note_label("note-a/b"), "note-6e6f74652d612f62");
        assert!(note_label("中文").starts_with(NOTE_LABEL_PREFIX));
    }

    #[test]
    fn legacy_host_coordinates_become_screen_coordinates() {
        let origin = legacy_host_origin(
            PhysicalPosition::new(0, 0),
            PhysicalSize::new(1920, 1040),
            1120,
            760,
        );
        assert_eq!(origin, PhysicalPosition::new(776, 24));
        assert_eq!(origin.x as f64 + 140.0, 916.0);
        assert_eq!(origin.y as f64 + 160.0, 184.0);
    }

    #[test]
    fn default_position_starts_at_the_monitor_top_right() {
        let note = default_note();
        let position = default_note_position(
            PhysicalPosition::new(0, 0),
            PhysicalSize::new(1920, 1040),
            1.0,
            0,
            &note,
        );
        assert_eq!(position, PhysicalPosition::new(1556, 24));
    }

    #[test]
    fn migration_marker_never_imports_legacy_state_twice() {
        let directory = std::env::temp_dir().join(format!(
            "my-sticky-notes-migration-marker-{}",
            SystemTime::now().duration_since(UNIX_EPOCH).expect("clock").as_nanos()
        ));
        let state_path = directory.join("tauri").join("state.json");
        let legacy_path = directory.join("MyStickyNotes").join("state.json");
        std::fs::create_dir_all(legacy_path.parent().expect("legacy parent"))
            .expect("create legacy directory");
        std::fs::write(&legacy_path, r#"{"version":5,"notes":[{"id":"old-note","todos":[]}]}"#)
            .expect("write legacy state");
        std::fs::create_dir_all(state_path.parent().expect("state parent"))
            .expect("create state directory");
        std::fs::write(legacy_migration_marker_path(&state_path), b"migrated\n")
            .expect("write migration marker");
        let (state, migrated) = load_or_migrate_state(&state_path, Some(&legacy_path))
            .expect("do not import legacy state twice");
        assert!(!migrated);
        assert_eq!(state.notes.len(), 1);
        assert_ne!(state.notes[0].id, "old-note");
        std::fs::remove_dir_all(&directory).expect("cleanup marker directory");
    }

    #[test]
    fn merges_legacy_notes_by_id_once() {
        let current: AppState = serde_json::from_str(
            r#"{"version":8,"notes":[{"id":"new-note","todos":[]}],"settings":{"language":"zh-CN"}}"#,
        )
        .expect("current state");
        let legacy: AppState = serde_json::from_str(
            r#"{"version":5,"settings":{"open_at_login":true,"language":"en"},"notes":[{"id":"old-note","todos":[]}]}"#,
        )
        .expect("legacy state");
        let merged = merge_legacy_state(current, legacy);
        assert_eq!(merged.notes.len(), 2);
        assert!(merged.settings.open_at_login);
        assert!(merged.notes.iter().any(|note| note.id == "old-note"));
    }

    #[test]
    fn atomic_state_write_replaces_existing_payload_without_temp_files() {
        let directory = std::env::temp_dir().join(format!(
            "my-sticky-notes-atomic-{}",
            SystemTime::now().duration_since(UNIX_EPOCH).expect("clock").as_nanos()
        ));
        let path = directory.join("state.json");
        std::fs::create_dir_all(&directory).expect("create state directory");
        std::fs::write(&path, b"old").expect("write old payload");
        write_json_atomically(&path, b"new").expect("replace state payload");
        assert_eq!(std::fs::read(&path).expect("read new payload"), b"new");
        assert!(std::fs::read_dir(&directory)
            .expect("read state directory")
            .all(|entry| !entry.expect("directory entry").file_name().to_string_lossy().ends_with(".tmp")));
        std::fs::remove_dir_all(&directory).expect("cleanup state directory");
    }

    #[test]
    fn note_height_is_header_only_when_collapsed() {
        let mut note = default_note();
        note.collapsed = true;
        assert_eq!(note_window_height(&note), NOTE_HEADER_HEIGHT);
    }
}
