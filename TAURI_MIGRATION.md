# Tauri Migration

This project is being rewritten from the original Python/Tkinter implementation
to a Tauri-based desktop app for Windows and macOS.

## Target architecture

- One Tauri application window hosts the desktop canvas, all note components,
  and the Settings surface.
- Notes are frontend components, not one WebView per note. This keeps the
  runtime closer to the lightweight target and avoids multiplying renderer
  memory as note count grows.
- The native host window is positioned against the current monitor work area,
  and default note placement is computed in the frontend from the current
  viewport width. This avoids relying on a hard-coded `x=760` that only works
  for one window size.
- Legacy or persisted note coordinates are clamped back into the current
  viewport so old state cannot leave a note off-screen after a resolution or
  DPI change.
- The Rust state layer deliberately preserves missing layout fields as empty
  values. It should not backfill screen-dependent defaults; otherwise legacy or
  partial state would bypass the viewport-relative placement logic.
- The note `-` action is now `collapsed`: it hides the todo body and keeps the
  top bar plus action buttons visible. It does not minimize to the taskbar.
- State remains local JSON and is exposed through Tauri commands:
  `load_state` and `save_state`.
- The Rust state loader can fall back to the legacy Python data path
  `%LOCALAPPDATA%\MyStickyNotes\state.json` and accepts the legacy
  `open_at_login` setting name.
- The app creates the tray icon only from Rust. The static Tauri config does
  not also declare a second tray icon.
- The main window starts with `skipTaskbar: true`. Opening Settings asks Rust
  to show the taskbar entry; closing Settings hides it again.
- On Windows, Rust also flips the native extended window style between
  `WS_EX_TOOLWINDOW` for note mode and `WS_EX_APPWINDOW` for Settings mode so
  the taskbar behavior does not depend only on Tauri's high-level
  `skip_taskbar` call.
- Pinned notes are synced to the host window through a Tauri command so the
  native topmost behavior can be checked once Cargo is available.
- The login-start setting now calls the Tauri autostart plugin through Rust
  commands instead of only updating local JSON.
- Settings are implemented in HTML/CSS so the app can move toward the cleaner
  Stretchly-style preference surface without fighting Tk layout limits.

## Current implementation status

Implemented in this checkpoint:

- `src/index.html`, `src/app.js`, and `src/styles.css` provide the first Tauri
  frontend.
- `src-tauri/src/main.rs` provides state load/save commands and a basic tray
  menu, plus taskbar visibility, topmost-window, and autostart commands.
- `src-tauri/tauri.conf.json` declares Windows `nsis` and macOS `dmg` bundle
  targets.
- `src-tauri/capabilities/default.json` declares the default Tauri v2 desktop
  permissions used by the shell.
- `src-tauri/icons/` contains generated Tauri bundle icons for Windows and
  macOS, produced by `scripts/build_app_icon.py`.
- `scripts/tauri_static_check.mjs` verifies that the Tauri scaffold contains
  the expected collapse behavior, settings surface, persisted state wiring,
  single Rust tray source, settings-driven taskbar visibility, topmost command
  wiring, native autostart wiring, capabilities file, bundle icons, stable
  GitHub Actions versions, and Win/mac bundle targets.
- `scripts/tauri_state_test.mjs` verifies the pure frontend state model,
  including viewport-relative default placement, off-screen legacy coordinate
  clamping, legacy `open_at_login` migration, and persisted collapse state.
- The push CI no longer builds the legacy Python installer. A manual
  `Tauri Build` workflow is available for Windows/macOS bundle validation. It
  uses `pnpm install --frozen-lockfile` so CI matches the checked-in
  `pnpm-lock.yaml`.
- The tag-triggered legacy Python `Release` workflow is paused during the Tauri
  migration so tags do not publish the old installer path by accident.
- Local Windows verification now passes:
  - `cargo check`
  - `cargo test`
  - `pnpm run check:frontend`
  - `pnpm run tauri:build`
  - DPI-aware runtime capture of the notes screen
  - DPI-aware runtime capture of the Settings screen
  - DPI-aware runtime capture of the collapsed-note state
  - Windows `WS_EX_TOPMOST` verification after clicking the pin button
  - Windows taskbar-style verification: note mode reports
    `toolWindow=true/appWindow=false`; Settings mode reports
    `toolWindow=false/appWindow=true`
- The Windows NSIS bundle has been generated at
  `src-tauri/target/release/bundle/nsis/My Sticky Notes_0.3.0-alpha.0_x64-setup.exe`.

Not complete yet:

- macOS DMG still needs to be verified on `macos-latest` or a real Mac.
- Update installation and deeper window behavior still need to be reimplemented
  with Tauri plugins or platform code.
- Native autostart is wired to the Tauri autostart plugin, but it still needs
  real runtime verification.
- Tray menu actions still need direct runtime checks.

## Required local toolchain

Install before running the full Tauri app:

- Node.js 18 or newer.
- Rust stable with Cargo.
- Tauri platform prerequisites for Windows or macOS.

Useful commands after installing the toolchain:

```powershell
pnpm install --frozen-lockfile
pnpm run check:frontend
cargo check --manifest-path src-tauri\Cargo.toml
cargo test --manifest-path src-tauri\Cargo.toml
pnpm run tauri:dev
pnpm run tauri:build
```

## Memory constraint

The rewrite should preserve the lightweight product feel. The architecture
should be measured against these working budgets before calling the migration
done:

- Idle with one note: target below 150 MB.
- Settings open: target below 250 MB.
- Five notes: target below 220 MB.
- Closing Settings should release any Settings-only memory.

If these budgets are missed, prefer reducing renderer count, removing heavy
frontend dependencies, and lazy-loading Settings before adding new features.
