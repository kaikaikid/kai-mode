# 飞书桥：远端收发面（设计正本）

> 状态：**方案定稿，实现另排**（2026-11-01 用户拍板「按照这个方案做……你只写方案，
> 通过 set-kai-mode 初始化新设置」）。
> 决策记在 [`docs/adr/0031-feishu-bridge.md`](../adr/0031-feishu-bridge.md)。

## 0. 一句话

**常驻脚本负责收、发、去重、鉴权、分诊和回调，零 token；只有白名单真人发来「需要判断」的话，
才唤醒一次 AI 会话。**

它让用户从飞书发起任务、看进度、点按钮拍板；它**不是**第二个舰桥——不推进 phase、不施工、
不替用户做产品取舍，也**不直接写** `.coding/runs/*/state.json`。

## 1. 事实基线（2026-11-01 本机实测）

| 事实 | 读数 |
|---|---|
| `lark-cli` | 1.0.93 已装；应用 `cli_aa17130cdab89bee`（feishu）已绑定 |
| 身份 | bot 就绪；无 user login（桥只用 bot 身份，**不算缺件**） |
| 事件通道 | `lark-cli event consume <EventKey>` 自起本地 bus daemon ＋ Feishu **WebSocket**；实测 `feishu-websocket: connected`；NDJSON 到 stdout 或 `--output-dir`，**不需要公网回调** |
| 关心的事件 | 用户消息、`card.action.trigger`（按钮，回传带 30 分钟卡片 token）、机器人被拉进群 |
| 出站 | `im +messages-send` / `+messages-reply`，支持 `--msg-type interactive` 与 `--idempotency-key` |
| 机器人所在群 | **0 个**（建群/拉群归安装阶段，见 §12） |

## 2. 不是什么

- 不是调度器：`travel drive` 仍是唯一的无人值守执行循环。
- 不是验收面：`travel accept/return/reopen` 不在桥上暴露；验收永远读 diff。
- 不是第二个真相源：run 的真相是 `.coding/runs/*/state.json`。
- 不做多应用/多仓路由：本轮一个机器人应用对应一个桥进程。

## 3. 架构

```
飞书 ──WebSocket──▶ lark-cli event consume ──▶ 收件箱(.coding/feishu/inbox/live/)
                                                    │ 去重(ledger) → 白名单(policy) → 分诊(triage)
                                                    ▼
                         ┌──────────────┬───────────┴────────────┐
                   确定性动作        需要判断              未授权
                 (记想法/开票/        (唤醒一次 AI)          (丢弃+审计)
                  gate/stop)              │
                         └──────▶ travel / travel serve ◀──────┘
                                        │
   飞书 ◀── outbox(重试/幂等) ◀── notify 轮询 state.json（完成/卡住/等拍板，零 token）
```

| 组件 | 落点 | 职责 |
|---|---|---|
| consumer | `v2/coding/feishu/consumer.py` | 每个 EventKey 一个 `lark-cli event consume` 子进程，规范化后写收件箱；断线退避重启 |
| ledger | `v2/coding/feishu/ledger.py` | stdlib sqlite3：事件去重、命令状态、run↔chat 绑定、outbox 索引 |
| policy | `v2/coding/feishu/policy.py` | 白名单、限速、@剥离、动作 HMAC 校验 |
| triage | `v2/coding/feishu/triage.py` | 命令解析与三路分流 |
| wake | `v2/coding/feishu/wake.py` | 串行唤醒一次宿主会话（复用宿主适配器），带冷却/超时/预算 |
| notify / outbox | `v2/coding/feishu/notify.py`、`outbox.py` | 状态指纹比对、三型卡片渲染、发送与退避重试 |
| callback | `v2/coding/feishu/callback.py` | 卡片动作 → 鉴权 → POST `travel serve` |
| 入口 | `v2/coding/feishu_main.py`、`v2/bin/feishu-bridge(.cmd)` | 单实例 pid、子进程守护、日志 |
| 契约 | `v2/skills/travel/feishu-bridge.md` | 事件/动作/出站三个信封，随技能分发 |
| CLI | `travel feishu serve\|status\|doctor\|show\|reply\|replay\|gc\|send-test` | 人读与自检入口；`show`/`reply` 是 AI 唯一能碰收件箱与回话的两条命令 |

运行态全部落 `.coding/feishu/`（`.coding/` 已在 `.gitignore`）：
`bridge.pid`、`inbox/{live,raw,quarantine}/`、`ledger.sqlite3`、`outbox/`、`snapshots/`、`wake/`、
`audit/`、`logs/`、`secret.json`。

Windows 静默：直接子进程一律 `CREATE_NO_WINDOW`；常驻用 `pythonw` 或计划任务 `wscript //B`。
lark-cli 自起的 bus daemon 是否另弹控制台**待实测**，若是则用 `.vbs` 包裹。

## 4. 收件箱契约

