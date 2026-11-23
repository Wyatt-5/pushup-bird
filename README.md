# 俯卧撑小鸟 Push-up Bird

一个用**身体姿势**控制的横版小游戏：小鸟的高度实时跟随你的身体高度，
你需要像做俯卧撑一样**上下起伏**，跟着会摆动的波浪通道穿过柱子。

课程项目：ISI3003A Python 开发实训 | 汕头大学 数学与计算机学院 计算机系

---

## 1. 玩法

- 屏幕上的柱子通道会**上下摆动**（固定正弦波）；
- 小鸟的垂直位置 = 你身体（眼睛/头部）的高度；
- 你趴下去，小鸟下降；你撑起来，小鸟上升；
- 跟住波浪通道就得分，撞到柱子或上下边界就结束；
- 速度与波浪幅度会随分数**自动递增**。

摄像头模式下是 **AR 式** 玩法：摄像头画面直接当背景，
小鸟就贴在你的眼睛上，你抬头低头、左右挪动，小鸟跟着走。

| 操作 | 键盘模式（默认，无需摄像头） | 摄像头模式 |
|---|---|---|
| 上升 | 上箭头 或 W（按住） | 撑起身体 |
| 下降 | 下箭头 或 S（按住） | 趴下身体 |
| 开始 | 空格（摄像头模式下必须先识别到人） | 空格 |
| 重开 | R 或 空格（回到准备界面，再按空格开始） | 同左 |
| 语音开始 | 对麦克风说「开始」 | 同左 |
| 显示/隐藏识别点 | F1（红点=眼睛，青线=肩肘腕） | F1 |
| 退出 | ESC | ESC |

---

## 2. 运行

```bash
# 1) 安装依赖
pip install -r requirements.txt

# 2) 键盘模式（推荐先跑这个）
python main.py

# 3) 摄像头体感模式（本机摄像头是 0 号 XiaoMi WebCam）
python main.py --control camera

# 4) 摄像头自检：确认能出画面、能识别到人
python tools/camera_check.py --pose

# 5) 无界面自检（只跑游戏逻辑）
python main.py --selftest --frames 3600

# 6) 无界面冒烟测试（控制 -> 模型 -> 渲染 整条链路）
python tests/smoke_test.py
```

---

## 3. 摄像头模式说明

### 3.1 摄像头编号

本机 DirectShow 设备表（编号就是 `--camera-index`）：

| 编号 | 设备 | 说明 |
|---|---|---|
| **0** | **XiaoMi WebCam** | **电脑摄像头，用这个** |
| 1 | Xiaomi 15 Pro（后置） | 手机 |
| 2 | 组合摄像头 | 虚拟设备 |
| 3 | Xiaomi 15 Pro（前置） | 手机 |

对应 `config.py` 里的 `CAMERA_INDEX`，当前已设为 `0`。

想看设备名可以装一下 pygrabber：

```bash
pip install pygrabber
python tools/camera_check.py
```

### 3.2 识别方式

用 MediaPipe 的 **Pose Landmarker**（单模型）同时拿到两类关键点：

| 指标 | 关键点索引 | 用途 |
|---|---|---|
| 双眼内/外眼角 | 1,2,3,4,5,6 | 眼睛 Y 坐标 -> 小鸟高度 |
| 肩 / 肘 / 腕 | 11,13,15 和 12,14,16 | 手肘夹角 -> 俯卧撑计数 / 姿势矫正 |

这是一个 **AR 式** 的叠加：

- 摄像头画面（镜像 + 等比裁成窗口比例）直接铺满背景，**不做任何平移/拉伸**；
- 小鸟的屏幕位置 = 你眼睛在画面里的位置（横向纵向都是），就贴在脸上；
- 碰撞判定用的也是这个坐标，所以**看到哪就是哪**，不会"看着躲过了却撞了"；
- AR 模式下不判上下边界、也不画地面，只有撞柱子才算死；
- 波浪缝隙的中心会对准"你静止时脸的高度"，所以不管摄像头怎么摆，
  缝隙都出现在你脸附近，不会出现"缝隙在头顶、人却在画面底部"；
- 小鸟水平位置夹在 100~700 之间，防止它跑到最右边被突然冒出的柱子撞到。

这不是眼动追踪，只是把眼睛坐标当"指针"用。

### 3.2.1 识别不到会怎样

- **没检测到人**：不让你按空格开始，画面提示"没检测到你"；
### 3.2.2 手肘检测（默认关闭）

`pose/posture.py` 里实现了完整的手肘夹角 + 姿势矫正 + 俯卧撑计数，
但**本机摄像头视场角有限**：做俯卧撑时手肘经常跑出画面（实测肘部关键点
y ≈ 1.10，已经超出画面），此时算出来的角度完全不可信。

所以默认关闭，开关在 `config.py`：

```python
ENABLE_ELBOW_FEATURE = False   # 改成 True 就恢复手肘检测
```

关闭后**俯卧撑计数不会消失**：改用眼睛高度的起伏来统计，
和键盘模式用的是同一套自适应阈值算法（`core/signal.py` 的 `PushupCounter`）。

