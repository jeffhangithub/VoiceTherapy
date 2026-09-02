"""
faster-whisper 本地 STT —— Pipecat SegmentedSTTService 自定义实现(含诊断日志)。

背景: pipecat 1.8.1 没有内置本地 faster-whisper 服务(STT 多为云 API),故自写。
基于: SegmentedSTTService 在 VAD 停后把整段语音交给 run_stt(audio) 一次。
  - wants_wav_segments=False → run_stt 收到裸 16-bit PCM(不是 WAV 容器)
  - run_stt 返回 AsyncGenerator, yield TranscriptionFrame 即完成一次转写
诊断: 日志前缀 [STT] — 用于定位语音环在哪一环断开。
"""
from __future__ import annotations

import asyncio
import time

import numpy as np
from faster_whisper import WhisperModel
from loguru import logger

from pipecat.frames.frames import (
    TranscriptionFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.services.settings import STTSettings
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
        # 填满 framework settings, 避免 NOT_GIVEN 警告
        super().__init__(
            settings=STTSettings(model=model, language=None),
            **kwargs,
        )
        self._model_name = model
        self._language = language
        self._device = device
        self._compute_type = compute_type
        self._model: WhisperModel | None = None  # 惰性加载, 首次转写时才下/载模型
        self._audio_frames = 0

    @property
    def wants_wav_segments(self) -> bool:
        # 本地模型读裸 16-bit PCM, 不要 WAV 头
        return False

    async def process_frame(self, frame, direction):
        # 诊断: 暴露 VAD 开口/闭嘴事件, 判断是否触发转写
        if isinstance(frame, VADUserStartedSpeakingFrame):
            logger.info(f"[STT] VAD: 用户开始说话 (frame={frame})")
        elif isinstance(frame, VADUserStoppedSpeakingFrame):
            logger.info(f"[STT] VAD: 用户停止说话 → 即将转写 (audio_buf 在 run_stt)")
        return await super().process_frame(frame, direction)

    # ---- 同步核心(在 executor 里跑, 不阻塞事件循环) ----
    def _transcribe_sync(self, pcm: bytes) -> str:
        if self._model is None:
            logger.info(f"[STT] 首次转写, 加载 faster-whisper 模型 '{self._model_name}' …")
            self._model = WhisperModel(
                self._model_name, device=self._device, compute_type=self._compute_type
            )
            logger.info(f"[STT] 模型加载完成")
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        logger.info(f"[STT] 开始转写 {len(audio) / 16000:.1f}s 音频 …")
        segments, _info = self._model.transcribe(
            audio, language=self._language, beam_size=1, vad_filter=True
        )
        text = "".join(s.text for s in segments).strip()
        logger.info(f"[STT] 转写结果: {text!r}")
        return text

    async def run_stt(self, audio: bytes):
        if not audio:
            return
        logger.info(f"[STT] run_stt 收到 {len(audio)} 字节音频")
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, self._transcribe_sync, audio)
        if text:
            yield TranscriptionFrame(text=text, user_id="", timestamp=str(time.time()))
