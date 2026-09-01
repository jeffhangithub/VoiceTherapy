# 语音服务选型分析

更新日期：2026-09-01

## 比较口径

以下估算统一假设一次会谈持续 60 分钟，其中用户实际说话 25 分钟，AI 输出约 6,000 个中文字符。Voice Gateway 通过 VAD 去掉大部分静音后再发送给 STT。

估算不含 Hermes 使用的语言模型费用、网络流量、电费、税费或供应商套餐折扣。“模型延迟”也不等于端到端延迟；真实体感还包括手机网络、Hermes 首 token、音频缓冲和车载蓝牙播放。供应商会调整型号和价格，上线前以控制台开通的 SKU 为准。

## 单项比较

| 服务 | 估算成本/会谈 | 中文与车载适配 | 速度 | 音色/表达 | 主要取舍 |
|---|---:|---|---|---|---|
| 火山引擎豆包 ASR 2.0 | 约 ¥0.42–¥1.88 | 中文优先；支持热词、上下文、快速结果+优化终稿、语义断句 | 适合实时流式；最终体感需实车测量 | 不适用 | 官方页面中的 2.0/SKU 价格为 ¥1/小时到 ¥4.5/小时，需按开通项确认 |
| Deepgram Nova-3 | $0.12；加关键词约 $0.15 | 官方列出简体中文与普通话；支持噪声/远场和关键词 | 成熟的流式 API | 不适用 | 中文心理咨询专有词与车内噪声仍需和豆包盲测；中文不能使用 Flux 原生轮次模型 |
| ElevenLabs Scribe Realtime | 约 $0.16；加关键词约 $0.18 | 覆盖 90+ 语言 | 官方标称约 150ms | 不适用 | 全球化接口简单，但中文车载准确率需实测 |
| 火山引擎豆包 TTS 2.0 | 约 ¥3.00 | 中文音库、情绪和韵律控制完整 | 单向大模型流式首包官方约 600ms；V3 双向流式可降低感知等待，但未给统一数字 | 自然，支持多种情绪 | 中文一体化最好；公开延迟指标不如部分海外厂商激进 |
| MiniMax Speech 2.8 Turbo | $0.36 | 中文与亚洲语言是重点方向，支持情绪、语速和音调 | 官方合作案例宣称端到端低于 250ms，仍需自测 | 温暖、细腻、呼吸和停顿自然 | 很适合咨询师音色候选；需增加第二家云服务与隐私审查 |
| ElevenLabs Flash v2.5 | $0.30 | 支持中文 | 模型推理官方约 75ms；东北亚 WebSocket TTFB 约 250–350ms | 音库多，速度优先 | 快；对中文自然度与稳定感需盲听 |
| ElevenLabs v3 Conversational | $0.30 | 支持 70+ 语言 | 官方约 280ms | 比 Flash 更富表达力 | 更像真人，但情绪过强不一定适合心理咨询，需要限制风格 |
| 本地 STT/TTS | 直接 API 成本为 0 | 可完全离线并定制词表 | 取决于 16GB Mac mini 的模型和量化；必须跑基准 | 系统音色通常不如专业云 TTS | 隐私最佳，作为断网和云服务故障的备用路径更合适 |

## 可直接选择的组合

### A. 中文一体化

- STT：火山引擎豆包 ASR 2.0。
- TTS：火山引擎豆包 TTS 2.0，V3 双向流式。
- 估算：约 ¥3.42–¥4.88/会谈。
- 优点：一个供应商；中文热词、上下文和音色控制完整；工程集成简单。
- 缺点：TTS 公开延迟指标偏保守；需要在真实网络下确认是否足够敏捷。

### B. 中文识别 + 温暖音色（首选原型）

- STT：火山引擎豆包 ASR 2.0。
- TTS：MiniMax Speech 2.8 Turbo。
- 估算：约 ¥0.42–¥1.88 + $0.36/会谈。
- 优点：保留中文识别优势，同时获得更自然、温暖、低压迫感的咨询师音色。
- 缺点：要管理两个账户和两套密钥；语音文本会经过两家服务，需要分别完成数据留存审查。

