from __future__ import annotations

from collections.abc import Callable
from threading import Event, Lock, Thread, Timer
from typing import Any

from pynput import keyboard, mouse

from .config import (
    LongPressConfig,
    normalize_gamepad_name,
    normalize_key_name,
    normalize_mouse_name,
)
from .logging_config import get_logger

logger = get_logger("listeners")

EventCallback = Callable[[str], None]


class LongPressTracker:
    def __init__(self, callback: EventCallback, config: LongPressConfig) -> None:
        self._callback = callback
        self._config = config
        self._lock = Lock()
        self._states: dict[str, Timer | None] = {}
        self._triggered: set[str] = set()
        logger.debug(
            "长按跟踪器已创建: enabled=%s threshold=%s interval=%s emit_press=%s suffix=%s",
            config.enabled,
            config.threshold,
            config.interval,
            config.emit_press,
            config.event_suffix,
        )

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def emit_press(self) -> bool:
        return self._config.emit_press

    def was_long_pressed(self, event_name: str) -> bool:
        with self._lock:
            return event_name in self._triggered

    def press(self, event_name: str) -> None:
        if not self._config.enabled:
            self._callback(event_name)
            return
        with self._lock:
            if event_name in self._states:
                logger.debug("忽略重复按下事件: %s", event_name)
                return
            timer = Timer(self._config.threshold, self._emit_long_press, (event_name,))
            timer.daemon = True
            self._states[event_name] = timer
            timer.start()
        if self._config.emit_press:
            self._callback(event_name)

    def release(self, event_name: str) -> None:
        if not self._config.enabled:
            return
        with self._lock:
            timer = self._states.pop(event_name, None)
            self._triggered.discard(event_name)
        if timer is not None:
            timer.cancel()
            logger.debug("释放事件已取消长按计时: %s", event_name)

    def stop(self) -> None:
        with self._lock:
            timers = tuple(
                timer for timer in self._states.values() if timer is not None
            )
            self._states.clear()
            self._triggered.clear()
        for timer in timers:
            timer.cancel()

    def _emit_long_press(self, event_name: str) -> None:
        long_press_event = f"{event_name}{self._config.event_suffix}"
        with self._lock:
            self._triggered.add(event_name)
        logger.debug("触发长按事件: %s", long_press_event)
        self._callback(long_press_event)
        if self._config.interval <= 0:
            with self._lock:
                if event_name in self._states:
                    self._states[event_name] = None
            return
        timer = Timer(self._config.interval, self._emit_long_press, (event_name,))
        timer.daemon = True
        with self._lock:
            if event_name not in self._states:
                timer.cancel()
                return
            self._states[event_name] = timer
            timer.start()


class KeyboardListener:
    def __init__(
        self,
        callback: EventCallback,
        *,
        trigger_on_release: bool = False,
        long_press: LongPressConfig | None = None,
    ) -> None:
        self._callback = callback
        self._trigger_on_release = trigger_on_release
        self._long_press = LongPressTracker(callback, long_press or LongPressConfig())
        self._listener: keyboard.Listener | None = None
        logger.debug(
            "键盘监听器已创建: trigger_on_release=%s long_press=%s",
            trigger_on_release,
            self._long_press.enabled,
        )

    def start(self) -> None:
        logger.info("启动键盘监听器")
        if self._long_press.enabled:
            self._listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
        else:
            self._listener = keyboard.Listener(
                on_press=None if self._trigger_on_release else self._on_key,
                on_release=self._on_key if self._trigger_on_release else None,
            )
        self._listener.start()

    def stop(self) -> None:
        self._long_press.stop()
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

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key is None:
            return
        name = key_to_name(key)
        if name:
            logger.debug("键盘按下事件: %s", name)
            self._long_press.press(name)

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key is None:
            return
        name = key_to_name(key)
        if name:
            logger.debug("键盘释放事件: %s", name)
            was_long = self._long_press.was_long_pressed(name)
            self._long_press.release(name)
            if self._trigger_on_release:
                self._callback(name)
            elif not self._long_press.emit_press and not was_long:
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

    def __init__(
        self, callback: EventCallback, *, long_press: LongPressConfig | None = None
    ) -> None:
        self._callback = callback
        self._long_press = LongPressTracker(callback, long_press or LongPressConfig())
        self._listener: mouse.Listener | None = None
        logger.debug("鼠标监听器已创建: long_press=%s", self._long_press.enabled)

    def start(self) -> None:
        logger.info("启动鼠标监听器")
        self._listener = mouse.Listener(
            on_click=self._on_click, on_scroll=self._on_scroll
        )
        self._listener.start()

    def stop(self) -> None:
        self._long_press.stop()
        if self._listener is not None:
            logger.info("停止鼠标监听器")
            self._listener.stop()
            self._listener = None

    def _on_click(self, x: int, y: int, button: Any, pressed: bool) -> None:
        name = mouse_button_to_name(button)
        if not name:
            return
        logger.debug("鼠标点击事件: %s pressed=%s x=%s y=%s", name, pressed, x, y)
        if self._long_press.enabled:
            if pressed:
                self._long_press.press(name)
            else:
                was_long = self._long_press.was_long_pressed(name)
                self._long_press.release(name)
                if not self._long_press.emit_press and not was_long:
                    self._callback(name)
            return
        if pressed:
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
