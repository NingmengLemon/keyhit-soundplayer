# keyhit-soundplayer

一个低延迟、系统范围键盘/鼠标/手柄按键音效播放器。

## 功能

- 使用 `pygame.mixer` 低缓冲音频播放。
- 使用 `pynput` 捕获系统范围键盘按键和鼠标点击/滚轮。
- 使用 `inputs` 捕获手柄按钮与方向键事件。
- TOML 配置按键到音效的自由映射。
- 支持后一个音效打断前一个音效，可全局或按绑定配置。
- 支持 `default`、`group:*` 这种简单批量映射。
- 支持单按键多音效轮播。

## 运行

```bat
uv sync
uv run keyhit-soundplayer -c config.toml
```

安装为 uv tool 后运行：

```bat
uv tool install .
keyhit-soundplayer -c config.toml
```

日志控制参数：

```bat
uv run keyhit-soundplayer -c config.toml --log-level DEBUG
uv run keyhit-soundplayer -c config.toml --verbose
uv run keyhit-soundplayer -c config.toml --quiet
```

也可以用模块方式运行：

```bat
uv run python -m keyhit_soundplayer -c config.toml
```

## 配置

默认配置见 `config.toml`。常用写法：

```toml
[default]
sound = "resources/cn_025.wav"

[groups]
"group:letters" = "resources/cn_025.wav"
"group:digits" = "resources/cn_026.wav"
"group:special" = "resources/cn_027.wav"
"group:mouse_buttons" = "resources/cn_025.wav"
"group:mouse_wheel" = "resources/cn_026.wav"

[bindings]
space = { sounds = ["resources/cn_025.wav", "resources/cn_026.wav"], interrupt = true }
"mouse:left" = { sounds = ["resources/cn_025.wav", "resources/cn_026.wav"] }
"mouse:right" = "resources/cn_027.wav"
"mouse:wheel_up" = "resources/cn_028.wav"
"gamepad:BTN_SOUTH" = "resources/cn_025.wav"
```

内置组包括：`letters`、`digits`、`numbers`、`function`、`arrows`、`modifiers`、`editing`、`special`、`mouse_buttons`、`mouse_wheel`、`mouse`、`face`、`shoulders`、`dpad`、`sticks`。
