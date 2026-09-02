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

项目处于设计与 Phase 0+1（本机可验证的文字 MVP）阶段。

- **Phase 0 已交付**：Obsidian `咨询/` 子系统目录结构 + 模板（见 `templates/vault-structure/`）
- **Phase 1 已交付**：Hermes `counselor` 与 `session-notes` skill（见 `hermes-skills/`）
- 尚未接入真实咨询记录或云端语音密钥

## 核心原则

- Hermes 是唯一的咨询对话与工具编排核心，STT/TTS 只做语音输入输出。
- Obsidian 咨询知识库第一阶段只读、目录白名单、检索结果可追溯。
- 原始音频只在内存中处理，不写磁盘、不进入日志。
- 浏览器不持有 Hermes 或供应商密钥。
- 驾驶模式优先语音、打断和低交互，减少注意力分散。
- 真实咨询数据（会谈全文、档案等）只存在于本地 Obsidian vault，本仓库仅含结构模板与可复用代码，不纳入任何真实咨询内容。
