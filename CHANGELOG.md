# Changelog

> VoiceTherapy 迭代优化小结（倒序，最新在上）。

## v1.9.10（2026-09-11）语音轨结构预注入（修「语音场无结构」）

- **发现**：语音轨走「单次 completion」，**不加载 counselor skill** → 此前语音场只拿到 `_PERSONA` + 热层 + 回顾，**S0-S7 状态机从未生效**（这解释了督导"没有共同目标／结构推进不当"的批评：不是没执行好，是结构根本没上场）。
- **修（方案 C）**：`counselor` skill 新增「## 语音轨骨架（S0–S5 精简 + 安全）」节（**单一真源**）；`counselor_context.build()` **预注入该节**（读不到则回退内置兜底常量）。语音轨从此**无条件有流程**，**不用匹配任何触发话**。
- 变更：`counselor/SKILL.md`（v1.5.0）、`voice_orchestrator/counselor_context.py`。
- 本轮分析（根因/谄媚/实测/方案取舍）见 `VoiceTherapy_咨询师调优分析.md`（抽象化，不含真实咨询内容）。

## v1.9.9（2026-09-11）督导落地：咨询师结构/话术/思考结构迭代

据 **deepseek-v4-pro** 对 2026-09-10 会谈督导意见的落地分析（`咨询/督导/`），改：

- **`counselor_context._PERSONA`**（运行时生效）：语气条加「少说『你真正的意思是…』，多做『让我确认我有没有理解你』」；新增护栏：
  **⑤** 不替第三方定动机 ｜ **⑥** 不把「控制不了对方」扩成「只能等/没出路」 ｜ **⑦** 被纠正先确认、不立刻抛新解释 ｜ **⑧** 判断前分三层（事实／他的解释／你的假设）｜ **⑨** 家庭·儿童安全评估（优先级仅次 S7）｜ **⑩** 不评价药物/医疗方案。
- **`counselor` skill**（部署版 + 仓库版）：总规则加安全评估；S0 回顾缩短 + 「过度确定/只能等」的开场修复句；S2 共同确定本次目标；S3 一次一焦点不连珠追问；S4 三层区分 + 控制/影响区分；S5 承接收尾不封死；人设语言加「少说/多做」；「你永远不做的事」加不评价药物、不病理化第三方。
- 来源：`咨询/督导/2026-09-10-AI访谈-督导意见.md`（ChatGPT）→ `咨询/督导/拟定改动_2026-09-10.md`（pro 落地）。

## v1.9.8（2026-09-11）咨询督导功能（AI 咨询师外部督导闭环）

- **新 skill `supervision`**（部署版 + 仓库版）：把会谈逐字记录交给**另一个 AI（ChatGPT）**取督导意见，再落地到咨询师。
  - **A 生成督导请求**：读某场会谈逐字记录 → 组「四维（风格/结构/话术/思考结构）+ 观察→假设→建议」的请求 md，供 Jeff 粘贴给 ChatGPT。
  - **B 落地反馈**：解析 ChatGPT 督导 md → 四类映射锚点（风格→`counselor_context._PERSONA`；结构→counselor skill 状态机；话术→skill 人设语言；思考结构→框架）→ 出**拟定改动**待确认 → 双版本同步。
- **半自动**：Jeff 手动在 ChatGPT 获取督导、存 md 导入（无 OpenAI key，不走 API）。
- **B 步强制深推理**：落地督导分析**用 `deepseek-v4-pro`**（非默认 flash）——经 `hermes -z "<任务>" -m deepseek-v4-pro --provider deepseek` 一次性进程跑，深思考后出拟定改动。
- **落点**：vault `咨询/督导/`（`请求_*.md` / `反馈_*.md` / README）；逐字记录敏感，**不入仓库**。

## v1.9.7（2026-09-11）咨询师表达风格调简练

- `counselor_context` 人设：回复风格由「适中 3~6 句」改为**简练——通常 2~3 句、一次只说一个要点、直击核心**；不啰嗦、不堆排比、**不复述 Jeff 刚说过的话**，宁可短。
- counselor skill（部署版 + 仓库版）：driving 单条回复 **≤3 句**；「人设语言」条同步。

## v1.9.6（2026-09-11）非语音过滤调优（实测两段后）

- **实测结论**：VAD **未过度收紧**——真实说话全部正常触发（VAD 开始 = 转写次数），两段测试仅丢 1 条纯叹词 `嗯。`。
- **A（防误删真实应答）**：单个 `嗯/对/好/是/行` 保留；只丢**重复叹词**（嗯嗯/呃呃/对对）与**非应答语气词**（呃/唔/欸）。
- **B（清短噪声）**：`<0.7s` 却转出 ≥3 字、或含 **≥3 连续拉丁字母**（如 `contacttact还行。`）→ 丢弃。
- 变更：`sensevoice_stt.py`。

