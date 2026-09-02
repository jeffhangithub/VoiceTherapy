# VoiceTherapy

基于 Hermes Agent、Obsidian 个人知识库和实时语音服务的私人心理支持工具。

目标是在 iPhone 和车载蓝牙场景中提供低延迟、可打断的双向语音对话。Hermes 负责对话推理与知识检索；Mac mini 作为常驻服务端；原始音频不落盘，只按用户选择保存逐字稿和摘要。

> 本项目用于个人心理支持和自我反思，不替代持证心理咨询、医疗诊断或紧急服务。

## 权威设计文档

**设计以飞书文档 v0.2 为准**：

- [设计文档：本地 Hermes 心理咨询语音助手（Counselor Voice Agent）v0.2](https://my.feishu.cn/wiki/RUCJwUxq0iP1K5k6wuXc81K4nVb)
  （腾讯/飞书链接不可用时，以仓库内 `docs/` 或下方同步内容为准——飞书为唯一真相源）

本仓库不再维护独立的本地架构文档副本；所有产品决策、架构、验收标准、阶段划分均以飞书文档 v0.2 为唯一权威。

## 当前状态

项目处于设计与文字轨道（Phase 0+1+2）完成、语音轨道未启动的阶段。

- **Phase 0 已交付**：Obsidian `咨询/` 子系统目录结构 + 模板（见 `templates/vault-structure/`，含 `洞察/`）
- **Phase 1 已交付**：Hermes `counselor` 与 `session-notes` skill（见 `hermes-skills/`）
- **Phase 2 已交付**：Hermes `recall` skill（历史会谈检索，只读）
- **Phase 4 前置已交付**：Hermes `weekly-insights` skill（周洞察；实际运行需待会谈数据积累）
- **待接入**：真实咨询记录、语音编排轨道（Phase 3：VAD/ASR/TTS/barge-in/WebRTC）

## 仓库架构

按设计文档 §3.1 的四层组织，**本仓库不含任何真实咨询内容**（那只存于本地 vault）。

```
VoiceTherapy/
├── README.md                # 总览 + 权威设计文档(飞书 v0.2) + 当前状态
├── .gitignore               # 忽略 .venv/ 与真实咨询数据
├── hermes-skills/           # 【C层 Hermes】咨询系统 skill（大脑"会什么"）
│   ├── counselor/           #   S0–S7 对话引擎、driving/desk、危机边界
│   ├── session-notes/       #   会谈写回（新建AI会谈、更新热层）
│   ├── recall/              #   历史检索（只读，带日期引用）
│   └── weekly-insights/     #   周洞察（→ 洞察/YYYY-Wxx.md）
├── templates/vault-structure/  # 【D层 vault】Obsidian 目录空模板（镜像 咨询/）
│   ├── _系统/               #   咨询师人设 / 边界与危机 / 会谈流程
│   ├── 来访者/我/           #   档案 / 工作同盟 / 人物关系 / 模式 / 有效干预 / 未完成 + 会谈模板
│   ├── 主题/                #   议题→会谈反向索引
│   └── 洞察/                #   周洞察落盘处
└── voice_orchestrator/      # 【B层 语音编排】本仓库真正可执行的代码
    ├── hermes_brain.py      #   大脑客户端 → 本地 Hermes 8642（OpenAI兼容, stream, 会话连续性）
    ├── faster_whisper_stt.py #  自定义本地中文 STT（Pipecat service）
    ├── edge_tts_service.py  #  自定义中文 TTS（edge→ffmpeg→PCM）
    └── orchestrator.py      #  Pipecat pipeline（已在本机活测：STT→Hermes→edge女声→扬声器 + 打断 均通）
```

**分界**：`hermes-skills/` = 大脑行为（skill）；`templates/vault-structure/` = 长期记忆的骨架；`voice_orchestrator/` = 本项目的软件本体。`.venv/` 为本地运行依赖，不入库。

## 核心原则

- Hermes 是唯一的咨询对话与工具编排核心，STT/TTS 只做语音输入输出。
- Obsidian 咨询知识库第一阶段只读、目录白名单、检索结果可追溯。
- 原始音频只在内存中处理，不写磁盘、不进入日志。
- 浏览器不持有 Hermes 或供应商密钥。
- 驾驶模式优先语音、打断和低交互，减少注意力分散。
- 真实咨询数据（会谈全文、档案等）只存在于本地 Obsidian vault，本仓库仅含结构模板与可复用代码，不纳入任何真实咨询内容。
