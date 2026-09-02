"""
faster-whisper 本地 STT —— Pipecat SegmentedSTTService 自定义实现。

背景: pipecat 1.8.1 没有内置本地 faster-whisper 服务(STT 多为云 API),故自写。
基于: SegmentedSTTService 在 VAD 停后把整段语音交给 run_stt(audio) 一次。
  - wants_wav_segments=False → run_stt 收到裸 16-bit PCM(不是 WAV 容器)
  - run_stt 返回 AsyncGenerator, yield TranscriptionFrame 即完成一次转写
faster-whisper 的中文转写链路已在别处头验通过(edge 合成→ffmpeg 解码→转写回中文)。
"""
from __future__ import annotations

import asyncio
import time

import numpy as np
from faster_whisper import WhisperModel

from pipecat.frames.frames import TranscriptionFrame
from pipecat.services.stt_service import SegmentedSTTService


class FasterWhisperSTTService(SegmentedSTTService):
    """本地 faster-whisper 中文 STT(分段式, VAD 停后整段转写)。"""

    def __init__(
        self,
        *,
        model: str = "base",
        language: str = "zh",
        device: str = "cpu",
        compute_type: str = "int8",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._model_name = model
        self._language = language
        self._device = device
        self._compute_type = compute_type
        self._model: WhisperModel | None = None  # 惰性加载, 首次转写时才下/载模型

    @property
    def wants_wav_segments(self) -> bool:
        # 本地模型读裸 16-bit PCM, 不要 WAV 头
        return False

    # ---- 同步核心(在 executor 里跑, 不阻塞事件循环) ----
    def _transcribe_sync(self, pcm: bytes) -> str:
        if self._model is None:
            self._model = WhisperModel(
                self._model_name, device=self._device, compute_type=self._compute_type
            )
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _info = self._model.transcribe(
            audio, language=self._language, beam_size=1, vad_filter=True
        )
        return "".join(s.text for s in segments).strip()

    async def run_stt(self, audio: bytes):
        if not audio:
            return
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, self._transcribe_sync, audio)
        if text:
            yield TranscriptionFrame(text=text, user_id="", timestamp=str(time.time()))
