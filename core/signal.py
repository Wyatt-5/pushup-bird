"""信号处理工具：平滑、映射、俯卧撑计数。

纯 Python 实现，不依赖 pygame / opencv，可单独做单元测试，
也方便复用到摄像头（后端）版本。
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional, Tuple


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def map_range(v: float, in_lo: float, in_hi: float, out_lo: float, out_hi: float) -> float:
    """把 [in_lo, in_hi] 的数值线性映射到 [out_lo, out_hi]，超界自动夹紧。

    in_lo 可以大于 in_hi（用于把"图像 y 越大越靠下"翻转成"越大越靠上"）。
    """
    if in_hi == in_lo:
        return out_lo
    t = clamp((v - in_lo) / (in_hi - in_lo), 0.0, 1.0)
    return out_lo + (out_hi - out_lo) * t


class ExpSmoother:
    """一阶指数平滑，用于去掉摄像头/键盘信号的抖动。"""

    def __init__(self, alpha: float = 0.2) -> None:
        self.alpha = clamp(alpha, 0.0, 1.0)
        self.value: Optional[float] = None

    def update(self, x: float) -> float:
        if self.value is None:
            self.value = x
        else:
            self.value += self.alpha * (x - self.value)
        return self.value

    def reset(self) -> None:
        self.value = None


@dataclass
class PushupCounter:
    """根据一维高度信号（0~1）统计俯卧撑次数与幅度。

    使用自适应阈值，所以不管你幅度大小（键盘行程 / 摄像头俯卧撑深度），
    只要在最近 window 秒内有足够大的起伏，就能计数。

    判定逻辑：
      * lo/hi = 最近 window 秒内信号的最小/最大值；
      * 起伏范围 hi-lo 小于 min_range 时视为"没在动"，不计数；
      * 信号落到 lo + band*(hi-lo) 以下 -> 记为"下去"；
      * 状态为"下去"且信号升到 hi - band*(hi-lo) 以上 -> 计 1 次。
    """

    band: float = 0.25
    min_range: float = 0.15
    min_interval: float = 0.30
    window: float = 3.0

    count: int = 0
    amplitude: float = 0.0

    _state_is_down: bool = False
    _cooldown: float = 0.0
    _t: float = 0.0
    _buf: Deque[Tuple[float, float]] = field(default_factory=deque)

    def update(self, value: float, dt: float) -> None:
        value = clamp(value, 0.0, 1.0)
        self._t += dt
        self._cooldown = max(0.0, self._cooldown - dt)

        self._buf.append((self._t, value))
        while self._buf and (self._t - self._buf[0][0]) > self.window:
            self._buf.popleft()

        lo = min(v for _, v in self._buf)
        hi = max(v for _, v in self._buf)
        self.amplitude = hi - lo

        if (hi - lo) < self.min_range:
            return

        low_th = lo + (hi - lo) * self.band
        high_th = hi - (hi - lo) * self.band

        if value <= low_th:
            self._state_is_down = True
        elif value >= high_th and self._state_is_down:
            if self._cooldown <= 0.0:
                self.count += 1
                self._cooldown = self.min_interval
            self._state_is_down = False

    def reset(self) -> None:
        self.count = 0
        self.amplitude = 0.0
        self._state_is_down = False
        self._cooldown = 0.0
        self._t = 0.0
        self._buf.clear()
