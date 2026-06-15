from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from random import choice
from threading import Lock

import pygame

from .config import AppConfig, Binding
from .logging_config import get_logger

logger = get_logger("player")


class SoundPlayer:
    """Low-latency pygame mixer based sound player."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._lock = Lock()
        self._round_robin: dict[str, int] = defaultdict(int)
        self._sounds: dict[Path, pygame.mixer.Sound] = {}
        self._current_channel: pygame.mixer.Channel | None = None
        self._started = False
        logger.debug("音频播放器已创建")

    def start(self) -> None:
        if self._started:
            logger.debug("音频播放器已启动，跳过重复启动")
            return
        audio = self._config.audio
        logger.info(
            "初始化音频: frequency=%s size=%s channels=%s buffer=%s volume=%s channel_count=%s",
            audio.frequency,
            audio.size,
            audio.channels,
            audio.buffer,
            audio.volume,
            self._config.playback.channel_count,
        )
        pygame.mixer.pre_init(
            frequency=audio.frequency,
            size=audio.size,
            channels=audio.channels,
            buffer=audio.buffer,
        )
        pygame.init()
        pygame.mixer.set_num_channels(self._config.playback.channel_count)
        preloaded_count = 0
        for binding in self._iter_bindings():
            for path in binding.sounds:
                self._load_sound(path)
                preloaded_count += 1
        self._started = True
        logger.info(
            "音频播放器已启动，预加载音效引用数=%s，唯一音效数=%s",
            preloaded_count,
            len(self._sounds),
        )

    def stop(self) -> None:
        with self._lock:
            if not self._started:
                logger.debug("音频播放器未启动，跳过停止")
                return
            logger.info("停止音频播放器")
            pygame.mixer.stop()
            pygame.mixer.quit()
            pygame.quit()
            self._started = False

    def play_for_event(self, event_name: str) -> bool:
        binding = self._config.bindings.get(event_name)
        if binding is None:
            binding = self._config.bindings.get("*") or self._config.default_binding
            if binding is not None:
                logger.debug("事件使用默认绑定: event=%s", event_name)
        if binding is None:
            logger.debug("事件无绑定: event=%s", event_name)
            return False
        self.play(event_name, binding)
        return True

    def play(self, event_name: str, binding: Binding) -> None:
        if not binding.sounds:
            logger.warning("事件绑定没有音效: event=%s", event_name)
            return
        with self._lock:
            sound_path = self._choose_sound_path(event_name, binding)
            sound = self._load_sound(sound_path)
            sound.set_volume(self._config.audio.volume)
            should_interrupt = (
                self._config.playback.interrupt
                if binding.interrupt is None
                else binding.interrupt
            )
            if should_interrupt:
                logger.debug(
                    "打断当前音效并播放: event=%s sound=%s", event_name, sound_path
                )
                pygame.mixer.stop()
                self._current_channel = pygame.mixer.find_channel(force=True)
            else:
                logger.debug("叠放播放音效: event=%s sound=%s", event_name, sound_path)
                self._current_channel = pygame.mixer.find_channel(force=True)
            self._current_channel.play(sound)

    def _choose_sound_path(self, event_name: str, binding: Binding) -> Path:
        if len(binding.sounds) == 1:
            return binding.sounds[0]
        if binding.rotation == "random" or self._config.playback.rotation == "random":
            sound_path = choice(binding.sounds)
            logger.debug("随机选择音效: event=%s sound=%s", event_name, sound_path)
            return sound_path
        index = self._round_robin[event_name] % len(binding.sounds)
        self._round_robin[event_name] += 1
        sound_path = binding.sounds[index]
        logger.debug(
            "轮播选择音效: event=%s index=%s sound=%s", event_name, index, sound_path
        )
        return sound_path

    def _load_sound(self, path: Path) -> pygame.mixer.Sound:
        resolved = path.resolve()
        sound = self._sounds.get(resolved)
        if sound is None:
            if not resolved.exists():
                logger.error("音效文件不存在: %s", resolved)
                raise FileNotFoundError(f"音效文件不存在: {resolved}")
            logger.debug("加载音效: %s", resolved)
            sound = pygame.mixer.Sound(str(resolved))
            self._sounds[resolved] = sound
        return sound

    def _iter_bindings(self) -> list[Binding]:
        bindings = list(self._config.bindings.values())
        if self._config.default_binding is not None:
            bindings.append(self._config.default_binding)
        return bindings
