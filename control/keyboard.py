"""键盘控制源。

用 ↑/↓（或 W/S）连续调节一个虚拟"身体高度"，
再喂给和摄像头完全相同的 target_height 接口。

这样即使没有摄像头，也能完整验证游戏逻辑，
并且它正是"后端替换"演示里的那个替换目标。
"""
from __future__ import annotations

import config
from control.base import ControlSource, ControlState
from core.signal import PushupCounter, clamp


class KeyboardControlSource(ControlSource):
    mode = "键盘"

    def __init__(self, rate: float = 0.9) -> None:
        # rate: 每秒能改变多少归一化高度（0.9 ≈ 1.1 秒走完整个范围）
        self.rate = rate
        self.value = 0.5
        self.counter = PushupCounter(
            band=config.PUSHUP_BAND,
            min_range=config.PUSHUP_MIN_RANGE,
            window=config.PUSHUP_WINDOW,
            min_interval=config.PUSHUP_MIN_INTERVAL,
        )

    def step(self, dt: float, *, up: bool = False, down: bool = False) -> ControlState:
        if up:
            self.value += self.rate * dt
        if down:
            self.value -= self.rate * dt
        self.value = clamp(self.value, 0.0, 1.0)

        self.counter.update(self.value, dt)
        return self._state()

    def reset(self) -> None:
        self.counter.reset()

    def _state(self) -> ControlState:
        return ControlState(
            target_height=self.value,
            pushup_count=self.counter.count,
            amplitude=self.counter.amplitude,
            elbow_angle=None,
            form_ok=None,
            mode=self.mode,
        )
