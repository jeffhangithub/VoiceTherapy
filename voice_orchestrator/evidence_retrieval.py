"""evidence_retrieval.py —— 语音轨道 L3 原始证据检索（本地、快、可追溯）。

背景：语音大脑是单次 chat completion，不能现场 agentic 翻库。当 Jeff 要"原话/具体说了什么/
翻一下那次录音"时，由 orchestrator 侧先本地检索 raw/咨询纪要/ 的 L3 逐字稿，把匹配段落
（带 日期 + 说话人 + 时间戳）作为补充注入给大脑，再让它据此回应。

设计：
- 分层：L1 纪要/概要(已由 counselor_context 常驻) → L3 逐字稿(本模块按需下钻)。
- 逐字稿文件：raw/咨询纪要/<日期>_<标题>.md（无 _纪要 后缀），含 frontmatter
  (feishu_url/duration/keywords) 与「说话人 N 时间戳」分段的正文。
- 检索：先用查询词与每场「标题+关键词」匹配选场次（无命中则取最近一场）；再在该场正文里
  按词命中挑出若干说话人段落，返回可追溯的证据块。
- 纯只读、无外部依赖（不引 torch/embedding）。中文用字符 bigram 近似分词。
"""
from __future__ import annotations

import re
from pathlib import Path

VAULT_DEFAULT = Path(
    "/Users/ironsoul/Library/Mobile Documents/iCloud~md~obsidian/Documents/Vaults/Jeff"
)
_HUMAN_DIRNAME = "raw/咨询纪要"

# 触发"要原始证据"的意图词
_EVIDENCE_TRIGGERS = (
    "原话", "原声", "逐字", "一字不差", "具体说", "具体怎么", "怎么说的", "怎么讲",
    "他当时说", "她当时说", "当时说", "翻一下", "翻翻", "查一下那次", "那次录音",
    "录音里", "妙记", "原文", "逐字稿", "文字记录", "记录里", "说过什么", "讲了什么",
)

# 中文常见停用词/填充（近似，够用即可）
_STOP = set(
    "的了是我你他她它们这那和与及或在有一不没也很就都而之其把被给对从到跟向为以"
    "呢吧啊呀哦嗯吗么嘛啦哇啊哈请问一下那个这个怎么什么时候说讲聊次那阵子"
)
_STOP_BIGRAMS = {"一个", "一下", "我们", "你们", "他们", "自己", "时候", "什么", "怎么", "那那"}


def is_evidence_query(text: str) -> bool:
    t = text or ""
    return any(w in t for w in _EVIDENCE_TRIGGERS)


def _terms(text: str) -> list[str]:
    """提取查询词：ASCII 词(≥2) + 中文 bigram(≥2，交叉停用字则丢)。丢弃单字以避噪声。"""
    text = text or ""
    terms: list[str] = []
    for w in re.findall(r"[A-Za-z0-9]{2,}", text):
        terms.append(w.lower())
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    for i in range(len(cjk) - 1):
        a, b = cjk[i], cjk[i + 1]
        if a in _STOP or b in _STOP:  # 交叉停用字的多为跨词噪声
            continue
        bg = a + b
        if bg in _STOP_BIGRAMS:
            continue
        terms.append(bg)
    seen, out = set(), []
    for t in terms:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


_DATE_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_RECENT_WORDS = ("上次", "上一次", "最近", "那次", "那天", "这回", "这次", "前几", "那天", "上一")


def _human_dir(vault: Path | None) -> Path:
    return (vault or VAULT_DEFAULT) / _HUMAN_DIRNAME


def _transcript_files(vault: Path | None = None) -> list[Path]:
    d = _human_dir(vault)
    if not d.exists():
        return []
    return sorted(
        [p for p in d.glob("20*.md") if not p.name.endswith("_纪要.md")],
        key=lambda p: p.name,
        reverse=True,  # 新的在前
    )


