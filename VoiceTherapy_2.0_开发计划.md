# VoiceTherapy 2.0 开发计划（分析报告）

> 状态：规划中 · 日期：2026-09-02 · 作者：Jeff（经 AI 整理）
> 定位：作为 2.0 的架构分析与路线图，供后续开发按阶段推进；1.x 保持可用并继续维护。

---

## 0. 摘要

- 1.x 已实现：手机浏览器 WebRTC 语音对话（Tailscale 直连 Mac Mini + Hermes 大脑）、实时转写、自动存 `AI-访谈` 到 Obsidian。
- **1.x 的硬边界 = 手机浏览器回声（AEC）**：外放时机器人会听到自己的声音，导致自我打断/胡言乱语。
- **2.0 核心 = 增加一个原生手机 App**（个人自用、不上架），用 **native AEC（WebRTC AEC3）** 根治回声，实现真正免提/全双工打断。
- **关键判断**：因已有 Tailscale P2P 直连，**原生 App 不需要任何托管 SFU（LiveKit/Daily 云）**——native WebRTC 直连现有 Mini runner 即可，完全自托管。
- 网页 PWA 与原生 App **双客户端并存**，共享同一 Hermes 大脑与信号协议。

---

## 1. 背景与 1.x 现状

**产品**：VoiceTherapy —— 用 Hermes（Jeff 自己的 agent + vault）驱动的人工语音咨询助手。价值不在"能语音对话"（商品化），而在"记得上次聊到哪、用咨询师方式陪你梳理、聊完自动归档"。

**1.x 已交付（已验证）**：
| 能力 | 说明 |
|---|---|
| 本机语音环 | 麦克风→VAD→faster-whisper→Hermes→edge TTS→扬声器 |
| barge-in（3.2） | 本机打断 ~5ms 停播 |
| 手机 WebRTC（3.3） | 浏览器 PWA ↔ Mini runner ↔ Hermes；对话+打断可用 |
| 自动常驻 | Mini launchd 起 runner + tailscale serve |
| 定制 PWA | 咨询师头像/计时器/实时转写+历史/暂停退出 |
| 结束存库 | 结束对话→写 `咨询/.../会谈/YYYY-MM-DD-AI-访谈.md` |
| STT 精度 | faster-whisper `small` + beam5 |

**技术栈**：Pipecat 1.8.1 · faster-whisper(local) · edge-tts(云) · Hermes@8642(模型 DeepSeek/云) · WebRTC P2P · Tailscale。

---

## 2. 2.0 目标

1. **真 AEC**：外放免提场景下机器人不自听，支持全双工打断（对标小智 AI）。
2. **原生 App**：iOS（个人自用、不上架、免费/付费签名），可扩展到 Android。
3. **保留网页 PWA**：作轻量随手入口，与原生 App 并存。
4. **可选增强**：手机端流式 ASR（出中间转写 + 隐私）、更低音频延迟。

---

## 3. 核心问题分析

### 3.1 回声根因
手机单设备：扬声器播女声 → 麦克风收进女声 → 机器人把"自己的话"当用户输入 → 自打断 + 转写残词 → 无限回声循环。日志实证：女声一开口 ~1s 即 `User started speaking`(VAD 把回声当人声) → `broadcasting interruption`。

### 3.2 为什么浏览器难做真 AEC
- `getUserMedia({audio:true})` 的 `echoCancellation` **默认 true**，但手机浏览器对「播放远端 WebRTC 音轨 + 采麦克风」这条链路，**原生 AEC 常不生效**（iOS Safari 尤弱）。
- 远程音轨经 `<audio>` 播出，未作为参考注入麦克风采集的 AEC DSP。
- Web Audio 无现成自适应滤波节点；手写 NLMS 需采样级同步（播放延迟 20–50ms+时钟漂移），手机 CPU 吃力且不稳。**浏览器不是 AEC 的正确载体**。

### 3.3 参照：小智 AI（xiaozhi）如何解决
小智是 ESP32 硬件，跑 Espressif 音频框架 **AEC+AGC+NS（本地 DSP）**。它能边播边听不自听，是因为**设备完全掌控自己播的音频（参考信号）**，用参考从麦克风里精确减掉自己的回声。**= 原生/硬件 AEC 是治本，躲/半双工不是。**

### 3.4 延迟：ASR 放哪的影响（分析，非改动）
非同网高 RTT（Tailscale 实测 ~1.3s）下，现链路首声 ≈3.5–5s：
- 上行尾音(≈0.65) + VAD(0.5) + ASR(0.5) + LLM 首 token(1–2.5s) + TTS(0.3) + 回复下行(0.65)。
- **ASR 上手机只省上行音频段 ~1–1.4s（~25–30%）**；大头是 LLM 首 token + 回复下行，与 ASR 位置无关。
- ASR 上手机的真价值 = **流式中间转写(UX) + 隐私 + 流量**，不是延迟。

---

## 4. 关键决策

