# My Sticky Notes

一个本地优先、Todo 导向的极简桌面便签，使用 Tauri 2 / Rust 实现 Windows 与 macOS 桌面壳层。

## 当前实现

- 多张无标题便签；每张可独立使用九种主题色。
- Todo 支持新增、编辑、完成、删除和长文本换行。
- `＋ / 删除 / 置顶 / 收起` 位于便签标题栏；收起只保留长条和按钮。
- 点击左侧颜色圆点展开九色面板；右下角可调整便签尺寸。
- 默认按显示器工作区的右上角定位，尺寸按系统 DPI 计算，不依赖单台电脑的固定像素坐标。
- 便签窗口始终不出现在任务栏；托盘左键恢复便签，菜单可打开设置或退出。
- 设置是按需创建的独立原生窗口，因此只有打开设置时才会出现任务栏图标。
- 同一用户会话只保留一个应用实例；重复启动会恢复首实例，不会再创建额外渲染器。
- 设置提供登录后启动与中英文切换；关于页显示当前版本与开源地址。
- 数据只保存在本机 JSON 文件中，不依赖服务端。

## 运行时结构

```text
main notes webview      仅承载全部便签，透明、无任务栏入口
settings webview        从托盘按需创建，关闭即销毁
Rust host               托盘、窗口定位、置顶、自启、状态读写、打包
plain HTML/CSS/JS       无框架运行时与额外 UI 依赖
```

这避免了“每张便签一个 WebView”的内存线性增长，同时也避免设置页一直常驻。

## 开发

要求：Node.js 20+、pnpm 11、Rust stable，以及平台对应的 Tauri 系统依赖。

```powershell
pnpm install --frozen-lockfile
pnpm run check:frontend
cargo check --manifest-path src-tauri\Cargo.toml
cargo test --manifest-path src-tauri\Cargo.toml
pnpm run tauri:dev
```

## 验证与打包

```powershell
pnpm run tauri:build
python scripts\tauri_runtime_probe.py --skip-autostart
```

Windows NSIS 安装包会生成在：

```text
src-tauri\target\release\bundle\nsis\My Sticky Notes_0.3.0_x64-setup.exe
```

已在 Windows 打包程序上验证：五张便签、托盘恢复、独立设置窗口、任务栏隔离、右上角工作区定位、重复启动退出和运行时内存预算。四次隔离探针中，五张便签为 32.5–72.2 MB 工作集，设置打开为 33.2–72.4 MB；预算分别为 220 MB 与 250 MB。

## 自动更新

“检查更新”只在用户点击时访问固定的 GitHub Releases 来源。发现新版后，Windows 会下载对应的 NSIS 安装器，等待便签进程退出后静默启动安装；macOS 会下载并打开对应 DMG，系统可能仍要求确认或将应用拖入 Applications。该路径面向本项目的两位可信用户，不使用签名更新服务、后台轮询或额外常驻进程。详见 [TAURI_MIGRATION.md](TAURI_MIGRATION.md)。

## 跨平台

`tauri.conf.json` 同时声明 Windows `nsis` 和 macOS `dmg` 打包目标。Windows 已完成真实运行时验证；macOS 仍需在真实 Mac 或 GitHub 的 macOS runner 上完成 DMG 与托盘/自启行为验证。

## 许可

[MIT License](LICENSE)。便签图标来自 Lucide，见 [src/assets/icons/LICENSE-lucide.txt](src/assets/icons/LICENSE-lucide.txt)。
