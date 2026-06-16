# keyhit-soundplayer

一个低延迟、系统范围键盘/鼠标/手柄按键音效播放器。

## 功能

- 使用 `pygame.mixer` 低缓冲音频播放。
- 使用 `pynput` 捕获系统范围键盘按键和鼠标点击/滚轮。
- 使用 `inputs` 捕获手柄按钮与方向键事件。
- 使用有序 `[[rules]]` 配置指令维护按键到音效的最终映射。
- 支持键盘按键/鼠标按钮长按事件，可配置阈值、重复间隔和事件后缀。
- 支持限制最多同时播放的音效数量；超出上限时新音效会顶掉最早触发且未结束的音效。
- 支持 `group:*` 批量选择器。
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
[playback]
max_simultaneous = 2

[listener.long_press]
enabled = true
threshold = 0.5
interval = 0.0
emit_press = true
event_suffix = ".long_press"

[[rules]]
action = "set"
selector = "all"
sounds = [{ directory = "resources", glob = "*.wav" }]
rotation = "random"

[[rules]]
action = "set"
selector = "space"
sounds = ["resources/025.wav", "resources/026.wav"]
max_simultaneous = 1

[[rules]]
action = "set"
selector = "space.long_press"
sound = "resources/028.wav"
max_simultaneous = 1

[[rules]]
action = "set"
selector = "mouse:left"
sounds = [
  "resources/025.wav",
  { directory = "resources", glob = "*.wav", regex = "cn_02[56]\\.wav$" },
]

[[rules]]
action = "add"
selector = ["space", "enter"]
sounds = ["resources/028.wav"]

[[rules]]
action = "clear"
selector = "escape"
```

`[[rules]]` 会按文件中的出现顺序执行，并维护一个绑定状态表。每条规则包含 `action` 和 `selector`：

- `set`：覆盖目标 selector 的绑定。
- `add`：追加音效到已有绑定，最终去重；没有已有绑定时等同 `set`。
- `clear` / `remove`：删除目标 selector 的绑定。

`selector` 支持单个按键、按键数组、`all` 默认绑定、`group:*` 批量选择器、`mouse:*`、`gamepad:*`。内置组包括：`letters`、`digits`、`numbers`、`function`、`arrows`、`modifiers`、`editing`、`special`、`mouse_buttons`、`mouse_wheel`、`mouse`、`face`、`shoulders`、`dpad`、`sticks`。

音效源可以混用直接文件路径与目录源对象。目录源会在解析时递归扫描目录，并按 `glob` + `regex` 过滤得到文件列表；同一绑定中的最终音效路径会自动去重并保持稳定顺序。

播放上限配置位于 `[playback]` 的 `max_simultaneous`，也可在单条绑定中用 `max_simultaneous` 覆盖。达到上限后再次触发新音效时，会停止当前仍在播放队列中最早触发的音效，再播放新音效。

长按配置位于 `[listener.long_press]`：启用后，键盘按键和鼠标按钮会在按住超过 `threshold` 秒时触发一个额外事件，默认事件名为普通事件名加 `event_suffix`，例如 `space.long_press`、`mouse.left.long_press`。`interval = 0.0` 表示每次按住只触发一次长按事件；设置为大于 0 的秒数后会持续重复触发。`emit_press = false` 可关闭按下瞬间的普通事件，仅保留释放事件（当 `trigger_on_release = true`）和长按事件。手柄按钮和鼠标滚轮当前没有可靠释放信号，因此不参与长按判定。
