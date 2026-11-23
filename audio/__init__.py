"""音频层：背景音乐 + 音效 + 语音触发。

表现层只依赖这里暴露的简单接口（play / start_bgm / consume），
不直接碰 pygame.mixer 或语音识别库。
"""
