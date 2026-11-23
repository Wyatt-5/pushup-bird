"""贴图资源：加载与预处理。

素材来自 Classic Flappy Bird 的公开重制版贴图集：
    https://github.com/samuelcust/flappy-bird-assets
（仅用于课程项目演示，版权归原作者所有）

本模块是唯一知道"图片从哪来、长什么样"的地方，
其他层不直接接触贴图文件。
"""
from __future__ import annotations

import os
from typing import Dict, List, Tuple

import pygame

import config

SPRITE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sprites"
)


def _path(name: str) -> str:
    path = os.path.join(SPRITE_DIR, name)
    if not os.path.exists(path):
        raise RuntimeError(f"缺少贴图文件：{path}")
    return path


def load(name: str) -> pygame.Surface:
    """加载一张贴图并转换成带 alpha 的显示格式。"""
    return pygame.image.load(_path(name)).convert_alpha()


# ----------------------------------------------------------------------
# 背景 / 地面
# ----------------------------------------------------------------------
def make_background(w: int, h: int) -> pygame.Surface:
    """把竖版背景按高度缩放后横向平铺。"""
    src = load("background-day.png")
    sw, sh = src.get_size()
    scale = h / sh
    tile_w = max(1, int(round(sw * scale)))
    tile = pygame.transform.smoothscale(src, (tile_w, h))

    surf = pygame.Surface((w, h)).convert()
    x = 0
    while x < w:
        surf.blit(tile, (x, 0))
        x += tile_w
    return surf


def make_ground(w: int, h: int) -> pygame.Surface:
    """底部地面条，横向平铺。"""
    src = load("base.png")
    sw, sh = src.get_size()
    scale = h / sh
    tile_w = max(1, int(round(sw * scale)))
    tile = pygame.transform.smoothscale(src, (tile_w, h))

    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    x = 0
    while x < w:
        surf.blit(tile, (x, 0))
        x += tile_w
    return surf


# ----------------------------------------------------------------------
# 小鸟
# ----------------------------------------------------------------------
BIRD_FRAME_NAMES: Tuple[str, str, str] = (
    "yellowbird-upflap.png",
    "yellowbird-midflap.png",
    "yellowbird-downflap.png",
)


def make_bird_frames(width: int, height: int) -> List[pygame.Surface]:
    """返回 [上挥翅, 平翅, 下挥翅] 三帧。"""
    return [
        pygame.transform.smoothscale(load(name), (width, height))
        for name in BIRD_FRAME_NAMES
    ]


# ----------------------------------------------------------------------
# 管道
# ----------------------------------------------------------------------
class PipeArt:
    """把 pipe-green.png 拆成"管口 + 管身"，并按需要的高度实时拼接。

    pipe-green.png 尺寸 52x320：
        * 第 0~23 行  是较宽的"管口"
        * 第 24~320 行 是较窄的"管身"
    这样拼接后，无论缝隙多高，管口都保持原始形状，管身被纵向拉长。
    """

    CAP_H_SRC = 24
    MAX_CACHE = 80

    def __init__(self, width: int) -> None:
        src = load("pipe-green.png")
        sw, sh = src.get_size()

        self.width = width
        self.cap_h = max(1, int(round(self.CAP_H_SRC * width / sw)))

        cap_src = src.subsurface(pygame.Rect(0, 0, sw, self.CAP_H_SRC)).copy()
        self._body_src = src.subsurface(
            pygame.Rect(0, self.CAP_H_SRC, sw, sh - self.CAP_H_SRC)
        ).copy()
        self._cap = pygame.transform.smoothscale(cap_src, (width, self.cap_h))

        self._cache: Dict[Tuple[int, bool], pygame.Surface] = {}

    def surface(self, height: int, flip: bool = False) -> pygame.Surface:
        """height 为整根管道的可见高度；flip=True 得到管口朝下的版本。"""
        height = max(self.cap_h + 2, int(height))
        key = (height, flip)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        if len(self._cache) > self.MAX_CACHE:
            self._cache.clear()

        surf = pygame.Surface((self.width, height), pygame.SRCALPHA)
        body_h = height - self.cap_h
        body = pygame.transform.smoothscale(self._body_src, (self.width, body_h))
        surf.blit(body, (0, self.cap_h))
        surf.blit(self._cap, (0, 0))

        if flip:
            surf = pygame.transform.flip(surf, False, True)

        self._cache[key] = surf
        return surf
