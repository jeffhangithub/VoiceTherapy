---
name: counseling-notes-jeff
description: "心理咨询咨询纪要(Jeff 定制版)。将心理咨询会谈录音文字稿整理为来访者(Jeff)个人视角的结构化咨询纪要,内容用 counseling-notes 七段模板,落 vault raw/咨询纪要/ 并用 VoiceTherapy 兼容命名,同时云盘双保存。关键词:心理咨询纪要、咨询纪要、therapy notes、咨询录音整理。仅用于心理咨询类;迈斯沃克客户拜访用 mathworks-meeting-minutes,其他会议用 meeting-minutes-generator。"
category: counselor
---

# 心理咨询咨询纪要(counseling-notes-jeff)

> 把心理咨询会谈录音文字稿,整理成**来访者 Jeff 个人视角**的结构化咨询纪要。**双落盘**:vault `raw/咨询纪要/`(VoiceTherapy 读取处)+ 飞书云盘咨询目录。

## 适用范围
- 心理咨询/治疗会谈录音(林老师真人会谈 或 明确的心理咨询场景)转写稿。
- 客户拜访(迈斯沃克)→ 用 `mathworks-meeting-minutes`;朝乾投资/其他 → `meeting-minutes-generator`。

### ⚠️ 归属判定护栏(防误判,尤其标题含蓄的会谈)
判定一份录音是不是心理咨询,**必须读正文开头若干段 + 说话人结构**,不能只靠标题关键词——历史教训:标题含蓄的心理会谈(如「个人生活状态与心理觉察」「状态复盘」「亲密关系与个人成长」)不含"咨询/心理"显式词,但实为心理咨询(2026-09-05 排查确认:MathWorks/文字记录/ 曾混入此类件,根因=妙记自动产物落点 + 标题关键词误判)。
判定依据(自上而下):
1. **心理咨询**:正文呈「来访者(Jeff)+ 咨询师(林老师)」一对一心理会谈结构;或围绕 Jeff 个人情绪/关系/成长/生活状态的深度对话(咨询师提问引导、Jeff 倾诉);正文无 MATLAB/Simulink 产品与技术演示内容。
2. **迈斯沃克**:汽车客户用 MATLAB/Simulink 的技术/产品/商务交流,说话人含 TMW cast(韩轶奇/龚小平/凯文/玉源)。
3. **冲突裁决**:以对话性质为准(个人心理深度对话=咨询;汽车客户技术/商务交流=迈斯沃克);拿不准标"待人工",不要误归类、误落盘。


## ⚠️ 与 VoiceTherapy 的命名硬约束(最关键)
VoiceTherapy 的 `counselor_context.py` 开场回顾**只扫 `raw/咨询纪要/` 下文件名以 `YYYY-MM-DD` 开头、含 `_纪要.md`、日期最大的文件**。
所以 vault 文件名**必须**用 `YYYY-MM-DD_HHmm_<主题>_纪要.md`(与现有咨询纪要一致),**不是** counseling-notes 模板默认的 `咨询纪要_名字_第N次.md`。

## 落点
- **vault**:`raw/咨询纪要/YYYY-MM-DD_HHmm_<主题>_纪要.md`
- **云盘**:同一内容建在线 docx 存云盘咨询目录 `咨询录音/`(folder-token `Rgd2fE5Zjlnc4pdm4X0cIKcznHf`),串行导入。命名可用可读标题。

## 说话人识别
- 区分"咨询师"与"来访者(Jeff)"。称呼线索:咨询师被称"老师/×医生/×老师"(林老师);来访者自称"我"。
- 纪要以"我(来访者)"与"咨询师"记录,不标转写编号。
- 真人会谈(林老师)与 AI 会谈注意区分来源,frontmatter 记 therapist 或 ai 来源。

## 七段模板(内容,counseling-notes)
```
一、本次咨询概览        ← 咨询师/来访者/第N次/时间时长/形式/主题标签
二、议题与背景          ← 上次遗留议题回顾 + 本次话题/近况
三、会谈过程            ← 按议题分小节,中性转述 + 关键对话摘录
四、我的感受与觉察      ← 情绪起伏/触动点/新领悟(第一人称)
五、咨询师的回应与建议  ← 澄清/提问/解释/建议/练习
六、本次收获小结        ← 最重要收获1-3条 + 未解决困惑(遗留议题)
七、行动计划与下次安排  ← 想尝试的改变/练习、下次时间与待谈主题
```

**质量规则**:
- 忠实会谈不虚构;听不清/缺段落标"(录音缺失,待补)"
- 非评判、去术语(用概念时一句大白话解释)
- 保护隐私:不写无关第三方可识别细节,用"家人/同事/伴侣"称谓
- 情绪词用录音原话("很累""空空的""松了一口气"),不过度解读
- **前端 frontmatter 加 `source:` + `date:` + `therapist:`(林老师/其它)**,与 AI 会谈(AI-访谈)区分

## frontmatter 模板
```yaml
---
source: feishu-minutes
type: 心理咨询纪要
meeting_date: <YYYY-MM-DD>
duration: <时长>
therapist: 林老师        # 真人会谈;若是 AI 会谈写"AI"
privacy: sensitive
status: 正式版
---
```

## 执行步骤(自动 cron 用)
1. 读文字记录(frontmatter 拿 feishu_url/日期/时长),通读全文到 truncated:false。
2. 识别咨询师与来访者、第几次、主题标签。
3. 按七段模板生成纪要,文件头加 frontmatter。
4. 双落盘:vault `raw/咨询纪要/<YYYY-MM-DD_HHmm_主题>_纪要.md`;云盘 `咨询录音/`(`Rgd2fE5Zjlnc4pdm4X0cIKcznHf`)在线 docx。
5. 更新 vault `raw/咨询纪要/` 索引/开场回顾的 last_recapped 依赖的文件名日期自然覆盖。

## 安全
- 咨询区(vault `咨询/`、`raw/咨询纪要/`)敏感,只写本纪要文件,不改动既有 human 记录、不删任何东西。
- lark-cli 前 export HTTPS_PROXY/HTTP_PROXY=http://127.0.0.1:7897;typed flags;ASCII 临时路径导入(cp 到 ~/.tmp_*.md),成功删临时文件。

## 依赖
- `jeff-vault`(路径)、`lark-drive`、`lark-shared`。Clash 代理 127.0.0.1:7897。
