# VoiceTherapy 咨询师调优：督导闭环 + 语音轨结构预注入（2026-09-11）

> 一次外部督导触发的一轮迭代：根因分析 → 实测 → 改动。**本文只记方法与结论，不含任何真实咨询内容**（逐字记录、督导原文均只在本地 vault `咨询/督导/`，不入库）。

## 0. 缘起
外部督导（由 ChatGPT 出意见，见 `supervision` skill）指出 AI 咨询师的问题：**解释快于澄清、替第三方定动机、未形成共同工作目标、缺家庭/儿童安全评估、把猜测当事实**。本轮回答两个问题：**为什么会这样？改哪里？**

## 1. 关键发现：语音轨**不加载 skill → 结构从未生效**
- 语音轨走「**单次 chat completion**」（无 agent 工具循环）→ **不加载 counselor skill**。
- `counselor_context.build()` 只预注入三样：`_PERSONA`（人设+边界+护栏+语气+开场规则）+ 热层（工作同盟/未完成/档案）+ 林老师开场回顾。
- **skill 的 S0-S7 状态机、mode 表、上下文瘦身规则、写回交棒——语音场全都没生效。**
- ⇒ 督导批的"没有共同工作目标／结构推进不当"，**不是"skill 执行得不好"，而是"结构根本没上场"**：AI 靠一段人设自由发挥。（skill 的"触发词"只对文字轨那种真 agent 会话有效。）

## 2. LLM 为什么这样：谄媚 + 助理本能
- **谄媚（sycophancy）是 RLHF 的普遍行为**，非某模型特有：*Sharma et al., "Towards Understanding Sycophancy in Language Models", arXiv:2310.13548（ICLR 2024）*——5 个 SOTA 助手普遍如此，根因是**人类偏好数据偏爱"顺着用户"的回答**；形式化放大机制见 *arXiv:2602.01002*；综述见 *arXiv:2411.15287*。
- 叠加**"总要有用、要给个解释"的 helpfulness 偏向** → 解释密度高、澄清不足。
- ⇒ 咨询师的两个失效模式（顺着来访者叙事加戏／把猜测升级为事实／过早给解释）与这两点吻合。

## 3. 实测：flash vs pro，以及 system prompt 的作用
**方法**：同一场真实会谈、同一节点，两种 system prompt（完整人设 vs 最小提示）× 两个模型（flash / pro），生成"下一条咨询师回应"；严格版 temp=0、6 节点、24 组。

**结论**：
- **system prompt 是最强变量**：同一模型，最小提示→完整人设，回复长度/解释密度近乎腰斩（≈180→≈100 字）。**护栏的作用 >> 换模型。**
- **pro 更主动做"安全评估"**（唯一稳健的模型差异）；**约束弱时 flash 更爱"给解释/贴人格标签"**。
- **"替第三方定动机"两者都犯** ⇒ **光靠 system prompt 压不死谄媚/臆断**，只能降频。

## 4. 方案取舍：结构怎么补
- "让语音 session 默认触发 skill"——**做不到**：skill 要由 agent 工具循环"加载"才生效，语音轨没有循环；要触发就得变回 agentic（正是此前卡死 ~80s 的路）。
- A（关键词强制问安全）→ 太教条、显得"大惊小怪"；B（输出格式分栏）→ 啰嗦稚嫩；C（说话前内省改写）→ 每次多一次 LLM 往返、延迟翻倍，与实时语音冲突。**A/B/C 均否决。**
- **采用**：把 skill 的 S0–S5 **精简骨架**写成 skill 里一个**专门小节**（**单一真源**），由 `build()` **预注入**（读不到则回退内置兜底）。⇒ 语音轨**无条件有流程**，**不用匹配任何触发话**。

## 5. 本轮改动
| 版本 | 改动 |
|---|---|
| v1.9.8 | 新增 `supervision` skill：督导闭环（生成 ChatGPT 督导请求 / 落地督导反馈，落地用 deepseek-v4-pro 深推理） |
| v1.9.9 | 督导落地：`_PERSONA` 加护栏⑤–⑩（不替第三方定动机／不把"控制不了对方"说成"只能等"／被纠正先确认／判断前分三层／安全评估／不评价药物）；counselor skill 各阶段加约束 |
| v1.9.10 | **语音轨结构预注入**：counselor skill 新增「语音轨骨架（S0–S5 精简 + 安全）」节（单一真源），`counselor_context.build()` 预注入 + 兜底 |

## 参考
- Sharma et al. *Towards Understanding Sycophancy in Language Models*. arXiv:2310.13548（ICLR 2024）
- *Sycophancy in Large Language Models: Causes and Mitigations*. arXiv:2411.15287
- *How RLHF Amplifies Sycophancy*. arXiv:2602.01002
