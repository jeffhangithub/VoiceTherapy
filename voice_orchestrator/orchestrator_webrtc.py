"""VoiceTherapy Phase 3.3 —— 手机 WebRTC 版 orchestrator（Pipecat small-webrtc runner）。

与 orchestrator.py(本机 LocalAudio) 同一套 STT/LLM/TTS/VAD，只是把传输层换成
SmallWebRTCTransport：手机浏览器(client-js @pipecat-ai/client-js + small-webrtc)
经 Tailscale 连到 Mini 的 runner(/api/offer 信令)，跑「手机麦克风 → VAD → 转写
→ Hermes 8642 → edge女声 → 手机扬声器」全链路，打断靠 VAD barge-in。

用法（需 Tailscale 已起，两端同 tailnet）：
    HTTPS_PROXY=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897 \\
    .venv/bin/python orchestrator_webrtc.py --host 0.0.0.0 --port 7860 -t webrtc
手机浏览器开 http://<Mini-Tailscale-IP>:7860/ 加载客户端，点 Connect。

注意：runner 从「调用它的模块」里发现 `async def bot(runner_args)`，故本文件自带入口。
"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

# 复用现有组件/常量（load_hermes_api_key 等在 orchestrator.py）
sys.path.insert(0, str(Path(__file__).parent))
from orchestrator import (  # noqa: E402
    SAMPLE_RATE,
    build_llm,
    load_hermes_api_key,
)
from edge_tts_service import EdgeTTSService  # noqa: E402
from sensevoice_stt import SenseVoiceSTTService  # noqa: E402

from pipecat.audio.vad.silero import SileroVADAnalyzer  # noqa: E402
from pipecat.audio.vad.vad_analyzer import VADParams  # noqa: E402
from pipecat.pipeline.pipeline import Pipeline  # noqa: E402
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy  # noqa: E402
from pipecat.processors.aggregators.llm_context import LLMContext  # noqa: E402
from pipecat.processors.aggregators.llm_response_universal import (  # noqa: E402
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments  # noqa: E402
from pipecat.transports.base_transport import BaseTransport, TransportParams  # noqa: E402
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection  # noqa: E402
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport  # noqa: E402
from pipecat.workers.runner import WorkerRunner  # noqa: E402


async def run_bot(transport: BaseTransport, _runner_args: RunnerArguments):
    """拼 WebRTC 版管线（与 orchestrator.py 同构，VAD 灵敏度放宽便于手机试）。"""
    stt = SenseVoiceSTTService()
    tts = EdgeTTSService()
    llm = build_llm()  # Hermes 8642, key 从 .env 读，不硬编码

    context = LLMContext()
    vad = SileroVADAnalyzer(
        params=VADParams(confidence=0.5, start_secs=0.2, stop_secs=0.5, min_volume=0.3)
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

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=SAMPLE_RATE,
            audio_out_sample_rate=SAMPLE_RATE,
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        processor_unusable_policy=ProcessorUnusablePolicy.END,
    )

    runner = WorkerRunner(handle_sigint=_runner_args.handle_sigint)
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(_transport, _client):
        logger.info("📱 手机客户端已连接 —— WebRTC 语音环就绪，请说话")
        # 人设/开场回顾由 build_llm() 按会话注入 system_instruction，此处不再重复注入
        # 可选：连接后打个招呼，让 Jeff 听到出声即确认链路通
        # (先不自动说话，避免与用户抢话；由用户先开口触发)

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, _client):
        logger.info("📱 手机客户端断开")
        await runner.cancel()

    await runner.run()


async def bot(runner_args: RunnerArguments):
    """Runner 入口：用 runner 注入的 WebRTC 连接建传输。"""
    webrtc_connection: SmallWebRTCConnection = runner_args.webrtc_connection
    transport = SmallWebRTCTransport(
        webrtc_connection=webrtc_connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    )
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
