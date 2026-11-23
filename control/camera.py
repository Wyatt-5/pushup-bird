"""摄像头体感控制源（MediaPipe Tasks API / Pose Landmarker）。

AR 式的两类输出：
  * 摄像头原始画面                -> View 直接当背景贴图
  * 眼睛位置（水平 + 垂直）        -> 小鸟直接贴在你的眼睛上
  * 肩/肘/腕夹角                  -> 俯卧撑计数 / 姿势矫正

几个关键设计：
  1. 用 model_asset_buffer 而不是 model_asset_path —— MediaPipe 的 C++ 层
     打不开含中文的路径，本项目正好在"大三上"目录下。
  2. 读帧 + 推理放后台线程，主循环只取最新结果，避免摄像头 30fps 拖慢游戏。
  3. 先把画面裁成和窗口一致的比例再检测，这样关键点坐标和背景是对齐的。
"""
from __future__ import annotations

import os
import threading
import time
from typing import Optional, Sequence

import config
from control.base import ControlSource, ControlState
from core.signal import ExpSmoother, PushupCounter, clamp
from pose.posture import ElbowFormAnalyzer, angle_at

# 姿态模型文件（随项目一起提交，约 5.5MB）
MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "models", "pose_landmarker_lite.task",
)


class CameraControlSource(ControlSource):
    mode = "摄像头"

    # Pose 关键点索引（MediaPipe Pose 标准 33 点）
    EYE_IDS = (1, 2, 3, 4, 5, 6)      # 双眼内眼角/眼中/外眼角
    LEFT_ARM = (11, 13, 15)           # 左肩 / 左肘 / 左腕
    RIGHT_ARM = (12, 14, 16)          # 右肩 / 右肘 / 右腕

    def __init__(
        self,
        camera_index: int = 0,
        smooth_alpha: float = 0.45,
        mirror: bool = True,
        min_visibility: float = 0.5,
        process_height: int = 480,
        detect_interval: int = 2,
        gain: float = 1.0,
        up_angle: float = 150.0,
        down_angle: float = 95.0,
    ) -> None:
        self.camera_index = camera_index
        self.mirror = mirror
        self.min_visibility = min_visibility
        self.process_height = process_height
        self.detect_interval = max(1, int(detect_interval))
        self.gain = gain

        self.backend_name = "?"

        self._smooth_x = ExpSmoother(alpha=smooth_alpha)
        self._smooth_y = ExpSmoother(alpha=smooth_alpha)

        # 手肘（姿势矫正）—— 受视场角限制，默认由 config 关掉
        self._elbow_enabled = bool(getattr(config, "ENABLE_ELBOW_FEATURE", False))
        self._elbow = ElbowFormAnalyzer(down_angle=down_angle, up_angle=up_angle)

        # 不看手肘时，用眼睛高度的起伏来数俯卧撑（和键盘模式同一套算法）
        self._height_counter = PushupCounter(
            band=getattr(config, "PUSHUP_BAND", 0.25),
            min_range=getattr(config, "PUSHUP_MIN_RANGE", 0.15),
            window=getattr(config, "PUSHUP_WINDOW", 3.0),
            min_interval=getattr(config, "PUSHUP_MIN_INTERVAL", 0.30),
        )

        self._cv2 = None
        self._mp = None
        self._landmarker = None
        self._cap = None

        self._pointer_x: float = 0.5
        self._pointer_y: float = 0.5
        self._wave_center_y: Optional[float] = None
        self._reference_y: Optional[float] = None
        self._eye_points = []
        self._arm_points = []
        self._arm_in_frame: bool = False
        self._height: float = 0.5
        self._baseline_y: Optional[float] = None
        self._elbow_angle: Optional[float] = None
        self._pose_seen: bool = False

        self._frame_index: int = 0
        self._timestamp_ms: int = 0
        self._last_detect_at: float = 0.0

        # 背景帧
        self._frame_rgb = None
        self._frame_seq: int = 0

        self._lock = threading.Lock()
        self._latest = ControlState(mode=self.mode)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def start(self) -> None:
        try:
            import cv2
            import mediapipe as mp
            from mediapipe.tasks.python import BaseOptions, vision
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "摄像头模式需要 opencv-python 与 mediapipe，请先运行："
                "pip install -r requirements.txt"
            ) from exc

        if not os.path.exists(MODEL_PATH):
            raise RuntimeError(
                f"找不到姿态模型文件：{MODEL_PATH}\n"
                "请确认 assets/models/pose_landmarker_lite.task 存在。"
            )

        self._cv2 = cv2
        self._mp = mp

        with open(MODEL_PATH, "rb") as fp:
            model_bytes = fp.read()

        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_buffer=model_bytes),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)

        self._cap = self._open_camera(cv2)
        if self._cap is None:
            raise RuntimeError(
                f"无法打开摄像头（index={self.camera_index}），"
                "请先运行 python tools/camera_check.py 看看哪个编号可用。"
            )

        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="camera-worker", daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    def _open_camera(self, cv2):
        """依次尝试不同后端，返回第一个能读到"非全黑"画面的设备。"""
        candidates = (
            (self.camera_index, cv2.CAP_DSHOW),
            (self.camera_index, cv2.CAP_ANY),
        )
        for index, backend in candidates:
            cap = cv2.VideoCapture(index, backend)
            if not cap.isOpened():
                cap.release()
                continue

            # 耐心预热：有些摄像头要 1 秒左右才出第一帧真实画面
            deadline = time.time() + 1.5
            while time.time() < deadline:
                ok, frame = cap.read()
                if ok and frame is not None and float(frame.mean()) > 1.0:
                    self.backend_name = "DSHOW" if backend == cv2.CAP_DSHOW else "ANY"
                    return cap
                time.sleep(0.01)
            cap.release()
        return None

    # ------------------------------------------------------------------
    # 后台线程
    # ------------------------------------------------------------------
    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                time.sleep(0.01)

    def _tick(self) -> None:
        ok, frame = self._cap.read()
        if not ok or frame is None:
            time.sleep(0.005)
            return

        cv2 = self._cv2
        if self.mirror:
            frame = cv2.flip(frame, 1)

        # 先裁成和窗口一致的比例，保证关键点坐标和背景对齐
        frame = self._crop_to_window(frame)
        self._update_background(frame)

        self._frame_index += 1
        if self.detect_interval > 1 and (self._frame_index % self.detect_interval) != 0:
            return

        image = self._to_mediapipe_image(frame)
        if image is None:
            return

        now = time.perf_counter()
        elapsed = 0.0 if self._last_detect_at == 0.0 else now - self._last_detect_at
        self._last_detect_at = now

        self._timestamp_ms += max(1, int(elapsed * 1000)) or 33
        result = self._landmarker.detect_for_video(image, self._timestamp_ms)

        poses = getattr(result, "pose_landmarks", None)
        if not poses:
            self._pose_seen = False
        else:
            self._pose_seen = True
            pose = poses[0]
            step_dt = max(elapsed, 1 / 60.0)
            self._update_position(pose, frame.shape[1], frame.shape[0], step_dt)
            self._update_elbow(pose, frame.shape[1], frame.shape[0], step_dt)

        with self._lock:
            self._latest = self._state()

    # ------------------------------------------------------------------
    def _crop_to_window(self, frame):
        """把画面中心裁剪成和游戏窗口相同的宽高比，避免拉伸变形。"""
        h, w = frame.shape[:2]
        target_ar = config.SCREEN_W / float(config.SCREEN_H)
        src_ar = w / float(h)
        if src_ar > target_ar:
            new_w = max(1, int(h * target_ar))
            x0 = (w - new_w) // 2
            return frame[:, x0:x0 + new_w]
        if src_ar < target_ar:
            new_h = max(1, int(w / target_ar))
            y0 = (h - new_h) // 2
            return frame[y0:y0 + new_h, :]
        return frame

    def _update_background(self, frame) -> None:
        """把画面等比缩放到窗口大小。不做任何平移/拉伸，避免边缘被拉花。"""
        cv2 = self._cv2
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (config.SCREEN_W, config.SCREEN_H), interpolation=cv2.INTER_LINEAR)
        self._frame_rgb = rgb
        self._frame_seq += 1

    def _to_mediapipe_image(self, frame):
        cv2 = self._cv2
        h, w = frame.shape[:2]
        if h > self.process_height:
            scale = self.process_height / float(h)
            small = cv2.resize(frame, (max(1, int(w * scale)), self.process_height))
        else:
            small = frame
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        return self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb.copy())

    # ------------------------------------------------------------------
    def _update_position(self, pose: Sequence, w: int, h: int, dt: float = 1 / 30.0) -> None:
        try:
            xs = [pose[i].x for i in self.EYE_IDS]
            ys = [pose[i].y for i in self.EYE_IDS]
        except IndexError:
            return

        # 平滑，去掉眼睛关键点的抖动
        eye_x = clamp(self._smooth_x.update(sum(xs) / len(xs)), 0.0, 1.0)
        eye_y = clamp(self._smooth_y.update(sum(ys) / len(ys)), 0.0, 1.0)

        # 水平：眼睛在画面里的横向位置
        self._pointer_x = eye_x

        # 垂直：直接给归一化坐标，小鸟就贴着眼睛，不做任何夹紧
        if self.gain != 1.0:
            eye_y = clamp(0.5 + self.gain * (eye_y - 0.5), 0.0, 1.0)
        self._pointer_y = eye_y

        # 波浪通道的中心对准"你静止时脸所在的高度"，
        # 这样不管摄像头怎么摆，缝隙都会出现在你脸附近，游戏才玩得下去。
        if self._baseline_y is None:
            self._baseline_y = eye_y
        else:
            self._baseline_y += 0.01 * (eye_y - self._baseline_y)
        self._wave_center_y = self._baseline_y * config.SCREEN_H
        self._reference_y = self._baseline_y

        # 调试：把 6 个眼角/眼睛关键点记下来，View 可以画出来
        self._eye_points = list(zip(xs, ys))

        # 不看手肘时，用眼睛高度的起伏来统计俯卧撑次数
        if not self._elbow_enabled:
            self._height_counter.update(eye_y, dt)

    def _update_elbow(self, pose: Sequence, w: int, h: int, dt: float) -> None:
        if not self._elbow_enabled:
            return

        side = None
        best_vis = 0.0
        for ids in (self.LEFT_ARM, self.RIGHT_ARM):
            vis = sum(getattr(pose[i], "visibility", 1.0) for i in ids) / 3.0
            if vis > best_vis:
                best_vis, side = vis, ids

        if side is None or best_vis < self.min_visibility:
            self._arm_points = []
            self._arm_in_frame = False
            self._elbow_angle = None
            return

        sh, el, wr = (pose[i] for i in side)
        self._arm_points = [(sh.x, sh.y), (el.x, el.y), (wr.x, wr.y)]

        # 只要有任意一个点跑出画面，手肘角度就是瞎算的，直接不采信
        inside = all(
            -0.02 <= x <= 1.02 and -0.02 <= y <= 1.02
            for x, y in self._arm_points
        )
        self._arm_in_frame = inside
        if not inside:
            self._elbow_angle = None
            return

        aspect = w / max(1, h)
        angle = angle_at(
            (sh.x * aspect, sh.y),
            (el.x * aspect, el.y),
            (wr.x * aspect, wr.y),
        )
        self._elbow_angle = angle
        self._elbow.update(angle, dt)

    # ------------------------------------------------------------------
    def step(self, dt: float, *, up: bool = False, down: bool = False) -> ControlState:
        """非阻塞：直接返回后台线程算好的最新结果。"""
        with self._lock:
            state = self._latest
            if self._frame_rgb is not None:
                state.camera_frame = self._frame_rgb
                state.camera_frame_seq = self._frame_seq
        state.mode = self.mode
        return state

    def _state(self) -> ControlState:
        if self._elbow_enabled:
            count = self._elbow.count
            form_ok = self._elbow.form_ok
        else:
            count = self._height_counter.count
            form_ok = None

        return ControlState(
            target_height=self._height,
            pushup_count=count,
            amplitude=self._height_counter.amplitude,
            elbow_angle=self._elbow_angle if self._elbow_enabled else None,
            form_ok=form_ok,
            pose_visible=self._pose_seen,
            pointer_x=self._pointer_x,
            pointer_y=self._pointer_y,
            wave_center_y=self._wave_center_y,
            reference_y=self._reference_y,
            eye_points=self._eye_points,
            arm_points=self._arm_points if self._elbow_enabled else [],
            arm_in_frame=self._arm_in_frame if self._elbow_enabled else None,
            camera_frame=self._frame_rgb,
            camera_frame_seq=self._frame_seq,
            mode=self.mode,
        )

    def reset(self) -> None:
        self._elbow.reset()
        self._height_counter.reset()
        self._smooth_x.reset()
        self._smooth_y.reset()
        self._height = 0.5
        self._pointer_x = 0.5
        self._elbow_angle = None
        self._baseline_y = None
        self._pointer_y = 0.5
        self._reference_y = None
        self._arm_points = []
        self._arm_in_frame = False

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception:
                pass
            self._landmarker = None