## v1.9.5（2026-09-11）非语音/呼吸误识别治理

- **症状**：咨询中呼吸、语气叹词被 SenseVoice 误转成乱字符/凭空汉字，混进对话。
- **① VAD 收紧**（`orchestrator.py` + `orchestrator_webrtc.py`）：`confidence 0.5→0.6`、`start_secs 0.2→0.35`（需 ~350ms 连续语音才开一回合）、`min_volume 0.3→0.5`（挡低声呼吸）——从源头减少对呼吸/杂音的触发。
- **② SenseVoice 输出过滤**（`sensevoice_stt._clean_transcript`）：剥掉 SenseVoice 标签；命中 `nospeech/Laughter/BGM/Cough…` 等**非语音事件标签**即整段丢弃；**纯叹词/语气词**（嗯/呃/啊…，去标点后仅剩填充字）丢弃；正常短回复（好/对/嗯对）与正文保留。
- 变更：`sensevoice_stt.py` / `orchestrator.py` / `orchestrator_webrtc.py`。

## v1.9.4（2026-09-11）会话卫生：VoiceTherapy 会话不再堆积在 `/sessions`

- **背景**：Hermes 的 `/sessions` 默认只隐藏 `subagent/tool`，`api_server`（VoiceTherapy）会话只要未归档就会出现在列表里，长期堆积。
- **本次**：清理历史遗留孤儿会话（1 条早于 counselor 预注入的 OPEN 会话，指纹对不上未被自动归档）+ 把已结束的 VoiceTherapy 会话置 `archived=1`，使其从 `/sessions` 消失（飞书等其他渠道会话分毫未动）。
- **⚠️ 待办（未做）**：Hermes 的 `PATCH /api/sessions/{id}` 只接受 `title/end_reason`，**不支持 `archived`** → 自动归档（`hermes_session.end_session`）目前只置 `ended_at`，新会话仍会出现在 `/sessions`。要一劳永逸需在结束时直写 `state.db` 置 `archived=1`（简单可逆，待定）。

## v1.9.3（2026-09-11）长会谈卡顿与断句修复 + 逐字记录时间线

- **背景**：53 分钟会谈到 ~50min 时明显卡顿、反馈句子出现"半段"。日志定位两个独立真因。
- **① 卡顿 = 上下文暴涨**：全程 `prompt tokens` 涨到 36k+，LLM `TTFAT` 尾段升到 3.8–5.1s。修复：开启 pipecat **上下文自动摘要**（`LLMAssistantAggregatorParams(enable_auto_context_summarization=True, max_context_tokens=12000, max_unsummarized_messages=40)`），较早对话自动压缩成摘要，绑住 prompt 规模。改 `orchestrator.py` + `orchestrator_webrtc.py`。
- **② 半段 = edge-tts 间歇空音频**：末段 20:47–20:53 出现 8+ 次 `No audio was received`，每次丢一句。修复：`edge_tts_service.py` `_synth_to_pcm` 加**最多 3 次重试**（0.3/0.6s 退避），仍空则静默跳过该句、不抛错中断管线。
- **③ 逐字记录时间线（北京时间）**：`web_client/main.js` 每句气泡记 `ts`；`web_server.js` 落盘时按 **UTC+8** 给每句加 `[HH:MM:SS]` 前缀（`bj()`，不依赖 Mac Mini 本机时区），表头标"（北京时间）"。
- 变更：`edge_tts_service.py` / `orchestrator.py` / `orchestrator_webrtc.py` / `web_client/main.js` / `web_server.js`。

## v1.9.2（2026-09-03）分层证据：可下钻到原始逐字稿

- **背景**：App 之前只能到"咨询纪要/整理层"（L1/L2），够不到 `raw/咨询纪要/` 里的**原始录音逐字稿**（L3，说话人+时间戳+飞书妙记链接），缺"原始证据"。
- **文字轨道**：`recall` skill 升 **v1.1.0**——路径常量纳入原始证据根；新增"分层证据"节：L2 不足时按需下钻 L3 逐字稿取原话/时间线证据，引用必带 **日期+说话人+时间戳**（+feishu_url），并对转写误差如实标注。
- **语音轨道**：新增 `evidence_retrieval.py`——本地检索 L3 逐字稿（按标题/关键词选场、按说话人段落选块，返回可追溯证据块）；`EvidenceInjector` Pipecat 处理器插入 `user_aggregator → llm` 之间：识别"要原话/证据"意图 → 检索 → 作为 system 消息注入 → 大脑据此回应（纯附加、旁路、不阻塞；检索不到不注入）。
- 变更：`evidence_retrieval.py`(新) / `orchestrator.py` / `orchestrator_webrtc.py` / recall skill(v1.1.0)。

## v1.9.1（2026-09-03）Hermes 会话生命周期修复