> 换广角摄像头、或者把相机放远一点能拍到全身时，把开关改回 True 即可。

### 3.3 踩过的三个坑（都已修好）

1. **mediapipe 1.x 删掉了 `mp.solutions`**
   旧教程里的 `mp.solutions.holistic` 已经不可用，本项目改用 Tasks API。

2. **中文路径打不开模型**
   MediaPipe 的 C++ 层无法打开含中文的路径（本项目正好在"大三上"目录下）。
   解决办法是先由 Python 读成 bytes，再用 `model_asset_buffer` 传入。

3. **Windows 默认后端返回全黑帧**
   OpenCV 默认走 MSMF 后端，某些驱动一直返回全黑画面。
   现在会先试 DirectShow（CAP_DSHOW），并预热约 1.5 秒。

### 3.4 为什么游戏不会卡

摄像头本身只有 30fps，`read()` 会阻塞约 33ms。如果放在游戏主循环里，
整个游戏会被拖到 30fps。所以**读帧 + 模型推理放在后台线程**，
主循环只取最新结果：实测从 33ms/帧 降到 0.6ms/帧。

HUD 右上角会显示 `摄像头·已识别` / `摄像头·未识别`，方便你确认机位。

---

## 4. 项目结构（MVP 架构）

```
pushup_bird/
├── main.py                      程序入口 / 自检 / 摄像头自检
├── config.py                    全部可调参数（改这里不改代码结构）
├── assets/
│   ├── sprites/                 Flappy Bird 贴图
│   └── models/                  pose_landmarker_lite.task（约 5.5MB）
├── core/                        Model 模型层（纯逻辑，不 import pygame）
│   ├── entities.py              数据实体 Bird / Pipe
│   ├── game_model.py            游戏规则、正弦波浪、碰撞、计分、难度
│   └── signal.py                平滑 / 映射 / 自适应俯卧撑计数
├── control/                     可替换的输入后端
│   ├── base.py                  ControlSource 抽象接口 + ControlState
│   ├── keyboard.py              键盘实现（上下键模拟身体高度）
│   └── camera.py                摄像头实现（Pose Landmarker + 后台线程）
├── pose/
│   └── posture.py               手肘夹角 + 姿势矫正 / 俯卧撑计数（纯算法）
├── view/                        View 视图层（只负责画）
│   ├── assets.py                贴图加载 + 管道拼接
│   └── pygame_view.py           Pygame 渲染 + 输入事件
├── presenter/                   Presenter 表现层
│   └── game_presenter.py        串联 Model / View / ControlSource
├── tools/
│   └── camera_check.py          摄像头自检工具
├── tests/
│   └── smoke_test.py            无界面冒烟测试
└── docs/                        运行截图（报告用）
```

### 三层解耦

| 层 | 职责 | 不允许做的事 |
|---|---|---|
| Model | 小鸟/柱子/碰撞/分数/难度 | 不 import pygame、不知道输入从哪来 |
| View | 只把快照画到屏幕 | 不改游戏状态、不读游戏规则 |
| Presenter | 取控制量 -> 推进 Model -> 渲染 View | 不写游戏规则、不写绘制细节 |

层与层之间只传数据：Model 输出 `GameSnapshot`，ControlSource 输出 `ControlState`，
View 只吃 `GameSnapshot + HUD`。

---

## 5. 如何做「前端替换 / 后端替换」（课程要求的重点）

### 5.1 后端替换（推荐演示这个）

所有输入都被抽象成同一个接口：

```python
class ControlSource(ABC):
    def step(self, dt, *, up=False, down=False) -> ControlState: ...
```

`ControlState` 只有一个核心字段 `target_height`（0~1）。

所以 **把摄像头输入换成键盘输入，游戏、渲染一行都不用改**：

```bash
python main.py --control keyboard   # 后端 A：键盘
python main.py --control camera     # 后端 B：摄像头体感
```

你还可以再写一个 `MouseControlSource` / `GamepadControlSource`，
实现同一个 `step()` 即可接入 —— 这就是"替换后端实现完全不同的需求"。

### 5.2 前端替换

Model 只输出与渲染无关的 `GameSnapshot`，所以可以完全不换后端，只换 View：

- 把小鸟画面换成「跟着波浪走的圆点 + 轨迹线」的数据可视化；
- 换成「节奏条 / 高度指示器」；
- 换成 matplotlib 实时曲线展示你的俯卧撑波形。

只要新 View 消费同一个 `GameSnapshot`，后端与控制层都不用动。

---

## 6. 可调参数（config.py）

