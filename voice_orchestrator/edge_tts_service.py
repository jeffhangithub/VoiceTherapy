"""
edge-tts —— Pipecat TTSService 自定义实现(中文女声, 免费, 含诊断日志)。

背景: pipecat 1.8.1 没有内置 edge-tts 服务, 故自写。
edge-tts 输出 MP3 → ffmpeg 解码成 16kHz 单声道 s16le PCM 喂给 Pipecat。
诊断: 日志前缀 [TTS] — 定位语音环在哪一环断开。
"""
from __future__ import annotations

import asyncio
import io
import subprocess

import edge_tts
from loguru import logger

from pipecat.frames.frames import TTSAudioRawFrame
from pipecat.services.settings import TTSSettings
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
        # 填满 framework settings, 避免 NOT_GIVEN 警告
        super().__init__(
            settings=TTSSettings(voice=voice, model=None, language=None),
            **kwargs,
        )
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
        logger.info(f"[TTS] run_tts 收到文字: {text[:60]!r}")
        loop = asyncio.get_running_loop()
        pcm = await loop.run_in_executor(None, self._synth_to_pcm, text)
        logger.info(f"[TTS] 合成 PCM {len(pcm)} 字节, 开始播放")
        # 切成 ~100ms 帧逐段 yield, 便于打断(barge-in)在帧边界停播
        # 注意: 必须 yield TTSAudioRawFrame(带 context_id, 继承 OutputAudioRawFrame),
        #       不能 yield 普通 AudioRawFrame —— 否则输出传输因缺 id/transport_destination 拒收
        frame_bytes = int(self._sr * 0.1) * 2  # 100ms, 16-bit mono
        for i in range(0, len(pcm), frame_bytes):
            yield TTSAudioRawFrame(
                audio=pcm[i : i + frame_bytes],
                sample_rate=self._sr,
                num_channels=1,
                context_id=context_id,
            )
        logger.info(f"[TTS] 播放完成")
