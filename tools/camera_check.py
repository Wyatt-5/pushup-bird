"""摄像头自检工具：找出哪个编号是本机真正的摄像头。

用法：
    python tools/camera_check.py          只检查 config.CAMERA_INDEX（本机是 3 号）
    python tools/camera_check.py --pose   顺便测一下姿态能不能识别出人
    python tools/camera_check.py --show   弹窗预览，用来确认哪个编号是笔记本摄像头
    python tools/camera_check.py --all    扫描 0~4 号（会顺带唤醒手机投屏摄像头，慎用）

注意：0/1/2 号是手机投屏/虚拟摄像头，本机摄像头是 3 号。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2


def open_with_warmup(index: int, backend: int):
    """打开摄像头并预热，返回 (cap, 平均亮度)；打不开或全黑返回 (None, 0)。"""
    cap = cv2.VideoCapture(index, backend)
    if not cap.isOpened():
        cap.release()
        return None, 0.0
    mean = 0.0
    for _ in range(20):
        ok, frame = cap.read()
        if ok and frame is not None:
            mean = float(frame.mean())
            if mean > 1.0:
                return cap, mean
    return cap, mean


def check_pose(cap):
    """用当前摄像头的一帧跑一次姿态检测，看能不能识别到人。"""
    try:
        from control.camera import MODEL_PATH
        import numpy as np
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        with open(MODEL_PATH, "rb") as fp:
            data = fp.read()
        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_buffer=data),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
        )
        landmarker = vision.PoseLandmarker.create_from_options(options)
        ok, frame = cap.read()
        if not ok or frame is None:
            landmarker.close()
            return "读帧失败"
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).copy()
        result = landmarker.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), 1
        )
        found = bool(result.pose_landmarks)
        landmarker.close()
        return "识别到人体 ✅" if found else "没识别到人（站远一点/调亮一点再试）"
    except Exception as exc:  # pragma: no cover
        return f"跳过（{exc}）"


def list_device_names() -> None:
    """打印 DirectShow 设备名（需要 pygrabber，装不上就跳过）。"""
    try:
        from pygrabber.dshow_graph import FilterGraph
    except ImportError:
        print("（没有 pygrabber，看不到设备名；pip install pygrabber 可显示）\n")
        return
    try:
        names = FilterGraph().get_input_devices()
    except Exception:
        return
    print("DirectShow 设备列表（编号即 --camera-index）：")
    for i, name in enumerate(names):
        print(f"  {i} | {name}")
    print()


def main() -> int:
    show = "--show" in sys.argv
    do_pose = "--pose" in sys.argv
    scan_all = "--all" in sys.argv

    list_device_names()

    import config

    indices = list(range(0, 5)) if scan_all else [config.CAMERA_INDEX]

    print("编号 | 后端   | 平均亮度 | 结果")
    print("-----+--------+----------+---------------------------")
    working = []
    for index in indices:
        for name, backend in (("DSHOW", cv2.CAP_DSHOW), ("ANY", cv2.CAP_ANY)):
            cap, mean = open_with_warmup(index, backend)
            if cap is None:
                cap, mean = None, 0.0
            if mean <= 1.0:
                if cap is not None:
                    cap.release()
                continue

            status = "有画面 ✅"
            if do_pose:
                status += "  " + check_pose(cap)

            if show:
                print(f"  正在预览 {index} 号，按任意键继续……")
                while True:
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        break
                    cv2.putText(frame, f"CAMERA {index} ({name})", (20, 40),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
                    cv2.imshow("camera check", frame)
                    if cv2.waitKey(1) & 0xFF != 255:
                        break
                cv2.destroyAllWindows()

            print(f"{index:4d} | {name:6s} | {mean:8.1f} | {status}")
            working.append((index, name))
            cap.release()
            break

    if not working:
        print("没有找到任何可用的摄像头。")
        return 1

    print()
    print("可用的摄像头：")
    for index, name in working:
        print(f"  --camera-index {index}   ({name})")
    print()
    print("把合适的编号填进 config.py 的 CAMERA_INDEX，")
    print("或者运行时加参数：python main.py --control camera --camera-index N")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
