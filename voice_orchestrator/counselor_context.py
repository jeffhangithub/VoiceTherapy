"""
counselor_context.py — 咨询开场上下文组装器（供语音编排器预注入，避免大脑现场 agentic 翻库）。

背景：语音端用「单次 chat completion」调 Hermes agent；若让大脑现场去"加载 counselor skill +
读多份 vault 文件"，会因跑不动 agent 工具循环而卡/极慢。故由本模块在会话开始前，把 counselor 需要的
动态背景（人设 + 热层摘要 + 林老师最近会谈开场回顾）直接拼成一条 system 指令，大脑只负责据此说话。

职责：
1. 组装固定人设 + 边界 + 热层三件（工作同盟/未完成/档案）摘要 → 每次开场预注入。
2. 开场回顾（事件驱动）：扫 raw/咨询纪要/ 最新 _纪要，若 date > 开场回顾.md 的 last_recapped，
   则把其 概要 纳入指令（让大脑开场先回顾），并把 last_recapped 更新为该 date（回顾已"交棒"给开场）。
只读 human 记录；只写 咨询/来访者/我/开场回顾.md。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# Vault 根：优先读环境变量 VT_VAULT（允许未来重构换库/移动，无需改码），缺省回退到当前 Jeff vault。
# 路径设计为"根可配、子路径派生"，故下方 MY/SYS/RECAP_FILE/HUMAN_DIR 均随 VAULT 自动跟随，只需在 VT_VAULT 处换根。
_VAULT_DEFAULT = Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/Vaults/Jeff"
VAULT = Path(os.environ.get("VT_VAULT", _VAULT_DEFAULT))
MY = VAULT / "咨询" / "来访者" / "我"
SYS = VAULT / "咨询" / "_系统"
RECAP_FILE = MY / "开场回顾.md"
HUMAN_DIR = VAULT / "raw" / "咨询纪要"

# 语音轨骨架：单一真源 = counselor skill 的「## 语音轨骨架」节（语音轨不加载 skill，故预注入）。
# 读不到该节（skill 缺失/被改）时回退到内置兜底，保证语音轨永不裸奔。
_SKILL_MD = Path.home() / ".hermes" / "skills" / "counselor" / "SKILL.md"
_SKELETON_FALLBACK = (
    "【本场结构】按此推进，但不必机械报阶段，顺着他走：\n"
    "- S0 开场：简短问候→（有回顾就先回顾林老师最近一场）→带钩子；别替他总结\"成长/成果\"。\n"
    "- S1 签到：一句问他今天什么状态，让他自由铺陈；别急着上框架。\n"
    "- S2 聚焦+定目标：把议题收成一个焦点，并【共同确定】「今天这段时间，怎样的帮助对你最有用」——别替他猜。\n"
    "- S3 探索：一次一个焦点、只问一个开放问题；先共情与澄清，再上框架。\n"
    "- S4 工作：轻推一步；【上框架前先分三层】——事实/他的解释/你的假设；只轻推他的解释，不把假设当结论。\n"
    "- S5 收束：让他用自己的话总结；结束前问一句此刻感受，留一个可继续的小方向，不封死出路。\n"
    "【安全·情境化】当他描述持续、反复、可能升级的伤害（对他或孩子）时，自然先关切一句安全"
    "（如「最近一次具体发生了什么」）；别像念清单；安全未清前不深挖动机。\n"
    "【始终】沉默/停顿是他思考的时间，绝不因此结束；不诊断、不贴标签、不替第三方定动机；引用必带日期。"
)

_PERSONA = (
    "你是 Jeff 的心理咨询助理（林老师——他的真人咨询师——的助理与延伸），本场是正式咨询会话。"
    "定位：辅助回顾、反映、澄清、轻结构 sparring 的陪伴者，不是治疗师、不是林老师的替代。"
    "固定边界：不诊断、不贴病理标签；不做危机干预（遇自伤/自杀意向只稳定与转介）；不编造没记录的事实，"
    "引用必带日期；涉及第三方（太太/父亲/孩子等）保持概括。"
    "中文自然；先共情与澄清，再上框架；多用问题少下判断。"
    "少说『你真正的意思是…』，多做『让我确认我有没有理解你』；多反映、多澄清，少替他补动机。"
    "回复风格：简练——通常 2~3 句、一次只说一个要点，直击核心；先共情与澄清，再上框架。"
    "保持温度和具体，但别啰嗦、别堆排比、别复述 Jeff 刚说过的话；宁可短，也不要为凑长度而展开。"
    "护栏：①语音识别可能误读 Jeff 的话——当他转述/记不清某段、或提到听起来像事实但你不确定的点时，如实说明并请他确认，绝不把可能误读的内容当成已确认事实。"
    "②不做破坏性动作——不因一次可能听错的语音指令就删除/改写 vault 档案或未完成钩子；确需改动，先明确说出要改什么、请他确认后再动。"
    "③回顾与钩子一律按『假设，待 Jeff 确认』处理，不作为定论。"
    "开场规则：你的第一段回应必须是『简短问候 →（若给了【本场开场回顾】就先回顾林老师最近一场）→ 再自然往下』；禁止用 未完成/档案/工作同盟 里的钩子当作开场话题。"
    "④绝不在 Jeff 沉默/停顿思考时结束会话——咨询中的留白是正常的思考时间；只有 Jeff 明确说出要结束时才结束，绝不主动退出。"
    "⑤不替第三方定动机——太太/父亲/孩子等不在场，你无从知道他们『真正想什么』『只是…还是…』；只反映 Jeff 自己的感受与推测，并标注『这是你的推测』，不把猜测说成事实。"
    "⑥区分『不能替对方改变』与『你自己仍有选择』——对方怎么变你控制不了，但你和孩子怎么被保护、你愿意承担多少，是可以一起看的；不把处境说成『只能等』『没有出口』。"
    "⑦被纠正时先确认——Jeff 说『不是』『你理解错了』，先一句『明白，我理解偏了』，不要立刻再给一个深层解释。"
    "⑧下判断前分清三层——事实（他报告发生的）／他的解释（他怎么理解）／你的假设（你推测的，须按『假设，待确认』说）；只对他的解释轻推，不把你的假设当结论。"
    "⑨安全评估——当 Jeff 描述自己或孩子持续承受『情绪暴力/暴怒/伤害』时，先做最小安全评估（最近一次具体发生了什么／是否升级／孩子是否安全／有哪些支持），从一句开始，不机械问全套；安全未清前不推进动机解释、不建议重启夫妻治疗。"
    "⑩不评价药物/医疗方案——不把『药』描绘成轻省路径、不承诺缓解比例、不把『拒绝用药』解读为『不愿努力』；是否用药须由医生评估。"
)


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2]
    return text


def _read_head(p: Path, max_chars: int = 900) -> str:
    if not p.exists():
        return ""
    try:
        body = _strip_frontmatter(p.read_text(encoding="utf-8")).strip()
        return body[:max_chars]
    except Exception:
        return ""


def _is_test_placeholder(p: Path) -> bool:
    """若文件 frontmatter 的 status 含 测试/验证，视为测试占位 → 不注入为真实背景。"""
    if not p.exists():
        return True
    try:
        head = p.read_text(encoding="utf-8")[:400]
        return bool(re.search(r"^status\s*[:：]\s*(测试|验证)", head, re.M))
    except Exception:
        return True


def _latest_human_session():
    """返回 (date_str, path) 或 None：raw/咨询纪要/ 下日期最大的 _纪要。"""
    if not HUMAN_DIR.exists():
        return None
    best = None
    for f in HUMAN_DIR.glob("*_纪要.md"):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", f.name)
        if m and (best is None or m.group(1) > best[0]):
            best = (m.group(1), f)
    return best


def _recapped_date() -> str | None:
    if not RECAP_FILE.exists():
        return None
    # last_recapped 与冒号间可能有 ** (markdown 加粗), 用 [^:\n]* 容错
    m = re.search(
        r"last_recapped[^:\n]*[:：]\s*(?:\(([^)]*)\)|([\d-]+|空|无))",
        RECAP_FILE.read_text(encoding="utf-8"),
    )
    if not m:
        return None
    val = (m.group(1) or m.group(2) or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", val):
        return val
    return None


def _extract_summary(md_text: str, max_chars: int = 700) -> str:
    """取 _纪要 的 ## 概要 段落；找不到则取 frontmatter 后正文头部。"""
    m = re.search(r"##\s*概要\s*\n(.*?)(?:\n##\s|\Z)", md_text, re.S)
    if m:
        return m.group(1).strip()[:max_chars]
    body = _strip_frontmatter(md_text).strip()
    return body[:max_chars]


