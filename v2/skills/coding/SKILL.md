---
name: coding
status: active
approved_by: human:kaikaikid
approved: 2026-10-31
sources: []
description: >
  V2 执行内核的唯一入口：一个 issue 一个 run，主会话规划与验收，物理子会话执行；
  默认 2 个普通槽 + 1 个加急槽，每槽 1 个子代理；一次触发连续跑到门点才停。用 `coding` 控制平面推进，
  不直接改 state.json。与机场体系（V1）并存，不调用其角色。
  触发：`/coding <任务>`、`/coding status`、`/coding resume`、`/coding gc`、`/coding adopt`、`/warp <任务>`、`/jump <任务>`；
  中文「用 V2 做」「开个 run」也认。
version: 0.1.0
updated: 2026-10-31
allowed-tools: Read Grep Bash
compatibility: Host-agnostic
---

# Coding —— V2 执行内核入口

> 设计正本：`docs/design/2026-10-30-v2-execution-kernel.md`
> 实现：`v2/coding/`，命令 `v2/bin/coding`
> 安装：`v2/README.md`

## 这是什么

`/coding` 是 V2 的唯一交互入口。**你只跟主会话说话**；子会话是物理进程，
不直接找你。一次 `/coding <任务>` 管一个 run 的规划、派工、验收、发货全程。

与创作体系（`/producer` `/writer` `/artist`）和机场体系（`/pilot` `/tower` `/ace`）
严格分开：`/coding` 只做代码开发，不调用它们的角色，也不共用状态。

## 铁律

1. **能脚本就脚本**：状态推进、槽位、worktree、touchset、预算、续跑全走
   `coding` 命令；**绝不手改 `.coding/runs/*/state.json`**。
2. **只在门点停**：`/coding` 手动挡在 G0/G1/G2 停；`/warp` 自动挡由门卫子代理自动批门，只在红线/异常时停。
3. **验收读 diff**：子会话报告是 claim，不是事实；`coding review` 的门卫子代理读实际 diff 再裁决。
4. **子会话不发货**：worker 与 reviewer 都不 push/merge；发货只由主会话在门点后执行。

## 流程

```
/coding <任务>
  → coding run "<任务>"            # 开 run（并发满则 queued）
  → 拆任务图 → coding plan        # 每任务：brief / tier / deps / touchset / ac / ui
  → G0：把任务图给用户看 → coding gate <run> g0 approve
  → （有 UI）G1：设计规格 → coding gate <run> g1 approve
  → 循环：
      coding next                 # 取 ready 任务
      coding spawn <run> <task>   # 起 worker 子会话
      coding report <run> <task>  # 收报告 + diff 对账
      coding review <run> <task>  # 门卫子代理独立只读审查（新上下文）
      读裁决 → coding accept 或 coding return --defects "..."
  → 全部 accepted → G2：coding gate <run> g2 approve   # merge → 收尾门 → push → 关票
```

## 命令速查

| 命令 | 作用 |
|---|---|
| `coding run <issue> [--urgent] [--base main] [--depends r-x]` | 开 run |
| `coding adopt <issue>` | 晚激活：接管当前未提交改动为 baseline |
| `coding plan <run> --file tasks.json` | 写任务图 |
| `coding gate <run> g0\|g1\|g2 approve\|reject\|skip` | 过门；reject 有回流 |
| `coding next [run]` | 下一个可派任务（含 touchset / 槽位判断） |
| `coding spawn <run> <task> [--adapter ...]` | 起子会话 |
| `coding report <run> <task> [--timeout]` | 等 worker 结束，收报告，校验 files_changed ⊆ git diff |
| `coding review <run> <task> [--apply] [--adapter]` | 门卫子代理独立只读审查，产出 accept/return |
| `coding accept\|return\|reopen <run> <task>` | 验收 / 打回 / 撤销 |
| `coding resume <run>` | 从 state.json 续跑 |
| `coding status [--html]` | 看板（在做 / 在等 / 已完成） |
| `coding doctor` | 状态与 git 对账 |
| `coding gc [--all]` | 清理已收尾 worktree 与分支 |
| `coding stop <run>` | 停 run，保留状态 |
| `coding warp <issue> [--tasks f.json]` | 曲速全自动：自动批门 + 施工，**不发货**（停在 closing） |
| `coding jump <issue>` | 跃迁全自动：加急 + 自动发货，唯一有发货权的全自动入口 |
| `coding drive [--run r] [--adapter a] [--review-adapter b]` | 脚本无人值守跑完整条流水线 |

## 任务图

```json
{"tasks": [
  {"id": "t1", "title": "短名", "brief": "自包含任务书", "tier": "light|medium|careful|heavy|fable",
   "deps": ["t0"], "touchset": ["src/x/**"], "ac": ["可核的完成定义"], "ui": false}
]}
```

- `touchset` 重叠的任务不会并发；跨 run 重叠也排队。
- `ui: true` 才会触发 G1。
- `deps` 未 accepted/abandoned 时任务不 ready。

## 失败处理

| 现象 | 动作 |
|---|---|
| 子会话超时/崩溃 | `coding spawn --retry` 重试一次；再失败转 blocked |
| 报告解析失败 | 读 diff 自判，不重试 |
| 报告与 diff 不符 | 视为 partial，必须读 diff |
| 连续 return 3 轮 | 转 blocked，叫醒人 |
| merge 冲突 | 脚本自动 rebase 一次；仍冲突 → blocked |
| 发货失败（收尾门红 / push 被拒） | run 转 blocked，产出保留 |

## 曲速模式（/warp）

`/warp <任务> [--tasks tasks.json]` = 全自动挡：施工全程 AI 自推，门卫代理批 G0/G1/G2，只在红线/异常时停。
- `--tasks` 可在开 run 时直接写任务图；并发满时 run 排队，槽位空出后自动提升（`promote_queued`）。
- 普通槽 2 + 加急槽 1，同时跑最多 3 个 run；每 run 1 个子代理，全局最多 3 个。
- return 上限 3 轮，failed 重试 2 次，merge 冲突自动 rebase 一次。
- 发货权只归加急：普通 `/warp` 停在 closing（next_action 注明等发货），由舰桥或人工 `gate g2 approve` 发货；
  `/jump` 才自动发货 = merge → 收尾门 → push → 关票，全脚本化。
- push 目标默认 `dev`（dev 不存在则退回当前分支）。
- issue 引用自动识别：任务文本里的 `#123` 或 GitHub issue URL 会自动关票；识别不到则跳过，不阻塞发货。
- `coding drive` 是零干预驱动：脚本循环 spawn → report → review → accept，槽位空出自动提升排队 run，直到全部终态或 blocked。
- `coding drive --review-adapter mock` 可让审查走更便宜的适配器（生产默认与 worker 相同）。

## 跃迁触发（/jump）

`/jump <任务>` = 跃迁（加急）：走加急预留槽，不抢占普通 run，touchset 重叠时排队到该任务验收。
未显式触发时一律问用户是否用 `/jump`（跃迁）。

## 触发策略

未显式指定命令时，一律先问用户：「是否用 `/jump` 跃迁？」
用户确认后再执行；不自行决定。

## 与其他体系

- V1 机场体系：并存，命令与状态都不共享。装 V2 不动 V1。
- 创作体系：`/coding` 只管代码；作品交付走 `/producer` 等。
- 看板：`coding status` / `coding status --html`；不接 V1 航班信息。
