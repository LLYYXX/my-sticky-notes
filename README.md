# My Sticky Notes

一个本地优先、Todo 导向的极简桌面便利贴。项目当前正在从 Python/Tkinter
迁移到 Tauri/Rust，目标是同时支持 Windows 和 macOS，并保持轻量、低打扰的桌面体验。

> 当前 Tauri 版本仍处于迁移验证阶段。前端状态、静态契约、旧 Python 回归测试、
> `cargo test`、Windows `tauri build`、真实 GUI 便签/设置页截图和默认右上角定位
> 已通过；托盘菜单、自启和 macOS DMG 仍需进一步验证。

迁移细节和当前阻塞项见 [TAURI_MIGRATION.md](TAURI_MIGRATION.md)。

## 当前 Tauri 目标

- 多张无标题便签，单窗口承载，避免每张便签一个渲染进程。
- 默认新便签按当前 viewport 出现在右上角，不依赖固定分辨率坐标。
- 每张便签可单独选择九种颜色。
- Todo 支持添加、编辑、完成、删除；长条目在边缘自动换行。
- `-` 按钮语义为“收起”：只隐藏待办内容，保留顶部长条和操作按钮。
- 置顶状态同步到原生窗口 topmost 行为。
- 设置页按需打开；设置页打开时显示任务栏入口，关闭后恢复轻量常驻。
- 托盘由 Rust 单一来源创建，托盘可恢复便签或打开设置。
- 登录后自动启动已接入 Tauri autostart 插件。
- 打包目标保留 Windows NSIS 和 macOS DMG。

## 目录

```text
src/                 Tauri 前端，原生 HTML/CSS/JS
src-tauri/           Tauri/Rust shell、托盘、状态、窗口命令、打包配置
sticky_notes/        旧 Python/Tkinter 实现，迁移期间保留回归测试
scripts/             图标生成、静态契约和状态测试脚本
tests/               旧 Python 版本回归测试
```

## 开发环境

Tauri 路线需要：

- Node.js 18 或更新版本；
- pnpm；
- Rust stable 与 Cargo；
- 对应平台的 Tauri 系统依赖。

## 可运行检查

```powershell
pnpm install --frozen-lockfile
pnpm run check:frontend
cargo check --manifest-path src-tauri\Cargo.toml
cargo test --manifest-path src-tauri\Cargo.toml
python -m unittest discover -s tests
git diff --check
```

`pnpm run check:frontend` 会执行：

- `src/app.js` / `src/state.js` 语法检查；
- Tauri 静态契约检查；
- 前端状态模型测试。

## 完整 Tauri 验证

```powershell
pnpm run tauri:dev
pnpm run tauri:build
```

当前 Windows 本地已成功生成：

```text
src-tauri\target\release\bundle\nsis\My Sticky Notes_0.3.0-alpha.0_x64-setup.exe
```

已在 Windows 本地实际检查：

- 首张便签按当前工作区右上角定位；
- clean state 下默认便签完整可见；
- `-` 只收起内容并保留顶部长条与操作按钮；
- 设置页可从运行时顶栏打开；
- 置顶按钮会触发 Windows 原生 `WS_EX_TOPMOST`；
- 默认便签窗口为 `toolWindow=true/appWindow=false`，设置页打开后切换为 `toolWindow=false/appWindow=true`；
- Windows NSIS 安装包可生成。

还需要实际检查：

- 托盘菜单是否能恢复便签、打开设置、退出应用；
- 登录后自启是否对应系统启动项；
- macOS DMG 是否能正常产出。

## CI / Release

- `CI` 会运行前端 Tauri 静态契约和旧 Python 回归测试。
- `Tauri Build` 是手动工作流，使用 `pnpm install --frozen-lockfile` 在
  GitHub Actions 上验证 Windows/macOS Tauri 打包。
- `Release` 暂停自动 tag 发布；旧 Python 发布流已禁用，避免迁移期间误发旧包。

## 旧 Python 版本

迁移期间仍保留旧入口用于对照和回归：

```powershell
python app.py
```

旧版本的安装包、更新器和 Windows 专属行为不再是当前主线目标。新的发布路线以
Tauri 打包为准。

## 许可

项目使用 [MIT License](LICENSE)。图标资源的第三方许可见
[assets/icons/LICENSE-lucide.txt](assets/icons/LICENSE-lucide.txt)。
