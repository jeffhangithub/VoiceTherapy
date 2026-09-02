---
name: session-notes
description: "心理咨询会谈写回。当 Jeff 结束一次 AI 会谈（说「先这样」「结束」「我到了」，或收到 session.end 信号）时触发：新建 AI 会谈笔记 会谈/YYYY-MM-DD-AI-<标签>.md、覆盖更新 未完成.md、六槽有变化才更新 档案.md（注明日期）、新人物追加 人物与关系.md、有效技术追加 有效干预.md。所有写操作必须限定在 <vault>/咨询/ 内（含路径安全校验），永不修改 type:human 文件正文。"
version: 1.0.0
author: Jeff
---

# session-notes — 心理咨询会谈写回

在每次 AI 心理咨询会谈结束时，把本次会谈的收获写回 vault 的「咨询」子系统。这是《本地 Hermes 心理咨询语音助手》Phase 1 的核心交付。

## 什么时候使用（触发）

- Jeff 说「先这样」「结束」「我到了」等结束语
- 收到 `session.end` 信号
- 一轮 AI 会谈自然收束，需要落盘记录时

不触发的情形：非咨询对话、日常闲聊、还没到会谈结束。

## 路径常量

```text
VAULT = /Users/ironsoul/Library/Mobile Documents/iCloud~md~obsidian/Documents/Vaults/Jeff
咨询根 = <VAULT>/咨询/

来访者/我/会谈/           ← AI 单次会谈笔记（本 skill 新建）
来访者/我/未完成.md       ← 每节结束覆盖更新
来访者/我/档案.md         ← 六槽档案（有变化才更新，注明日期）
来访者/我/人物与关系.md   ← 新人物会后追加
来访者/我/模式.md         ← 周/会后轻量更新（本 skill 只做轻量，不覆盖）
来访者/我/有效干预.md     ← 有效技术会后追加
```

首次运行若 `咨询/` 目录不存在，先创建它（含 `来访者/我/会谈/` 子目录）。所有写操作只发生在 `咨询/` 内部。

## 安全路径校验（每次写操作前必须做）

这是**最高优先级**的硬约束，任何写操作前都要校验：

1. **限定在 `咨询/` 内**：任何待写入/待编辑的路径，都必须满足
   `真实路径(目标) == 真实路径(<VAULT>/咨询/) 或其子路径`。用 `realpath` / 绝对路径前缀判断，禁止 `../`、符号链接越界、以及任何落到 `咨询/` 之外的目标。
2. **绝不碰 type:human 文件**：写回只针对 AI 会谈笔记（`type: AI`）和本系统自己维护的汇总文件（档案.md / 未完成.md / 人物与关系.md / 模式.md / 有效干预.md）。凡是 frontmatter 里有 `type: human` 的文件（如 `raw/咨询纪要/` 下的逐字稿、林老师会谈记录），**只读不写，正文一字不改**。
3. **校验顺序**：先 `read_file` 读取目标文件头部 frontmatter，确认其 `type` 字段；再决定是否写入。对不确定类型的文件，默认不写。

Python 校验示例（可复制到脚本里用）：

```python
import os

VAULT = "/Users/ironsoul/Library/Mobile Documents/iCloud~md~obsidian/Documents/Vaults/Jeff"
CONSULT = os.path.join(VAULT, "咨询")

def safe_target(path: str) -> bool:
    """目标必须落在 <VAULT>/咨询/ 内，且不是 type:human 文件。"""
    real_vault = os.path.realpath(VAULT)
    real_consult = os.path.realpath(CONSULT)
    real_target = os.path.realpath(path)
    # 1) 必须位于 咨询/ 之下（含 咨询/ 本身）
    if not (real_target == real_consult or real_target.startswith(real_consult + os.sep)):
        return False
    return True
```

调用时：先 `safe_target(目标路径)` 返回 True 才写；返回 False 立即中止并报告。

## 写回工作流（按顺序执行）

### 第 1 步：新建 AI 会谈笔记

