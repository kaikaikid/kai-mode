# 飞书通道：lark-cli 长连接 ＋ 交互卡片

> 合同正本：[`docs/design/2026-11-18-channel-contract.md`](../../docs/design/2026-11-18-channel-contract.md)。
> 设计出处：ADR-0031（用 CLI 长连接做远端收发面，不做公网回调）。
> 本文只写**落法**；命令与事件名以现场 `lark-cli` 的 `--help` 与实测为准。

## 0. 前置：先看登录态

```bash
lark-cli --version
lark-cli auth status
```

- `auth status` 显示 bot 身份可用 ⇒ 才允许谈「已接线」。
- 未登录／未授权 ⇒ 通道状态标 **未接线**，投递直接失败并明说原因；
  **不许**回退到"假装已发送"或静默丢弃。安装期按缺件登记。
- 不把任何账号信息写进本仓：app 绑定、白名单、默认群都住机器级配置。

## 1. 入站：长连接，不用公网回调

- 事件来源：`lark-cli` 的 bus daemon 建立 **Feishu WebSocket**，事件以 **NDJSON** 推出；
  桥只消费 NDJSON，不监听公网端口、不配回调 URL、不做轮询。
- 消费入口（当期记录）：

```bash
lark-cli event consume card.action.trigger
```

  事件名／订阅参数以 `lark-cli event --help` 现测为准；换版本先复核再改脚本。
- 事件流只落本地文件或内存队列；**不把原始 payload 转发到任何外部地址**。

## 2. 出站：交互卡片与幂等键

| 合同原语 | 飞书落法 |
|---|---|
| `deliver(card) -> ref` | `lark-cli im +messages-send`（或 `+messages-reply`）发交互卡片；`ref` 取返回的 message_id |
| `ack(ref, status)` | 用同一 message_id 更新卡片（补发新卡时 `ref` 换成新卡的 message_id） |
| `parse(payload)` | 只从事件里取 `card_id`／`choice`／`text`／`actor`（open_id），其余丢弃 |

- 卡片投递带**幂等键**：`card_id + version`；同键重复投递不重发。
- 按钮选项必须在卡片定义里显式列出；回调里的 `choice` 不在选项表内 ⇒ 视为非法，丢弃并审计。

## 3. 鉴权：白名单 ＋ HMAC/nonce

1. **白名单**：`answerers`（open_id 列表，可另配 chat_id）默认空＝全拒。
   `actor` 不在白名单 ⇒ 不执行动作、不外发、只留审计（默认只存正文哈希）。
2. **HMAC**：动作回调带签名，覆盖 `card_id + version + choice + actor + nonce`；
   签名密钥只住机器级配置与环境变量，**不进仓、不进卡片正文、不进日志**。
3. **nonce 一次性**：每个 nonce 只接受一次；重复 nonce ⇒ 直接丢弃（防重放）。
4. **卡片 token 不是身份凭证**：它只用于更新卡片；能不能动只看 `actor` 与 HMAC。
5. 校验顺序固定：`nonce 未用过` → `HMAC 正确` → `actor 在白名单` → `卡片状态为 open`
   → 幂等键未消费。任一步失败即停，失败原因写审计。

## 4. 三态与过期

- 卡片从 `open` 起；第一条合法回执把状态推到 `decided` 并记录 `actor` 与选项；
  外层处理完调 `ack(ref, "closed")` 收口。
- 飞书按钮有 **30 分钟失效**的外部约束（ADR-0031 记录）。过期后按钮点不动，
  不是错误状态：**补发新卡**（新 `card_id`、version+1），旧卡 `ack(ref, "closed")`。
- 重复点击、重复回调一律按幂等键丢弃，不覆盖已 `decided` 的结果。

## 5. 能力与降级（必须明说）

| 场景 | 行为 |
|---|---|
| `lark-cli auth status` 未就绪 | 状态=未接线；投递失败并回报"飞书未登录"；表单/文本回执一并不可用 |
| WebSocket 断开 | 重连；断开期间不接单，恢复后从 NDJSON 断点续读（按实现层游标） |
| 卡片过期 | 补发新卡，旧卡 closed；不原地更新 |
| 白名单为空 | 全拒；只审计，不外发 |
| 群被解散/机器人被移出 | 投递失败，状态标未接线并登记缺件 |

降级必须写进回执：哪条通道、降到什么形态、缺哪项能力——**不静默**。

## 6. 不做

- 不建群、不拉人、不改群成员（归安装阶段，见 ADR-0031 D6）。
- 不写 run 状态、不推进 phase、不发货；写动作一律回受控端点。
- 不读附件/富文本树/引用消息；正文只按数据存。
- 不把外部正文当指令拼进命令或提示词。
