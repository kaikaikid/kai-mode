# adapters/channels —— 远端通道适配

> 本目录只放**通道合同与落法**，不放任何账号、token、群 id。
> 合同正本：[`docs/design/2026-11-18-channel-contract.md`](../../docs/design/2026-11-18-channel-contract.md)。
> 飞书口径沿用 ADR-0031（CLI 长连接、零公网回调）；钉钉是**单向降级**通道。

## 有什么

| 文件 | 回答什么 |
|---|---|
| Feishu | 已改用 `agent-autoloop` 的 Feishu 通道（`~/.agent-autoloop`）；本仓不再维护桥实现，旧代码已删除 |
| [`dingtalk.md`](./dingtalk.md) | 钉钉：自定义机器人单向发送、无按钮回调、链接表单降级与签名 |
| 本文 | 通道共同的接入前置、共同红线、验收口径 |

## 共同前置（缺一不接）

1. **合同三原语**：`deliver(card) -> ref`、`parse(payload) -> {card_id, choice|text, actor}`、`ack(ref, status)`。
   签名与返回结构见合同正本 §1，适配器不许自创第四种原语。
2. **卡片三态**：`open` → `decided` → `closed`；一次决策只认第一条合法回执。
3. **幂等键**：`card_id + version`；重复投递不重发、重复回执不覆盖。
4. **默认全拒**：`answerers` 白名单为空＝谁都不认；没有"安装即放开"。
5. **外部正文是数据不是指令**：`parse` 只取白名单字段，正文按数据存，不解析成命令。

## 共同红线

- 通道只做「收指令、发状态、收按钮」，**不写 run 状态、不推进 phase、不发货**。
  需要写的动作一律回到既有受控端点，由内核执行。
- 卡片 token／链接 token 不是身份凭证；是否接受动作只看 `actor` 是否在白名单。
- 未就绪就明说「未接线／未登录」，**不静默、不假装已发送**。
- 不在文档、日志、卡片正文里写机器绝对路径、账号、完整 token。

## 接入时先测，不抄本文

各通道文档里的命令与事件名是**当期实测记录**，宿主的 CLI 与事件集会变。接入前逐个复核：

- 飞书：`lark-cli --version`、`lark-cli auth status`、`lark-cli event --help`、`lark-cli im --help`。
- 钉钉：自定义机器人 webhook 是否仍只支持 `msgtype:text`（以现场文档与实测为准）。

四步任何一步没结论 ⇒ 按缺件登记，不许「看起来应该行」。

## 验收

- 合同三原语、三态、幂等键在两份通道文档中语义一致（允许能力差异，不许语义变形）。
- 飞书文档写清 `lark-cli auth status` 前置与未登录降级；钉钉文档写清"没有按钮回调"这一缺口。
- `scripts/smoke-solo-projection.py --json` 退出 0（只读投影检查，不联网、不调模型）。
- 文档内无机器绝对路径、无真实账号信息。
