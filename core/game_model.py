"""模型层核心：游戏规则与物理。

设计要点：
  * 本模块完全不 import pygame / opencv / mediapipe，纯粹是数据与规则；
  * 输入只有一个抽象量：target_height ∈ [0, 1]（0=屏幕底部，1=屏幕顶部）；
  * 因此"键盘版"与"摄像头版"只需提供同一个 target_height，
    Model 与小游戏本身不需要任何改动 —— 这就是前后端解耦的落点。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List

import config
from core.entities import Bird, Pipe
from core.signal import clamp


@dataclass
class PipeView:
    """供视图层渲染的柱子快照（屏幕坐标）。"""

    screen_x: float
    gap_top: float
    gap_bottom: float


@dataclass
class GameSnapshot:
    """一帧的只读快照，View 只依赖它，不直接接触 Model。"""

    bird_x: float
    bird_y: float
    pipes: List[PipeView]
    score: int
    speed: float
    amplitude: float
    scroll_offset: float
    game_over: bool


class GameModel:
    def __init__(self) -> None:
        self.reset()

    # ------------------------------------------------------------------
    def reset(self) -> None:
        self.bird = Bird(x=config.BIRD_X, y=config.GAP_CENTER_MID)
        self.pipes: List[Pipe] = []
        self.scroll_offset: float = 0.0
        self.next_pipe_world_x: float = config.FIRST_PIPE_OFFSET
        self.score: int = 0
        self.game_over: bool = False
        self._target_height: float = 0.5
        self._ar_mode: bool = False
        self._wave_center: float = None

    # ------------------------------------------------------------------
    # 几何
    # ------------------------------------------------------------------
    @property
    def speed(self) -> float:
        return min(
            config.SCROLL_SPEED_MAX,
            config.SCROLL_SPEED_START + self.score * config.SCROLL_SPEED_PER_SCORE,
        )

    @property
    def amplitude(self) -> float:
        return min(
            config.WAVE_AMPLITUDE_MAX,
            config.WAVE_AMPLITUDE_START + self.score * config.WAVE_AMPLITUDE_PER_SCORE,
        )

    def _gap_limits(self):
        """缝隙中心允许的范围。

        AR 模式下没有地面，可以用满整个屏幕，让缝隙围绕你的脸摆动。
        """
        half = config.GAP_HEIGHT / 2.0
        if self._ar_mode:
            margin = config.AR_GAP_MARGIN
            return half + margin, config.SCREEN_H - half - margin
        return config.GAP_CENTER_MIN, config.GAP_CENTER_MAX

    def gap_center(self, world_x: float) -> float:
        """缝隙中心随世界坐标做固定正弦摆动 —— 这就是"上上下下的通道"。"""
        center = self._wave_center if self._wave_center is not None else config.GAP_CENTER_MID
        raw = center + self.amplitude * math.sin(
            2.0 * math.pi * world_x / config.WAVE_LENGTH
        )
        lo, hi = self._gap_limits()
        return clamp(raw, lo, hi)

    def _height_norm_to_y(self, norm: float) -> float:
        """把 0~1 的控制量映射成屏幕 y（注意 y 轴向下）。"""
        top_y = config.TOP_MARGIN + config.BIRD_RADIUS
        bottom_y = config.SCREEN_H - config.BOTTOM_MARGIN - config.BIRD_RADIUS
        return bottom_y - clamp(norm, 0.0, 1.0) * (bottom_y - top_y)

    # ------------------------------------------------------------------
    # 每帧推进
    # ------------------------------------------------------------------
    def step(
        self,
        dt: float,
        target_height: float,
        pointer_x: float = None,
        pointer_y: float = None,
        wave_center: float = None,
    ) -> None:
        if self.game_over:
            return
        self._target_height = clamp(target_height, 0.0, 1.0)
        self._ar_mode = pointer_y is not None
        self._wave_center = wave_center

        alpha = 1.0 - math.exp(-config.BIRD_FOLLOW_RATE * dt)

        # 1) 垂直方向
        if pointer_y is not None:
            # AR 模式：小鸟就是你眼睛在画面里的位置，不做任何夹紧
            target_y = clamp(pointer_y, 0.0, 1.0) * config.SCREEN_H
        else:
            target_y = self._height_norm_to_y(self._target_height)
        self.bird.y += (target_y - self.bird.y) * alpha

        # 2) 水平方向：摄像头模式下直接贴着眼睛，键盘模式固定不动
        if pointer_x is None:
            target_x = config.BIRD_X
        else:
            target_x = clamp(
                pointer_x * config.SCREEN_W, config.BIRD_X_MIN, config.BIRD_X_MAX
            )
        self.bird.x += (target_x - self.bird.x) * alpha

        # 2) 世界滚动
        self.scroll_offset += self.speed * dt

        # 3) 生成 / 回收管道
        while self.next_pipe_world_x < self.scroll_offset + config.SCREEN_W + config.PIPE_SPACING:
            self.pipes.append(Pipe(world_x=self.next_pipe_world_x))
            self.next_pipe_world_x += config.PIPE_SPACING
        self.pipes = [
            p for p in self.pipes if p.world_x - self.scroll_offset > -config.PIPE_W - 20
        ]

        # 4) 碰撞 + 计分
        self._check_collisions()
        self._update_score()

    def follow(self, dt: float, pointer_x: float = None, pointer_y: float = None) -> None:
        """准备界面专用：只让小鸟跟着人走，不推进管道/计分。"""
        alpha = 1.0 - math.exp(-config.BIRD_FOLLOW_RATE * dt)
        if pointer_y is not None:
            target_y = clamp(pointer_y, 0.0, 1.0) * config.SCREEN_H
            self.bird.y += (target_y - self.bird.y) * alpha
        if pointer_x is not None:
            target_x = clamp(
                pointer_x * config.SCREEN_W, config.BIRD_X_MIN, config.BIRD_X_MAX
            )
            self.bird.x += (target_x - self.bird.x) * alpha

    # ------------------------------------------------------------------
    def _check_collisions(self) -> None:
        r = config.BIRD_RADIUS
        bird_left = self.bird.x - r
        bird_right = self.bird.x + r
        half_gap = config.GAP_HEIGHT / 2.0

        # 上下边界（AR 模式下小鸟跟着眼睛走，不判边界，只有撞柱子才算死）
        if not self._ar_mode:
            if self.bird.y - r < config.TOP_MARGIN or self.bird.y + r > config.SCREEN_H - config.BOTTOM_MARGIN:
                self.game_over = True
                return

        for p in self.pipes:
            sx = p.world_x - self.scroll_offset
            if bird_right < sx or bird_left > sx + config.PIPE_W:
                continue
            center = self.gap_center(p.world_x)
            gap_top = center - half_gap
            gap_bottom = center + half_gap
            if self.bird.y - r < gap_top or self.bird.y + r > gap_bottom:
                self.game_over = True
                return

    def _update_score(self) -> None:
        for p in self.pipes:
            if not p.scored and (p.world_x - self.scroll_offset) + config.PIPE_W < self.bird.x:
                p.scored = True
                self.score += 1

    # ------------------------------------------------------------------
    def snapshot(self) -> GameSnapshot:
        half_gap = config.GAP_HEIGHT / 2.0
        pipe_views: List[PipeView] = []
        for p in self.pipes:
            sx = p.world_x - self.scroll_offset
            center = self.gap_center(p.world_x)
            pipe_views.append(
                PipeView(screen_x=sx, gap_top=center - half_gap, gap_bottom=center + half_gap)
            )
        return GameSnapshot(
            bird_x=self.bird.x,
            bird_y=self.bird.y,
            pipes=pipe_views,
            score=self.score,
            speed=self.speed,
            amplitude=self.amplitude,
            scroll_offset=self.scroll_offset,
            game_over=self.game_over,
        )
