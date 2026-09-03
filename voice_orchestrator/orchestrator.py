"""VoiceTherapy Phase 3.1 —— Pipecat 1.8.1 本机实时语音环 orchestrator。

管线（cascade，文字 MVP 之后接语音）:
    麦克风 → LocalAudioTransport → Silero VAD → SenseVoiceSTT(本地中文)
      → LLM(本地 Hermes API Server 8642, OpenAI 兼容) → EdgeTTS(中文) → 扬声器

架构（Pipecat 1.8.1 当前 Worker/PipelineTask/PipelineWorker 范式，对照官方模板
`cli/templates/server/_blocks/run_bot_logic_cascade.jinja2` + `_macros/pipeline_components.jinja2`）:

    Pipeline([transport.input(), stt, user_aggregator, llm, tts,
              transport.output(), assistant_aggregator])
    由 PipelineWorker 承载，WorkerRunner 驱动。

关键接法：
- VAD：`SileroVADAnalyzer` 挂在 `LLMUserAggregator`（`LLMContextAggregatorPair` 的
  `user_params.vad_analyzer`）。用户开口/闭嘴产生的 VAD 帧沿管线回传到上游的
  `SegmentedSTTService`，触发「闭嘴后整段转写」。
- LLM：`OpenAILLMService(base_url=..., api_key=...)` 指到本地 Hermes 8642。这两个参数
  走 `BaseOpenAILLMService` 的 kwargs → `create_client` → `AsyncOpenAI(api_key, base_url)`；
  模型名 / 系统提示走 `OpenAILLMService.Settings(model=..., system_instruction=...)`。
- 全链路 16kHz（Silero VAD 只支持 8k/16k），单声道。

注意：真正开麦/发声（LocalAudioTransport 打开 PortAudio 流、VAD 实时判停、edge-tts 联网合成）
必须真机活测；本文件只保证 import 无错 + 对象图可构造。
"""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
from pipecat.workers.runner import WorkerRunner

from edge_tts_service import EdgeTTSService
from sensevoice_stt import SenseVoiceSTTService

# ---- 常量 ----
SAMPLE_RATE = 16000  # 全链路 16kHz，Silero VAD 只支持 8000/16000
HERMES_BASE_URL = "http://127.0.0.1:8642/v1"
HERMES_MODEL = "hermes-agent"
HERMES_ENV_PATH = Path.home() / ".hermes" / ".env"
# 咨询开场上下文：由 counselor_context 预注入(人设+热层+林老师开场回顾)，
# 避免大脑现场 agentic 翻库造成的卡顿/高延时。在 build_llm() 时(每场会话开始)组装。
from counselor_context import build as build_counselor_context  # noqa: E402


def load_hermes_api_key() -> str:
    """从 ~/.hermes/.env 读 API_SERVER_KEY（优先环境变量，绝不硬编码）。"""
    env = os.environ.get("API_SERVER_KEY")
    if env:
        return env
    if HERMES_ENV_PATH.exists():
        m = re.search(r"^API_SERVER_KEY=(.+)$", HERMES_ENV_PATH.read_text(), re.M)
        if m:
            return m.group(1).strip()
    raise RuntimeError(f"未找到 API_SERVER_KEY（检查 {HERMES_ENV_PATH} 或环境变量 API_SERVER_KEY）")


def build_transport_params() -> LocalAudioTransportParams:
    """本机音频传输参数：16kHz 单声道收发，默认系统输入/输出设备。"""
    return LocalAudioTransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        audio_in_sample_rate=SAMPLE_RATE,
        audio_out_sample_rate=SAMPLE_RATE,
        audio_in_channels=1,
        audio_out_channels=1,
        # input_device_index / output_device_index 默认 None = 系统默认设备
    )


def build_llm() -> OpenAILLMService:
    """把 LLM 指到本地 Hermes gateway API Server（完整 agent，OpenAI 兼容）。"""
    return OpenAILLMService(
        api_key=load_hermes_api_key(),
        base_url=HERMES_BASE_URL,
        settings=OpenAILLMService.Settings(
            model=HERMES_MODEL,
            system_instruction=build_counselor_context(),  # 每场会话开始组装(预注入)
        ),
    )


def build_services():
    """构造三个 service（STT / LLM / TTS），供 headless 验证或后续复用。"""
    return {
        "stt": SenseVoiceSTTService(),  # 中文专用，本地，快而准
        "llm": build_llm(),
        "tts": EdgeTTSService(),           # edge-tts 中文，MP3 → ffmpeg → 16k PCM
    }


def build_pipeline(transport: LocalAudioTransport, llm: OpenAILLMService) -> Pipeline:
    """按官方 cascade 模板顺序拼装管线对象图。

    顺序（对照 pipeline_components.jinja2 的 cascade_pipeline 宏）:
        input → stt → user_aggregator → llm → tts → output → assistant_aggregator
    """
    stt = SenseVoiceSTTService()
    tts = EdgeTTSService()

    # LLM 上下文 + 用户/助手聚合器；VAD 挂在用户聚合器上（Silero 判停触发 STT）
    # 灵敏度放宽：min_volume 降低、stop_secs 拉长，便于首次调试触发
    context = LLMContext()
    vad = SileroVADAnalyzer(
        params=VADParams(
            confidence=0.5,
            start_secs=0.2,
            stop_secs=0.5,
            min_volume=0.3,
        )
    )
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=vad),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )
    return pipeline


async def main() -> None:
    """本机实时语音环入口：构造 transport/LLM/pipeline → PipelineWorker → WorkerRunner。"""
    logger.info("VoiceTherapy 语音环启动（Hermes 大脑 @ 127.0.0.1:8642）…")

    transport = LocalAudioTransport(build_transport_params())
    llm = build_llm()
    pipeline = build_pipeline(transport, llm)

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=SAMPLE_RATE,
            audio_out_sample_rate=SAMPLE_RATE,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())