def _front(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip()
    return fm


def _keywords(text: str) -> str:
    m = re.search(r"关键词[:：]\s*(.+)", text)
    return m.group(1).strip() if m else ""


def retrieve_evidence(query: str, vault: Path | None = None, max_blocks: int = 4,
                      block_chars: int = 220) -> str:
    """返回可注入大脑的证据文本（带日期+说话人+时间戳）；无命中返回 ""。"""
    terms = _terms(query)
    files = _transcript_files(vault)
    if not files:
        return ""

    # 预载每场的 (text, fm, kws)
    loaded = []
    for p in files:
        try:
            t = p.read_text(encoding="utf-8")
        except Exception:
            continue
        fm = _front(t)
        loaded.append((p, t, fm, _keywords(t)))

    # —— 选场次 ——
    best = None
    # 1) 查询里给了明确日期
    dm = _DATE_RE.search(query)
    if dm:
        want = f"{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
        for p, t, fm, kws in loaded:
            if _session_date(p.name) == want:
                best = (p, t, fm); break
    # 2) 出现"上次/最近/那次"等 → 取最近一场
    if best is None and any(w in query for w in _RECENT_WORDS):
        p, t, fm, _ = loaded[0]  # files 已按新→旧排序
        best = (p, t, fm)
    # 3) 否则按词命中标题+关键词打分
    if best is None:
        bs = 0
        for p, t, fm, kws in loaded:
            hay = (fm.get("title", "") + " " + kws).lower()
            sc = sum(1 for tm in terms if tm and tm in hay)
            if sc > bs:
                best, bs = (p, t, fm), sc
        if best is None:
            p, t, fm, _ = loaded[0]
            best = (p, t, fm)

    p, body, fm = best
    date = _session_date(p.name)
    title = fm.get("title", p.stem)

    # —— 选证据块 ——
    blocks = _split_speaker_blocks(body)
    scored = []
    for spk, ts, txt in blocks:
        s = sum(1 for tm in terms if tm and tm in txt)
        if s > 0:
            scored.append((s, spk, ts, txt))
    scored.sort(key=lambda x: x[0], reverse=True)
    picked = scored[:max_blocks]
    if not picked:
        return ""

    lines = [f"【L3 原始证据 · 来自 {date} 真人会谈《{title}》逐字稿】",
             "（引用请带 日期+说话人+时间戳；以下为转写原文，可能有语音识别误差）"]
    for _s, spk, ts, txt in picked:
        snippet = txt.strip().replace("\n", " ")
        if len(snippet) > block_chars:
            snippet = snippet[:block_chars] + "…"
        lines.append(f"- {spk} {ts}：「{snippet}」")
    feishu = fm.get("feishu_url")
    if feishu:
        lines.append(f"（原始出处：{feishu}）")
    return "\n".join(lines)


def _session_date(name: str) -> str:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", name)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else name


def _split_speaker_blocks(body: str) -> list[tuple[str, str, str]]:
    """把逐字稿切成 (说话人, 时间戳, 文本) 段。段落形如 '说话人 1 00:01:07.440\\n你在是吧？'"""
    out = []
    pat = re.compile(r"^(说话人\s*\d+)\s+(\d{2}:\d{2}:\d{2}\.\d{3})\s*$")
    cur_spk = cur_ts = None
    buf: list[str] = []
    for line in body.splitlines():
        m = pat.match(line.strip())
        if m:
            if cur_spk and buf:
                out.append((cur_spk, cur_ts, "\n".join(buf).strip()))
            cur_spk, cur_ts, buf = m.group(1), m.group(2), []
        elif cur_spk is not None:
            if line.strip():
                buf.append(line.strip())
    if cur_spk and buf:
        out.append((cur_spk, cur_ts, "\n".join(buf).strip()))
    return out


def _msg_text(content) -> str:
    """取一条消息的纯文本（兼容 str 或 [{type:text,text:...}]）。"""
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return str(content or "")


class EvidenceInjector:
    """Pipecat 处理器：在 user 消息进 LLM 前，若为"要原始证据"意图，检索 L3 逐字稿
    并把证据（带日期+说话人+时间戳）作为 system 消息注入上下文，再交给 LLM。

    纯附加、旁路：检索不到就不注入；同一条 query 只注入一次，避免累积。
    惰性导入 pipecat，保证纯检索函数在无 pipecat 环境也可用。
    """

    def __init__(self, vault: Path | None = None, **kwargs):
        from pipecat.frames.frames import LLMContextFrame
        from pipecat.processors.frame_processor import FrameProcessor
        self._LLMContextFrame = LLMContextFrame

        class _Impl(FrameProcessor):
            def __init__(_self):
                super().__init__(**kwargs)
                _self._last = None

            async def process_frame(_self, frame, direction):
                await super().process_frame(frame, direction)
                if isinstance(frame, LLMContextFrame):
                    try:
                        _self._maybe_inject(frame.context)
                    except Exception:
                        pass
                await _self.push_frame(frame, direction)

            def _maybe_inject(_self, context):
                last_user = None
                for m in reversed(context.get_messages()):
                    if isinstance(m, dict) and m.get("role") == "user":
                        last_user = _msg_text(m.get("content"))
                        break
                if not last_user or last_user == _self._last:
                    return
                if not is_evidence_query(last_user):
                    return
                ev = retrieve_evidence(last_user, vault)
                if ev:
                    context.add_message({"role": "system", "content": ev})
                    _self._last = last_user

        self.processor = _Impl()
