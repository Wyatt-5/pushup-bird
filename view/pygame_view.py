"""Pygame 视图实现。

职责单一：把 GameSnapshot + HUD 数据画到屏幕上。
不读取输入、不修改游戏状态。
"""
from __future__ import annotations

import math
import os
from typing import Dict, List, Optional

import pygame

import config
from core.game_model import GameSnapshot
from view.assets import PipeArt, load, make_background, make_bird_frames, make_ground


class PygameView:
    def __init__(self, title: str = "俯卧撑小鸟 Push-up Bird") -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((config.SCREEN_W, config.SCREEN_H))
        pygame.display.set_caption(title)
        self.clock = pygame.time.Clock()

        self.background = make_background(config.SCREEN_W, config.SCREEN_H)
        self.ground = make_ground(config.SCREEN_W, config.GROUND_H)
        self.bird_frames = make_bird_frames(config.BIRD_SPRITE_W, config.BIRD_SPRITE_H)
        self.pipe_art = PipeArt(config.PIPE_W)

        self._last_bird_y: Optional[float] = None

        # 摄像头背景缓存
        self._cam_surface: Optional[pygame.Surface] = None
        self._cam_seq: int = -1

        self.gameover_img: Optional[pygame.Surface] = None
        try:
            self.gameover_img = pygame.transform.smoothscale(
                load("gameover.png"), (288, 63)
            )
        except Exception:
            self.gameover_img = None

        self.font_big = self._font(64)
        self.font_mid = self._font(28)
        self.font_small = self._font(20)

    # ------------------------------------------------------------------
    _FONT_CANDIDATES = (
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhl.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\Deng.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    )

    @classmethod
    def _font(cls, size: int) -> pygame.font.Font:
        # 直接按文件路径加载，避免 pygame.font.match_font 在部分
        # Windows 字体注册表异常时抛 TypeError 的问题。
        for path in cls._FONT_CANDIDATES:
            if os.path.exists(path):
                try:
                    return pygame.font.Font(path, size)
                except Exception:
                    continue
        return pygame.font.Font(None, size)

    # ------------------------------------------------------------------
    def tick(self, fps: int) -> float:
        """限制帧率并返回本帧秒数。"""
        return self.clock.tick(fps) / 1000.0

    def poll_events(self) -> List[str]:
        """把按键翻译成与视图无关的语义命令。"""
        commands: List[str] = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                commands.append("quit")
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    commands.append("quit")
                elif event.key in (pygame.K_SPACE, pygame.K_RETURN):
                    commands.append("confirm")
                elif event.key == pygame.K_r:
                    commands.append("restart")
                elif event.key == pygame.K_F1:
                    commands.append("toggle_debug")
        return commands

    def read_move_keys(self):
        """返回 (上, 下) 按键状态，让 Presenter 不直接依赖 pygame。"""
        keys = pygame.key.get_pressed()
        up = keys[pygame.K_UP] or keys[pygame.K_w]
        down = keys[pygame.K_DOWN] or keys[pygame.K_s]
        return bool(up), bool(down)

    # ------------------------------------------------------------------
    def render(self, snap: GameSnapshot, hud: Dict) -> None:
        is_ar = hud.get("camera_frame") is not None
        self._draw_background(hud)
        self._draw_pipes(snap)
        if not is_ar:
            # AR 模式下不画地面，否则小鸟会"钻到地下"
            self.screen.blit(self.ground, (0, config.SCREEN_H - config.GROUND_H))
        self._draw_bird(snap)
        if hud.get("debug_eyes"):
            self._draw_eye_points(hud.get("eye_points"))
            self._draw_arm_points(
                hud.get("arm_points"), hud.get("form_text", ""), hud.get("arm_in_frame", True)
            )
        self._draw_hud(snap, hud)
        self._draw_overlays(snap, hud)
        pygame.display.flip()

    # ------------------------------------------------------------------
    def _draw_background(self, hud: Dict) -> None:
        """有摄像头画面就把它当背景（AR 模式），否则用静态天空背景。"""
        frame = hud.get("camera_frame")
        if frame is None:
            self.screen.blit(self.background, (0, 0))
            return

        seq = hud.get("camera_frame_seq", 0)
        if seq != self._cam_seq or self._cam_surface is None:
            height, width = frame.shape[:2]
            surface = pygame.image.frombuffer(frame.tobytes(), (width, height), "RGB")
            self._cam_surface = surface.convert()
            self._cam_seq = seq

        self.screen.blit(self._cam_surface, (0, 0))

    # ------------------------------------------------------------------
    def _draw_pipes(self, snap: GameSnapshot) -> None:
        art = self.pipe_art
        for pipe in snap.pipes:
            x = int(round(pipe.screen_x))
            if x > config.SCREEN_W or x + config.PIPE_W < 0:
                continue

            gap_top = int(round(pipe.gap_top))
            gap_bottom = int(round(pipe.gap_bottom))

            # 上方管道：管口朝下
            if gap_top > 0:
                self.screen.blit(art.surface(gap_top, flip=True), (x, 0))

            # 下方管道：管口朝上
            bottom_h = config.SCREEN_H - gap_bottom
            if bottom_h > 0:
                self.screen.blit(art.surface(bottom_h, flip=False), (x, gap_bottom))

    def _draw_eye_points(self, points) -> None:
        """调试标记：把检测到的眼角/眼睛关键点画成小红点（F1 开关）。"""
        if not points:
            return
        for nx, ny in points:
            pos = (int(nx * config.SCREEN_W), int(ny * config.SCREEN_H))
            pygame.draw.circle(self.screen, (255, 40, 40), pos, 6)
            pygame.draw.circle(self.screen, (255, 255, 255), pos, 6, 2)

    def _draw_arm_points(self, points, form_text: str = "", in_frame: bool = True) -> None:
        """调试标记：肩-肘-腕三个点连成一条线，肘部高亮（F1 开关）。

        有点跑出画面时贴到边缘并标红，提示"你的手没进画面"。
        """
        if not points or len(points) < 3:
            return

        max_x, max_y = config.SCREEN_W - 1, config.SCREEN_H - 1
        pts = []
        any_outside = False
        for nx, ny in points:
            px, py = int(nx * config.SCREEN_W), int(ny * config.SCREEN_H)
            if px < 0 or px > max_x or py < 0 or py > max_y:
                any_outside = True
            pts.append((max(0, min(max_x, px)), max(0, min(max_y, py))))

        ok = in_frame and not any_outside
        line_color = (0, 220, 255) if ok else (255, 60, 60)
        pygame.draw.lines(self.screen, line_color, False, pts, 4)

        for i, pos in enumerate(pts):
            radius = 8 if i == 1 else 6
            color = ((0, 255, 120) if i == 1 else (0, 160, 200)) if ok else (255, 60, 60)
            pygame.draw.circle(self.screen, color, pos, radius)
            pygame.draw.circle(self.screen, (255, 255, 255), pos, radius, 2)

        label = form_text if ok else "手臂不在画面内"
        surface = self.font_small.render(label, True, (0, 255, 120) if ok else (255, 80, 80))
        self.screen.blit(surface, (pts[1][0] + 12, pts[1][1] - 12))

    def _draw_bird(self, snap: GameSnapshot) -> None:
        # 按垂直速度挑帧：上升=上挥翅，下降=下挥翅，平移=平翅
        if self._last_bird_y is None:
            self._last_bird_y = snap.bird_y
        dy = snap.bird_y - self._last_bird_y
        self._last_bird_y = snap.bird_y

        if dy < -0.8:
            frame = 0
        elif dy > 0.8:
            frame = 2
        else:
            frame = 1

        image = self.bird_frames[frame]
        rect = image.get_rect(center=(int(snap.bird_x), int(snap.bird_y)))
        self.screen.blit(image, rect)

    # ------------------------------------------------------------------
    def _text(self, text: str, font: pygame.font.Font, pos, color=config.TEXT_COLOR) -> None:
        surface = font.render(text, True, color)
        self.screen.blit(surface, pos)

    def _text_right(self, text: str, font: pygame.font.Font, right_x: int, y: int,
                    color=config.TEXT_COLOR) -> None:
        surface = font.render(text, True, color)
        rect = surface.get_rect()
        rect.topright = (right_x, y)
        self.screen.blit(surface, rect)

    def _draw_panel(self, x: int, y: int, w: int, h: int) -> None:
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(panel, (255, 255, 255, 175), panel.get_rect(), border_radius=10)
        pygame.draw.rect(panel, (255, 255, 255, 90), panel.get_rect(), 2, border_radius=10)
        self.screen.blit(panel, (x, y))

    def _draw_hud(self, snap: GameSnapshot, hud: Dict) -> None:
        self._draw_panel(10, 10, 205, 92)
        self._draw_panel(config.SCREEN_W - 250, 10, 240, 92)

        self._text(f"分数  {snap.score}", self.font_mid, (20, 16))
        self._text(f"速度  {snap.speed:5.1f}", self.font_small, (20, 52))
        self._text(f"模式  {hud.get('mode', '-')}", self.font_small, (20, 78))

        right = config.SCREEN_W - 20
        self._text_right(f"俯卧撑 {hud.get('pushup_count', 0)}", self.font_mid, right, 16)
        self._text_right(f"幅度 {hud.get('amplitude', 0.0):0.2f}", self.font_small, right, 52)

        form_text = hud.get("form_text", "")
        if form_text:
            color = (30, 140, 60) if hud.get("form_ok", True) else (190, 60, 60)
            self._text_right(form_text, self.font_small, right, 78, color)

    # ------------------------------------------------------------------
    def _draw_overlays(self, snap: GameSnapshot, hud: Dict) -> None:
        if not hud.get("started", True):
            self._draw_reference_arc(snap, hud)
            if not hud.get("can_start", True):
                # 摄像头模式下还没识别到人：先不让开始
                self._draw_panel(config.SCREEN_W // 2 - 270, config.SCREEN_H // 2 - 120, 540, 160)
                self._center_text("没检测到你", self.font_big, config.SCREEN_H // 2 - 105,
                                  (200, 40, 40))
                self._center_text("请站到摄像头前，让头、肩膀、手臂都进画面",
                                  self.font_mid, config.SCREEN_H // 2 - 30)
                self._center_text("识别到之后按 空格 开始", self.font_small,
                                  config.SCREEN_H // 2 + 12, (90, 90, 90))
                return

            self._center_text("按 空格 开始", self.font_big, config.SCREEN_H // 2 - 90,
                              (200, 40, 40) if hud.get("warn") else config.TEXT_COLOR)
            self._center_text("↑ / ↓ 控制高度，跟着波浪通道走", self.font_mid,
                              config.SCREEN_H // 2 - 10, (70, 70, 70))
            if hud.get("warn"):
                self._center_text("还没识别到你，先站到摄像头前", self.font_small,
                                  config.SCREEN_H // 2 + 40, (200, 40, 40))
            return

        if snap.game_over:
            if self.gameover_img is not None:
                rect = self.gameover_img.get_rect(
                    center=(config.SCREEN_W // 2, config.SCREEN_H // 2 - 110)
                )
                self.screen.blit(self.gameover_img, rect)
                text_y = config.SCREEN_H // 2 - 40
            else:
                self._center_text("游戏结束", self.font_big, config.SCREEN_H // 2 - 120,
                                  (180, 40, 40))
                text_y = config.SCREEN_H // 2 - 20
            self._center_text(f"得分 {snap.score}    按 R 或 空格 重新开始", self.font_mid, text_y)

    def _draw_reference_arc(self, snap: GameSnapshot, hud: Dict) -> None:
        """准备界面：用一对弧形括号标出"你现在的参考位置"。"""
        ref = hud.get("reference_y")
        if ref is None:
            return

        cx = int(snap.bird_x)
        cy = int(ref * config.SCREEN_H)
        rect = pygame.Rect(
            cx - config.REFERENCE_ARC_W // 2,
            cy - config.REFERENCE_ARC_H // 2,
            config.REFERENCE_ARC_W,
            config.REFERENCE_ARC_H,
        )

        # 左右两个弧，上下各留一点缺口，看起来像一对括号
        pygame.draw.arc(self.screen, (255, 255, 255), rect,
                        math.pi * 0.62, math.pi * 1.38, 3)
        pygame.draw.arc(self.screen, (255, 255, 255), rect,
                        -math.pi * 0.38, math.pi * 0.38, 3)

        label = self.font_small.render("参考位置", True, (255, 255, 255))
        label_rect = label.get_rect()
        label_rect.midbottom = (cx, rect.top - 6)
        self.screen.blit(label, label_rect)

    def _center_text(self, text: str, font: pygame.font.Font, y: int, color=config.TEXT_COLOR) -> None:
        surface = font.render(text, True, color)
        rect = surface.get_rect()
        rect.midtop = (config.SCREEN_W // 2, y)
        self.screen.blit(surface, rect)

    # ------------------------------------------------------------------
    def close(self) -> None:
        pygame.quit()
