# VoiceTherapy — voice_orchestrator（B 层 · 语音编排）

跑在 Mac Mini 上的常驻语音编排层：把**麦克风↔扬声器的实时音频环**（本机环 + 手机 WebRTC）接到 Hermes（大脑）。

对应设计文档 §3.1 的 **B 层**：管 VAD / ASR / 判停 / 打断 / TTS 与证据注入；音频不进 Hermes，只把**文本**交给它。不做咨询推理（那是 C 层 Hermes + D 层 vault 的事）。

## 当前架构选型

| 层 | 选型 | 说明 |
|---|---|---|
| 编排 | **Pipecat 1.8** | pipeline 入口 `orchestrator.py`(本机) / `orchestrator_webrtc.py`(手机) |
| VAD | Silero | 句级判停；**收紧抗噪**（confidence 0.6 / start 0.35s / min_volume 0.5）|
| ASR | **SenseVoice**（sherpa-onnx，本地中文）| 当前默认；输出侧**非语音/叹词过滤**（丢呼吸/笑声/重复叹词/短噪声，留真实短应答）|
| TTS | **edge-tts**（微软免费，无 key）| 流式首帧→PCM；**空音频自动重试** |
| 大脑 | **Hermes gateway API Server**（`127.0.0.1:8642`，完整 agent + counselor skill + vault）| 单次 chat completion |
| 上下文 | `counselor_context.build()` 预注入 | 人设 + 热层(过滤测试态) + 最近林老师会谈回顾；**自动摘要**(>12k token)防长会谈变慢 |
| 证据 | `evidence_retrieval.py` + `EvidenceInjector` | 要「原话/证据」时本地检索 **L3 逐字稿**按需注入（带日期+说话人+时间戳）|
| 打断 | Pipecat barge-in（**本地停播 + 取消当前生成**）| 不依赖远端 stop 接口 |
| 网络(手机) | Tailscale + WebRTC | `https://mac.tail844e3d.ts.net/` |
| 会话生命周期 | `hermes_session.py` | 结束复刻指纹 → 归档 Hermes 会话(置 `ended_at`) |

> 备选 STT：`faster_whisper_stt.py`（中文弱，默认已换 SenseVoice）。

## Hermes 大脑连接契约（实测）

- **端点**：`http://127.0.0.1:8642/v1` —— Hermes gateway **API Server**（跑完整 agent：counselor skill + vault 访问）
- **认证**：`Authorization: Bearer $API_SERVER_KEY`（key 在 `~/.hermes/.env`，本机回环用）
- **格式**：OpenAI Chat Completions（`POST /v1/chat/completions`）
- **会话连续性**：**不**发 `X-Hermes-Session-Id` 头——Hermes 按 `(system_prompt + 首条用户消息)` 的 sha256 **指纹**推导稳定 session_id（一场一条）；结束时由 `hermes_session.end_session` 复刻同指纹并 `PATCH /api/sessions/{id}` 归档。
- **系统指令**：每场由 `counselor_context.build()` 组好整段预注入（非运行时 agentic 翻库——单次 completion 现场翻库会卡死）。
- **打断**：barge-in 在 Pipecat 内完成（停播 + 取消当前 LLM/TTS），无需远端接口。

> ⚠️ 不是 `hermes proxy`——那是连云 OAuth 的薄代理、无 skill/vault，不能用。本编排器只接上面这个完整 agent 端点。

## 文件

```
voice_orchestrator/
├── orchestrator.py          # 本机实时语音环(麦克风/扬声器，pipeline 入口)
├── orchestrator_webrtc.py   # 手机 WebRTC runner（SmallWebRTCTransport，:7860）
├── sensevoice_stt.py        # 本地中文 STT(sherpa-onnx SenseVoice) + 非语音/叹词过滤
├── faster_whisper_stt.py    # 备选 STT(faster-whisper，中文弱)
├── edge_tts_service.py      # 中文 TTS(edge→ffmpeg→PCM；流式首帧；空音频重试)
├── counselor_context.py     # 咨询开场上下文组装器(预注入人设+热层+林老师回顾)
├── evidence_retrieval.py    # 分层证据：本地检索 L3 逐字稿 + EvidenceInjector
├── hermes_session.py        # Hermes 会话生命周期(结束复刻指纹→归档)
├── hermes_brain.py          # (遗留)早期独立 Hermes 客户端，当前未接线
├── web_server.js            # 自定义页静态 + /api/offer 反代 runner + /api/save 存库
├── web_client/              # 定制咨询师 PWA(index/styles/main/manifest/icon)
└── asr_models/              # (gitignore)SenseVoice onnx 模型，按需下载
```

## 运行

- **常驻(launchd，开机自启)**：`com.voicetherapy.webrtc.runner`(7860) + `com.voicetherapy.web.server`(8050)
- **对外**：`tailscale serve` 根 → `web_server.js`(8050) → 手机开 `https://mac.tail844e3d.ts.net/`
- 本机环：`orchestrator.py`（与手机路径共用 STT/LLM/TTS/VAD + `counselor_context`）
