# Contributing

欢迎提交问题和改进。请保持改动聚焦，并在提交前运行：

```powershell
python -m pip install ".[dev]"
python -m unittest discover -v
python scripts\ui_smoke_test.py
```

涉及窗口层级、任务栏或通知区域行为的改动，还应运行：

```powershell
python scripts\desktop_behavior_regression.py
```

提交 Pull Request 时，请说明用户可见变化、验证方式，以及是否影响已有 `state.json` 数据。
