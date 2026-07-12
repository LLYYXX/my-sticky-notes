use serde::Deserialize;
use std::{
    env, fs,
    path::{Path, PathBuf},
    process::Command,
    thread,
    time::Duration,
};
use tauri::AppHandle;

const RELEASE_DOWNLOAD_BASE: &str = "https://github.com/LLYYXX/my-sticky-notes/releases/download";
const UPDATE_EXIT_DELAY: Duration = Duration::from_millis(250);
const WINDOWS_LAUNCHER_SCRIPT: &str = r#"
param([int]$ParentPid, [string]$InstallerPath, [string]$RelaunchPath, [string]$SelfPath)
$ErrorActionPreference = 'Stop'
$parent = Get-Process -Id $ParentPid -ErrorAction SilentlyContinue
if ($null -ne $parent) { $parent.WaitForExit() }
$installer = Start-Process -FilePath $InstallerPath -ArgumentList @('/S') -PassThru
$installer.WaitForExit()
if (Test-Path -LiteralPath $RelaunchPath) { Start-Process -FilePath $RelaunchPath }
Remove-Item -LiteralPath $InstallerPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $SelfPath -Force -ErrorAction SilentlyContinue
"#;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct UpdateRequest {
    tag: String,
    asset_names: Vec<String>,
}

#[tauri::command]
pub async fn download_and_install_update(app: AppHandle, request: UpdateRequest) -> Result<bool, String> {
    tauri::async_runtime::spawn_blocking(move || install_update(app, request))
        .await
        .map_err(|error| format!("update worker stopped unexpectedly: {error}"))?
}

fn install_update(app: AppHandle, request: UpdateRequest) -> Result<bool, String> {
    let asset_name = select_update_asset(&request)?;
    let destination = update_destination(asset_name)?;
    let source = release_asset_url(&request.tag, asset_name)?;
    download_asset(&source, &destination)?;
    let relaunch_path = env::current_exe().map_err(|error| error.to_string())?;
    launch_installer_after_parent_exits(&destination, &relaunch_path, std::process::id())?;
    schedule_app_exit(app);
    Ok(true)
}

fn select_update_asset(request: &UpdateRequest) -> Result<&str, String> {
    if !is_valid_tag(&request.tag) {
        return Err("update release tag is invalid".to_owned());
    }
    let candidates = request
        .asset_names
        .iter()
        .filter(|name| asset_matches_current_platform(name))
        .collect::<Vec<_>>();
    match candidates.as_slice() {
        [asset_name] => Ok(asset_name.as_str()),
        [] => Err("the release has no installer for this platform".to_owned()),
        _ => Err("the release has ambiguous installers for this platform".to_owned()),
    }
}

fn asset_matches_current_platform(name: &str) -> bool {
    if !is_valid_asset_name(name) {
        return false;
    }
    let lower = name.to_ascii_lowercase();
    let matches_product = lower.starts_with("my sticky notes_")
        || lower.starts_with("my.sticky.notes_");
    let matches_architecture = architecture_tokens()
        .iter()
        .any(|token| lower.contains(token));
    matches_product && matches_architecture && platform_extension_matches(&lower)
}

#[cfg(target_os = "windows")]
fn platform_extension_matches(name: &str) -> bool {
    name.ends_with("-setup.exe")
}

#[cfg(target_os = "macos")]
fn platform_extension_matches(name: &str) -> bool {
    name.ends_with(".dmg")
}

#[cfg(not(any(target_os = "windows", target_os = "macos")))]
fn platform_extension_matches(_name: &str) -> bool {
    false
}

fn architecture_tokens() -> &'static [&'static str] {
    match env::consts::ARCH {
        "x86_64" => &["_x64", "_x86_64"],
        "aarch64" => &["_aarch64"],
        _ => &[],
    }
}

fn is_valid_tag(tag: &str) -> bool {
    let normalized = tag.strip_prefix('v').unwrap_or(tag);
    !normalized.is_empty()
        && normalized.len() <= 80
        && normalized
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'-'))
}

