# VoiceTherapy — voice_orchestrator

Phase 3 语音编排器。跑在 Mac Mini 上，作为常驻进程，把**麦克风↔扬声器的实时音频环**接到 Hermes（大脑）上。

对应设计文档 §3.1 的 **B 层（语音编排）**：管 VAD / ASR / 判停 / 打断 / TTS；**只传文本 + mode + session_id** 给 Hermes，音频不进 Hermes。不做咨询推理（那是 C 层 Hermes + D 层 vault 的事）。

## 当前架构选型（已定，不选 LiveKit）

| 层 | 选型 | 阶段 |
|---|---|---|
| 编排 | **Pipecat** | Phase 3.1 起 |
| VAD | Silero | 3.1 |
| ASR | faster-whisper（本地）→ SenseVoice/FunASR 流式 | 起步→再切 |
| TTS | edge（微软免费，无 key）→ CosyVoice 流式（本地） | 起步→再切 |
| 大脑 | Hermes gateway API Server | 3.1 |
| 打断 | Pipecat barge-in（停播 + `POST /v1/runs/{id}/stop` 取消生成） | 3.2 |
| 网络(手机) | Tailscale + WebRTC | 3.3 |

## Hermes 大脑连接契约（已实测）

- **端点**：`http://127.0.0.1:8642/v1`（Hermes gateway API Server 平台，跑**完整 agent**：带 counselor skill + vault 访问）
- **认证**：`Authorization: Bearer $API_SERVER_KEY`（key 在 `~/.hermes/.env`，本机回环用）
- **格式**：OpenAI Chat Completions（`POST /v1/chat/completions`，`stream=true`）
- **会话连续性**：请求头带 `X-Hermes-Session-Id: <uuid>` 让多轮语音保持同一 agent 会话
- **长时记忆范围**：`X-Hermes-Session-Key` 头（可选，记忆按 key 分域）
- **打断取消**：`POST /v1/runs/{run_id}/stop`（barge-in 时中断当前生成）
- **mode**（driving/desk）作为系统消息注入本轮 agent

> ⚠️ 不是 `hermes proxy`——那是连云 OAuth 的薄代理、无 skill/vault，不能用。本编排器只接上面这个完整 agent 端点。

## 目录（规划）

```
voice_orchestrator/
├── config.example.yaml   # 编排配置模板（复制为 config.yaml）
├── orchestrator.py        # Pipecat pipeline：mic→VAD→ASR→Hermes→TTS→speaker
├── hermes_brain.py        # 封装到 8642 的 OpenAI 兼容调用 + stream + cancel
└── README.md
```

## 运行前提（Phase 3.1）

1. Hermes gateway 已启用 API Server（`.env` 加 `API_SERVER_ENABLED=true` + `API_SERVER_KEY`，端口 8642）
2. `pip install pipecat-ai` 及音频/模型依赖（见 `pyproject.toml` / 安装说明）
3. 本机麦克风 + 扬声器可用

## 分步落地

- **3.1** 本机环：mic → VAD(Silero) → ASR(faster-whisper) → Hermes(stream) → TTS(edge) → speaker
- **3.2** barge-in：Pipecat 打断 + 停播 + `POST /v1/runs/{id}/stop`
- **3.3** 手机 WebRTC over Tailscale（复用 Pipecat 的 WebRTC/LiveKit transport）
