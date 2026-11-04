---
name: fleet
status: active
approved_by: human:kaikaikid
approved: 2026-10-31
sources: []
description: >
  舰队执行内核（由舰桥调度）：一个 issue 一个 run（舰船），主会话规划与验收，宿主自己的子代理执行；
  舰队（fleet）= 同一宿主拉起的 run 集合，舰船数 1–3（默认 2）、船员数（并发子代理）1–5（默认 5）按舰队独立计数；
  一次触发连续跑到门点才停。用 `travel` 控制平面推进（`coding` 兼容别名一版），不直接改 state.json。
  只走宿主原生子代理，不拉 CLI 进程。由舰桥在开船时调用（用户口令 `/warp`、`/jump` 归舰桥）；
  控制面命令 `travel <子命令>`（`coding` 兼容一版）；中文「用舰队做」「开个 run」也认。
version: 0.7.0
updated: 2026-11-05
allowed-tools: Read Grep Bash
compatibility: Host-agnostic; host must be able to spawn subagents
---

# fleet —— 舰队执行内核（星际穿越剧本）

> 设计正本：`docs/design/2026-10-30-v2-execution-kernel.md`
> 实现：`engine/coding/`，命令 `engine/bin/travel`（`engine/bin/coding` 兼容别名一版）
> 安装：`engine/README.md`

## 这是什么

`/warp` `/jump` 由舰桥触发，fleet 只负责施工执行与验收。**你只跟主会话说话**；施工交给宿主自己的子代理，
不拉起 CLI 进程，也不要求挂机。主会话开着，调度就在；关了就停了。

与创作体系（`/producer` `/writer` `/artist`）严格分开：fleet 只做代码开发，不调用它们的角色，也不共用状态。

## 铁律

1. **能脚本就脚本**：状态推进、槽位、worktree、touchset、预算、续跑全走
   `travel` 命令；**绝不手改 `.coding/runs/*/state.json`**。
2. **插话在会话里，自动在 `travel auto` 里**：`travel claim` 输出任务卡，主会话用本宿主的子代理执行；
   `travel review` 输出审查卡，用只读子代理审查。人不在线时由 `travel auto` 驱动，它只调
   `.coding/config.json` 的 `worker_cmd` / `reviewer_cmd`（或环境变量 `TRAVEL_WORKER_CMD` / `TRAVEL_REVIEWER_CMD`）配好的宿主命令（宿主的 headless 一次性会话），
   内核不内置任何厂商适配器；不配就如实报缺件。
3. **只在门点停**：手动挡在 G0/G1/G2 停；`/warp` 自动挡由门卫子代理自动批门，只在红线/异常时停。
4. **验收读 diff**：子代理报告是 claim，不是事实；`travel report` 对账 diff，主会话读实际 diff 再裁决。
5. **子会话不发货**：worker 与 reviewer 都不 push/merge；发货只由主会话在门点后执行。

## 流程

```
/warp <任务>
  → travel run "<任务>"            # 开 run（并发满则 queued）
  → 拆任务图 → travel plan        # 每任务：brief / tier / deps / touchset / ac / ui
  → G0：把任务图给用户看 → travel gate <run> g0 approve
  → （有 UI）G1：设计规格 → travel gate <run> g1 approve
  → 循环：
      travel next                 # 取 ready 任务
      travel claim <run> <task>   # 原子占位，输出任务卡（不起进程）
      用本宿主的可写子代理执行任务卡   # 方法：`tdd`（先红后绿）；报告写到卡上的 report_path
      travel report <run> <task>  # 读文件 + diff 对账
      travel review <run> <task>  # 输出审查卡
      用本宿主的只读子代理审查        # 方法：`code-review`（Standards / Spec 双轴）；报告写到 review_report_path
      travel verdict <run> <task> --file <path>
  → 全部 accepted → G2：travel gate <run> g2 approve   # merge → 收尾门 → push → 关票
```

## 方法（按名用宿主中央库原版）

各节点点名方法，本技能不复述正文；宿主中央库没有就按缺件登记，不假装已具备。

| 节点 | 方法 | 用在哪一步 |
|---|---|---|
| 拆任务图 | `to-tickets` | 需求 → 可验收的票与任务卡 |
| 施工 | `tdd` | 接缝＝任务 AC 里的验证命令；非代码票不硬写测试 |
| 审查 | `code-review` | 只读子代理按 Standards / Spec 双轴读实际 diff |
| 连续失败 | `diagnosing-bugs` | 两轮还不过先造反馈环，不盲改 |
| 术语 / ADR | `domain-modeling` | 涉及新概念或长期结构时 |

## 任务卡与审查卡

`travel claim` 输出：`task_id`、`brief`、`worktree`、`touchset`、`ac`、`report_path`、`diff_base`。

- 子代理必须在 `worktree` 里工作，只改 `touchset` 范围内的文件。
- 完成后把报告写到 `report_path`（JSON，见下方报告契约）。

`travel review` 输出：`task_id`、`worktree`、`diff_base`、`changed_files`、`ac`、`touchset`、
`review_report_path`、`read_only`。

- 必须用**只读**子代理；读实际 diff，对照 AC，输出 `{verdict: accept|return, defects:[], reason:""}`。
- 然后 `travel verdict <run> <task> --file <path>` 写回。

## 报告契约

