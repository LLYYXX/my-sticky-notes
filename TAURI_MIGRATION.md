# Tauri migration status

## Architecture decision

The migration keeps one transparent Tauri webview for all notes. It is the only
always-running renderer and is marked as a tool window so it stays out of the
taskbar. Each note is a lightweight DOM component, not a second process or a
second webview.

Settings is deliberately different: Rust creates its normal native window only
after the tray menu asks for it. Closing that window destroys the settings
webview. This isolates taskbar behaviour and keeps settings-only memory out of
the idle path.

Before the Tauri shell is constructed, a tiny standard-library loopback
listener reserves the app's single-instance endpoint. A duplicate launch sends
an activation handshake to the first process, which shows and focuses the note
window; the duplicate exits without creating another webview. This avoids a
second renderer and adds no runtime dependency.

Responsibilities are separated as follows:

- `src/state.js`: pure persisted state and viewport-safe note normalization.
- `src/views.js`: note and settings rendering only.
- `src/app.js`: interaction bindings, persistence boundary, and native command
  bridge.
- `src-tauri/src/main.rs`: state file, tray, window lifetime, work-area/DPI
  placement, topmost state, autostart, and packaging integration.
- `src-tauri/src/single_instance.rs`: cross-platform local activation handshake
  and duplicate-launch guard.

## DPI and resolution rule

The note host uses the current monitor work area and scale factor. Rust first
caps its logical width and height to the available work area, then positions
the resulting physical window at the top right. The browser computes default
note coordinates from its resulting viewport. No fixed monitor-resolution
coordinate is restored from persisted state.

State version 8 does not restore the obsolete note `height` field. Notes grow
with their Todo content by default. A `bodyHeight` is persisted only after the
user drags the lower-right resize grip.

## Verified Windows evidence

The current release executable was checked with an isolated five-note state:

- note host: `toolWindow=true`, `appWindow=false`;
- settings: separately created `appWindow=true`, `toolWindow=false`;
- tray left click restores notes; the tray menu opens settings and exits;
- a second packaged launch exits with code 0 after activating the first window;
- release build: `My Sticky Notes_0.3.0-alpha.1_x64-setup.exe` generated;
- four isolated five-note launches: 32.5–72.2 MB working set; with Settings
  open: 33.2–72.4 MB. Windows/WebView working-set residency is bimodal on this
  machine, so this range is more representative than one cold-start sample.

The enforced Windows runtime budgets are 150 MB for one note, 220 MB for five
notes, and 250 MB while Settings is open. The probe measures the application
process working set; shared OS WebView resources should also be inspected with
platform profiling before declaring a production performance SLA.

## Direct update for the trusted two-user distribution

The requested distribution model deliberately uses a small direct updater
instead of Tauri's signed updater plugin. It is inactive until the user presses
Check update. The renderer reads the latest release metadata from the fixed
`LLYYXX/my-sticky-notes` GitHub repository and passes only its tag plus asset
names to the native host. The host accepts only the expected product name,
current CPU architecture, and platform installer extension; it constructs the
canonical HTTPS GitHub release URL itself.

On Windows the host downloads the selected NSIS installer into the system temp
directory. A short-lived PowerShell launcher waits for the parent process to
exit, starts the installer with `/S`, waits for installation to finish, deletes
the temporary installer and itself, then relaunches the app. This is the same
important lifecycle separation used by standalone updaters: the process that
replaces application files is not the process being replaced. The app adds no
background update check, persistent helper executable, or updater dependency.

On macOS the host downloads and opens the matching DMG. macOS may still require
the user to approve the app or copy it into Applications; transparent in-place
replacement is intentionally not claimed for an unsigned DMG.

The repository's `Tauri Build` workflow is the pre-release quality gate. It
now runs on each `main` push and pull request for both Windows and macOS: each
job uses the locked pnpm dependency graph, runs the frontend and Rust tests,
builds the native bundle, and uploads it as a CI artifact. It does not create a
GitHub Release or require any signing secret.

`Release` is deliberately manual. It validates the matching JavaScript and
Tauri versions, builds the same Windows and macOS native bundles, and uploads
them to the GitHub Release tagged `v<package-version>`. This provides the exact
release assets consumed by the direct updater without creating releases on
ordinary pushes.

## macOS

The bundle target includes `dmg` and an `.icns` icon. A macOS runner or real
Mac still needs to verify DMG generation, LaunchAgent autostart, tray behaviour
and the dynamic settings window before macOS support can be called complete.