def _read_voice_skeleton() -> str:
    """读取 counselor skill 的「## 语音轨骨架」节；失败回退内置兜底。语音轨不加载 skill，故预注入。"""
    try:
        txt = _SKILL_MD.read_text(encoding="utf-8")
        m = re.search(r"##\s*语音轨骨架[^\n]*\n(.*?)(?:\n##\s|\Z)", txt, re.S)
        if m:
            # 去掉引用块(>)注释行，只留正文
            sec = "\n".join(l for l in m.group(1).splitlines() if not l.lstrip().startswith(">")).strip()
            if len(sec) > 60:
                return "【本场结构 · 来自 counselor skill】\n" + sec
    except Exception:
        pass
    return _SKELETON_FALLBACK


def build() -> str:
    """组装完整的 system 指令（含预注入热层 + 可选开场回顾），并更新 last_recapped。"""
    parts = [_PERSONA, _read_voice_skeleton()]

    # —— 热层（每次预注入，供大脑全程参考；status:测试/验证 的占位不注入为真实背景）——
    hot = []
    for name in ("工作同盟", "未完成", "档案"):
        p = MY / f"{name}.md"
        if _is_test_placeholder(p):
            continue
        body = _read_head(p)
        if body:
            hot.append(f"【{name}】\n{body}")
    if hot:
        parts.append(
            "以下是 Jeff 的当前咨询背景（来自知识库，已为你载入，不要逐字复述，据此自然回应即可）：\n"
            + "\n\n".join(hot)
        )

    # —— 开场回顾（事件驱动，林老师最近一场）——
    recap_txt = ""
    new_recap_date = None
    latest = _latest_human_session()
    if latest:
        date, path = latest
        recapped = _recapped_date()
        if recapped is None or date > recapped:
            summary = _extract_summary(path.read_text(encoding="utf-8"))
            if summary:
                recap_txt = (
                    f"【本场开场回顾】你刚发现 Jeff 最近一次林老师会谈（{date}）还没回顾过。"
                    f"请在开场问候之后，把下面这段用你自己的话、2–4 句、带日期地简要回顾给 Jeff"
                    f"（回顾是一次性的，放在本场第一段回应，之后不再重复提）：\n{summary}"
                )
                new_recap_date = date
    if recap_txt:
        parts.append(recap_txt)

    instruction = "\n\n".join(parts)

    # 回顾已交棒给开场 → 更新 last_recapped，避免下个进程重复
    if new_recap_date and RECAP_FILE.exists():
        try:
            txt = RECAP_FILE.read_text(encoding="utf-8")
            txt = re.sub(
                r"\*{0,3}last_recapped[^:\n]*[:：]([^\n]*)",
                lambda m: f"**last_recapped**：{new_recap_date}",
                txt, count=1,
            )
            RECAP_FILE.write_text(txt, encoding="utf-8")
        except Exception:
            pass

    return instruction
