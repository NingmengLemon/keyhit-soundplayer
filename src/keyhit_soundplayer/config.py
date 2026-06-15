from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from .logging_config import get_logger

logger = get_logger("config")

InterruptMode = Literal["always", "never"]

_SPECIAL_ALIASES: dict[str, str] = {
    "esc": "escape",
    "escape": "escape",
    "enter": "enter",
    "return": "enter",
    "space": "space",
    "tab": "tab",
    "backspace": "backspace",
    "delete": "delete",
    "del": "delete",
    "shift": "shift",
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "cmd": "cmd",
    "win": "cmd",
    "windows": "cmd",
    "caps_lock": "caps_lock",
    "capslock": "caps_lock",
}

_KEY_GROUPS: dict[str, list[str]] = {
    "letters": [chr(code) for code in range(ord("a"), ord("z") + 1)],
    "digits": [str(i) for i in range(10)],
    "numbers": [str(i) for i in range(10)],
    "function": [f"f{i}" for i in range(1, 25)],
    "arrows": ["up", "down", "left", "right"],
    "modifiers": ["shift", "ctrl", "alt", "cmd"],
    "editing": ["backspace", "delete", "enter", "tab", "space"],
    "special": [
        "escape",
        "enter",
        "space",
        "tab",
        "backspace",
        "delete",
        "insert",
        "home",
        "end",
        "page_up",
        "page_down",
        "up",
        "down",
        "left",
        "right",
    ],
}

_GAMEPAD_GROUPS: dict[str, list[str]] = {
    "face": [
        "gamepad.btn_south",
        "gamepad.btn_east",
        "gamepad.btn_west",
        "gamepad.btn_north",
    ],
    "shoulders": [
        "gamepad.btn_tl",
        "gamepad.btn_tr",
        "gamepad.btn_tl2",
        "gamepad.btn_tr2",
    ],
    "dpad": [
        "gamepad.abs_hat0x.-1",
        "gamepad.abs_hat0x.1",
        "gamepad.abs_hat0y.-1",
        "gamepad.abs_hat0y.1",
    ],
    "sticks": ["gamepad.btn_thumbl", "gamepad.btn_thumbr"],
}

_MOUSE_ALIASES: dict[str, str] = {
    "left": "left",
    "right": "right",
    "middle": "middle",
    "x1": "x1",
    "x2": "x2",
    "button8": "x1",
    "button9": "x2",
    "wheel_up": "wheel_up",
    "wheel_down": "wheel_down",
    "wheel_left": "wheel_left",
    "wheel_right": "wheel_right",
    "scroll_up": "wheel_up",
    "scroll_down": "wheel_down",
    "scroll_left": "wheel_left",
    "scroll_right": "wheel_right",
}

_MOUSE_GROUPS: dict[str, list[str]] = {
    "mouse_buttons": [
        "mouse.left",
        "mouse.right",
        "mouse.middle",
        "mouse.x1",
        "mouse.x2",
    ],
    "mouse_wheel": [
        "mouse.wheel_up",
        "mouse.wheel_down",
        "mouse.wheel_left",
        "mouse.wheel_right",
    ],
    "mouse": [
        "mouse.left",
        "mouse.right",
        "mouse.middle",
        "mouse.x1",
        "mouse.x2",
        "mouse.wheel_up",
        "mouse.wheel_down",
        "mouse.wheel_left",
        "mouse.wheel_right",
    ],
}


@dataclass(frozen=True, slots=True)
class AudioConfig:
    frequency: int = 44_100
    size: int = -16
    channels: int = 2
    buffer: int = 128
    volume: float = 1.0


@dataclass(frozen=True, slots=True)
class PlaybackConfig:
    interrupt: bool = True
    channel_count: int = 8


@dataclass(frozen=True, slots=True)
class ListenerConfig:
    keyboard: bool = True
    mouse: bool = True
    gamepad: bool = True
    gamepad_poll_interval: float = 0.001
    trigger_on_release: bool = False


@dataclass(frozen=True, slots=True)
class Binding:
    sounds: tuple[Path, ...]
    interrupt: bool | None = None


@dataclass(frozen=True, slots=True)
class AppConfig:
    base_dir: Path
    audio: AudioConfig = field(default_factory=AudioConfig)
    playback: PlaybackConfig = field(default_factory=PlaybackConfig)
    listener: ListenerConfig = field(default_factory=ListenerConfig)
    bindings: dict[str, Binding] = field(default_factory=dict)
    default_binding: Binding | None = None


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).expanduser().resolve()
    logger.info("加载配置文件: %s", config_path)
    with config_path.open("rb") as fp:
        raw = tomllib.load(fp)
    config = parse_config(raw, base_dir=config_path.parent)
    logger.info(
        "配置加载完成: bindings=%s default=%s keyboard=%s mouse=%s gamepad=%s",
        len(config.bindings),
        config.default_binding is not None,
        config.listener.keyboard,
        config.listener.mouse,
        config.listener.gamepad,
    )
    return config