- **背景**：VoiceTherapy 经 `/v1/chat/completions`(不带 `X-Hermes-Session-Id`) 调 Hermes。api_server 用 `sha256(system_prompt + 首条用户消息)` 指纹把整场归到一条 session（非每请求泄漏），但这些 stateless 会话**从不置 `ended_at`** → 孤儿累积。
- **自动归档**：新增 `hermes_session.py`，会话结束(手机断开)时复刻同一指纹 session_id 并 `PATCH /api/sessions/{id}` 置 `ended_at`。复刻 id 经实测**逐字命中** Hermes 的 `X-Hermes-Session-Id`；纯附加、不动转写管线，指纹失配仅 404 无副作用。
- **一次性清理**：将此前遗留的 **35 条** VoiceTherapy `api_server` 孤儿会话全部归档(仅填 `ended_at`，不删行)；飞书(feishu)等其它 source 会话**零触碰**（结构上按 `source='api_server'` 过滤，天然隔离）。
- 变更：`hermes_session.py`(新) / `orchestrator.py` / `orchestrator_webrtc.py` / `CHANGELOG.md`。

## v1.9.0（2026-09-03）语音轨道全通 + 咨询大脑实装

### 🎙️ 手机语音（Phase 3.3）打通可用
- **WebRTC 手机路径**：手机浏览器 ↔ Mac Mini runner(7860) ↔ Hermes 大脑(8642)，对话 + barge-in 真机验证可用。
- **常驻免重扫**：Mac Mini `launchd` 自启 runner + Tailscale Serve（URL 永久固定，首次加主屏幕成 PWA 图标即可）。
- **定制咨询师 PWA**（`web_client/` + `web_server.js`）：咨询师主题界面、计时器、实时转写 + 历史气泡、开始/暂停/结束。
- **结束自动存库**：`/api/save` 在会话结束把逐字稿写成 vault `咨询/来访者/我/会谈/YYYY-MM-DD-AI-访谈.md`。（后按方案B迁至 `raw/ai-therapy/`，见 v1.9.2/迁移单）
- **UI 打磨**：对话改成微信式**逐句气泡**（每条 bot 回复独立成泡，不再堆成大段）；开始/结束按钮**固定底部**不随文字被顶走；通话中自动压缩问候区给对话让位。

### 🔊 语音识别（ASR）持续升级
- `faster-whisper`：`base → small`（+beam 5），并加中文 `initial_prompt` 语境提示。
- 实测延迟（M4）：`small` 1.4s / `medium` 3.9s（同一 6.5s 中文样本）。
- **换 SenseVoice**（sherpa-onnx，`sensevoice_stt.py`）：中文专用、带标点、**又准又快**——同一样本 **0.6s**，明显优于 whisper。faster-whisper 留作备选。

### 🧠 咨询大脑（本轮核心）
- **开场预注入方案 A**（`counselor_context.py`）：语音走单次 chat completion，无法现场 agentic 翻库（曾卡死 80s+）→ 改为**每场会话开始时**拼好 `人设 + 热层 + 最近林老师会谈回顾` 一起注入，大脑只负责说话。实测首响 ~3s。
- **按会话组装**：上下文移到 `build_llm()`（每场连接组装），而非守护进程启动时——避免"开场回顾"在开机瞬间被消耗、会话里却见不到。
- **开场回顾**：第一段回应 = 问候 → 回顾最近一场林老师会谈（事件驱动，`last_recapped` 防重复）。
- **测试数据不再冒充真实**：预注入过滤 `status:测试/验证` 的热层占位（9/2 验证场曾把假钩子当 Jeff 真事开场，致困惑）。
- **护栏**：① 不因 Jeff 沉默/停顿思考就结束会话（留白正常）；② 不因一次可能听错的语音指令就删改 vault 档案；③ 回顾/钩子一律按"假设待确认"处理。
- **语气校准**：啰嗦 → 过度简短 → 适中（3~6 句，能稍展开但不高篇）。

### ⚡ 响应延迟（分支 `feat/latency-p1-p2`）
- 真实日志量化：停→首声 ~4–5s（ASR 0.9–2.9 / LLM 0.75–2.3 / TTS 1.1–1.4s）。
- P1：轻 persona + 极短首句；P2：edge-TTS **流式首帧**（帧 100ms→20ms，首帧 ~1s）。
- 文档：《VoiceTherapy_响应延迟优化.md》《VoiceTherapy_2.0_开发计划.md》并入 main。

### 🐛 测试中修掉的真实 bug
- 停顿后"退出"→ 定位为**客户端连接断开**（非 AI 决定结束），加护栏 + 提示排查手机连接。
- 所有 bot 回复拼进同一气泡 → 改为每用户回合重置气泡。

### 🧹 工程与数据卫生
- `asr_models/` 不入库（1GB 模型按需下载）。
- vault 冒烟残留即时清理；测试产物标 `status:测试` 且不再被预注入。