- 一个事件一个文件：`inbox/live/<received_ms>-<dedup_key>.json`，只由 consumer 写，`tmp` + `os.replace`。
- 原始行留 `inbox/raw/<event_key>/<received_ms>.ndjson`（排障用，7 天）。
- 解析失败进 `inbox/quarantine/`，带原因。
- 信封 `schema: kai-mode-feishu-event/1`：必填 `dedup_key / event_key / received_at / kind`，`event_id`（投递 ID）一并记下便于排障；
  `kind ∈ {message, card_action, bot_added, unknown}`。
- **去重键按事件类型分**（`lark-cli event schema` 明文：`event_id` 是投递 ID，**不可**作消息去重键）：
  消息事件用 `message_id`；卡片动作用 `nonce`；其它事件用 `event_id`。
  消息事件再退化为 `sha256(chat_id + create_time + content)`（字段名以 schema 为准），并记 `dedup_source`。
- 保留：live 30 天、raw 7 天、audit 90 天、ledger 90 天；**pending/wake 永不自动删**。
- AI 不直接翻收件箱，只读 `travel feishu show <event_id>`。

## 5. 白名单与鉴权（默认全拒）

- `allow.users[]`（open_id）、`allow.chats[]`（chat_id）、`allow.dm`、`require_mention`。
  **默认全空 = 谁都不认**；没有「安装即放开」。
- 群消息：必须 @机器人 ∧ chat 在白名单 ∧ 发送者在白名单。
- 卡片动作：open_id 在白名单 ∧ 会话已绑定 ∧ 动作 HMAC 通过 ∧ nonce 未用过。
  **卡片 token 不是身份凭证**，只用于更新卡片。
- `bot_added` 只记账并通知固定群，**不自动把新群加白**。
- 未授权：不外发、不执行，写 `audit/unauthorized.ndjson`（默认只存正文哈希与长度）。
- 限速：每用户 10 条/分钟、100 条/小时。
- 密钥只放 `.coding/feishu/secret.json` 或环境变量，不进任何 tracked 文件、不进日志。

## 6. 分诊（确定性优先）

| 消息 | 判据 | 动作 | 唤醒 AI |
|---|---|---|---|
| `状态` | 命令词 | 读 `serve /api/runs` 回状态卡 | 否 |
| `想法 <原文>` | 前缀 | 写 `<ideas_dir>/YYYY-MM-DD-<slug>.md`，原文一字不改 | 否 |
| `票 ...` 六件套齐 | 目标/AC/允许/禁止/验证/依赖与红线 | `gh issue create`，正文带 `<!-- kai-mode-feishu:<message_id> -->` | 否 |
| `票 ...` 缺件 | 缺任一件 | 起草 → 「开票」确认卡，点按钮才建票 | 是 |
| `曲速/跃迁` 自带任务图 | 消息含合法 tasks JSON | `travel warp/jump --tasks` | 否 |
| `曲速/跃迁` 只有一句话 | 无任务图 | 拆图后再调 `travel warp/jump` | 是 |
| `批/拒 g2 <run>`、`停 <run>` | 命令词 | POST `serve` 的 gate/stop | 否 |
| `发货 <run>` | 命令词 | 先回确认卡，点「确认发货」才 POST g2 | 否 |
| 其他文本 | 未命中 | 入 wake 队列 | 是 |

规则：脚本只做确定性动作；AI 只做规划、起草、自由问答；**红线由人定**（发货、删未提交内容、花钱、对外发布），
桥不自我批准。

## 7. 出站：三型卡片

notify 每 15 秒比对一次 `state.json`（serve 在线则读它的 `/api/runs`），指纹稳定 10 秒才发，同状态不重发。
**没有心跳，没有日报。**

| 卡片 | 触发 | 卡面 | 按钮 |
|---|---|---|---|
| 完成 | `phase=done` | 结果一句话、run、票号/commit、是否 push、关票结果 | 详情 |
| 卡住 | `phase=blocked` / 发货失败 / 审查无结论 | 卡在哪、为什么、试过几轮、建议下一步 | 重试 drive / 停止 / 详情 |
| 等拍板 | G0/G1/G2 pending / `phase=closing` | 哪个门、要拍什么、任务图或设计摘要 | 批准 / 打回 / 稍后（G2 追加「确认发货」） |

回话目标：`run_bindings(run_id → chat_id, origin_message_id)`。飞书发起的 run 回原会话（超出回复窗口就发同群）；
本地发起的 run 发默认群。**卡片文案由模板生成，不交给 AI 写**；AI 的回复另发文本并标 `source=ai`。

## 8. 按钮：只走 `travel serve`

- `gate → POST /api/runs/<id>/gate {gate, decision}`；`stop → /api/runs/<id>/stop`；`重试 → /api/drive`。
- 全部要求 `X-Travel-Token`；**不新增写端点**，不绕过 serve 的 Host/Origin/body 上限校验。
- 桥不 import `v2.coding.state`，不调 `save()`，不写 `state.json`（验收用源码检查证明）。
- 30 分钟卡片 token：只用来原地更新卡片，**不作授权**。超过 25 分钟直接发新卡；
  更新失败（错误码待实测）记 `card_update_expired` 并补发新卡，不静默失败。
