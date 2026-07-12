# Tauri migration status

## Window model

My Sticky Notes runs as one application process. Every sticky note is a small,
frameless native Tauri window with a unique `note-*` label. It owns only the
note rectangle, so the desktop remains clickable between notes. The application
does not create a persistent transparent desktop-sized host window.

Settings is deliberately separate: Rust creates its normal native window only
when the tray menu requests it. It is the only normal taskbar window. Note
windows are tool windows and remain out of the taskbar.

Before the Tauri shell is constructed, a standard-library loopback listener
reserves the single-instance endpoint. A duplicate launch activates the existing
process and exits. Several native note windows therefore still mean one app
instance and one state store, not several application instances.

Responsibilities are separated as follows:

- `src/state.js`: persisted state normalization and local fallback state.
- `src/views.js`: rendering a single note or Settings only.
- `src/app.js`: focused-note interaction bindings and native command bridge.
- `src-tauri/src/main.rs`: native note-window lifetime, state store, tray,
  autostart, coordinate migration, and packaging integration.
- `src-tauri/src/single_instance.rs`: local activation handshake.

## Coordinates and persistence

Each new note starts at the primary monitor work-area top right and cascades
from that point. Native move events persist physical screen coordinates. This
avoids browser viewport coordinates and fixed-resolution assumptions.

State version 9 converts v8 coordinates from the former host-relative model to
screen coordinates once, using the current work area and scale factor. The old
Tk/Python state is also imported once from `%LOCALAPPDATA%\MyStickyNotes\state.json`;
the old file remains untouched. The obsolete `height` field is ignored, while a
`bodyHeight` is saved only after the user uses the resize grip.

## Verified Windows evidence

The packaged app was tested in an isolated data directory with two notes:

- two separate `toolWindow=true`, `appWindow=false` note windows were created;
- each verified note was about 443 by 176 physical pixels on the test display;
- no visible window was desktop sized, so no transparent click-blocking host
  existed;
- tray left click restored all note windows; the tray menu opened Settings and
  exited the app;
- Settings was a separate `appWindow=true`, `toolWindow=false` window;
- a second packaged launch exited with code 0 while the first process remained;
- the release executable used Windows GUI subsystem 2, so it has no console
  window;
- isolated working set was 68.1 MB with two notes and 68.2 MB with Settings.

Each note uses a native WebView, so capacity limits should be measured against
representative note counts rather than extrapolated from a transparent overlay.

## Direct update for the trusted two-user distribution

The updater runs only after the user presses Check update. The renderer reads
metadata from the fixed `LLYYXX/my-sticky-notes` GitHub repository and passes
only the selected tag and asset names to Rust. Rust reconstructs canonical HTTPS
release URLs and accepts only the current platform's expected installer name.

On Windows a short-lived PowerShell launcher waits for the app process to exit,
silently runs the NSIS installer, cleans up the temporary installer, and then
relaunches the app. On macOS the app downloads and opens the appropriate DMG;
the user may still need to approve it or copy it to Applications.

For the one-time Tk/Python transition, the NSIS pre-install hook closes the old
`MyStickyNotes.exe` without opening a shell and removes its legacy Run-key
entry. Releases also include the old updater's installer-name alias and
`SHA256SUMS.txt`, so `0.2.x` can verify the first Tauri installer.

The early Tauri `0.3.1` updater required a space-containing asset name, but
GitHub normalizes Release asset filenames with special characters. It therefore
needs one manual installation of `0.3.2`; the current updater accepts the
normalized dotted installer name for all later updates.

## CI and supported platforms

`Tauri Build` runs on every `main` push and pull request. It validates the
locked pnpm graph, frontend checks, Rust tests, and native bundles on Windows,
Apple Silicon macOS, and Intel macOS. A `v*` tag or manual Release run publishes
the Windows x64 installer plus both macOS DMGs. Real Macs are still needed to
validate tray and LaunchAgent behavior on the target operating systems.