fn is_valid_asset_name(name: &str) -> bool {
    !name.is_empty()
        && name.len() <= 200
        && name.bytes().all(|byte| {
            byte.is_ascii_alphanumeric() || matches!(byte, b'.' | b'_' | b'-' | b' ')
        })
}

fn release_asset_url(tag: &str, asset_name: &str) -> Result<String, String> {
    if !is_valid_tag(tag) || !is_valid_asset_name(asset_name) {
        return Err("update asset is invalid".to_owned());
    }
    Ok(format!(
        "{RELEASE_DOWNLOAD_BASE}/{}/{}",
        encode_segment(tag),
        encode_segment(asset_name)
    ))
}

fn encode_segment(value: &str) -> String {
    value
        .bytes()
        .flat_map(|byte| match byte {
            b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'.' | b'-' | b'_' => {
                vec![byte as char]
            }
            _ => format!("%{byte:02X}").chars().collect(),
        })
        .collect()
}

fn update_destination(asset_name: &str) -> Result<PathBuf, String> {
    let directory = env::temp_dir().join("my-sticky-notes-update");
    fs::create_dir_all(&directory).map_err(|error| error.to_string())?;
    let destination = directory.join(asset_name);
    if destination.exists() {
        fs::remove_file(&destination).map_err(|error| error.to_string())?;
    }
    Ok(destination)
}

fn download_asset(source: &str, destination: &Path) -> Result<(), String> {
    let curl = if cfg!(target_os = "windows") {
        "curl.exe"
    } else {
        "/usr/bin/curl"
    };
    let mut command = Command::new(curl);
    command
        .args([
            "--fail",
            "--location",
            "--proto",
            "=https",
            "--connect-timeout",
            "15",
            "--max-time",
            "180",
            "--retry",
            "2",
            "--retry-max-time",
            "180",
        ]);
    if cfg!(target_os = "windows") {
        command.arg("--ssl-no-revoke");
    }
    let status = command
        .arg("--output")
        .arg(destination)
        .arg(source)
        .status()
        .map_err(|error| format!("unable to start the system downloader: {error}"))?;
    if status.success() {
        Ok(())
    } else {
        let _ = fs::remove_file(destination);
        Err(format!("update download failed with status {status}"))
    }
}

#[cfg(target_os = "windows")]
fn launch_installer_after_parent_exits(
    path: &Path,
    relaunch_path: &Path,
    parent_pid: u32,
) -> Result<(), String> {
    let launcher_path = path.with_file_name(format!(
        ".my-sticky-notes-update-launcher-{parent_pid}.ps1"
    ));
    fs::write(&launcher_path, WINDOWS_LAUNCHER_SCRIPT).map_err(|error| error.to_string())?;
    let launch_result = Command::new("powershell.exe")
        .args([
            "-NoProfile",
            "-NonInteractive",
            "-WindowStyle",
            "Hidden",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
        ])
        .arg(&launcher_path)
        .arg(parent_pid.to_string())
        .arg(path)
        .arg(relaunch_path)
        .arg(&launcher_path)
        .spawn()
        .map(|_| ())
        .map_err(|error| format!("unable to start the update launcher: {error}"));
    if launch_result.is_err() {
        let _ = fs::remove_file(&launcher_path);
    }
    launch_result
}

#[cfg(target_os = "macos")]
fn launch_installer_after_parent_exits(
    path: &Path,
    _relaunch_path: &Path,
    _parent_pid: u32,
) -> Result<(), String> {
    Command::new("open")
        .arg(path)
        .spawn()
        .map(|_| ())
        .map_err(|error| format!("unable to open the update disk image: {error}"))
}

#[cfg(not(any(target_os = "windows", target_os = "macos")))]
fn launch_installer_after_parent_exits(
    _path: &Path,
    _relaunch_path: &Path,
    _parent_pid: u32,
) -> Result<(), String> {
    Err("direct installation is unsupported on this platform".to_owned())
}

