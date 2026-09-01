# Hermes v0.18.0 集成合同核查

核查日期：2026-09-01。

核查对象：当前实际安装于 `/Users/ironsoul/.hermes/hermes-agent` 的 Hermes Agent。本文记录 Voice Gateway 可以依赖的本地合同，以及尚未完成的验证。

## 1. 证据等级

- **运行已确认**：Hermes Gateway 由 launchd 监管并正在运行。
- **源码已确认**：读取当前安装版本的实现和随附测试用例。
- **测试未执行**：运行时虚拟环境没有安装 `pytest`；本次未擅自下载开发依赖。
- **端到端未确认**：API Server 当前未启用，因此尚未以真实模型调用验证延迟、事件顺序和取消行为。

下述结论属于“当前本机源码合同”，不能替代下一阶段的真实 API 冒烟与延迟测试。

## 2. 推荐调用面

MVP 使用 Runs API：

```text
POST /v1/runs
GET  /v1/runs/{run_id}
GET  /v1/runs/{run_id}/events
POST /v1/runs/{run_id}/stop
```

选择原因：

- 创建接口立即返回 `202` 与 `run_id`，不会让手机连接等待整个 Agent 回合。
- SSE 事件包含 `message.delta`、`tool.started`、`tool.completed`、`reasoning.available`、`approval.request`、`run.completed`、`run.failed` 和 `run.cancelled`。
- `message.delta` 可直接进入回答分句器，满足流式 TTS 的前置条件。
- `/stop` 会调用当前 Agent 的 `interrupt()`，再取消包装任务。
- 状态接口便于手机断线重连后判断回合是否仍在运行。

## 3. 请求与状态策略

每次用户回合：

1. Voice Gateway 完成最终 STT 后提交 `POST /v1/runs`。
2. 请求携带稳定的应用会话 `session_id`、本回合 `input`、安全 `instructions` 和有界 `conversation_history`。
3. 收到 `run_id` 后订阅事件流。
4. 累积 `message.delta`，按自然短句切分并提交 TTS。
5. 收到 `run.completed` 后保存最终文本与 token usage。
6. 收到失败或取消事件后丢弃未确认的 TTS 队列。

Runs API 不提供 `/v1/responses` 的命名 `conversation` 自动链，因此多轮历史由 Voice Gateway 明确维护。第一版建议保留最近若干完整回合和一个滚动摘要，避免把无限增长的逐字历史重复发送给模型。

`X-Hermes-Session-Key` 是长期记忆作用域，不等于对话历史，也不等于授权命名空间。第一版只有在独立咨询 Profile 的 memory 策略确认后才启用。

## 4. 抢话与取消

抢话分成两个独立动作：

```text
手机检测到用户重新开口
  1. 立即停止本地音频播放器和清空待播放队列
  2. Voice Gateway 调用 /v1/runs/{run_id}/stop
  3. 取消尚未完成的 TTS 请求
  4. 开始新的 STT 回合
```

本地停播负责达到 400 ms 的可感知指标。Hermes 后端停止属于资源回收和防止旧回答继续产生；源码明确说明执行器线程不能由 `task.cancel()` 强制抢占，接口最多等待 5 秒，由 `agent.interrupt()` 协作退出。

## 5. 认证与网络边界

当前实现具备以下启动保护：

- 即使只绑定 loopback，也没有 `API_SERVER_KEY` 就拒绝启动。
- key 少于 16 字符或被识别为占位值时拒绝启动。
- Bearer token 使用常量时间比较。
- 浏览器 Origin 默认被拒绝；只有显式 CORS allowlist 才放行。
- 请求体上限为 10 MB。
- Agent 服务接口共享并发上限，默认是 10。

本项目约束：

- Hermes API 只绑定 `127.0.0.1`。
- 浏览器/PWA 不直接调用 Hermes，因此不需要为 Hermes 开启 CORS。
- API key 只存在于独立 Profile 与 Voice Gateway 服务端环境中。
- Voice Gateway 对外提供另一层个人身份认证，不复用 Hermes key。
- 个人语音场景把 Hermes `max_concurrent_runs` 调低到 2：一个当前回合和一个短暂取消中的旧回合。
- Hermes Profile 不启用 terminal、browser、automation 等非咨询工具。

## 6. 独立 Profile 策略

当前只有 `default` Profile，模型为 DeepSeek，且该 Profile 同时承载 Discord 与飞书配置。

后续不直接克隆整个 `.env`，以免把无关平台凭据带进咨询服务。确认本地开发后：

1. 创建名为 `therapyvoice` 的独立 Profile，不设为全局默认。
2. 只复制或重新配置必要的模型凭据。
3. 使用独立 API key、SOUL、安全规则、skills、memory、session DB 和日志。
4. 使用与默认 Gateway 不冲突的端口和独立后台服务名。
5. 验证默认 Discord/飞书 Gateway 在整个过程中不受影响。

## 7. API Server 启用后的必测清单

真实模型冒烟测试必须覆盖：

1. 无认证和错误认证返回 401。
2. `/v1/health` 正常，敏感接口仍要求认证。
3. `POST /v1/runs` 返回 202 与唯一 `run_id`。
4. 事件流按顺序出现 `message.delta` 和终态事件。
5. 两个不同 `session_id` 的历史互不串线。
6. `/stop` 后手机立即停播，Hermes 最终进入 cancelled 或停止状态。
7. 订阅中断后通过状态接口恢复，不重复播放旧 delta。
8. 并发上限生效；第三个同时回合被拒绝或排队。
9. Hermes 重启后，Voice Gateway 能给出明确错误并自动重连。
10. 日志中不出现 API key、咨询正文、完整 STT 音频或第三方凭据。

## 8. 下一决策门

仓库、Obsidian 目录、iPhone/车载蓝牙和 Mac mini 常驻方式均已确认。创建 Profile 前只剩语音方案需要确认：选择主 STT/TTS、备用服务，并确认相应云端服务可以短暂处理音频和合成文本。详见 `voice-provider-options.md`。
