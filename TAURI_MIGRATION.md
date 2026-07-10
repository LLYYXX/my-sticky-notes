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

Responsibilities are separated as follows:

- `src/state.js`: pure persisted state and viewport-safe note normalization.
- `src/views.js`: note and settings rendering only.
- `src/app.js`: interaction bindings, persistence boundary, and native command
  bridge.
- `src-tauri/src/main.rs`: state file, tray, window lifetime, work-area/DPI
  placement, topmost state, autostart, and packaging integration.

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
- release build: `My Sticky Notes_0.3.0-alpha.0_x64-setup.exe` generated;
- five-note working set: 70.9 MB; settings-open working set: 71.1 MB.

The enforced Windows runtime budgets are 150 MB for one note, 220 MB for five
notes, and 250 MB while Settings is open. The probe measures the application
process working set; shared OS WebView resources should also be inspected with
platform profiling before declaring a production performance SLA.

## Remaining release prerequisite: signed updater

Tauri's official updater verifies signed artifacts before installing them. To
enable the requested automatic GitHub Release installation, the release owner
must provide a persistent updater signing key, add its private part to GitHub
Actions as `TAURI_SIGNING_PRIVATE_KEY`, and publish the matching signed
`latest.json` plus updater artifacts. The public key can then be committed in
`tauri.conf.json` and the updater plugin can be enabled without weakening
installer verification.

This is intentionally not replaced with an unsigned download-and-execute
fallback.

## macOS

The bundle target includes `dmg` and an `.icns` icon. A macOS runner or real
Mac still needs to verify DMG generation, LaunchAgent autostart, tray behaviour
and the dynamic settings window before macOS support can be called complete.
