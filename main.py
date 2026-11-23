"""俯卧撑小鸟 —— 程序入口。

用法：
    python main.py                          # 键盘模式（默认）
    python main.py --control camera         # 摄像头体感模式
    python main.py --selftest --frames 600  # 无界面自检（只跑模型）

架构（MVP）：
    Model      core/game_model.py     纯规则，不依赖 pygame
    View       view/pygame_view.py    只负责绘制
    Presenter  presenter/game_presenter.py  把两者和 ControlSource 粘起来
    Control    control/*              可替换的输入后端
"""
from __future__ import annotations

import argparse
import sys

import config


def build_control(name: str, camera_index: int):
    if name == "camera":
        from control.camera import CameraControlSource

        return CameraControlSource(camera_index=camera_index, gain=config.CAMERA_GAIN)
    from control.keyboard import KeyboardControlSource

    return KeyboardControlSource()


def _perfect_target(model, cfg) -> float:
    """一个"完美跟手"的虚拟玩家：把目标高度对准波浪通道的中心。"""
    world_at_bird = model.scroll_offset + cfg.BIRD_X
    target_y = model.gap_center(world_at_bird)
    top_y = cfg.TOP_MARGIN + cfg.BIRD_RADIUS
    bottom_y = cfg.SCREEN_H - cfg.BOTTOM_MARGIN - cfg.BIRD_RADIUS
    if bottom_y == top_y:
        return 0.5
    return max(0.0, min(1.0, (bottom_y - target_y) / (bottom_y - top_y)))


def run_selftest(frames: int) -> int:
    """无界面自检：用一个"完美跟手"的虚拟玩家驱动模型，验证逻辑不崩。"""
    import config as app_config
    from core.game_model import GameModel

    model = GameModel()
    dt = 1.0 / 60.0
    for _ in range(frames):
        model.step(dt, _perfect_target(model, app_config))
        if model.game_over:
            break
    snap = model.snapshot()
    seconds = snap.scroll_offset / max(1.0, app_config.SCROLL_SPEED_START)
    print(f"自检完成：约 {seconds:.0f} 秒的游戏时长")
    print(f"  得分      : {snap.score}")
    print(f"  当前速度  : {snap.speed:.1f}")
    print(f"  当前幅度  : {snap.amplitude:.1f}")
    print(f"  游戏结束  : {snap.game_over}")
    print(f"  管道数量  : {len(snap.pipes)}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="俯卧撑小鸟")
    parser.add_argument("--control", choices=["keyboard", "camera"], default="keyboard")
    parser.add_argument("--camera-index", type=int, default=config.CAMERA_INDEX)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--frames", type=int, default=600)
    parser.add_argument("--no-audio", action="store_true", help="关闭背景音乐与音效")
    parser.add_argument("--no-voice", action="store_true", help="关闭语音开始")
    args = parser.parse_args(argv)

    if args.selftest:
        return run_selftest(args.frames)

    from core.game_model import GameModel
    from presenter.game_presenter import GamePresenter
    from view.pygame_view import PygameView

    from audio.sound import SoundManager
    from audio.voice import VoiceStartListener

    view = PygameView()
    control = build_control(args.control, args.camera_index)

    sound = SoundManager(
        bgm_volume=config.BGM_VOLUME,
        sfx_volume=config.SFX_VOLUME,
        enabled=config.AUDIO_ENABLED and not args.no_audio,
    )
    if not sound.enabled:
        print(f"[音频] 已关闭：{sound.error}")

    presenter = GamePresenter(GameModel(), control, view, audio=sound)

    voice = None
    if config.VOICE_ENABLED and not args.no_voice:
        voice = VoiceStartListener(
            keyword=config.VOICE_KEYWORD,
            should_listen=lambda: not presenter.started,
        )
        if voice.start():
            presenter.voice = voice
            print(f"[语音] 已开启：对着麦克风说「{config.VOICE_KEYWORD}」即可开始")
        else:
            print(f"[语音] 不可用：{voice.error}")

    try:
        presenter.run()
    except RuntimeError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        try:
            view.close()
        except Exception:
            pass
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
