"""hermes_session.py —— 管理 VoiceTherapy 与 Hermes api_server 的会话生命周期。

背景：VoiceTherapy 每场对话经 /v1/chat/completions(不带 X-Hermes-Session-Id) 调用 Hermes。
api_server 用 (system_prompt + 首条用户消息) 的 sha256 指纹推导稳定 session_id
(见 ~/.hermes/hermes-agent/gateway/platforms/api_server.py _derive_chat_session_id)，
把整场对话归到同一条 session；但这些 stateless 会话从不被置 ended_at。

本模块让 VoiceTherapy 在会话结束(手机断开)时：
  1) 用同一条系统提示 + 首句复刻出 Hermes 推导的 session_id
  2) PATCH /api/sessions/{id} {end_reason:...} 把它归档(置 ended_at)
纯附加、不动转写逻辑；指纹对不上时 PATCH 404 无副作用。
"""
from __future__ import annotations

import hashlib

import httpx
from loguru import logger

_HERMES_ROOT = "http://127.0.0.1:8642"  # Hermes api_server 根(不带 /v1)


def derive_session_id(system_prompt: str, first_user_message: str) -> str:
    """复刻 Hermes api_server 的指纹 session_id（须与它收到的字符串逐字一致）。"""
    seed = f"{system_prompt or ''}\n{first_user_message}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"api-{digest}"


def first_user_text(messages) -> str | None:
    """从 pipecat LLMContext.messages 里取首条 user 消息的纯文本。"""
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        # 新版 pipecat content 可能是 [{type:text,text:...}]
        if isinstance(content, list):
            parts = []
            for p in content:
                if isinstance(p, dict) and p.get("type") == "text":
                    parts.append(p.get("text", ""))
                elif isinstance(p, str):
                    parts.append(p)
            text = "".join(parts).strip()
        else:
            text = str(content).strip()
        if text:
            return text
    return None


async def end_session(
    session_id: str,
    api_key: str | None,
    end_reason: str = "conversation_ended",
    timeout: float = 3.0,
) -> bool:
    """PATCH /api/sessions/{id} 置 ended_at。best-effort，失败仅记日志。"""
    if not session_id or not api_key:
        logger.info("[HermesSession] 跳过结束(缺 session_id 或 key)")
        return False
    url = f"{_HERMES_ROOT}/api/sessions/{session_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.patch(url, headers=headers, json={"end_reason": end_reason})
        if resp.status_code in (200, 204):
            logger.info(f"[HermesSession] 已归档会话 {session_id} (end_reason={end_reason})")
            return True
        logger.info(f"[HermesSession] 结束会话 {session_id} → HTTP {resp.status_code} (无副作用, 指纹可能已变)")
        return False
    except Exception as exc:
        logger.warning(f"[HermesSession] 结束会话失败: {exc}")
        return False
