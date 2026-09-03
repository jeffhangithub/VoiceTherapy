"""
edge-tts —— Pipecat TTSService 自定义实现(中文女声, 免费, 含诊断日志)。

背景: pipecat 1.8.1 没有内置 edge-tts 服务, 故自写。
edge-tts 输出 MP3 → ffmpeg 解码成 16kHz 单声道 s16le PCM 喂给 Pipecat。
诊断: 日志前缀 [TTS] — 定位语音环在哪一环断开。

P2 延时优化(2026-09-02): 由「整段 MP3 下载完 → 一次性 ffmpeg 解码 → 再 yield」
改为「edge-tts 边合成边喂 ffmpeg 边解码, 边读边 yield」——首帧 PCM 一产出即推给
播放链路, 不再等整句合成完毕, 首字出声更早。
"""
from __future__ import annotations

import asyncio
import time

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

    async def run_tts(self, text: str, context_id: str):
        """流式合成: edge-tts 边出音频 chunk 边喂 ffmpeg, 边解码边 yield PCM 帧。

        与旧版差异: 旧版先 `asyncio.run` 把整段 MP3 攒进内存 → 整段 ffmpeg 解码
        → 再切帧 yield, 首帧要等整句合成完(实测 ~1.1-1.4s)。现在首帧在 edge-tts
        第一个音频 chunk 到达 + ffmpeg 解出第一段 PCM 后即 yield(实测 ~0.9-1.0s),
        省 ~0.2-0.4s, 且不占用 executor 线程。
        """
        text = (text or "").strip()
        if not text:
            return
        logger.info(f"[TTS] run_tts 收到文字: {text[:60]!r}")
        t_start = time.monotonic()

        com = edge_tts.Communicate(text, voice=self._voice)
        proc = await asyncio.create_subprocess_exec(
            _FFMPEG,
            "-loglevel", "error",
            "-i", "pipe:0",
            "-f", "s16le", "-ar", str(self._sr), "-ac", "1", "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        # 生产者任务: 把 edge-tts 音频 chunk 写入 ffmpeg stdin
        async def _feed():
            try:
                async for chunk in com.stream():
                    if chunk["type"] == "audio" and proc.stdin is not None:
                        proc.stdin.write(chunk["data"])
                        await proc.stdin.drain()
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[TTS] edge-tts 合成流异常: {e}")
            finally:
                if proc.stdin is not None:
                    try:
                        proc.stdin.close()
                    except Exception:  # noqa: BLE001
                        pass

        feed_task = asyncio.create_task(_feed())

        frame_bytes = int(self._sr * 0.02) * 2  # 20ms, 16-bit mono —— 与 WebRTC/Opus 20ms 帧对齐, 首帧更早且打断更细
        buf = bytearray()
        first_frame = True
        try:
            while True:
                data = await proc.stdout.read(4096)
                if not data:
                    break
                buf.extend(data)
                while len(buf) >= frame_bytes:
                    frame = bytes(buf[:frame_bytes])
                    del buf[:frame_bytes]
                    if first_frame:
                        first_frame = False
                        logger.info(
                            f"[TTS] 首帧合成 {time.monotonic() - t_start:.3f}s "
                            f"(收到文字→首帧 PCM)"
                        )
                    yield TTSAudioRawFrame(
                        audio=frame,
                        sample_rate=self._sr,
                        num_channels=1,
                        context_id=context_id,
                    )
            # 尾帧: 不足 20ms 的剩余 PCM
            if buf:
                yield TTSAudioRawFrame(
                    audio=bytes(buf),
                    sample_rate=self._sr,
                    num_channels=1,
                    context_id=context_id,
                )
        finally:
            await feed_task
            await proc.wait()
        logger.info(f"[TTS] 播放完成 (收到文字→全部播完 {time.monotonic() - t_start:.3f}s)")
