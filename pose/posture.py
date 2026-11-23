"""手肘姿态分析与俯卧撑计数（纯算法，不依赖 opencv / mediapipe）。

对应需求里的"姿势矫正"：
  * 用 肩-肘-腕 三点计算手肘夹角；
  * 用回滞阈值把连续角度判定成"弯曲 / 伸直 / 过渡中"；
  * 统计有效的俯卧撑次数，并给出动作是否到位。
"""
from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple

Point = Tuple[float, float]


def angle_at(a: Point, b: Point, c: Point) -> float:
    """计算以 b 为顶点、a-b-c 的夹角（角度制，0~180）。"""
    v1x, v1y = a[0] - b[0], a[1] - b[1]
    v2x, v2y = c[0] - b[0], c[1] - b[1]
    n1 = math.hypot(v1x, v1y)
    n2 = math.hypot(v2x, v2y)
    if n1 < 1e-6 or n2 < 1e-6:
        return 180.0
    cos = (v1x * v2x + v1y * v2y) / (n1 * n2)
    cos = max(-1.0, min(1.0, cos))
    return math.degrees(math.acos(cos))


class ElbowFormAnalyzer:
    """把手肘角度序列变成"俯卧撑次数 + 动作到位与否"。

    down_angle: 夹角小于它 → 判定为"下去（弯曲到位）"
    up_angle:   夹角大于它 → 判定为"撑起（伸直到位）"
    两者之间为过渡区，不做计数，避免抖动。
    """

    def __init__(self, down_angle: float = 95.0, up_angle: float = 150.0,
                 min_interval: float = 0.35) -> None:
        self.down_angle = down_angle
        self.up_angle = up_angle
        self.min_interval = min_interval

        self.angle: Optional[float] = None
        self.count: int = 0
        self.form_ok: bool = True

        self._is_down: bool = False
        self._cooldown: float = 0.0

    @property
    def phase(self) -> str:
        if self.angle is None:
            return "无信号"
        if self.angle <= self.down_angle:
            return "下压到位"
        if self.angle >= self.up_angle:
            return "撑起到位"
        return "过渡中"

    def update(self, angle: float, dt: float) -> None:
        self.angle = angle
        self._cooldown = max(0.0, self._cooldown - dt)

        if angle <= self.down_angle:
            self._is_down = True
            self.form_ok = True
        elif angle >= self.up_angle:
            if self._is_down and self._cooldown <= 0.0:
                self.count += 1
                self._cooldown = self.min_interval
            self._is_down = False
            self.form_ok = True
        else:
            # 停在中间：算"没做标准"
            self.form_ok = False

    def reset(self) -> None:
        self.angle = None
        self.count = 0
        self.form_ok = True
        self._is_down = False
        self._cooldown = 0.0
