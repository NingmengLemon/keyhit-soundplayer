from __future__ import annotations

from collections.abc import Callable
from threading import Event, Thread
from typing import Any

from pynput import keyboard, mouse

from .config import normalize_gamepad_name, normalize_key_name, normalize_mouse_name
from .logging_config import get_logger

logger = get_logger("listeners")

EventCallback = Callable[[str], None]


class KeyboardListener:
    def __init__(
        self, callback: EventCallback, *, trigger_on_release: bool = False
    ) -> None:
        self._callback = callback
        self._trigger_on_release = trigger_on_release
        self._listener: keyboard.Listener | None = None
        logger.debug("键盘监听器已创建: trigger_on_release=%s", trigger_on_release)

    def start(self) -> None:
        logger.info("启动键盘监听器")
        self._listener = keyboard.Listener(
            on_press=None if self._trigger_on_release else self._on_key,
            on_release=self._on_key if self._trigger_on_release else None,
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            logger.info("停止键盘监听器")
            self._listener.stop()
            self._listener = None

    def _on_key(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key is None:
            return
        name = key_to_name(key)
        if name:
            logger.debug("键盘事件: %s", name)
            self._callback(name)


def key_to_name(key: keyboard.Key | keyboard.KeyCode) -> str | None:
    char = getattr(key, "char", None)
    if isinstance(char, str) and char:
        if not char.isprintable() or char.isspace():
            logger.debug("忽略不可打印/空白键盘字符: repr=%r", char)
            return None
        normalized = normalize_key_name(char)
        return normalized or None
    key_name = getattr(key, "name", None)
    if isinstance(key_name, str) and key_name:
        normalized = normalize_key_name(key_name)
        return normalized or None
    text = str(key)
    if text.startswith("Key."):
        normalized = normalize_key_name(text.removeprefix("Key."))
        return normalized or None
    logger.debug("无法识别键盘按键: %s", key)
    return None


class MouseListener:
    """System-wide mouse click and wheel listener."""

    def __init__(self, callback: EventCallback) -> None:
        self._callback = callback
        self._listener: mouse.Listener | None = None
        logger.debug("鼠标监听器已创建")

    def start(self) -> None:
        logger.info("启动鼠标监听器")
        self._listener = mouse.Listener(
            on_click=self._on_click, on_scroll=self._on_scroll
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            logger.info("停止鼠标监听器")
            self._listener.stop()
            self._listener = None

    def _on_click(self, x: int, y: int, button: Any, pressed: bool) -> None:
        if not pressed:
            return
        name = mouse_button_to_name(button)
        if name:
            logger.debug("鼠标点击事件: %s x=%s y=%s", name, x, y)
            self._callback(name)

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        logger.debug("鼠标滚轮原始事件: x=%s y=%s dx=%s dy=%s", x, y, dx, dy)
        if dy > 0:
            self._callback("mouse.wheel_up")
        elif dy < 0:
            self._callback("mouse.wheel_down")
        if dx > 0:
            self._callback("mouse.wheel_right")
        elif dx < 0:
            self._callback("mouse.wheel_left")


def mouse_button_to_name(button: Any) -> str | None:
    button_name = getattr(button, "name", None)
    if isinstance(button_name, str) and button_name:
        return normalize_mouse_name(button_name)
    text = str(button)
    if text.startswith("Button."):
        return normalize_mouse_name(text.removeprefix("Button."))
    return normalize_mouse_name(text)


class GamepadListener:
    """Background listener for gamepad key-like events using the inputs package."""

    _BUTTON_PREFIXES = ("BTN_",)
    _HAT_CODES = {"ABS_HAT0X", "ABS_HAT0Y"}

    def __init__(self, callback: EventCallback, *, retry_interval: float = 1.0) -> None:
        self._callback = callback
        self._retry_interval = retry_interval
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._reported_unplugged = False
        logger.debug("手柄监听器已创建: retry_interval=%s", retry_interval)

    def start(self) -> None:
        if self._thread is not None:
            logger.debug("手柄监听器已启动，跳过重复启动")
            return
        logger.info("启动手柄监听器")
        self._thread = Thread(
            target=self._run, name="keyhit-gamepad-listener", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            logger.info("停止手柄监听器")
            self._thread.join(timeout=1.0)
            self._thread = None

    def _run(self) -> None:
        try:
            from inputs import UnpluggedError, get_gamepad
        except Exception:
            logger.exception("手柄监听不可用")
            return

        logger.debug("手柄监听线程已进入事件循环")
        while not self._stop_event.is_set():
            try:
                events = get_gamepad()
            except UnpluggedError:
                if not self._reported_unplugged:
                    logger.info("未检测到手柄，保持后台等待连接")
                    self._reported_unplugged = True
                if self._stop_event.wait(self._retry_interval):
                    return
                continue
            except Exception as exc:
                logger.warning("读取手柄事件失败: %s", exc)
                if logger.isEnabledFor(10):
                    logger.debug("手柄事件读取异常详情", exc_info=True)
                if self._stop_event.wait(self._retry_interval):
                    return
                continue
            if self._reported_unplugged:
                logger.info("已检测到手柄事件，恢复手柄监听")
                self._reported_unplugged = False
            for event in events:
                name = gamepad_event_to_name(event)
                if name is not None:
                    logger.debug("手柄事件: %s", name)
                    self._callback(name)


def gamepad_event_to_name(event: Any) -> str | None:
    event_type = str(getattr(event, "ev_type", ""))
    code = str(getattr(event, "code", ""))
    state = int(getattr(event, "state", 0))
    if (
        event_type == "Key"
        and code.startswith(GamepadListener._BUTTON_PREFIXES)
        and state == 1
    ):
        return normalize_gamepad_name(code)
    if event_type == "Absolute" and code in GamepadListener._HAT_CODES and state != 0:
        return normalize_gamepad_name(f"{code}.{state}")
    return None
