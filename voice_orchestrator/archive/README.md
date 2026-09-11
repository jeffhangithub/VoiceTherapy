# archive/ — 已退役文件

这里放**曾经使用、现已停用**的文件，保留作历史参考，但不参与当前运行。

| 文件 | 退役原因 |
|---|---|
| `hermes_brain.py` | Phase 3.1 初始的独立 Hermes 客户端封装（自带 `X-Hermes-Session-Id` 契约）。主线已改为 `orchestrator*.py` + `counselor_context` 预注入 + `hermes_session` 指纹归档，此文件当前无任何引用。 |

> 说明：`hermes_brain.py` 里的 **`X-Hermes-Session-Id` / `mode` 系统消息注入** 等描述是早期设计，**与现行实现不符**——现行见 `../README.md` 的「Hermes 大脑连接契约」。
