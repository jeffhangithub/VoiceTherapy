# VoiceTherapy 公开化改造计划（个人版 → 可扩展云架构）

> 状态：规划草案 · 2026-09-03
> 背景：当前为单机单用户个人使用，用 Tailscale(L3 VPN) 打通 NAT，不开公网端口、隐私本地化。本文件思考：**方案稳定后若要做成公开多用户应用，媒体承载层如何演进为开放、可扩展架构**。产品层（Hermes 大脑 + SenseVoice + edge TTS + counselor_context + web_client）几乎原样复用，只替换"NAT 终结 / 媒体承载"这一层。

---

## 1. 动机与边界

- **为什么当前用 Tailscale**：手机 ↔ 家里 Mini 传的是 **WebRTC(UDP)**；Mini 在家庭 NAT 后无公网 IP。外网到达 NAT 后设备只有三条路——①打洞(端口转发) ②第三方中转(relay) ③L3 虚拟专网(VPN)。Tailscale = WireGuard 的 L3 网，能原样承载 UDP WebRTC、免开公网端口、自带设备认证与 HTTPS 证书，是**单用户个人场景**最省最稳的组合。
- **为什么 HTTP 隧道(Cloudflare Tunnel/ngrok)不适合**：它们按 TCP/HTTP 设计，**难以干净承载 UDP 的 WebRTC**（除非改传输或走 TURN，都更慢更复杂）。真 L3(VPN) 或公网直连/SFU 才是语音 WebRTC 的正确承载。
- **VPN 对语音的影响**：同 WiFi 直连 P2P ~1ms；异地直连 P2P 亦快；仅回退 DERP 中继时 +10–40ms 且可能抖。但语音"卡顿感"主导来自**句级换手 + ASR/LLM/TTS 处理延迟**，非传输层。公开化后应由云信令 + 媒体节点承载，把承载与处理解耦。

**演进边界**：本文件只管"承载/架构"，不动产品语义（会话流程、咨询师人设、开场回顾、护栏等）。

---

## 2. 现状架构（个人版）

```
手机 PWA
  ⇅ WebRTC(UDP)
Tailscale Serve (mac.tail844e3d.ts.net)   ← NAT 终结在个人 overlay
  └→ web_server.js(8050)  静态 + /api/offer 反代 + /api/save
       └→ orchestrator_webrtc.py(7860) SmallWebRTCTransport runner
            └→ Pipecat: VAD → SenseVoiceSTT → Hermes大脑(8642, counselor_context 预注入) → edge TTS(流式)
 结束 → /api/save → 本地 vault 会谈/…
Hermes 大脑 与 管线 都跑在 家里 Mac Mini（私有、离线 ASR）
```

**承载层耦合点**：Tailscale Serve 同时承担「域名/HTTPS」「信令」「媒体到达 NAT」。单用户够用；多用户/公开则这些职责必须拆开并放到公网可达处。

---

## 3. 目标架构（公开版）

```
客户端 App / 浏览器
   ⇅ 信令(HTTPS/WSS, 公网) + 媒体(SFU/TURN)
云端网关(公网可达)
   ├─ 认证 / 鉴权(每用户 / 每会话)
   ├─ 信令服务(Signal)        —— 建立会话、下发 SDP/ICE
   ├─ SFU / TURN               —— 媒体转发 / NAT 穿透(LiveKit / mediasoup / 自建 TURN)
   └─ 会话调度(把用户会话路由到空闲 Hermes worker)
        ⇅ 内部(可信网络) WebRTC/WSS
云端 Hermes Worker 池
   └─ 复用同一管线:
        SenseVoice STT → Hermes 大脑(每用户独立 vault/上下文, counselor_context 预注入) → edge TTS
   （worker 弹性伸缩 / 多租户隔离）
```

**分层解耦原则**：
1. **信令/控制面** 与 **媒体面** 分离；两者都放公网可达处。
2. **承载层**（信令/SFU/TURN/调度）与 **产品层**（Hermes+ASR+TTS+counselor）分离。
3. 单用户上下文 / vault 数据按用户隔离，仍遵循"真实咨询内容不外泄给第三方"原则（可选私有部署或加密存储）。

---

## 4. 可复用 vs 需替换 清单

| 组件 | 现状 | 公开化处理 |
|---|---|---|
| `orchestrator_webrtc.py` 管线结构 | 单 bot | 大部分复用；bot/媒体承载换成 SFU 客户端接入 |
| `sensevoice_stt.py` | 本地 Mini | **决策点**：本地 worker 节点 or 云端(需 GPU/CPU 配额) |
| `edge_tts_service.py` | edge 云端 | 复用 |
| `counselor_context.py` | 预注入本地 vault | 复用；vault 改按用户路由/加载 |
| Hermes 大脑 | Mini 本地 8642 | **挪到云端 worker**(或保留混合：会话大脑云、ASR 本地) |
| Tailscale Serve / NAT 终结 | 个人 overlay | **替换**为云信令 + TURN/SFU |
| `web_server.js` 反代 | Mini | 拆为云网关 + 静态托管(CDN) |
| `/api/save` | 写本地 vault | 按用户写云端/加密库(架构不变,目标变) |
| 手机 PWA | 连 tailscale URL | 连公网域名, 逻辑复用 |

---

## 5. 分阶段迁移路线

- **M0（现状冻结）**：个人版跑稳，积累真实会话数据与反馈；产品层(咨询师体验)不再因承载改动而返工。
- **M1（承载抽离）**：把「信令 + 媒体」从 `orchestrator_webrtc.py` 中抽象成可替换传输接口；先在同一台公网 VPS 上复刻个人版(仍单用户、但 VPS 有公网 IP 直连 WebRTC)，验证**去掉 Tailscale 后直连**是否满足延迟/抖动预算。
- **M2（多用户 + SFU/TURN）**：接 LiveKit 或 mediasoup 做 SFU/TURN + 信令；手机端走标准 WebRTC 对接；加入认证与每用户 vault/上下文路由。
- **M3（横向扩展）**：Hermes worker 池 + 会话调度 + 伸缩；ASR/TTS 就近部署或上 GPU；监控(延迟/抖动/成本)与配额。
- **M4（合规/上架）**：隐私政策、数据归属、加密存储、可能的端侧 ASR 以降成本/保隐私。

每阶段验收：**端到端首声延迟 + 抖动(WebRTC RTT/丢包/抖动缓冲)达标**，且 counselor 体验不回退。

---

## 6. 抖动/延迟关注点（公开版必须测）

- 在 WebRTC 层采集 `RTT / packetLoss / jitterBufferDelay`（RTCPeerConnection.getStats），建立基线，而非凭"有没有 VPN"判断。
- 承载(信令/SFU/TURN/云端位置) vs 处理(ASR/LLM/TTS)分别计量——抖动/卡顿主要归因到处理侧还是网络侧。
- 异地/蜂窝路径用 TURN/SFU 就近选路，控制回退抖动。

---

## 7. 待决策点

1. **承载技术选型**：LiveKit / mediasoup / 自建 TURN + 自研信令？
2. **Hermes 与 ASR 部署**：全云、全本地(边缘)、还是混合（会话大脑云 + 语音本地）？
3. **隐私/合规策略**：真实咨询内容是否加密存储、是否可审计、是否承诺不训练。
4. **单机"大脑即助理"的会话语义**是否在多租户下保持（每用户一个 counselor 上下文）。

---

## 8. 与主文档关系

- 本文件专注**承载/架构演进**；产品设计与验收仍以飞书文档 v0.2 为准。
- 阶段 M1 起的详细验收标准建议回填飞书文档对应章节。
