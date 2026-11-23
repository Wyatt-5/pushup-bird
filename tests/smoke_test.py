"""无界面冒烟测试：验证 控制 -> 模型 -> 渲染 整条链路不崩溃。

运行：
    python tests/smoke_test.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import config
from control.keyboard import KeyboardControlSource
from core.game_model import GameModel
from presenter.game_presenter import GamePresenter
from view.pygame_view import PygameView


def main() -> int:
    view = PygameView()
    control = KeyboardControlSource()
    presenter = GamePresenter(GameModel(), control, view)
    presenter.started = True

    top_y = config.TOP_MARGIN + config.BIRD_RADIUS
    bottom_y = config.SCREEN_H - config.BOTTOM_MARGIN - config.BIRD_RADIUS

    def fake_keys():
        model = presenter.model
        target_y = model.gap_center(model.scroll_offset + config.BIRD_X)
        want = max(0.0, min(1.0, (bottom_y - target_y) / (bottom_y - top_y)))
        cur = presenter.control.value
        return want > cur + 0.005, want < cur - 0.005

    view.read_move_keys = fake_keys

    frames = 0
    for _ in range(600):
        presenter._update(1 / 60)
        view.render(presenter.model.snapshot(), presenter._hud())
        frames += 1
        if presenter.model.game_over:
            break

    snap = presenter.model.snapshot()
    print(f"渲染帧数 : {frames}")
    print(f"得分     : {snap.score}")
    print(f"游戏结束 : {snap.game_over}")
    print(f"俯卧撑   : {presenter._state.pushup_count}")
    view.close()
    print("冒烟测试通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
