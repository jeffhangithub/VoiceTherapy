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
# 3) 语气词/应答字集合
_ANSWER_OK = set("嗯对好是行要中")                 # 单字可能是真实应答 → 保留
_DEAD_FILLER = set("呃唔欸唉喂咦哦噢啊呀哇哈嘿嘻哎呕唷喏嘛嗳诶呣噷嘸")  # 非应答语气词 → 丢
_PUNCT = re.compile(r"[\s，。、！？；：,.!?;:~～…·\-—'\"“”‘’()（）]+")
_LATIN_RUN = re.compile(r"[A-Za-z]{3,}")            # 拉丁碎词(如 contacttact)
_CJK = re.compile(r"[\u4e00-\u9fff]")               # 任一汉字


def _looks_like_noise(text: str, dur_s: float) -> bool:
    """仅在【完全不含中文】时才判噪声。

    修正：旧版把"含 ≥3 连续拉丁字母"或"<0.7s 却出多字"当噪声，
    会**误删含 ADHD/AI/PPT 等缩写的真实发言**（2026-09-14 曾整句丢弃
    "对，因为我刚才说我自己是ADHD。"）。现规则：只要含任一汉字 → 真实发言，绝不丢；
    只有完全无中文的碎片（"Yeah."/"It why."/"contacttact"）才判噪声。dur_s 保留入参、不再用。
    """
    if _CJK.search(text):          # 含任何汉字 → 真实发言
        return False
    core = _PUNCT.sub("", text)
    return bool(core)              # 完全无中文且非空 → 噪声碎片


def _clean_transcript(text: str, dur_s: float = 99.0) -> str:
    """清理 SenseVoice 输出：剥标签、丢非语音事件、丢纯语气词/重复叹词、丢短噪声。返回 '' 表示丢弃。

    A：单个"嗯/对/好"等可能真是应答 → 保留；只丢重复叹词(嗯嗯/呃呃)与非应答语气词(呃/唔/欸)。
    B：过短音频却出拉丁碎词/多字乱码 → 判噪声丢弃。
    """
    if not text:
        return ""
    if _NONSPEECH_TAG.search(text):     # 笑声/咳嗽/BGM/nospeech 等 → 整段非语音
        return ""
    t = _ANY_TAG.sub("", text).strip()   # 剥掉语言/ITN 等标签
    core = _PUNCT.sub("", t)
    if not core:
        return ""
    if _looks_like_noise(t, dur_s):      # B：短音频噪声
        return ""
    if len(core) == 1:                   # A：单字
        return "" if core in _DEAD_FILLER else t   # 呃/唔/啊→丢；嗯/对/好/累…→留
    # A：多字且全是语气/应答字
    if all(ch in (_ANSWER_OK | _DEAD_FILLER) for ch in core):
        if len(set(core)) == 1:          # 重复同一字(嗯嗯/呃呃/对对)→丢
            return ""
        if any(ch in _ANSWER_OK for ch in core) and not any(ch in _DEAD_FILLER for ch in core):
            return t                     # 嗯对/嗯好 等含真实应答字 → 留
        return ""                        # 嗯呃 等含非应答语气字 → 丢
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
        dur_s = len(audio) / 2 / 16000  # 16-bit mono @16k
        text = _clean_transcript(raw, dur_s)
        if not text:
            if raw:
                logger.info(f"[SenseVoice] 过滤非语音/叹词/噪声({dur_s:.2f}s), 丢弃: {raw!r}")
            return
        yield TranscriptionFrame(text=text, user_id="", timestamp=str(time.time()))


def _find_latest_model_dir() -> Path:
    if not _MODELS_DIR.exists():
        raise FileNotFoundError(f"未找到 ASR 模型目录: {_MODELS_DIR}")
    dirs = sorted(_MODELS_DIR.glob(_MODEL_GLOB), key=lambda p: p.stat().st_mtime, reverse=True)
    if not dirs:
        raise FileNotFoundError(f"未找到 SenseVoice 模型: {_MODELS_DIR / _MODEL_GLOB}")
    return dirs[0]
