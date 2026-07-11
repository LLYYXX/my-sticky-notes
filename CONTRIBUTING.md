# Contributing

The supported runtime is Tauri 2: Node.js 20+, pnpm 11, and stable Rust.

```powershell
pnpm install --frozen-lockfile
pnpm run check:frontend
cargo test --locked --manifest-path src-tauri\Cargo.toml
pnpm run tauri:dev
```

For a Windows packaging change, also run:

```powershell
pnpm run tauri:build
python scripts\tauri_runtime_probe.py --skip-autostart
python scripts\tauri_single_instance_probe.py
```

Keep the notes host as one renderer. Settings must remain on-demand, and
network or installer work must remain user-triggered rather than persistent.
