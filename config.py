"""项目全局配置。

所有可调参数集中在此，便于调参与演示"需求适配"（改配置而不改各层实现）。
"""
from __future__ import annotations

SCREEN_W: int = 960
SCREEN_H: int = 600
FPS: int = 60

# ---------------- 小鸟 ----------------
BIRD_X: int = 180
BIRD_RADIUS: int = 18          # 碰撞圆半径（略小于贴图，手感更宽容）
BIRD_SPRITE_W: int = 48
BIRD_SPRITE_H: int = 34
# 每帧向目标高度靠拢的速率（单位：1/秒，越大约跟得越紧）
BIRD_FOLLOW_RATE: float = 12.0

# ---------------- 波浪通道 ----------------
PIPE_W: int = 72
PIPE_SPACING: int = 320            # 相邻管道之间的世界坐标间距
WAVE_LENGTH: float = 760.0         # 正弦波一个完整周期对应的世界像素
GAP_HEIGHT: float = 170.0          # 上下管道之间的缝隙高度
TOP_MARGIN: int = 50
BOTTOM_MARGIN: int = 50
GROUND_H: int = 50             # 底部地面高度（= BOTTOM_MARGIN，视觉与判定一致）
FIRST_PIPE_OFFSET: float = 820.0   # 第一根管道距离起点的世界像素

# ---------------- 速度 / 难度（自动随分数递增） ----------------
SCROLL_SPEED_START: float = 170.0
SCROLL_SPEED_MAX: float = 420.0
SCROLL_SPEED_PER_SCORE: float = 9.0

WAVE_AMPLITUDE_START: float = 80.0
WAVE_AMPLITUDE_MAX: float = 140.0
WAVE_AMPLITUDE_PER_SCORE: float = 3.0

# 缝隙中心的取值范围（自动计算，保证管道不跑出屏幕）
GAP_CENTER_MID: float = SCREEN_H / 2
GAP_CENTER_MIN: float = TOP_MARGIN + GAP_HEIGHT / 2
GAP_CENTER_MAX: float = SCREEN_H - BOTTOM_MARGIN - GAP_HEIGHT / 2

# ---------------- 俯卧撑计数（基于高度信号，自适应阈值） ----------------
PUSHUP_BAND: float = 0.25          # 上下各取当前起伏范围的 25% 作为触发带
PUSHUP_MIN_RANGE: float = 0.15     # 起伏范围小于它就视为"没在动"
PUSHUP_WINDOW: float = 3.0         # 统计最近多少秒内的极值（秒）
PUSHUP_MIN_INTERVAL: float = 0.30  # 两次有效俯卧撑之间的最小间隔（秒）

# AR 模式下允许缝隙中心到达的范围（因为没有地面，可以用满整个屏幕）
AR_GAP_MARGIN: int = 8

# ---------------- 音频 ----------------
AUDIO_ENABLED: bool = True
BGM_VOLUME: float = 0.28        # 背景音乐音量（0~1）
SFX_VOLUME: float = 0.70        # 音效音量（0~1）

# ---------------- 语音触发 ----------------
VOICE_ENABLED: bool = True      # 对着麦克风说"开始"就开局
VOICE_KEYWORD: str = "开始"

# ---------------- 参考位置（准备界面的弧形标记） ----------------
REFERENCE_ARC_W: int = 190
REFERENCE_ARC_H: int = 120

# 手肘检测（姿势矫正）开关。
# 本机摄像头视场角有限，做俯卧撑时手肘经常跑出画面，角度不可信，
# 所以默认关闭；代码完整保留，坐远/换广角摄像头后可以改回 True。
ENABLE_ELBOW_FEATURE: bool = False

# ---------------- 摄像头 ----------------
# 本机 DirectShow 设备表（编号就是 --camera-index）：
#   0 | XiaoMi WebCam                    <- 电脑摄像头，用这个
#   1 | 浅安.的Xiaomi 15 Pro（后置）      <- 手机
#   2 | 组合摄像头                        <- 虚拟设备
#   3 | 浅安.的Xiaomi 15 Pro（前置）      <- 手机
CAMERA_INDEX: int = 0

# 摄像头模式下小鸟相对眼睛的放大倍数（1.0 = 严格贴在眼睛上）
CAMERA_GAIN: float = 1.0

# AR 模式下小鸟水平位置的允许范围（屏幕像素）
# 不夹紧的话小鸟可能跑到最右边，管道一出现就撞上
BIRD_X_MIN: int = 100
BIRD_X_MAX: int = 700

# ---------------- 颜色 ----------------
BG_TOP = (150, 205, 240)
BG_BOTTOM = (215, 240, 255)
PIPE_BODY = (74, 165, 74)
PIPE_DARK = (44, 110, 44)
BIRD_BODY = (255, 214, 64)
BIRD_BELLY = (255, 246, 214)
TEXT_COLOR = (40, 40, 40)
