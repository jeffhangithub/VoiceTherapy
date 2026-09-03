# VoiceTherapy

基于 Hermes Agent、Obsidian 个人知识库和实时语音服务的私人心理支持工具。

目标是在 iPhone 和车载蓝牙场景中提供低延迟、可打断的双向语音对话。Hermes 负责对话推理与知识检索；Mac mini 作为常驻服务端；原始音频不落盘，只按用户选择保存逐字稿和摘要。

> 本项目用于个人心理支持和自我反思，不替代持证心理咨询、医疗诊断或紧急服务。

## 权威设计文档

**设计以飞书文档 v0.2 为准**：

- [设计文档：本地 Hermes 心理咨询语音助手（Counselor Voice Agent）v0.2](https://my.feishu.cn/wiki/RUCJwUxq0iP1K5k6wuXc81K4nVb)
  （腾讯/飞书链接不可用时，以仓库内 `docs/` 或下方同步内容为准——飞书为唯一真相源）

本仓库不再维护独立的本地架构文档副本；所有产品决策、架构、验收标准、阶段划分均以飞书文档 v0.2 为唯一权威。

## 实现的技术架构（运行态）

大脑 = 本地 Hermes Agent API Server（`127.0.0.1:8642`，OpenAI 兼容，加载 counselor 等 skill + vault）。STT/TTS 只在端上做语音进出，大脑负责对话与检索。

**手机语音路径（3.3，主场景）：**
```
手机 PWA(web_client/)
  ⇅ WebRTC(音频 + 实时转写事件)
https://mac.tail844e3d.ts.net/ ── Tailscale Serve
  └→ web_server.js(:8050)   静态页 + /api/offer 反代 + /api/save 存库
       └→ orchestrator_webrtc.py(:7860)  SmallWebRTCTransport runner
            └→ Pipecat 管线：
                手机麦克风 → VAD(判停) → SenseVoiceSTT(本地中文, 整段转写)
                → Hermes 大脑(8642) —— 系统指令 = counselor_context.build()
                   (每场会话开始预注入: 人设 + 热层[过滤测试态] + 最近林老师会谈回顾)
                → EdgeTTSService(edge→ffmpeg→PCM, 流式首帧)
                → 手机扬声器(barge-in 可打断)
  会话结束 → /api/save → vault 咨询/来访者/我/会谈/YYYY-MM-DD-AI-访谈.md
```
**本机语音路径（3.1/3.2，平行）：** `orchestrator.py`（麦克风/扬声器本地音频）与手机路径共用同一套 STT/LLM/TTS/VAD 与 `counselor_context`。

**常驻（launchd，开机自启）：** `com.voicetherapy.webrtc.runner`(7860) / `com.voicetherapy.web.server`(8050)；Tailscale Serve 把根路径指到自定义页。

**关键设计取舍：**
- **预注入而非现场翻库**：语音是单次 chat completion，大脑若现场 agentic 读 vault 会卡死(80s+) → 开场由 `counselor_context` 拼好注入。
- **数据卫生**：`status:测试` 的占位不被当真实背景；原始音频仅内存处理，不落盘不入日志；真实咨询内容只存本地 vault。
- **延迟**：本地 ASR(SenseVoice) + 同 WiFi；P1/P2(TTS 流式首帧/轻 persona) 已在分支。

## 当前版本更新说明

见 **[CHANGELOG.md](CHANGELOG.md)** —— 过去 24 小时优化小结（手机语音打通、SenseVoice 换装、咨询大脑预注入 + 开场回顾 + 护栏、延迟优化、UI 打磨等）。

## 当前状态

文字轨道（Phase 0/1/2/4）与**语音轨道（Phase 3）均已打通并真机验证**。

- **Phase 0–4 已交付**：Obsidian `咨询/` 结构（`templates/`）、`counselor`/`session-notes`/`recall`/`weekly-insights` skill（见 `hermes-skills/`）
- **Phase 3.1/3.2 已验收**：本机实时语音环 + barge-in（打断 ~5ms）
- **Phase 3.3 手机语音已打通**：手机浏览器 WebRTC ↔ Mac Mini runner ↔ Hermes，对话 + 打断可用
- **随时能聊**：Mac Mini launchd 自启 runner + tailscale serve（URL 固定，免重扫）
- **识别**：本地 **SenseVoice**（sherpa-onnx，中文专用，带标点；比 whisper 更快更准）
- **咨询大脑**：开场预注入 `counselor_context`（人设 + 热层 + 最近林老师会谈回顾；过滤测试态占位；护栏：不因沉默退出、不擅自删改档案）
- **定制 PWA 客户端**：咨询师主题界面、计时器、实时转写+历史、暂停/退出、结束自动存 `AI-访谈` 到 vault

规划文档：`VoiceTherapy_2.0_开发计划.md`（原生 App + 免托管 AEC 路线）、`VoiceTherapy_响应延迟优化.md`（P1/P2 已完成于分支 `feat/latency-p1-p2`）。

## 仓库架构

按设计文档 §3.1 分层组织，**本仓库不含任何真实咨询内容**（那只存于本地 vault）。

```
VoiceTherapy/
├── README.md
├── VoiceTherapy_2.0_开发计划.md     # 2.0 原生 App 路线
├── VoiceTherapy_响应延迟优化.md     # 响应延迟分析与 P1-P4 路径
├── hermes-skills/                   # 【C层 Hermes】咨询 skill（counselor/session-notes/recall/weekly-insights）
├── templates/vault-structure/       # 【D层 vault】Obsidian 目录空模板
└── voice_orchestrator/              # 【B层 语音编排】本仓库软件本体
    ├── orchestrator.py              #   本机实时语音环(pipeline 入口)
    ├── orchestrator_webrtc.py       #   手机 WebRTC runner(bot) 入口
    ├── sensevoice_stt.py            #   本地中文 STT(sherpa-onnx SenseVoice，当前默认)
    ├── faster_whisper_stt.py        #   备选 STT(faster-whisper，中文弱，默认已换 SenseVoice)
    ├── edge_tts_service.py          #   中文 TTS(edge→ffmpeg→PCM；流式首帧)
    ├── counselor_context.py         #   咨询开场上下文组装器(预注入人设+热层+林老师回顾)
    ├── web_server.js                #   自定义页静态 + /api/offer 反代到 runner + /api/save 存库
    ├── web_client/                  #   定制咨询师 PWA(index/styles/main/manifest/icon)
    └── asr_models/                  #   (gitignore)SenseVoice onnx 模型，按需下载，不入库
```

**分界**：`hermes-skills/` = 大脑行为；`templates/` = 长期记忆骨架；`voice_orchestrator/` = 软件本体（`.venv/` 与 `asr_models/` 不入库）。

**本地常驻（launchd）**：`com.voicetherapy.webrtc.runner`（7860 runner）+ tailscale serve（手机访问）；`com.voicetherapy.web.server`（8050 自定义页）。Hermes 大脑跑在 `127.0.0.1:8642`。

## 核心原则

- Hermes 是唯一的咨询对话与工具编排核心，STT/TTS 只做语音输入输出。
- Obsidian 咨询知识库第一阶段只读、目录白名单、检索结果可追溯。
- 原始音频只在内存中处理，不写磁盘、不进入日志。
- 浏览器不持有 Hermes 或供应商密钥。
- 驾驶模式优先语音、打断和低交互，减少注意力分散。
- 真实咨询数据（会谈全文、档案等）只存在于本地 Obsidian vault，本仓库仅含结构模板与可复用代码，不纳入任何真实咨询内容。