| 决策 | 结论 | 理由 |
|---|---|---|
| AEC 载体 | **原生 App** | OS 提供系统级 AEC（iOS AVAudioSession / Android AcousticEchoCanceler），或内嵌 **WebRTC AEC3**（Zoom/微信等 VoIP 标准）。OS 知道 App 自己播了什么 → 可精确消回声。 |
| 是否托管 SFU | **不需要** | LiveKit/Daily 托管是"媒体中继"，仅在两端无法直连时才需要。我们已有 **Tailscale P2P 直连**，1:1 通话不需中继。原生 WebRTC 直连 Mini = 完全自托管、隐私好、不上云。 |
| 客户端形态 | **双并存**：网页 PWA（保留）+ 原生 App（新增） | 网页轻量随手；原生 App 承载外放/免提/AEC。共享 Hermes 大脑与 `/api/offer` 信号。 |
| App 分发 | **个人自用、不上架** | 免审核；iOS 侧载需签名（见附录）。 |

---

## 5. 目标架构

```
                 ┌─────────────────────────────────────────┐
                 │            Mac Mini（Hermes 大脑）       │
                 │  Hermes agent @127.0.0.1:8642            │
                 │   + counselor skills + vault             │
                 │  voice orchestrator (Pipecat) runner     │
                 │   /api/offer (WebRTC 信令) · STT/TTS/VAD │
                 │  launchd 常驻 · tailscale serve          │
                 └──────────────────▲───────────────────────┘
                          Tailscale P2P（加密直连，无托管中继）
              ┌─────────────────────┴──────────────────────┐
       网页 PWA（1.x 保留）                       原生 App（2.0）
       浏览器，AEC 弱，耳机/安静房间               native AEC3，免提全双工
```

- **信令**：两端都走现有 `/api/offer`（SDP 交换），媒体 P2P 经 Tailscale 直连。
- **差异**：原生 App 的音频采集/播放走 native，叠加 WebRTC AEC3 → 全双工无回声。
- **Hermes 大脑完全不变**；只需新增/适配一个 native 客户端。

---

## 6. 技术选型

| 项 | 候选 | 倾向 | 理由 |
|---|---|---|---|
| 跨端框架 | Flutter / React Native | **Flutter** | 一套代码 iOS+Android；`flutter_webrtc` 封装原生 WebRTC（含 AEC） |
| 音频栈 | `flutter_webrtc` / 原生 webrtc-ios | flutter_webrtc | 底层 Google WebRTC（AEC3/NS/AGC），信号可接现有 runner |
| iOS 签名 | 免费 Apple ID | 先免费（7 天续签） | 自用工具可接受；必要时升付费 $99/年免每周续签 |
| 网络 | Tailscale（沿用） | 沿用 | 已有直连，不引入托管 |
| ASR（可选） | 手机端 SenseVoice/whisper.cpp | 2.0 后期 | 流式中间转写 + 隐私 |
| TTS/LLM | edge(云)/DeepSeek(云) | 沿用 | 1.x 已通 |

---

## 7. 路线图（Phase）

**Phase 2.0.1 —— 最小原生 AEC 验证（PoC）**
- 建 Flutter App，接 `flutter_webrtc`；实现连接我们 Mini 的 `/api/offer`。
- 验证：外放状态下无回声、全双工打断、单设备音频。
- 验收：安静房间外放说话，机器人不自听、可插话。

**Phase 2.0.2 —— 咨询师客户端体验**
- 移植 1.x 定制 PWA 的 UI 逻辑：头像、计时器、实时转写+历史、暂停/退出、结束→存库。
- 结束对话触发存 `AI-访谈`（沿用现有 `/api/save`）。

**Phase 2.0.3 —— 手机端流式 ASR（可选）**
- 端上 SenseVoice/whisper.cpp 出中间转写；文本传 Mini。
- 目标：边说要显示识别、原始音频不出设备。

**Phase 2.0.4 —— 收尾与双端共存**
- Android 适配、续签/签名流程固化、README/文档更新。

> 每一步 headless/模拟器可验部分先过，真机（Jeff 手机 + 真实网络）后置。

---

## 8. 风险与取舍

- **浏览器 AEC 不可根治** → 原生 App 才是解；网页端继续用"安静房间+耳机"定位。
- **原生 App 开发成本**：新项目规模（两平台），对单人开发者是大投入；但自用免发布 + Flutter 一套代码可摊薄。
- **iOS 侧载签名**：免费账号 7 天续签（每次 Xcode 重 build/连接），或付费 $99/年。
- **托管 SDK 诱惑**：LiveKit 云等看似省事，但引入第三方中继 + 数据出域；我们不需它。
- **网络依赖**：双端都依赖 Tailscale 在线 + Mini 常驻（web_server 的 launchd 常驻仍是 1.x 待办）。

---

## 9. 待决问题

1. 原生 App 是否要支持 Android（现仅有 iPhone）？
2. 免费签名（每周续签） vs 付费开发者账号（$99/年免烦）——先免费验证，正式用再升？
3. 手机端流式 ASR 是 2.0 必须还是可选？
4. 免提外放（开车）到底是不是核心场景？是 → 原生 AEC 才必要；否 → 可长期用网页+耳机。

---

## 10. 附录：iOS 免费 Apple ID 签名要点
- 免费 Apple ID（Personal Team）签名的 App **7 天过期**，需 **Xcode 重新 build/run（通常连线）** 或 AltStore/侧载工具自动续签。
- 限制：约 3 个 App ID 上限、部分 entitlements/推送不可用（WebRTC 语音一般不受影响）。
- 自用工具可接受；若嫌烦升付费账号。

---

*本报告为 2.0 开发的顶层分析与计划；具体实现细节随 Phase 推进补充。*