在 `咨询/来访者/我/会谈/` 下新建 `YYYY-MM-DD-AI-<标签>.md`，`<标签>` 用本次会谈的一句话主题（英文/拼音或简短中文，无空格无特殊字符）。用下方「AI 会谈模板」填充，`mode` 填 `driving`（开车口述）或 `desk`（桌面打字），`focus` 填本次焦点。

### 第 2 步：覆盖更新 未完成.md

用下方「未完成模板」整体覆盖 `未完成.md`，内容取自本次会谈结束时最新的「钩子 / 待观察 / 不要做」。

### 第 3 步：条件更新（有变化才写）

- **六槽**：本次会谈导致「档案六槽」任一槽发生变化，才更新 `档案.md` 对应槽位，并在该槽下注明日期 `(YYYY-MM-DD)`。没变化就不动档案.md。
- **新人物**：出现之前档案里没有的人物，才在 `人物与关系.md` 追加一条。
- **有效技术**：本次用到了有效干预/技术，才在 `有效干预.md` 追加一条（注明来源日期）。
- **模式.md**：仅做轻量追加（如有明显新浮现的模式），不整体覆盖。

### 第 4 步：永不修改 type:human 文件

上面的所有步骤都不触碰 `type: human` 文件。写回只针对 AI 会谈笔记与本系统维护的汇总文件。

## AI 会谈模板（新建时填充）

```markdown
---
date: {{date}}
type: AI
mode: {{driving|desk}}
focus: {{focus}}
mood_start: {{}}
mood_end: {{}}
techniques: []
crisis: false
---
# {{date}} AI {{mode}}
## 今日一件事
…
## 探索要点
…
## 工作（如有）
- 命名的模式：
- 尝试的句子/实验：
## Takeaway（≤3）
1.
2.
3.
## 写回
- 档案变动：
- 下次钩子：
```

## 未完成模板（每节结束覆盖）

```markdown
# 未完成
- 钩子：
- 待观察：
- 不要做：
```

## 档案六槽（档案.md 的六个栏目）

1. 反复情绪
2. 触发情境
3. 关系模式
4. 核心信念
5. 有效干预
6. 未完成议题

只有这六槽之一发生变化时，才更新 `档案.md` 对应槽，并在条目后注明 `(YYYY-MM-DD)`。不要为「没变化」制造更新。

## 各文件职责（写入目标速查）

| 文件 | 何时写 | 方式 |
|---|---|---|
| 会谈/*.md | 每节 AI 会谈 | 新建 |
| 未完成.md | 每节结束 | 覆盖 |
| 档案.md | 六槽有变化 | 按槽更新（注明日期） |
| 人物与关系.md | 出现新人物 | 追加 |
| 模式.md | 周/会后 | 轻量追加 |
| 有效干预.md | 出现有效技术 | 追加 |

## 边界规则

- **永不修改 `type: human` 文件正文**（林老师会谈逐字稿、人工记录）。只读不写。
- **不诊断、不贴病理标签**——写回是「记录察觉」，不是「治疗结论」。
- **隐私等级 sensitive**：涉及第三方（太太、父亲、孩子）保持概括，不写可识别细节。
- 写回失败必须可重试：写任何文件前先读完目标文件原文并留底，失败后能原样重放；尤其**避免静默丢失「下次钩子」**——未完成.md 的「钩子」是下次会话的入口，务必落盘成功后再收尾。若写回失败，明确告知 Jeff 并保留本次会谈的原始内容，不要假装已写入。

## Pitfalls

- **路径带空格**：vault 路径含空格（`Mobile Documents`），shell 里必须加引号；建议用脚本/`read_file`/`write_file` 直接传绝对路径，不要手工拼 shell 命令。
- **`../` 与符号链接**：校验时用 `realpath` 解析后再做前缀判断，防止 `..` 或 symlink 逃出 `咨询/`。
- **frontmatter 判断 type**：写之前先读目标文件头部的 `type:` 字段确认；`type: human` 一律跳过。
- **未完成.md 覆盖别丢钩子**：覆盖前先读旧文件，把仍需保留的「钩子」合并进新内容，不要凭空覆盖掉还没处理的钩子。