| 参数 | 含义 |
|---|---|
| `SCROLL_SPEED_*` | 前进速度及随分数的增长 |
| `WAVE_LENGTH` | 正弦波一个周期有多长（越小越抖） |
| `WAVE_AMPLITUDE_*` | 波浪幅度及随分数的增长 |
| `GAP_HEIGHT` | 柱子缝隙高度（越小越难） |
| `BIRD_FOLLOW_RATE` | 小鸟跟随身体的紧度 |
| `PUSHUP_*` | 俯卧撑计数的自适应阈值 |
| `CAMERA_INDEX` | 摄像头编号（本机是 0，XiaoMi WebCam） |
| `CAMERA_GAIN` | 小鸟相对眼睛的放大倍数（1.0 = 严格贴在眼睛上） |
| `ENABLE_ELBOW_FEATURE` | 手肘检测开关（默认 False，见 3.2.2） |
| `BIRD_X_MIN` / `BIRD_X_MAX` | 摄像头模式下小鸟的水平活动范围 |

摄像头内部参数在 `control/camera.py` 的构造函数里：
`smooth_alpha`（平滑强度）、`detect_interval`（每几帧推理一次）、
`up_angle` / `down_angle`（手肘伸直/弯曲阈值）。

---

## 7. 音频与语音

### 7.1 背景音乐 / 音效

| 文件 | 来源 | 用途 |
|---|---|---|
| `bgm.wav` | 程序合成（`tools/make_bgm.py`） | 循环背景音乐，无版权问题 |
| `hit.wav` | Flappy Bird 素材集 | 撞柱瞬间 |
| `die.wav` | Flappy Bird 素材集 | 撞柱后约 0.3 秒 |
| `wing.wav` / `point.wav` | Flappy Bird 素材集 | 预留（扇翅 / 得分） |

BGM 是可复现的：想换风格直接改 `tools/make_bgm.py` 重新生成，
和弦、BPM、旋律都在里面。

音量在 `config.py`：`BGM_VOLUME`（默认 0.28）、`SFX_VOLUME`（默认 0.70）。
启动参数 `--no-audio` 可以整个关掉音频。

### 7.2 语音说「开始」

`audio/voice.py` 用 `sounddevice` 录 2 秒音频，交给 SpeechRecognition
做中文识别，文本里包含「开始」就等同按下空格。

- 只在**准备界面**监听，开局后自动停止录音（省 CPU、也不会上传对局中的语音）；
- 识别走**在线接口**，没网时自动跳过，空格键始终可用；
- 没有麦克风或被占用时自动降级，不影响游戏；
- 启动参数 `--no-voice` 可以关掉。

### 7.3 参考位置标记

准备界面会在你脸的位置画一对**弧形括号**并标注「参考位置」：

- 括号的位置 = 你静止时眼睛的高度（`_baseline_y`）；
- 波浪缝隙的中心会对准这个高度，所以这个括号其实就是
  **"这一局的夹缝会绕着这里上下摆动"** 的提示；
- 开局后括号消失。

---
## 8. 美术素材

贴图来自 Classic Flappy Bird 的公开重制版素材集：

- https://github.com/samuelcust/flappy-bird-assets

| 文件 | 用途 |
|---|---|
| `background-day.png` | 平铺的天空/城市背景 |
| `base.png` | 底部地面条 |
| `yellowbird-{up,mid,down}flap.png` | 小鸟三帧动画（按升降切换） |
| `pipe-green.png` | 管道（代码拆成管口 + 管身，拼任意高度） |
| `gameover.png` | 结束画面 |

姿态模型来自 MediaPipe 官方模型库：
`pose_landmarker_lite.task`（float16，约 5.5MB）。

所有贴图加载与裁剪逻辑集中在 `view/assets.py`：想换素材只改这个文件，
Model 与 Presenter 完全不受影响。

> 贴图版权归 Flappy Bird 原作者 Dong Nguyen 所有，本项目仅用于课程作业演示。

---

## 9. 已完成 / 待办

- [x] 基础版：正弦波浪通道 + 键盘控制 + 自动难度 + 计分
- [x] MVP 三层解耦 + ControlSource 抽象
- [x] Flappy Bird 贴图接入（背景/地面/小鸟三帧/管道/gameover）
- [x] 俯卧撑计数（高度信号，自适应阈值）
- [x] 手肘夹角 / 姿势矫正算法
- [x] 摄像头体感模式（Pose Landmarker + 后台线程）
- [x] AR 模式：摄像头画面当背景，小鸟贴在眼睛上（缝隙跟着脸走）
- [x] F1 显示识别点（眼睛红点 + 肩肘腕连线），方便确认机位
- [x] 未识别到人时不允许开始
- [x] 手臂跑出画面时提示"手臂不在画面内"，不再输出假的手肘角度
- [x] 重开（R / 空格）回到准备界面，不会一重开就秒死
- [x] 摄像头自检工具（tools/camera_check.py）
- [x] 手肘检测做成开关（受视场角限制默认关闭，代码保留）
- [ ] 摄像头实机长时间联调与参数微调
- [ ] 姿势矫正与小鸟高度联动（需要更广的视场角，暂缓）
- [x] 背景音乐（程序合成）+ 撞柱/结束音效
- [x] 语音说「开始」开局
- [x] 准备界面的参考位置弧形标记
- [ ] 技术报告与演示视频

---

## 10. 说明

- 项目允许使用大模型辅助开发，使用情况会在技术报告中说明。
