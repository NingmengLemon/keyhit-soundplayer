from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from .logging_config import get_logger

logger = get_logger("config")

InterruptMode = Literal["always", "never"]
RotationMode = Literal["round_robin", "random"]

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


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class AudioConfig(ConfigModel):
    frequency: int = 44_100
    size: int = -16
    channels: int = 2
    buffer: int = 128
    volume: float = Field(default=1.0, ge=0.0, le=1.0)


class PlaybackConfig(ConfigModel):
    interrupt: bool = True
    channel_count: int = Field(default=8, ge=1)
    rotation: RotationMode = "round_robin"


class ListenerConfig(ConfigModel):
    keyboard: bool = True
    mouse: bool = True
    gamepad: bool = True
    gamepad_poll_interval: float = Field(default=0.001, gt=0.0)
    trigger_on_release: bool = False


class Binding(ConfigModel):
    sounds: tuple[Path, ...]
    interrupt: bool | None = None
    rotation: RotationMode | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_binding(cls, value: Any) -> dict[str, Any]:
        if isinstance(value, (str, Path)):
            return {"sounds": (value,)}
        if isinstance(value, list):
            return {"sounds": value}
        if not isinstance(value, dict):
            raise ValueError("绑定值必须是字符串、字符串数组或表")
        if "sounds" not in value and "sound" in value:
            return {**value, "sounds": value["sound"]}
        return value

    @field_validator("sounds", mode="before")
    @classmethod
    def normalize_sounds(cls, value: Any) -> Any:
        if isinstance(value, (str, Path)):
            return (value,)
        return value

    @field_validator("sounds")
    @classmethod
    def require_sounds(cls, value: tuple[Path, ...]) -> tuple[Path, ...]:
        if not value:
            raise ValueError("绑定至少需要一个音效")
        return value

    def resolve(self, base_dir: Path) -> Binding:
        return self.model_copy(
            update={
                "sounds": tuple(
                    resolve_sound_path(path, base_dir) for path in self.sounds
                )
            }
        )


class RawConfig(ConfigModel):
    audio: AudioConfig = Field(default_factory=AudioConfig)
    playback: PlaybackConfig = Field(default_factory=PlaybackConfig)
    listener: ListenerConfig = Field(default_factory=ListenerConfig)
    default: Binding | None = None
    groups: dict[str, Binding] = Field(default_factory=dict)
    bindings: dict[str, Binding] = Field(default_factory=dict)


class AppConfig(ConfigModel):
    base_dir: Path
    audio: AudioConfig = Field(default_factory=AudioConfig)
    playback: PlaybackConfig = Field(default_factory=PlaybackConfig)
    listener: ListenerConfig = Field(default_factory=ListenerConfig)
    bindings: dict[str, Binding] = Field(default_factory=dict)
    default_binding: Binding | None = None


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KEYHIT_",
        env_nested_delimiter="__",
        extra="ignore",
        frozen=True,
    )

    config: Path = Path("config.toml")
    log_level: str = "INFO"
    verbose: bool = False
    quiet: bool = False


class ConfigError(ValueError):
    """Raised when user supplied configuration is invalid."""


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
    try:
        parsed = RawConfig.model_validate(raw)
    except ValidationError as exc:
        logger.error("配置校验失败: %s", exc)
        raise ConfigError(str(exc)) from exc

    bindings: dict[str, Binding] = {}
    for section_name, items in (
        ("组映射", parsed.groups),
        ("精确映射", parsed.bindings),
    ):
        for selector, binding in items.items():
            expanded = expand_key_selector(selector)
            resolved = binding.resolve(base_dir)
            logger.debug("展开%s: %s -> %s", section_name, selector, expanded)
            for normalized in expanded:
                bindings[normalized] = resolved

    return AppConfig.model_validate(
        {
            "base_dir": base_dir,
            "audio": parsed.audio,
            "playback": parsed.playback,
            "listener": parsed.listener,
            "bindings": bindings,
            "default_binding": parsed.default.resolve(base_dir)
            if parsed.default is not None
            else None,
        }
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
