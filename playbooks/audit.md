> 状态（2026-10-22 同步）：按机场体系重做残留表保留（判据出处：项目仓 ADR-0137，历史，已由本仓 [0003](../docs/adr/0003-airport-rebuild-four-roles.md) 重述接管）；文中租约/班次/按铃/五角色等已退役机制以 0003 为准（日表＋Issue＋分支三件记录面、塔台独占 push）。

# 审计与通知

> 目标：任何一张票，事后都能回答“谁在什么时候、依据什么、改了什么、结果如何”。
> 审计不是聊天记录；不要把整段会话塞进日志。

## 一、事件日志

路径：项目配置 `audit.events`，默认 `.git/kai-scope/events.jsonl`（不进 git，追加写，不修改历史）。

每行一个 JSON，字段见 `schemas/event.schema.json`。最小示例：

```json
{"schema":1,"event_id":"a1b2c3...","ts":"2026-10-21T17:00:00+08:00","loop":"B","ticket":1854,"attempt":1,"actor":"group-a","role":"implementer","action":"task.started","from_state":"claimed","to_state":"running","target":"branch:exec/1854-v1-absorb","result":"ok","evidence":"worktree+.marker","cost":{"wallclock_s":3,"tokens":null}}
```

### 事件类型（建议）

| 类别 | action |
|---|---|
| 治理 | `task.ready`、`task.claimed`、`task.blocked`、`task.failed`、`task.requeued` |
| 执行 | `attempt.started`、`checkpoint.saved`、`commit.created`、`validation.started` |
| 反馈 | `validation.passed`、`validation.failed`、`repair.started`、`repair.stopped` |
| 交接 | `handoff.sent`、`handoff.rejected`、`activation.dispatched`、`activation.failed` |
| 出货 | `ship.validated`、`ship.pushed`、`task.landed`、`task.closed` |
| 安全 | `approval.required`、`approval.granted`、`policy.blocked`、`hold.set`、`hold.cleared` |
| 预算 | `budget.warning`、`budget.exhausted` |

## 二、记什么 / 不记什么

**记：**

- 触发原因、票号、attempt、执行器与模型配置（若有）。
- 开始/结束时间、墙钟、token 或明确 `null`。
- 分支、commit、push sha、PR 编号。
- 跑了哪些命令、退出码、关键 stdout 摘要（不是全文）。
- 验收逐条结果与证据路径。
- 状态变化、失败原因、下一步。
- 审批人、审批范围、有效期。

**不记：**

- 密钥、token、凭据、cookie。
- 整段聊天记录、完整 diff（用路径/commit 指针）。
- 用户隐私数据原文。
- 没有证据的“已确认/已完成”。

## 三、通知策略

只通知**有决策价值**的事件：

1. 票完成/落地（含 sha 与验收路径）。
2. 等待审批（要谁批什么、代价）。
3. 连续失败/熔断/停机。
4. 长期阻塞（超过项目阈值，默认 2 小时）。
5. 预算阈值（80%/100%）。
6. 安全策略拦截。
7. 需要用户肉眼看的视觉项。

**不通知：** 普通进度、每次重试、每条测试通过、正常的排队等待。这些进事件日志/日报正文，不打扰用户。

通知渠道由项目配置；本仓默认写日报一次＋终端摘要，不额外推送。

## 四、追溯链

一张票的完整证据链：

```text
Issue（合同+AC）
  → task-state-<票>.json（状态/attempt/租约/检查点）
  → events.jsonl（每次转移与证据）
  → branch + commits
  → acceptance-<票>.json（逐条 AC）
  → handoff（≤500 B 指针）
  → gate 输出 / push sha / PR
  → Issue close 评论（证据路径与 sha）
```

任何一环缺失，`closed` 都不算完整；Ground 关票前按这条链逐环核。

## 五、保留与清理

- 事件日志热保留 30 天；更早的按月归档（压缩），不删除已关票的证据文件。
- 验收文件、门输出、截图随票永久保留（在仓库或项目指定的证据目录）。
- 清理只清临时探针/中间读数，且必须确认不在任何票的证据链里。
- 不删未提交内容；不删别人的日志。

## 六、指标（按周看，不按单次看）

| 指标 | 定义 | 用途 |
|---|---|---|
| 关票数 | 本周 `closed` 的票 | 真实产出，不看“提交数” |
| 首次通过率 | 第一次 `validating` 就 pass 的比例 | 合同质量/实现质量 |
| 平均尝试次数 | `attempt` 总和 / 关票数 | 重试成本 |
| 同错率 | 同一错误签名重复的比例 | 是否在瞎试 |
| 阻塞时长 | `blocked` 到恢复的墙钟 | 人/依赖瓶颈 |
| 队列深度 | `ready` 票数 | 水位 |
| 落地时延 | `claimed` 到 `landed` | 流水线速度 |
| 每票成本 | wallclock/token | 预算与模型选择 |

指标只从事件日志与门 stdout 生成；**不许手写数字**。没有读数的指标写 `unknown`，不猜。
