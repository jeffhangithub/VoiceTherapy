# Hermes Skills — 咨询系统

本目录存放 VoiceTherapy 项目配套的 Hermes Agent skill。将这些 skill 安装到 Hermes 的 `~/.hermes/skills/` 即可启用咨询对话与写回能力。

## 目录结构

| 目录 | Skill | 职责 |
|------|-------|------|
| `counselor/` | counselor | 心理咨询辅助对话引擎：S0–S7 状态机、driving/desk 模式、热层记忆读取、危机处理边界。不写会谈文件（交棒 session-notes）。 |
| `session-notes/` | session-notes | 会谈写回：新建 AI 会谈笔记、更新未完成、条件更新六槽/人物/有效干预，永不修改 type:human 文件。 |
| `recall/` | recall | 历史会谈检索（只读）：按主题/模式定位再搜会谈，最多引用 2-3 段带日期，输出「当时发生→做了什么→与今天连接→一个问题」结构，driving 给 4 句压缩版，绝不写文件。 |
| `weekly-insights/` | weekly-insights | 周洞察：读本周（ISO 周）type:AI 会谈，聚合主题/进展/未完成钩子，写 `洞察/YYYY-Wxx.md` + 轻量追加 `模式.md`；结论标记为假设待 Jeff 确认，不碰 type:human。 |

## 安装

```bash
# 从本仓库复制到 Hermes skills 目录
cp -R hermes-skills/counselor ~/.hermes/skills/
cp -R hermes-skills/session-notes ~/.hermes/skills/
cp -R hermes-skills/recall ~/.hermes/skills/
cp -R hermes-skills/weekly-insights ~/.hermes/skills/
```

## 依赖的 Obsidian 目录结构

这两个 skill 约定咨询数据存放在 Obsidian vault 的 `咨询/` 子系统（完整模板见 `../templates/vault-structure/`）。首次运行前，请先按模板创建目录结构，或让 session-notes skill 自动创建。

> **隐私说明**：真实咨询数据（会谈全文、档案、未完成等）只存在于本地 Obsidian vault，本仓库仅保存结构模板与可复用代码，不含任何真实咨询内容。
