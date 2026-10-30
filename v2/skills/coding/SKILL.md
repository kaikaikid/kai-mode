---
name: coding
status: active
approved_by: human:kaikaikid
approved: 2026-10-31
sources: []
description: >
  V2 执行内核的唯一入口：一个 issue 一个 run，主会话规划与验收，物理子会话执行；
  默认 2 个普通槽 + 1 个加急槽；一次触发连续跑到门点才停。用 `coding` 控制平面推进，
  不直接改 state.json。与机场体系（V1）并存，不调用其角色。
  触发：`/coding <任务>`、`/coding status`、`/coding resume`、`/coding gc`、`/coding adopt`；
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
2. **只在门点停**：G0 计划、G1 设计（碰可见 UI）、G2 发货。其余全自动。
3. **验收读 diff**：子会话报告是 claim，不是事实；必须看实际改动再 accept。
4. **子会话不发货**：删除、force push、merge 只能由主会话在 G2 后做。

## 流程

```
/coding <任务>
  → coding run "<任务>"            # 开 run（并发满则 queued）
  → 拆任务图 → coding plan        # 每任务：brief / tier / deps / touchset / ac / ui
  → G0：把任务图给用户看 → coding gate <run> g0 approve
  → （有 UI）G1：设计规格 → coding gate <run> g1 approve
  → 循环：
      coding next                 # 取 ready 任务
      coding spawn <run> <task>   # 起子会话
      coding report <run> <task>  # 收报告 + diff 对账
      读 diff 对照 ac → coding accept 或 coding return --defects "..."
  → 全部 accepted → G2：coding gate <run> g2 approve   # merge + 回收 worktree
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
| `coding report <run> <task>` | 收报告，校验 files_changed ⊆ git diff |
| `coding accept\|return\|reopen <run> <task>` | 验收 / 打回 / 撤销 |
| `coding resume <run>` | 从 state.json 续跑 |
| `coding status [--html]` | 看板（在做 / 在等 / 已完成） |
| `coding doctor` | 状态与 git 对账 |
| `coding gc [--all]` | 清理已收尾 worktree 与分支 |
| `coding stop <run>` | 停 run，保留状态 |

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
| 连续 return 2 轮 | 转 blocked，问用户或重规划 |
| merge 冲突 | run 转 blocked，在 worktree 解冲突后重试 G2 |
| 预算到线 | run 转 blocked，产出保留 |

## 与其他体系

- V1 机场体系：并存，命令与状态都不共享。装 V2 不动 V1。
- 创作体系：`/coding` 只管代码；作品交付走 `/producer` 等。
- 看板：`coding status` / `coding status --html`；不接 V1 航班信息。
