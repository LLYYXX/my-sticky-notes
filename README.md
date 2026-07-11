# My Sticky Notes

一个本地优先、Todo 导向的极简桌面便签，使用 Tauri 2、Rust 和原生
WebView 实现，支持 Windows 与 macOS。

## Current behavior

- 多张无标题便签；每张是独立的无边框原生窗口，而非一个透明桌面覆盖层。
- 九种独立主题色，待办可新增、编辑、完成、删除，并会在边缘自动换行。
- 标题栏操作顺序为 `+ / 删除 / 置顶 / -`；`-` 收起内容，右下角可调整大小。
- 新便签默认位于主显示器工作区右上角，并按窗口原生坐标保存位置。
- 便签不显示在任务栏；托盘左键恢复全部便签，菜单可打开设置或退出。
- 设置为按需创建的正常窗口，包含登录后启动、中文/English 与关于/更新。
- 单实例：重复启动只会激活已有进程；多张便签窗口仍属于同一个应用进程。
- 所有数据保存在本地 JSON；不需要账号、云端或后台轮询。

## Architecture

```text
one application process
├─ note-<id> native windows   one small window per visible sticky note
├─ Settings native window     created only from the tray
├─ tray icon                  restore all / settings / quit
└─ Rust state store           one JSON state file, one instance guard
```

This model deliberately avoids a desktop-sized transparent WebView. A transparent
surface is still an OS hit-test rectangle, so it can block clicks even when its
CSS content is empty. Individual note windows keep the desktop usable between
notes.

## Development

Requirements: Node.js 22.13+, pnpm 11, Rust stable, and Tauri platform
dependencies.

```powershell
pnpm install --frozen-lockfile
pnpm run check:frontend
cargo test --manifest-path src-tauri\Cargo.toml
pnpm run tauri:dev
```

## Verification and packaging

```powershell
pnpm run tauri:build
python scripts\tauri_runtime_probe.py --skip-autostart --note-count 2
python scripts\tauri_single_instance_probe.py
```

The Windows installer is produced at:

```text
src-tauri\target\release\bundle\nsis\My Sticky Notes_0.3.1_x64-setup.exe
```

The runtime probe uses an isolated state directory and an independent
single-instance port, so it does not touch personal notes or a currently running
copy of the app.

## Updates and legacy migration

Check update contacts the fixed GitHub Releases source only when requested.
Windows downloads the matching NSIS installer and starts it after the app exits;
macOS downloads and opens the matching DMG. The project is distributed to two
trusted users and intentionally does not add a signed updater service or a
background update helper.

When moving from Tk/Python `0.2.x`, the installer silently closes the old
`MyStickyNotes.exe` and removes its legacy startup entry. On first Tauri launch,
the app imports `%LOCALAPPDATA%\MyStickyNotes\state.json` once and preserves the
old file. The Release contains the installer alias and `SHA256SUMS.txt` needed
by the old updater.

See [TAURI_MIGRATION.md](TAURI_MIGRATION.md) for migration, update, and
verification details.

## License

[MIT License](LICENSE). The note icons are from Lucide; see
[src/assets/icons/LICENSE-lucide.txt](src/assets/icons/LICENSE-lucide.txt).
