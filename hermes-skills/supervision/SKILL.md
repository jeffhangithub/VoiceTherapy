---
name: supervision
description: "咨询督导。当 Jeff 要给 AI 咨询师（counselor）做督导时触发：(A) 生成督导请求——把某场会谈逐字记录 + 督导指令整理成可粘贴给 ChatGPT 的 md；(B) 落地督导反馈——把 ChatGPT 返回的督导 md 解析成结构化建议，映射到 counselor 的『风格/结构/话术/思考结构』四类锚点，产出待 Jeff 确认的具体改动。不自动改行为。关键词：督导、supervision、咨询师督导、ChatGPT 督导、调整咨询师风格结构话术。"
version: 1.1.0
author: Jeff
---

# supervision — 咨询督导（AI 咨询师的外部督导闭环）

让 VoiceTherapy 的 AI 咨询师接受**外部督导**：把会谈逐字记录交给**另一个 AI（ChatGPT）**，取回督导意见，再把意见落到咨询师的人设/结构/话术/思考结构上。

**分工**：督导意见由 ChatGPT 出（Jeff 手动粘贴）；本 skill 负责**组请求**与**落地反馈**两端。**改行为一律先出拟定改动、经 Jeff 确认**（不自动生效）。

## 触发
- Jeff 说「做一次督导」「把这次会谈给 ChatGPT 督导」「落地督导反馈」「按督导意见调整咨询师」。
- 收到 Jeff 导入的 ChatGPT 督导 md 文件。

## 路径常量
```
VAULT   = <vault 根>（先认 VT_VAULT，否则默认 Jeff vault）
督导根   = <VAULT>/咨询/督导/
  请求_<YYYY-MM-DD>.md    ← 组给 ChatGPT 的督导请求
  反馈_<YYYY-MM-DD>.md    ← Jeff 从 ChatGPT 带回的督导反馈（人工放入）

会谈逐字记录（输入源）：
  <VAULT>/raw/ai-therapy/YYYY-MM-DD-AI-访谈.md    （AI 会谈，默认取最新）
  <VAULT>/raw/咨询纪要/YYYY-MM-DD_HHmm_<主题>.md   （林老师真人会谈逐字稿，可选）
```

## A. 生成督导请求
1. **选会谈**：默认取 `raw/ai-therapy/` 最新一场；Jeff 指定则用指定场（也可用林老师逐字稿）。
2. **读逐字记录**（含 `[HH:MM:SS]` 时间线与「我 / 咨询师」说话人）。
3. **组 `请求_<日期>.md`**，固定结构：
   - **角色**：你是资深心理咨询督导（整合取向：人本-存在 + 依恋 + 认知行为）。
   - **材料**：下面是一场 AI 咨询师与来访者的逐字记录（含时间线）。
   - **任务**：给出督导意见，**四维各给**：
     ① **风格/语气**（温度、长度、共情方式）
     ② **结构/流程**（开场→签到→聚焦→探索→工作→收束 的推进是否得当）
     ③ **话术**（具体句子：哪些好、哪些可换更贴的说法）
     ④ **思考结构/框架**（所用解释框架是否贴来访者、有无遗漏视角）
   - **每条格式**：观察 → 假设 → **具体可执行建议**。
   - **结尾**：指出「最该改的 3 个点」，按影响排序。
   - **固定声明**：非医疗、非危机干预；保护隐私（不写可识别第三方细节）。
4. 落 `咨询/督导/请求_<日期>.md`；把**全文**给 Jeff 去粘 ChatGPT。

## B. 落地督导反馈（核心）
> ⚠️ **本步必须用深度推理模型 `deepseek-v4-pro`（不是默认的 flash）**——分析督导、找改进、迭代人设需要深思考。执行方式：把「读反馈 md → 解析四维 → 映射锚点 → 起草拟定改动」作为一个自包含任务，交给一个**固定到 pro 的 Hermes 一次性进程**跑：
> ```
> hermes -z "<任务：读 <反馈md绝对路径>，按 supervision skill 的 B 步产出四维归类 + 逐条拟定改动(diff)>" -m deepseek-v4-pro --provider deepseek
> ```
> 把它返回的拟定改动拿回来核实，再给 Jeff 确认。（若当前会话本身已在 pro 上，可直接做。）

1. 读 Jeff 放入的 `咨询/督导/反馈_<日期>.md`（ChatGPT 输出）。
2. **解析**：按 ①②③④ 四维归类提取建议；识别「最该改的 3 点」。
3. **映射锚点**（哪类建议 → 改哪个文件）：
   | 督导维度 | 锚点 |
   |---|---|
   | 风格/语气 | `VoiceTherapy/voice_orchestrator/counselor_context.py` 的 `_PERSONA`（**运行时直接生效**）|
   | 结构/流程 | `~/.hermes/skills/counselor/SKILL.md`「状态机 S0-S7」|
   | 话术 | counselor skill「人设语言」+ 各 S 阶段示例 |
   | 思考结构/框架 | counselor skill 框架/工作节 + `_PERSONA` |
4. **产出拟定改动**：逐条给「文件 + 原文 → 建议改为」的 diff 形式，**等 Jeff 确认**（不直接改）。
5. 确认后 **apply**：**同时改部署版（`~/.hermes/skills/`）与仓库版（`VoiceTherapy/hermes-skills/`）**，保持一致；改 `counselor_context.py` 后**重启 runner** 才生效。

## 边界
- 督导意见是**输入**，不是命令：凡行为/人设改动，先出拟定改动、Jeff 确认后再动。
- **不改** `type:human` 记录（林老师会谈原文）。
- **隐私**：督导请求含逐字记录（敏感）→ 只存本地 vault `咨询/督导/`，**不入 GitHub 仓库**。

## Pitfalls
- **别把督导建议整段抄进人设**：先翻译成「本系统可执行的短规则」（如「少用排比/别复述对方」→ 进 `_PERSONA` 语气条），而非大段粘贴。
- **四类分清**：风格 vs 话术易混——**常驻语气**进 `_PERSONA`；**特定阶段的具体句子**进 skill 话术条目。
- **部署版 vs 仓库版**：counselor skill 有两份（`~/.hermes/skills/` 运行用 / `VoiceTherapy/hermes-skills/` 源），改一份**必同步**另一份。
- **`counselor_context.py` 改动需重启 runner** 才生效（`launchctl kickstart -k gui/$(id -u)/com.voicetherapy.webrtc.runner`）。
- **督导不替代真人督导/咨询**：这是 AI 咨询师的行为调优输入，不涉及 Jeff 本人的治疗判断。

## Version History
- 1.1.0 — B 步（落地督导分析）****强制用 `deepseek-v4-pro` 深度推理**（经 `hermes -z … -m deepseek-v4-pro --provider deepseek` 一次性进程），不再用默认 flash。
- 1.0.0 — 初始：A 组督导请求（四维）+ B 落地反馈（四维映射四锚点，先确认后改，双版本同步）。
