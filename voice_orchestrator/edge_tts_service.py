"""
edge-tts —— Pipecat TTSService 自定义实现(中文女声, 免费)。

背景: pipecat 1.8.1 没有内置 edge-tts 服务, 故自写。
基于: TTSService 抽象方法 run_tts(text, context_id) 需 yield AudioRawFrame。
edge-tts 输出 MP3 → 用 ffmpeg 解码成 16kHz 单声道 s16le PCM 喂给 Pipecat。
(Mac 上 /opt/homebrew/bin/ffmpeg 已装。edge-tts 联网合成, 需代理时启动前 export 代理。)

头验: edge 合成中文 → ffmpeg 解码 PCM 已通过。
"""
from __future__ import annotations

import asyncio
import io
import subprocess

import edge_tts

from pipecat.frames.frames import AudioRawFrame
from pipecat.services.tts_service import TTSService

_FFMPEG = "/opt/homebrew/bin/ffmpeg"


class EdgeTTSService(TTSService):
    """edge-tts 中文语音合成(默认 zh-CN-XiaoxiaoNeural 女声)。"""

    def __init__(
        self,
        *,
        voice: str = "zh-CN-XiaoxiaoNeural",
        sample_rate: int = 16000,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._voice = voice
        self._sr = sample_rate

    # ---- 同步核心: 合成 MP3 → ffmpeg 解码成 PCM(在 executor 线程跑) ----
    def _synth_to_pcm(self, text: str) -> bytes:
        async def _stream() -> bytes:
            com = edge_tts.Communicate(text, voice=self._voice)
            buf = io.BytesIO()
            async for chunk in com.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            return buf.getvalue()

        mp3 = asyncio.run(_stream())  # executor 线程无事件循环, 可安全 asyncio.run
        p = subprocess.run(
            [
                _FFMPEG, "-loglevel", "error",
                "-i", "pipe:0",
                "-f", "s16le", "-ar", str(self._sr), "-ac", "1", "pipe:1",
            ],
            input=mp3, capture_output=True, check=True,
        )
        return p.stdout

    async def run_tts(self, text: str, context_id: str):
        text = (text or "").strip()
        if not text:
            return
        loop = asyncio.get_running_loop()
        pcm = await loop.run_in_executor(None, self._synth_to_pcm, text)
        # 切成 ~100ms 帧逐段 yield, 便于打断(barge-in)在帧边界停播
        frame_bytes = int(self._sr * 0.1) * 2  # 100ms, 16-bit mono
        for i in range(0, len(pcm), frame_bytes):
            yield AudioRawFrame(
                audio=pcm[i : i + frame_bytes],
                sample_rate=self._sr,
                num_channels=1,
            )
