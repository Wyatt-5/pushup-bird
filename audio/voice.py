"""语音触发：说"开始"来开始游戏。

实现方式：
    1. sounddevice 录音 2 秒（不引入 pyaudio，依赖更少）；
    2. 交给 SpeechRecognition，用 Google 在线识别（zh-CN）；
    3. 识别文本里包含关键词就置位，由 Presenter 取走。

注意：
    * 在线识别需要网络；网络不可用时会静默跳过，不影响空格键开始；
    * 录音失败（没有麦克风/被占用）时自动降级为不可用。
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional


class VoiceStartListener:
    def __init__(
        self,
        keyword: str = "开始",
        chunk_seconds: float = 2.0,
        samplerate: int = 16000,
        should_listen: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.keyword = keyword
        self.chunk_seconds = chunk_seconds
        self.samplerate = samplerate
        self.should_listen = should_listen

        self.available: bool = False
        self.error: str = ""
        self.last_text: str = ""

        self._triggered = False
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._sr = None
        self._sd = None
        self._recognizer = None

    # ------------------------------------------------------------------
    def start(self) -> bool:
        try:
            import speech_recognition as sr
            import sounddevice as sd
        except ImportError as exc:
            self.error = f"缺少依赖：{exc}"
            return False

        try:
            sd.query_devices(kind="input")
        except Exception as exc:
            self.error = f"找不到输入设备：{exc}"
            return False

        self._sr = sr
        self._sd = sd
        self._recognizer = sr.Recognizer()
        self._recognizer.energy_threshold = 300
        self._recognizer.dynamic_energy_threshold = True

        self.available = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="voice-listener", daemon=True)
        self._thread.start()
        return True

    # ------------------------------------------------------------------
    def _loop(self) -> None:
        frames = int(self.chunk_seconds * self.samplerate)
        while not self._stop.is_set():
            if self.should_listen is not None and not self.should_listen():
                time.sleep(0.2)
                continue

            try:
                recording = self._sd.rec(
                    frames, samplerate=self.samplerate, channels=1, dtype="int16"
                )
                self._sd.wait()
            except Exception as exc:
                self.error = f"录音失败：{exc}"
                time.sleep(0.5)
                continue

            audio = self._sr.AudioData(recording.tobytes(), self.samplerate, 2)
            try:
                text = self._recognizer.recognize_google(audio, language="zh-CN")
            except Exception as exc:
                # UnknownValueError（没听清）和网络错误都只是跳过
                self.error = f"识别失败：{type(exc).__name__}"
                continue

            self.last_text = text
            self.error = ""
            if self.keyword in text.replace(" ", ""):
                self._triggered = True
                return

    # ------------------------------------------------------------------
    def consume(self) -> bool:
        """取走一次触发（一次性）。"""
        if self._triggered:
            self._triggered = False
            return True
        return False

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
