"""控制输入的抽象接口。

任何输入方式（键盘、摄像头、鼠标、手柄……）只要实现
    step(dt) -> ControlState
就能直接接入游戏，Presenter / Model / View 一行都不用改。
"""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ControlState:
    """一帧的控制结果。"""

    # 核心信号：目标高度 0.0=屏幕底部，1.0=屏幕顶部
    target_height: float = 0.5

    # 俯卧撑统计（姿势矫正 / 计数）
    pushup_count: int = 0
    amplitude: float = 0.0

    # 手肘姿势（摄像头模式下有值；键盘模式为 None）
    elbow_angle: Optional[float] = None
    form_ok: Optional[bool] = None

    # 画面里是否检测到人（仅摄像头模式有值）
    pose_visible: Optional[bool] = None

    # 眼睛的位置（0~1，相对画面宽高；仅摄像头模式有值）
    pointer_x: Optional[float] = None
    pointer_y: Optional[float] = None

    # 波浪通道的中心应当对准你的脸（屏幕像素 y；仅摄像头模式有值）
    wave_center_y: Optional[float] = None

    # 参考位置：你静止时脸所在的高度（0~1），准备界面用它画弧形标记
    reference_y: Optional[float] = None

    # 调试用：检测到的各个眼角/眼睛关键点 (x, y)，0~1
    eye_points: Optional[Any] = None

    # 调试用：肩 / 肘 / 腕 三个关键点 (x, y)，0~1
    arm_points: Optional[Any] = None

    # 手臂三个点是否都在画面内（不在画面内时手肘角度不可信）
    arm_in_frame: Optional[bool] = None

    # 摄像头原始画面（RGB uint8 数组），供 View 当背景用。
    # 用 seq 判断是不是新的一帧，避免每帧重复转换。
    camera_frame: Optional[Any] = None
    camera_frame_seq: int = 0

    # 当前输入模式名，用于 HUD 显示
    mode: str = "unknown"


class ControlSource(ABC):
    """控制源基类。"""

    mode: str = "base"

    def start(self) -> None:
        """初始化（如打开摄像头）。默认无操作。"""

    def step(self, dt: float, *, up: bool = False, down: bool = False) -> ControlState:
        """推进一帧并返回控制状态。

        up / down 仅键盘类实现使用，其他实现可忽略。
        """
        raise NotImplementedError

    def reset(self) -> None:
        """重新开始一局时重置内部状态。默认无操作。"""

    def close(self) -> None:
        """释放资源。默认无操作。"""
