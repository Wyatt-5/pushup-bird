"""背景音乐与音效播放。

资源来自 assets/audio/：
    bgm.wav   程序合成（tools/make_bgm.py 生成，无版权问题）
    hit.wav / die.wav / wing.wav / point.wav   来自 Flappy Bird 素材集

所有播放都做了异常兜底：没有声卡、mixer 初始化失败时游戏照常运行。
"""
from __future__ import annotations

import os

import pygame

AUDIO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "audio"
)


class SoundManager:
    def __init__(self, bgm_volume: float = 0.28, sfx_volume: float = 0.7,
                 enabled: bool = True) -> None:
        self.enabled = False
        self.error: str = ""
        self._sounds = {}
        self._bgm_path = os.path.join(AUDIO_DIR, "bgm.wav")
        self._bgm_volume = bgm_volume

        if not enabled:
            self.error = "已通过参数关闭"
            return

        try:
            pygame.mixer.init()
        except Exception as exc:  # 没有声卡/驱动时不要影响游戏
            self.error = f"mixer 初始化失败：{exc}"
            return

        for name in ("hit", "die", "wing", "point"):
            path = os.path.join(AUDIO_DIR, f"{name}.wav")
            if not os.path.exists(path):
                continue
            try:
                snd = pygame.mixer.Sound(path)
                snd.set_volume(sfx_volume)
                self._sounds[name] = snd
            except Exception:
                continue

        self.enabled = True

    # ------------------------------------------------------------------
    def start_bgm(self) -> None:
        if not self.enabled or not os.path.exists(self._bgm_path):
            return
        try:
            if not pygame.mixer.music.get_busy():
                pygame.mixer.music.load(self._bgm_path)
                pygame.mixer.music.set_volume(self._bgm_volume)
                pygame.mixer.music.play(-1)
        except Exception:
            pass

    def stop_bgm(self) -> None:
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

    def play(self, name: str) -> None:
        if not self.enabled:
            return
        snd = self._sounds.get(name)
        if snd is None:
            return
        try:
            snd.play()
        except Exception:
            pass

    def close(self) -> None:
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        try:
            pygame.mixer.quit()
        except Exception:
            pass
