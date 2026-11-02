---
name: travel-only
status: active
approved_by: human:kaikaikid
approved: 2026-11-02
sources:
  - resource: "../../../v2/skills/travel/SKILL.md"
    note: "共享数据契约、状态机、门点、报告格式；本技能只换派活方式"
description: >
  V2 执行内核的「宿主原生」轨道：不用 travel 拉起 CLI 进程，改用当前宿主自己的子代理派活。
  主会话必须开着；不承诺无人值守；挂机走原 travel。技能只教流程与数据契约，不出现宿主专有命令。
version: 0.1.0
updated: 2026-11-02
allowed-tools: Read Grep Bash
compatibility: Requires git, python3, and a host that can spawn subagents
metadata:
  alias: 宿主原生
---

# Travel-only —— 用宿主自己的子代理跑 V2

> 共享正本：`v2/skills/travel/SKILL.md`（状态机、任务图、门点、报告契约、发货链）。
> 本技能只改三步：派活、收活、审查。其它一律引用正本，不复制。

## 这是什么

`/travel-only` 是 V2 的第二条轨道：**不拉 CLI 进程**，而是用你正在用的宿主（Claude Code、Codex、Qoder、……）自己的子代理来执行任务。

- 主会话 = 调度员：拆任务、占位、验收、过门。
- 子代理 = 工人/审查员：一段新上下文，只干一件事，报告落文件。
- 无人值守、挂机、飞书自动唤醒 → 走原 `travel`（CLI 进程），本技能不承诺这些。

## 铁律（继承正本，只补两条）

1. 能脚本就脚本：占位、对账、门点、验收仍走 `travel` 命令；**绝不手改 `.coding/runs/*/state.json`**。
2. 主会话必须开着：子代理活在主会话的调度下；主会话关了，调度就断了。想挂机去睡，用 `travel`。

## 流程

```
/warp <任务>（或已有 run）
  → travel next                     # 取 ready 任务
  → travel claim <run> <task>       # 原子占位，输出任务卡
  → 用本宿主的子代理执行任务卡     # 可写子代理，报告写到卡上的 report_path
  → travel report <run> <task>      # 读文件 + diff 对账
  → travel review <run> <task> --native   # 输出审查卡，不起进程
  → 用本宿主的只读子代理审查        # 报告写到卡上的 review_report_path
  → travel verdict <run> <task> --file <review_report_path>
  → travel accept / travel return   # 或让 verdict 直接推进
  → 门点按正本走
```

## 任务卡（travel claim 输出）

字段：`task_id`、`brief`、`worktree`、`touchset`、`ac`、`report_path`、`diff_base`。

- 子代理必须在 `worktree` 里工作，只改 `touchset` 范围内的文件。
- 完成后把报告写到 `report_path`（JSON，按正本 §报告契约）。
- `diff_base` 作 diff 基线；主会话用 `travel report` 对账。

## 审查卡（travel review --native 输出）

字段：`task_id`、`worktree`、`diff_base`、`changed_files`、`ac`、`touchset`、`review_report_path`、`read_only`。

- 必须用**只读**子代理（宿主的只读工具面 / 沙箱）。
- 审查员读实际 diff，对照 AC，输出 `{verdict: accept|return, defects:[], reason:""}` 到 `review_report_path`。
- 然后 `travel verdict <run> <task> --file <path>` 写回。

## 宿主适配（每个宿主自己写）

本技能不出现宿主专有命令。每个宿主的 `adapters/<宿主>.md` 必须写清三件事：

1. 怎么起一个**新上下文**（子代理 / 独立进程 / 新会话）；
2. 怎么把工具面锁成**只读**；
3. 报告文件**落盘到哪**、主会话怎么读回来。

宿主没有原生子代理 ⇒ 该宿主 `/travel-only` 不适用，走原 `travel`（CLI 进程）。

## 边界

- 不承诺无人值守、不承诺挂机、不承诺飞书自动唤醒。
- 不改发货链（merge / push / 关票）——按正本走。
- 不复制正本的流程、状态机、报告格式——一律引用。
- 主会话开着是前提；关了就断。

## 与原 travel 的分工

| 需求 | 走哪条 |
|---|---|
| 人就在电脑前、跑几票 | `/travel-only` |
| 挂机、sleep、飞书自动干活 | `travel`（CLI 进程） |
| 跨宿主、宿主没原生子代理 | `travel`（CLI 进程） |

两套共享同一本账（`.coding/runs/`），session 记 `mode: native` 或 `cli`，看板与 doctor 能分清。
