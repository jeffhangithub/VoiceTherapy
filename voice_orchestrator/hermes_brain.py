"""
Hermes 大脑封装 —— VoiceTherapy voice_orchestrator 的 C 层客户端。

把「麦克风环识别出的文字」发给 Hermes gateway API Server（完整 agent，
带 counselor skill + vault 访问），并流式拿回回答。

端点: http://127.0.0.1:8642/v1  （.env 里的 API_SERVER_KEY 认证）
契约: OpenAI Chat Completions, stream=true
会话连续性: X-Hermes-Session-Id 头（同一场多轮保持同一 agent 会话）
mode(driving/desk): 作为系统消息注入，让 counselor 知道开车还是桌面

只做文本进出，不碰音频。可脱离 Pipecat 独立测试。
"""
from __future__ import annotations

import os
import uuid
import re
from pathlib import Path
from typing import Iterator, Optional

from openai import OpenAI


def _load_env_key() -> str:
    """从 ~/.hermes/.env 读 API_SERVER_KEY（不回显）。"""
    env = os.environ.get("API_SERVER_KEY")
    if env:
        return env
    p = Path.home() / ".hermes" / ".env"
    if p.exists():
        m = re.search(r"^API_SERVER_KEY=(.+)$", p.read_text(), re.M)
        if m:
            return m.group(1).strip()
    raise RuntimeError("API_SERVER_KEY 未找到（~/.hermes/.env 或环境变量）")


class HermesBrain:
    """面向 Hermes 完整 agent 的文本大脑客户端。"""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8642/v1",
        api_key: Optional[str] = None,
        model: str = "hermes-agent",
    ):
        self.model = model
        self._client = OpenAI(base_url=base_url, api_key=api_key or _load_env_key())
        # 会话连续性：一场通话共用一个 session_id，让 Hermes 记住同一场上下文
        self.session_id: str = str(uuid.uuid4())

    def new_session(self) -> None:
        """新开一场：换 session_id（= 让大脑不带上场记忆）。"""
        self.session_id = str(uuid.uuid4())

    # ---- 系统人设：让 counselor 以正确 mode 开启 ----
    @staticmethod
    def _system_for(mode: str = "desk") -> str:
        return (
            "你现在是 Jeff 的心理咨询辅助对话助手，按 counselor 流程进行。"
            f"当前 mode={mode}（driving=开车/语音短聊；desk=桌面/可深谈）。"
            "用中文、具体短句；开场带出上次未完成的话题钩子；"
            "一次只问一个问题；不诊断、不下结论、危机只转介。"
        )

    def chat(
        self,
        user_text: str,
        mode: str = "desk",
        history: Optional[list] = None,
        stream: bool = True,
    ) -> Iterator[str]:
        """把一句话发给大脑，yield 流式文本分片。

        history: 可选，[{"role","content"},...] 已有多轮；None 则只发本条。
        """
        system = {"role": "system", "content": self._system_for(mode)}
        user = {"role": "user", "content": user_text}
        messages = [system] + (history or []) + [user]

        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=stream,
            extra_headers={"X-Hermes-Session-Id": self.session_id},
        )
        if stream:
            for chunk in resp:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        else:
            yield resp.choices[0].message.content or ""


if __name__ == "__main__":
    import sys

    # 最小自测：发一句话，看流式回答
    brain = HermesBrain()
    text = sys.argv[1] if len(sys.argv) > 1 else "用一句话说明你准备好了。"
    print(f"[session_id={brain.session_id[:8]}] 发送: {text}\n---流式回复---")
    out = []
    for piece in brain.chat(text, mode="desk"):
        print(piece, end="", flush=True)
        out.append(piece)
    print("\n---done---")