```json
{"result": "done|partial|blocked",
 "files_changed": ["path — 改了什么"],
 "commit": "<HEAD sha，没有改动则为空>",
 "verification": ["命令 -> 结果"],
 "open_questions": ["..."],
 "notes": "<=100 字"}
```

解析失败 = 视为 `partial`，主会话读 diff 自判。

## 命令速查

| 命令 | 作用 |
|---|---|
| `travel run <issue> [--fleet id] [--ships 1-3] [--crew 1-5] [--urgent] [--base main] [--depends r-x]` | 开 run（舰队） |
| `travel adopt <issue>` | 晚激活：接管当前未提交改动为 baseline |
| `travel plan <run> --file tasks.json` | 写任务图 |
| `travel gate <run> g0\|g1\|g2 approve\|reject\|skip` | 过门；reject 有回流 |
| `travel next [run]` | 下一个可派任务（含 touchset / 槽位判断） |
| `travel claim <run> <task>` | 原子占位，输出任务卡（不 spawn） |
| `travel release <run> <task>` | 释放原生占位，任务回 pending |
| `travel report <run> <task>` | 读子代理报告，校验 files_changed ⊆ git diff |
| `travel review <run> <task>` | 输出审查卡（只读子代理执行） |
| `travel verdict <run> <task> --file <path>` | 写回审查裁决（accept/return） |
| `travel accept\|return\|reopen <run> <task>` | 验收 / 打回 / 撤销 |
| `travel resume <run>` | 从 state.json 续跑 |
| `travel status [--html]` | 看板（在做 / 在等 / 已完成） |
| `travel dirty [--json]` / `park` / `unpark` | 主树脏件分类与可逆收起 |
| `travel stop <run>` / `travel gc [--all]` | 停 run / 清已收尾资源 |
| `travel doctor` | 状态与 git 对账 |
| `travel warp <issue> [--ships 1-3] [--tasks f.json] [--no-auto]` | 曲速：自动批门 + 施工，**不发货**（停在 closing）；默认无人值守跑到停 |
| `travel jump <issue> [--ships 1-3] [--no-auto]` | 跃迁：加急 + 自动发货；默认无人值守跑到底，`--no-auto` 才逐条手动推 |
| `travel auto <run> [--worker-cmd ...] [--reviewer-cmd ...]` | 无人值守循环：claim → 派子会话 → report → 审查 → verdict，直到终态；宿主命令从 `.coding/config.json` 的 `worker_cmd`/`reviewer_cmd` 或同名环境变量读 |
| `travel assimilate <branch> --approve` | 吞并外部分支（必须显式 `--approve`） |

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
| 子代理超时/崩溃 | 主会话重派该任务一次；再失败转 blocked |
| 报告缺失/解析失败 | 视为 partial，读 diff 自判，不重试 |
| 报告与 diff 不符 | 视为 partial，必须读 diff |
| 连续 return 3 轮 | 转 blocked，叫醒人 |
| merge 冲突 | 脚本自动 rebase 一次；仍冲突 → blocked |
| 发货失败（收尾门红 / push 被拒） | run 转 blocked，产出保留 |

## 曲速模式（/warp）

`/warp <任务> [--tasks tasks.json]` = 全自动挡：施工全程主会话自推，门卫代理自动批 G0/G1，G2 留 pending（warp 不发货），只在红线/异常时停。
- `--tasks` 可在开 run 时直接写任务图；并发满时 run 排队，槽位空出后自动提升（`promote_queued`）。
- 舰队节制：舰船数（run）1–3（`--ships`，warp/jump 默认 2、`run` 默认 1）、船员数（并发子代理）1–5（`--crew`，默认 5），按舰队独立计数；
  不同舰桥 / agent 框架互不抢占，touchset 冲突检测仍全局。
- `--ships N` 一次创建 N 艘舰船（各自 worktree + 分支），共享 `fleet_id`（`<宿主>-<时间戳><后缀>`）；
  混搭曲速/跃迁时给两条命令传同一个 `--fleet <ID>`。
- return 上限 3 轮，failed 重试 2 次，merge 冲突自动 rebase 一次。
- 发货权只归加急：普通 `/warp` 停在 closing（next_action 注明等发货），由舰桥或人工 `gate g2 approve` 发货；
  `/jump` 才自动发货 = merge → 收尾门 → push → 关票，全脚本化。
- push 目标默认 `dev`；仓里没有 dev（如本仓已并入 main）则用当前分支。
- issue 引用自动识别：任务文本里的 `#123` 或 GitHub issue URL 会自动关票；识别不到则跳过，不阻塞发货。
- 吞并他人成果：`travel assimilate <branch> --approve`，必须用户同意后才执行。

## 跃迁触发（/jump）

`/jump <任务>` = 跃迁（加急）：走加急预留槽，不抢占普通 run，touchset 重叠时排队到该任务验收。
未显式触发时一律问用户是否用 `/jump`（跃迁）。

## 触发策略

未显式指定命令时，一律先问用户：「是否用 `/jump` 跃迁？」
用户确认后再执行；不自行决定。

## 与其他体系

- 创作体系：fleet 只管代码；作品交付走 `/producer` 等。
- 看板：`travel status` / `travel status --html`。
- 宿主必须能起子代理；起不了就如实报缺件，不退化成「自己写代码」。