def parse_config(raw: dict[str, Any], base_dir: Path) -> AppConfig:
    logger.debug("解析配置: base_dir=%s", base_dir)
    audio = _parse_dataclass(AudioConfig, raw.get("audio", {}))
    playback = _parse_dataclass(PlaybackConfig, raw.get("playback", {}))
    listener = _parse_dataclass(ListenerConfig, raw.get("listener", {}))

    default_binding = _parse_optional_binding(raw.get("default"), base_dir)
    bindings: dict[str, Binding] = {}

    for group_name, value in raw.get("groups", {}).items():
        binding = _parse_binding(value, base_dir)
        expanded = expand_key_selector(group_name)
        logger.debug("展开组映射: %s -> %s", group_name, expanded)
        for normalized in expanded:
            bindings[normalized] = binding

    for key_name, value in raw.get("bindings", {}).items():
        binding = _parse_binding(value, base_dir)
        expanded = expand_key_selector(key_name)
        logger.debug("展开精确映射: %s -> %s", key_name, expanded)
        for normalized in expanded:
            bindings[normalized] = binding

    return AppConfig(
        base_dir=base_dir,
        audio=audio,
        playback=playback,
        listener=listener,
        bindings=bindings,
        default_binding=default_binding,
    )


def expand_key_selector(selector: str) -> list[str]:
    text = selector.strip().lower()
    if text == "all":
        return ["*"]
    if text.startswith("group:"):
        group_name = text.removeprefix("group:")
        if group_name in _KEY_GROUPS:
            return _KEY_GROUPS[group_name]
        if group_name in _GAMEPAD_GROUPS:
            return _GAMEPAD_GROUPS[group_name]
        if group_name in _MOUSE_GROUPS:
            return _MOUSE_GROUPS[group_name]
        logger.error("未知按键组: %s", selector)
        raise ValueError(f"未知按键组: {selector}")
    if text.startswith("gamepad:"):
        return [normalize_gamepad_name(text.removeprefix("gamepad:"))]
    if text.startswith("mouse:"):
        return [normalize_mouse_name(text.removeprefix("mouse:"))]
    return [normalize_key_name(text)]


def normalize_key_name(name: str) -> str:
    text = str(name).strip().lower()
    if len(text) == 1:
        return text
    if text in _SPECIAL_ALIASES:
        return _SPECIAL_ALIASES[text]
    if text.startswith("key."):
        return normalize_key_name(text.removeprefix("key."))
    return text.replace(" ", "_")


def normalize_gamepad_name(name: str) -> str:
    text = str(name).strip().lower().replace(" ", "_")
    if text.startswith("gamepad."):
        return text
    return f"gamepad.{text}"


def normalize_mouse_name(name: str) -> str:
    text = str(name).strip().lower().replace(" ", "_")
    if text.startswith("mouse."):
        text = text.removeprefix("mouse.")
    text = _MOUSE_ALIASES.get(text, text)
    return f"mouse.{text}"


def resolve_sound_path(path: str | Path, base_dir: Path) -> Path:
    sound_path = Path(path)
    if not sound_path.is_absolute():
        sound_path = (base_dir / sound_path).resolve()
    return sound_path


def _parse_dataclass(
    cls: type[AudioConfig] | type[PlaybackConfig] | type[ListenerConfig], value: Any
) -> Any:
    if value is None:
        logger.debug("%s 使用默认配置", cls.__name__)
        return cls()
    if not isinstance(value, dict):
        logger.error("%s 配置类型错误: %r", cls.__name__, value)
        raise TypeError(f"{cls.__name__} 必须是表")
    allowed = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
    filtered = {key: item for key, item in value.items() if key in allowed}
    ignored = sorted(set(value) - allowed)
    if ignored:
        logger.warning("忽略未知 %s 配置项: %s", cls.__name__, ", ".join(ignored))
    logger.debug("%s 配置: %s", cls.__name__, filtered)
    return cls(**filtered)


def _parse_optional_binding(value: Any, base_dir: Path) -> Binding | None:
    if value is None:
        logger.debug("未配置默认绑定")
        return None
    return _parse_binding(value, base_dir)


def _parse_binding(value: Any, base_dir: Path) -> Binding:
    if isinstance(value, str):
        binding = Binding(sounds=(resolve_sound_path(value, base_dir),))
        logger.debug("解析单音效绑定: %s", binding.sounds[0])
        return binding
    if isinstance(value, list):
        binding = Binding(
            sounds=tuple(resolve_sound_path(item, base_dir) for item in value)
        )
        logger.debug("解析多音效绑定: %s", binding.sounds)
        return binding
    if not isinstance(value, dict):
        logger.error("绑定值类型错误: %r", value)
        raise TypeError("绑定值必须是字符串、字符串数组或表")

    sounds_value = value.get("sounds", value.get("sound"))
    if isinstance(sounds_value, str):
        sounds = (resolve_sound_path(sounds_value, base_dir),)
    elif isinstance(sounds_value, list):
        sounds = tuple(resolve_sound_path(item, base_dir) for item in sounds_value)
    else:
        logger.error("绑定表缺少 sound/sounds: %r", value)
        raise TypeError("绑定表需要 sound 或 sounds")

    if not sounds:
        logger.error("绑定音效列表为空: %r", value)
        raise ValueError("绑定至少需要一个音效")
    interrupt_value = value.get("interrupt")
    if interrupt_value is not None and not isinstance(interrupt_value, bool):
        logger.error("绑定 interrupt 类型错误: %r", interrupt_value)
        raise TypeError("interrupt 必须是布尔值")
    binding = Binding(sounds=sounds, interrupt=interrupt_value)
    logger.debug("解析绑定表: sounds=%s interrupt=%s", sounds, interrupt_value)
    return binding
