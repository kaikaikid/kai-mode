# 班次剧本 · 通用契约（v0.1）

> 项目专用剧本优先：项目 `<paths.shifts>/<role>.md` 存在时按它执行；没有才用本目录的参考剧本。
> 本文件只定义**跨项目不变的契约**：谁写哪个文件、结果码、handoff、按铃与验收。

## 一、角色与单一写者

| 角色 | 只负责 | 唯一写 |
|---|---|---|
| Tower | 排班、队列、租约、水位/刹车 | `plan.json`、`dispatch-queue-*`、租约 |
| Ground | 并车、门、push、关票、清账、回收已并树 | `ship-ledger`、push 结果 |
| Coordinator | 调度决策、停机牌、闸门、冷却 | `dispatch-plan`、`hold-*`、`gate-state` |
| Group-A/B | 施工、本地提交、验收证据 | `status-group-*`、`acceptance-*`、handoff |
| 用户 | 清停机牌、改方向、拍红线 | —— |

**一个语义一个写者**；接收方可以读，但不得改别人的文件。

## 二、状态文件（都住 `paths.state_dir`，不进 git）

| 文件 | 写者 | 读法 |
|---|---|---|
| `dispatch-queue-<group>.json` | Tower | `{schema,lane,tickets[],version,issued_at,issued_by}`；原子写 |
| `lease-<票>.json` / `current-task-<票>.json` | Tower 建，Group 销 | 允许改的文件清单；没租约不飞 |
| `status-<role>.json` | 该角色 | 四格：`result`／`tickets`／`commits`／`blocker`（必要时 `unverified`） |
| `handoff-<from>-<to>.json` | 发起角色 | 见 §四 |
| `acceptance-<票>.json` | Group 的 reviewer | 见 `playbooks/acceptance.md` |
| `ship-ledger.jsonl` | Ground | 每批一行：票号/commit/push/sha/门读数 |
| `dispatch-plan.json` | Coordinator | 该叫谁、为什么、冷却 |
| `activation-receipt-<ts>.json` | 启动器子会话 | 目标/jobId/run id/结果/失败原因 |
| `hold-<role>`／`hold-all` | Coordinator、用户 | 读到就停，不自动清 |
| `gate-state.json` | Coordinator | 闸门是否开、上次检查时间 |
| `relay-ledger.jsonl` | 各角色追加 | 报表/metrics 的唯一流水 |

## 三、结果码（只许这些）

`working`／`handoff`／`no-work`／`need-schedule`／`need-ship`／`blocked`／`need-user`／`stuck`／`done`／`partial`／`paused`。

- `need-schedule` ⇒ Tower；`need-ship` ⇒ Ground。
- `blocked` 必须带 `blocker` 原因与可验证指针（票号/路径/命令读数）。
- `done` 只在 `unverified=[]` 且无待发时写；否则 `partial`。
- 停机牌与闸门归 Coordinator；角色只写 `need-coordinator`/`blocked`，不自行清牌。

## 四、handoff（≤500 B，可验证指针）

```json
{"schema":1,"from":"group-a","to":"ground","tickets":[1829],"commits":["c592c8ec6"],"branch":"exec/1829-v4-knife2-3","acceptance":{"path":".git/kai-scope/acceptance-1829.json","sha256":"..."},"at":"2026-10-21T14:30:00+08:00","seq":7}
```

必带：`schema/from/to/tickets/commits/branch/acceptance/at/seq`；有阻塞加 `blocker`。

**只传指针，不改写结论**：不写“测试都过了／验收通过”，只给验收路径与哈希；Ground 自己读 `verdict`。

**接收方二次核验**：Ground 不信 handoff 的结论，自己跑 close-gate／push-preflight；状态卡 `done` 前必须 `unverified=[]`。

## 五、按铃（启动适配器）

- 目标在岗（令牌 holder 非空且心跳新鲜或 `runningAt` 非空）⇒ 只留 handoff，不按。
- 按铃走项目 `.ai/kai-mode.project.json` 的 `activation` 适配器。
- Qoder 推荐：`create_chat_session` 开“只按铃子会话”，子会话 `qoder_cron run`；模板见 `adapters/qoder.md`。
- 子会话只读 handoff＋注册档＋令牌＋验收摘要；≤3 次工具调用；不读票面/验收全文。
- 失败写 `activation-failed`／`missing-jobid`／`no-launcher`，由低频 Coordinator 兜底。

## 六、正常链路

```text
Tower ──队列/租约──► Group-A/B ──本地提交──► Ground
  ▲                      │                      │
  └──── 要新排班 ────────┘                      │
  ▲                                             │
  └──────────── 库存下降/要补排班 ──────────────┘
```

Coordinator 只处理链断、启动失败、连续失败、停机牌/闸门变化、全仓无活；正常链路不经过它。

## 七、迁移

新角色上线前先自证：一次 handoff 能叫起目标、重复 handoff 只起一次、缺字段/不可达/验收不过时目标不起。确认后停用旧班次；旧 job id 至少保留一个试点周期。
