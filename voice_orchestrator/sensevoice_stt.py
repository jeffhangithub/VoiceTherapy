"""
sensevoice_stt.py — 基于 sherpa-onnx 的 SenseVoice 本地 STT（Pipecat SegmentedSTTService）。

对比 faster-whisper：SenseVoice 为中文/粤语等优化的 ASR，普通话识别明显更准，且支持
ITN(逆文本正则，数字/时间归一)。本服务在 VAD 停后把整段音频交给 SenseVoice 转一次。

模型：sherpa-onnx 官方 SenseVoice onnx 模型，放 asr_models/<model_dir>/。
依赖：sherpa-onnx（轻量，无需 torch）。
"""
from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path

import numpy as np
from loguru import logger

from pipecat.frames.frames import (
    TranscriptionFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.services.settings import STTSettings
from pipecat.services.stt_service import SegmentedSTTService

# 模型目录：默认 asr_models 下最新的 sherpa-onnx-sense-voice-*
_MODELS_DIR = Path(__file__).parent / "asr_models"
_MODEL_GLOB = "sherpa-onnx-sense-voice-*"

# —— 非语音/填充词过滤（呼吸、笑声、语气叹词常被误转成乱字符）——
# 1) SenseVoice 的事件/非语音标签：命中即判定整段非语音，丢弃
_NONSPEECH_TAG = re.compile(
    r"<\|(nospeech|speech|Laughter|Applause|BGM|Cough|Sneeze|Cry|Event|Emotion|Noise|Silence)\|>",
    re.I,
)
# 2) 任意 SenseVoice 标签（如 <|zh|> <|itn|> <|Emotion|>）先剥掉
_ANY_TAG = re.compile(r"<\|[^|]*\|>")
# 3) 纯叹词/语气词（去掉标点空白后仅剩这些 → 视为呼吸/语气词，丢弃）
_FILLER_CHARS = set("嗯唔呣呃哦噢喔唉哎哎额诶欸诶呀嘛唷喏哈嘿嘻呵噷嘸啊")
_PUNCT = re.compile(r"[\s，。、！？；：,.!?;:~～…·\-—'\"“”‘’()（）]+")


def _clean_transcript(text: str) -> str:
    """清理 SenseVoice 输出：剥标签、丢弃非语音事件与纯叹气/呼吸段落。返回 '' 表示丢弃。"""
    if not text:
        return ""
    if _NONSPEECH_TAG.search(text):     # 笑声/咳嗽/BGM/nospeech 等 → 整段非语音
        return ""
    t = _ANY_TAG.sub("", text).strip()   # 剥掉语言/ITN 等标签
    core = _PUNCT.sub("", t)
    if not core:
        return ""
    if all(ch in _FILLER_CHARS for ch in core):  # 纯"嗯/呃/啊…"→ 呼吸或语气词
        return ""
    return t


class SenseVoiceSTTService(SegmentedSTTService):
    def __init__(
        self,
        *,
        model_dir: str | Path | None = None,
        num_threads: int = 2,
        language: str = "auto",
        use_itn: bool = True,
        **kwargs,
    ):
        super().__init__(settings=STTSettings(model="SenseVoice", language=None), **kwargs)
        if model_dir is None:
            model_dir = _find_latest_model_dir()
        self._model_dir = Path(model_dir)
        self._num_threads = num_threads
        self._language = language
        self._use_itn = use_itn
        self._recognizer = None  # 惰性加载

    @property
    def wants_wav_segments(self) -> bool:
        return False  # 要裸 16-bit PCM(与 faster_whisper 一致)

    async def process_frame(self, frame, direction):
        if isinstance(frame, VADUserStartedSpeakingFrame):
            logger.info("[SenseVoice] VAD: 用户开始说话")
        elif isinstance(frame, VADUserStoppedSpeakingFrame):
            logger.info("[SenseVoice] VAD: 用户停止 → 即将转写")
        return await super().process_frame(frame, direction)

    # 同步核心(executor 里跑)
    def _transcribe_sync(self, pcm: bytes) -> str:
        if self._recognizer is None:
            logger.info(f"[SenseVoice] 首次转写, 加载模型 {self._model_dir} …")
            import sherpa_onnx
            # 优先 int8 量化模型(CPU 快); 否则用 fp32 model.onnx
            onnx = self._model_dir / "model.int8.onnx"
            if not onnx.exists():
                onnx = self._model_dir / "model.onnx"
            self._recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
                model=str(onnx),
                tokens=str(self._model_dir / "tokens.txt"),
                num_threads=self._num_threads,
                use_itn=self._use_itn,
                language=self._language,
                debug=False,
            )
            logger.info("[SenseVoice] 模型加载完成")
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        logger.info(f"[SenseVoice] 开始转写 {len(samples) / 16000:.1f}s 音频 …")
        stream = self._recognizer.create_stream()
        stream.accept_waveform(16000, samples)
        self._recognizer.decode_stream(stream)
        text = (stream.result.text or "").strip()
        logger.info(f"[SenseVoice] 转写结果: {text!r}")
        return text

    async def run_stt(self, audio: bytes):
        if not audio:
            return
        logger.info(f"[SenseVoice] run_stt 收到 {len(audio)} 字节音频")
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, self._transcribe_sync, audio)
        text = _clean_transcript(raw)
        if not text:
            if raw:
                logger.info(f"[SenseVoice] 过滤非语音/叹词/噪声, 丢弃: {raw!r}")
            return
        yield TranscriptionFrame(text=text, user_id="", timestamp=str(time.time()))


def _find_latest_model_dir() -> Path:
    if not _MODELS_DIR.exists():
        raise FileNotFoundError(f"未找到 ASR 模型目录: {_MODELS_DIR}")
    dirs = sorted(_MODELS_DIR.glob(_MODEL_GLOB), key=lambda p: p.stat().st_mtime, reverse=True)
    if not dirs:
        raise FileNotFoundError(f"未找到 SenseVoice 模型: {_MODELS_DIR / _MODEL_GLOB}")
    return dirs[0]
