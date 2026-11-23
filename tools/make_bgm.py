"""合成一段可循环的 8-bit 风格背景音乐（避免外部素材版权问题）。

运行：
    python tools/make_bgm.py

输出：
    assets/audio/bgm.wav   （约 14.5 秒，无缝循环）
"""
from __future__ import annotations

import math
import os
import wave

import numpy as np

SR = 44100
BPM = 132.0
BEAT = 60.0 / BPM
BAR = BEAT * 4
BARS = 8


def note_freq(semitones_from_a4: int) -> float:
    return 440.0 * (2.0 ** (semitones_from_a4 / 12.0))


# 音名 -> 相对 A4 的半音数
NOTE = {
    "C3": -21, "D3": -19, "E3": -17, "F3": -16, "G3": -14, "A3": -12, "B3": -10,
    "C4": -9, "D4": -7, "E4": -5, "F4": -4, "G4": -2, "A4": 0, "B4": 2,
    "C5": 3, "D5": 5, "E5": 7, "G5": 10,
}


def envelope(n: int, attack: float = 0.01, release: float = 0.08) -> np.ndarray:
    a = max(1, int(attack * SR))
    r = max(1, int(release * SR))
    env = np.ones(n)
    a = min(a, n)
    env[:a] = np.linspace(0.0, 1.0, a)
    r = min(r, n)
    env[-r:] *= np.linspace(1.0, 0.0, r)
    return env


def tone(freq: float, dur: float, wave_type: str = "square", gain: float = 0.3) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    if wave_type == "square":
        sig = np.sign(np.sin(2 * math.pi * freq * t))
        sig = sig * 0.6 + np.sin(2 * math.pi * freq * t) * 0.4
    elif wave_type == "sine":
        sig = np.sin(2 * math.pi * freq * t)
    else:  # triangle 近似
        sig = 2 * np.abs(2 * ((t * freq) % 1) - 1) - 1
    return sig * envelope(n) * gain


def kick(dur: float = 0.12) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    freq = np.linspace(120.0, 45.0, n)
    phase = 2 * math.pi * np.cumsum(freq) / SR
    return np.sin(phase) * envelope(n, 0.002, 0.09) * 0.55


def hat(dur: float = 0.05) -> np.ndarray:
    n = int(dur * SR)
    noise = np.random.default_rng(7).normal(0, 1, n)
    return noise * envelope(n, 0.001, 0.04) * 0.09


def build() -> np.ndarray:
    total = int(BARS * BAR * SR) + SR // 2
    mix = np.zeros(total)

    def add(sig: np.ndarray, start_sec: float) -> None:
        i = int(start_sec * SR)
        j = min(total, i + len(sig))
        if i < total:
            mix[i:j] += sig[: j - i]

    # C - Am - F - G
    chords = [("C3", ["C4", "E4", "G4"]), ("A3", ["A4", "C5", "E5"]),
              ("F3", ["F4", "A4", "C5"]), ("G3", ["G4", "B4", "D5"])]

    for bar in range(BARS):
        chord_root, chord_notes = chords[bar % 4]
        bar_start = bar * BAR

        # 低音：每拍一下
        for b in range(4):
            add(tone(note_freq(NOTE[chord_root]), BEAT * 0.9, "triangle", 0.30),
                bar_start + b * BEAT)

        # 和弦铺底：每小节两次
        for half in range(2):
            for name in chord_notes:
                add(tone(note_freq(NOTE[name]), BEAT * 1.8, "sine", 0.10),
                    bar_start + half * 2 * BEAT)

        # 主旋律：八分音符琶音
        pattern = chord_notes + [chord_notes[0]]
        for eighth in range(8):
            name = pattern[eighth % len(pattern)]
            if eighth % 2 == 0:
                add(tone(note_freq(NOTE[name]) * 2, BEAT * 0.42, "square", 0.10),
                    bar_start + eighth * BEAT / 2)

        # 鼓
        for b in (0, 2):
            add(kick(), bar_start + b * BEAT)
        for eighth in range(8):
            add(hat(), bar_start + eighth * BEAT / 2)

    # 归一化，留点余量
    peak = float(np.max(np.abs(mix))) or 1.0
    mix = mix / peak * 0.75

    # 结尾做淡出，避免循环点爆音
    fade = int(0.05 * SR)
    mix[-fade:] *= np.linspace(1.0, 0.0, fade)
    return mix


def write_wav(path: str, samples: np.ndarray) -> None:
    data = (samples * 32767).astype(np.int16)
    stereo = np.repeat(data.reshape(-1, 1), 2, axis=1).reshape(-1)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as fp:
        fp.setnchannels(2)
        fp.setsampwidth(2)
        fp.setframerate(SR)
        fp.writeframes(stereo.tobytes())


def main() -> int:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(here, "assets", "audio", "bgm.wav")
    mix = build()
    write_wav(out, mix)
    print(f"wrote {out}  ({len(mix) / SR:.1f}s, {os.path.getsize(out)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
