from __future__ import annotations

import logging
import sys
from typing import Final

LOGGER_NAME: Final[str] = "keyhit_soundplayer"
DEFAULT_FORMAT: Final[str] = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
DEFAULT_DATE_FORMAT: Final[str] = "%H:%M:%S"


def get_logger(name: str | None = None) -> logging.Logger:
    if name:
        return logging.getLogger(f"{LOGGER_NAME}.{name}")
    return logging.getLogger(LOGGER_NAME)


def configure_logging(
    level: str = "INFO", *, verbose: bool = False, quiet: bool = False
) -> None:
    resolved_level = _resolve_level(level, verbose=verbose, quiet=quiet)
    root_logger = logging.getLogger(LOGGER_NAME)
    root_logger.setLevel(resolved_level)
    root_logger.propagate = False

    handler = _get_or_create_console_handler(root_logger)
    handler.setLevel(resolved_level)
    handler.setFormatter(logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT))


def _resolve_level(level: str, *, verbose: bool, quiet: bool) -> int:
    if quiet:
        return logging.WARNING
    if verbose:
        return logging.DEBUG
    normalized = level.strip().upper()
    value = getattr(logging, normalized, None)
    if isinstance(value, int):
        return value
    raise ValueError(f"未知日志级别: {level}")


def _get_or_create_console_handler(logger: logging.Logger) -> logging.Handler:
    for handler in logger.handlers:
        if getattr(handler, "_keyhit_console", False):
            return handler
    handler = logging.StreamHandler(sys.stderr)
    setattr(handler, "_keyhit_console", True)
    logger.addHandler(handler)
    return handler
