from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from queue import SimpleQueue
from threading import Event

from .config import AppConfig, load_config
from .listeners import GamepadListener, KeyboardListener, MouseListener
from .logging_config import configure_logging, get_logger
from .player import SoundPlayer

logger = get_logger("cli")


@dataclass(frozen=True, slots=True)
class RuntimeArgs:
    config: Path
    log_level: str
    verbose: bool
    quiet: bool


class App:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._player = SoundPlayer(config)
        self._events: SimpleQueue[str] = SimpleQueue()
        self._stop_event = Event()
        self._keyboard = KeyboardListener(
            self._enqueue, trigger_on_release=config.listener.trigger_on_release
        )
        self._mouse = MouseListener(self._enqueue)
        self._gamepad = GamepadListener(
            self._enqueue, retry_interval=config.listener.gamepad_poll_interval
        )
        logger.debug("运行时应用已初始化: base_dir=%s", config.base_dir)

    def run(self) -> None:
        logger.info("正在启动 keyhit-soundplayer")
        self._player.start()
        if self._config.listener.keyboard:
            self._keyboard.start()
        else:
            logger.info("键盘监听已被配置禁用")
        if self._config.listener.mouse:
            self._mouse.start()
        else:
            logger.info("鼠标监听已被配置禁用")
        if self._config.listener.gamepad:
            self._gamepad.start()
        else:
            logger.info("手柄监听已被配置禁用")
        logger.info("keyhit-soundplayer 已启动，按 Ctrl+C 退出")
        try:
            while not self._stop_event.is_set():
                if self._events.empty():
                    self._stop_event.wait(0.01)
                    continue
                event_name = self._events.get()
                logger.debug("收到输入事件: %s", event_name)
                try:
                    played = self._player.play_for_event(event_name)
                    if not played:
                        logger.debug("输入事件未匹配任何绑定: %s", event_name)
                        continue
                except Exception:
                    logger.exception("播放失败: event=%s", event_name)
        except KeyboardInterrupt:
            logger.info("收到退出信号")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        logger.info("正在停止 keyhit-soundplayer")
        self._stop_event.set()
        self._keyboard.stop()
        self._mouse.stop()
        self._gamepad.stop()
        self._player.stop()
        logger.info("keyhit-soundplayer 已停止")

    def _enqueue(self, event_name: str) -> None:
        logger.debug("输入事件入队: %s", event_name)
        self._events.put(event_name)


def parse_args(argv: list[str] | None = None) -> RuntimeArgs:
    import argparse

    parser = argparse.ArgumentParser(description="Global key hit sound player")
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="配置文件路径，默认当前目录下的 config.toml",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="日志级别，默认 INFO",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="启用 DEBUG 日志",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="仅输出 WARNING 及以上日志",
    )
    args = parser.parse_args(argv)
    return RuntimeArgs(
        config=args.config,
        log_level=args.log_level,
        verbose=args.verbose,
        quiet=args.quiet,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level, verbose=args.verbose, quiet=args.quiet)
    logger.debug("命令行参数: %s", args)
    config = load_config(args.config)
    app = App(config)
    app.run()
    return 0