fn schedule_app_exit(app: AppHandle) {
    thread::spawn(move || {
        thread::sleep(UPDATE_EXIT_DELAY);
        app.exit(0);
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_only_simple_release_paths() {
        assert!(is_valid_tag("v0.3.0-alpha.0"));
        assert!(is_valid_asset_name("My Sticky Notes_0.3.0_x64-setup.exe"));
        assert!(!is_valid_tag("v0.3.0/../../other"));
        assert!(!is_valid_asset_name("../installer.exe"));
    }

    #[test]
    fn release_urls_are_canonical_and_percent_encoded() {
        let url = release_asset_url("v0.3.0", "My Sticky Notes_0.3.0_x64-setup.exe")
            .expect("valid release URL");
        assert_eq!(
            url,
            "https://github.com/LLYYXX/my-sticky-notes/releases/download/v0.3.0/My%20Sticky%20Notes_0.3.0_x64-setup.exe"
        );
    }

    #[test]
    fn current_platform_filter_rejects_unrelated_asset_names() {
        assert!(!asset_matches_current_platform("source.zip"));
        assert!(!asset_matches_current_platform("Other App_0.3.0_x64-setup.exe"));
    }

    #[cfg(target_os = "windows")]
    #[test]
    fn accepts_the_published_dotted_windows_installer_name() {
        assert!(asset_matches_current_platform(
            "My.Sticky.Notes_0.3.0_x64-setup.exe"
        ));
    }

    #[cfg(target_os = "windows")]
    #[test]
    fn windows_launcher_waits_for_the_parent_before_silent_installation() {
        assert!(WINDOWS_LAUNCHER_SCRIPT.contains("WaitForExit"));
        assert!(WINDOWS_LAUNCHER_SCRIPT.contains("-ArgumentList @('/S')"));
        assert!(WINDOWS_LAUNCHER_SCRIPT.contains("$installer.WaitForExit()"));
        assert!(WINDOWS_LAUNCHER_SCRIPT.contains("$RelaunchPath"));
        assert!(WINDOWS_LAUNCHER_SCRIPT.contains("Remove-Item -LiteralPath $InstallerPath"));
        assert!(WINDOWS_LAUNCHER_SCRIPT.contains("Remove-Item -LiteralPath $SelfPath"));
    }

    #[cfg(target_os = "windows")]
    #[test]
    fn windows_launcher_runs_an_isolated_replacement_cycle() {
        let directory = std::env::temp_dir().join(format!(
            "my-sticky-notes-update-cycle-{}",
            std::process::id()
        ));
        let installer = directory.join("installer.cmd");
        let relaunch = directory.join("relaunch.cmd");
        let installed_marker = directory.join("installed.txt");
        let relaunched_marker = directory.join("relaunched.txt");
        let parent_pid = 999_999_999;
        std::fs::create_dir_all(&directory).expect("create update test directory");
        std::fs::write(
            &installer,
            format!("@echo off\r\necho installed > \"{}\"\r\n", installed_marker.display()),
        )
        .expect("write mock installer");
        std::fs::write(
            &relaunch,
            format!("@echo off\r\necho relaunched > \"{}\"\r\n", relaunched_marker.display()),
        )
        .expect("write mock relauncher");

        launch_installer_after_parent_exits(&installer, &relaunch, parent_pid)
            .expect("start isolated launcher");

        let launcher = directory.join(format!(
            ".my-sticky-notes-update-launcher-{parent_pid}.ps1"
        ));
        let deadline = std::time::Instant::now() + Duration::from_secs(10);
        while std::time::Instant::now() < deadline
            && (!installed_marker.exists()
                || !relaunched_marker.exists()
                || installer.exists()
                || launcher.exists())
        {
            thread::sleep(Duration::from_millis(50));
        }

        assert!(installed_marker.exists(), "mock installer should run");
        assert!(relaunched_marker.exists(), "mock app should restart");
        assert!(!installer.exists(), "temporary installer should be removed");
        assert!(!launcher.exists(), "temporary launcher should remove itself");
        std::fs::remove_dir_all(&directory).expect("cleanup update test directory");
    }
}