### C. 接口简单 + 速度优先

- STT：ElevenLabs Scribe Realtime。
- TTS：ElevenLabs Flash v2.5；需要更多情绪时切换 v3 Conversational。
- 估算：带关键词约 $0.48/会谈。
- 优点：一个供应商；STT/TTS 都有明确的低延迟产品；音色选择非常多。
- 缺点：中文车载准确度和跨区域网络延迟必须实测；Flash 的中文咨询音色未必最自然。

### D. 隐私优先

- STT：Mac mini 本地 Whisper 系列模型。
- TTS：本地系统音色或本地 TTS。
- 估算：直接 API 成本为 0。
- 优点：音频与文本不离开 Mac mini；断网仍能使用局域网部分能力。
- 缺点：16GB 主机上要同时运行 Hermes、检索和语音模型，识别延迟、车噪准确率和音色都可能弱于云服务。

## 推荐

原型第一轮采用 **B 作为主方案，D 作为隐私/故障基线**：

1. 豆包 ASR 2.0 使用快速+优化双结果、咨询专有热词、对话上下文和语义断句。
2. MiniMax Speech 2.8 Turbo 先试听三种非克隆音色：温暖女性、沉稳男性、中性陪伴感。
3. 同一组车内录音片段离线回放给豆包、Deepgram Nova-3 和本地 Whisper，比较字符错误率、专有词错误率、断句等待和第一条可用结果延迟。
4. TTS 用相同咨询文本比较 MiniMax、豆包双向流式和 ElevenLabs Flash/v3，测首个可播放音频、整句完成时间以及盲听偏好。
5. 原型阶段不克隆真实咨询师音色。除非取得明确授权，否则克隆可能造成身份混淆和依赖感。

最终选择不只看“最像真人”。心理咨询场景更适合温暖、稳定、低唤醒、不过度表演的声音：语速建议从 0.92–1.0 倍开始，停顿清晰，避免夸张耳语、喘息和情绪渲染。

## 验收指标

- 车内普通话首个稳定转写片段：目标中位数不超过 500ms。
- 用户说完到 Hermes 开始处理：目标中位数不超过 800ms。
- Hermes 产生首段回复到扬声器开始播放：目标中位数不超过 500ms。
- 简短回复的说完到听见声音：端到端目标中位数 1.5–2.2 秒。
- 用户打断时，本地立即静音：目标不超过 400ms；后端同时停止当前 Hermes run 和 TTS 流。
- 专有词命中率、车噪字符错误率和盲听偏好在同一测试集上记录，不能只凭官方宣传选择。

## 官方资料

- [火山引擎语音技术产品与套餐](https://www.volcengine.com/products/Audio-editing-and-sound-processing)
- [火山方舟价格](https://www.volcengine.com/product/ark)
- [豆包流式语音识别 2.0 配置](https://www.volcengine.com/docs/6348/1807452?lang=zh)
- [豆包 TTS 2.0 能力与延迟](https://www.volcengine.com/docs/6561/1257543?lang=zh)
- [豆包 TTS V3 双向流式接口](https://www.volcengine.com/docs/6561/2228192?lang=zh)
- [Deepgram 定价](https://deepgram.com/pricing)
- [Deepgram 模型与语言](https://developers.deepgram.com/docs/models-languages-overview/)
- [ElevenLabs API 定价](https://elevenlabs.io/pricing/api)
- [ElevenLabs 延迟说明](https://elevenlabs.io/docs/eleven-api/concepts/latency)
- [ElevenLabs TTS 模型](https://elevenlabs.io/docs/speech-synthesis/p)
- [MiniMax 按量价格](https://platform.minimax.io/docs/guides/pricing-paygo)
- [MiniMax Speech 2.8](https://www.minimax.io/news/minimax-speech-28)
- [MiniMax WebSocket TTS](https://platform.minimax.io/docs/api-reference/speech-t2a-websocket)
