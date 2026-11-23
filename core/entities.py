"""游戏内的纯数据实体（不包含行为，方便替换与测试）。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Pipe:
    """一根柱子。world_x 是世界坐标，不随滚动变化。"""

    world_x: float
    scored: bool = False


@dataclass
class Bird:
    """小鸟的位置。

    垂直方向由俯卧撑高度决定；水平方向在摄像头模式下跟着眼睛走，
    键盘模式下固定在 config.BIRD_X。
    """

    x: float
    y: float
