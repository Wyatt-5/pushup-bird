"""表现层（MVP 中的 Presenter）。

只做三件事：
  1. 从 ControlSource 取控制量；
  2. 交给 GameModel 推进逻辑；
  3. 把快照与 HUD 交给 View 渲染。
它不 import pygame，也不知道游戏规则和画法。
"""
from __future__ import annotations

from typing import Dict

import config
from control.base import ControlSource, ControlState
from core.game_model import GameModel


class GamePresenter:
    def __init__(self, model: GameModel, control: ControlSource, view,
                 audio=None, voice=None) -> None:
        self.model = model
        self.control = control
        self.view = view
        self.audio = audio          # 有 play()/start_bgm()/stop_bgm() 即可
        self.voice = voice          # 有 consume() 即可
        self.running: bool = True
        self.started: bool = False
        self.debug_eyes: bool = False
        self.warn_frames: int = 0
        self._prev_game_over: bool = False
        self._die_delay: int = 0
        self._state = ControlState(mode=control.mode)

    # ------------------------------------------------------------------
    def run(self) -> None:
        self.control.start()
        try:
            while self.running:
                dt = self.view.tick(config.FPS)
                self._handle_events()
                self._update(dt)
                self.view.render(self.model.snapshot(), self._hud())
        finally:
            if self.voice is not None:
                try:
                    self.voice.close()
                except Exception:
                    pass
            if self.audio is not None:
                try:
                    self.audio.close()
                except Exception:
                    pass
            self.control.close()
            self.view.close()

    # ------------------------------------------------------------------
    def _handle_events(self) -> None:
        for command in self.view.poll_events():
            if command == "quit":
                self.running = False
            elif command == "confirm":
                self._on_confirm()
            elif command == "restart":
                self._restart()
            elif command == "toggle_debug":
                self.debug_eyes = not self.debug_eyes

    def _on_confirm(self) -> None:
        """空格：结束后重开；未开始时尝试开始（要求先识别到人）。"""
        if self.model.game_over:
            self._restart()
            return
        if self.started:
            return
        if self._can_start():
            self.started = True
            if self.audio is not None:
                self.audio.start_bgm()
        else:
            self.warn_frames = 120

    def _can_start(self) -> bool:
        """摄像头模式下必须先识别到人，才允许开始。"""
        if self._state.mode == "键盘":
            return True
        return self._state.pose_visible is True

    def _restart(self) -> None:
        """重开一局：清空模型与控制状态，并退回"准备"界面。"""
        self.model.reset()
        self.control.reset()
        self.started = False
        self.warn_frames = 0
        self._prev_game_over = False
        self._die_delay = 0
        if self.audio is not None:
            self.audio.stop_bgm()

    # ------------------------------------------------------------------
    def _update(self, dt: float) -> None:
        if self.warn_frames > 0:
            self.warn_frames -= 1

        # 语音说"开始"等同按空格
        if self.voice is not None:
            try:
                if self.voice.consume():
                    self._on_confirm()
            except Exception:
                pass

        up, down = self.view.read_move_keys()
        self._state = self.control.step(dt, up=up, down=down)
        if self.started and not self.model.game_over:
            self.model.step(
                dt,
                self._state.target_height,
                self._state.pointer_x,
                self._state.pointer_y,
                self._state.wave_center_y,
            )
        else:
            # 准备界面/结束时也让人看到小鸟贴着自己的脸
            self.model.follow(dt, self._state.pointer_x, self._state.pointer_y)

        self._handle_audio_events()

    def _handle_audio_events(self) -> None:
        """撞柱瞬间播 hit，稍后播 die。"""
        over = self.model.game_over
        if over and not self._prev_game_over:
            self._die_delay = 16
            if self.audio is not None:
                self.audio.play("hit")
        if self._die_delay > 0:
            self._die_delay -= 1
            if self._die_delay == 0 and self.audio is not None:
                self.audio.play("die")
        self._prev_game_over = over

    # ------------------------------------------------------------------
    def _hud(self) -> Dict:
        s = self._state
        if s.mode == "摄像头" and s.arm_in_frame is False:
            form_text = "手肘：手臂不在画面内"
            form_ok = False
        elif s.elbow_angle is None:
            # 摄像头模式下手肘检测默认关闭，就不显示这一行
            form_text = "姿势  --（键盘模式）" if s.mode == "键盘" else ""
            form_ok = True
        else:
            form_text = f"手肘 {s.elbow_angle:3.0f}°  {'到位' if s.form_ok else '不到位'}"
            form_ok = bool(s.form_ok)

        mode_text = s.mode
        if s.pose_visible is True:
            mode_text = f"{s.mode}·已识别"
        elif s.pose_visible is False:
            mode_text = f"{s.mode}·未识别"

        return {
            "mode": mode_text,
            "camera_frame": s.camera_frame,
            "camera_frame_seq": s.camera_frame_seq,
            "pushup_count": s.pushup_count,
            "amplitude": s.amplitude,
            "form_text": form_text,
            "form_ok": form_ok,
            "started": self.started,
            "can_start": self._can_start(),
            "warn": self.warn_frames > 0,
            "reference_y": s.reference_y,
            "eye_points": s.eye_points,
            "arm_points": s.arm_points,
            "arm_in_frame": s.arm_in_frame,
            "debug_eyes": self.debug_eyes,
        }