- 待拍板超过 20 分钟重发新卡，最多 3 次；之后不再打扰。
- 双击：同 nonce 第二次直接回「已处理」；G2 仍受 `travel gate` 自身的 phase/任务/活会话守卫。

## 9. 幂等与断线

| 层 | 键 | 做法 |
|---|---|---|
| 事件 | 消息 `message_id`／卡片 `nonce`／其它 `event_id` | ledger `INSERT OR IGNORE`，重复只计数 |
| 命令 | `sha256(去重键 + 规范化命令)` | 先写 intent 行，成功写结果；崩溃靠状态恢复 |
| 卡片动作 | `run_id + kind + nonce` | nonce 一次性 |
| 出站 | `--idempotency-key = kaimode:<run_id>:<transition>:<updated_at>` | 重试不产生重复卡 |
| 开票 | issue 正文 `<!-- kai-mode-feishu:<message_id> -->` | 建票前按标记搜一次；只在这时调 `gh` |
| 开 run | ledger `origin_dedup_key` | 同一条消息不重复开舰队 |

consumer 退出后按 1s/2s/5s/10s/30s 退避重启；`bridge.pid` 单实例。
重连记缺口 `[last_event_at, reconnect_at]`；能补读就补读并按 id 去重，**补不了就发「可能漏消息」卡**，
不假装事件齐全。

## 10. 唤醒 AI：复用宿主适配器

- 一次唤醒 = 一次 `adapters.pick()` → `spawn(brief, cwd, session_dir, tier, read_only=False)`，
  与 worker 同一套机制（契约见 [host-adapter.md](../../v2/skills/travel/host-adapter.md)）。
- 串行、单飞：同一时刻只有一个唤醒会话；冷却 60 秒/用户，超时 600 秒，单次预算上限（默认 200k tokens）。
- 输出必须经 `travel feishu reply --wake <id>` 回到原会话；AI 不能直接调飞书。
- 状态变化、定时器、`bot_added`、未授权消息**一律不唤醒**。

## 11. 配置落点

**机器级**：`<KAI_AGENT_DATA_ROOT>/kai-mode/feishu.json`（与宿主适配器的信任表同一层）——
存 app 绑定、open_id 白名单、默认 chat_id、serve 地址与 token 变量名。这些是**机器绑定事实**，
不该跟着仓库走。

**项目级（可选）**：`.coding/feishu.json` —— 这个仓接不接、发到哪个群。

**不动** `templates/kai-mode.project.json`，不升 schema：项目实例里放 open_id / chat_id / token
等于把机器事实写进 tracked 文件，而且 schema 5→6 要连带改 init-project、check-instance 和所有旧实例迁移，
代价远大于收益。

## 12. 安装：交给 set-kai-mode

缺口扫描新增第 11 项「飞书桥」，安装步骤新增第 7 步「飞书桥（可选）」，验收与缺件三格写在那两处。
要点：

- 探法全只读：`lark-cli --version`、`auth status`、`event list`、`im +chat-list --as bot`、
  群成员 `bots[]`；**不做** `event consume`（会起 daemon）、不建群、不发消息。
- **建群与拉机器人由安装 agent / 用户完成**：优先 `lark-cli im +chat-create --as bot`（bot 是创建者，
  自动在群）；拉入既有群需群主/管理员操作，agent 只报「需要谁在飞书里点哪一步」。
- 运行时桥**不碰群成员**：不建群、不拉人、不退群、不发欢迎语。

## 13. 验收判据

| # | 判据 |
|---|---|
| 1 | 非白名单用户发言：零外发、零执行，`audit/unauthorized.ndjson` 恰好一条 |
| 2 | 状态变化到发出 ≤ 60 秒（15 秒轮询 ＋ 10 秒稳定 ＋ 余量） |
| 3 | 40 分钟前的卡片点击：要么执行并补发新卡，要么明确回「卡片已过期」，不得静默、不得重复改状态 |
| 4 | 双击 G2 只发一次货，第二次回「已处理」 |
| 5 | 杀掉 consumer：30 秒内重启，重放同一事件不产生重复卡 |
| 6 | 源码检查：`v2/coding/feishu/` 里没有 `state.save(`、没有直接写 `state.json` 的路径 |
| 7 | Windows 上启服务、发卡、回调全程不弹控制台 |
| 8 | `travel feishu doctor` 能报：lark-cli 版本、app、机器人所在群、consumer 心跳、serve 健康、outbox 积压、最后事件时间 |

## 14. 不做什么

不建群/拉人/退群、不直改 state.json、不推进 phase、不 spawn/review/accept、不自动开票、
不轮询 GitHub、不做常驻 AI 或定时唤醒、不解析语音图片文件、不做权限分级、
不做公网回调与跨群广播、不用 AI 写状态卡文案、不改 `travel serve` 的绑定与鉴权模型。

## 15. 待实测确认

事件字段路径（`event_id`/`open_id`/`chat_id`/`message_id`）、群消息是否仅 @ 时投递、
撤回/编辑是否产生事件、卡片原地更新与 token 过期错误码、30 分钟后旧卡按钮是否仍投递、
消息历史补读子命令、bus daemon 是否弹控制台、出站频率与卡片大小上限。
