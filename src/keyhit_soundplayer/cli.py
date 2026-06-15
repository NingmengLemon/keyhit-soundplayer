from __future__ import annotations

from pathlib import Path
from queue import SimpleQueue
from threading import Event
from typing import Annotated

import typer

from .config import AppConfig, RuntimeSettings, load_config
from .listeners import GamepadListener, KeyboardListener, MouseListener
from .logging_config import configure_logging, get_logger
from .player import SoundPlayer

logger = get_logger("cli")

typer_app = typer.Typer(
    add_completion=False,
    help="Global key hit sound player",
    no_args_is_help=False,
)

LogLevel = Annotated[
    str,
    typer.Option(
        "--log-level",
        help="日志级别，默认 INFO",
        case_sensitive=False,
    ),
]

ConfigPath = Annotated[
    Path,
    typer.Option(
        "--config",
        "-c",
        help="配置文件路径，默认当前目录下的 config.toml，也可用 KEYHIT_CONFIG 覆盖",
    ),
]

VerboseFlag = Annotated[
    bool,
    typer.Option("--verbose", "-v", help="启用 DEBUG 日志"),
]

QuietFlag = Annotated[
    bool,
    typer.Option("--quiet", "-q", help="仅输出 WARNING 及以上日志"),
]


class App:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._player = SoundPlayer(config)
        self._events: SimpleQueue[str] = SimpleQueue()
        self._stop_event = Event()
        self._keyboard = KeyboardListener(
            self._enqueue,
            trigger_on_release=config.listener.trigger_on_release,
            long_press=config.listener.long_press,
        )
        self._mouse = MouseListener(
            self._enqueue, long_press=config.listener.long_press
        )
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


@typer_app.command()
def run(
    config: ConfigPath = Path("config.toml"),
    log_level: LogLevel = "INFO",
    verbose: VerboseFlag = False,
    quiet: QuietFlag = False,
) -> None:
    settings = RuntimeSettings(
        config=config,
        log_level=log_level,
        verbose=verbose,
        quiet=quiet,
    )
    configure_logging(
        settings.log_level, verbose=settings.verbose, quiet=settings.quiet
    )
    logger.debug("运行配置: %s", settings)
    loaded_config = load_config(settings.config)
    app = App(loaded_config)
    app.run()


def main(argv: list[str] | None = None) -> int:
    typer_app(args=argv, prog_name="keyhit-soundplayer")
    return 0
