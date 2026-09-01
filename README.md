# VoiceTherapy

基于 Hermes Agent、Obsidian 个人知识库和实时语音服务的私人心理支持工具。

目标是在 iPhone 和车载蓝牙场景中提供低延迟、可打断的双向语音对话。Hermes 负责对话推理与知识检索；Mac mini 作为常驻服务端；原始音频不落盘，只按用户选择保存逐字稿和摘要。

> 本项目用于个人心理支持和自我反思，不替代持证心理咨询、医疗诊断或紧急服务。

## 当前状态

项目处于设计与技术基线阶段，尚未接入真实咨询记录或云端语音密钥。

- [总体架构与实施计划](docs/architecture-plan.md)
- [Hermes 集成契约](docs/hermes-integration-contract.md)
- [产品决策记录](docs/product-decisions.md)
- [语音服务选型分析](docs/voice-provider-options.md)

## 核心原则

- Hermes 是唯一的咨询对话与工具编排核心，STT/TTS 只做语音输入输出。
- Obsidian 咨询知识库第一阶段只读、目录白名单、检索结果可追溯。
- 原始音频只在内存中处理，不写磁盘、不进入日志。
- 浏览器不持有 Hermes 或供应商密钥。
- 驾驶模式优先语音、打断和低交互，减少注意力分散。
