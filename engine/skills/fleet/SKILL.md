---
name: fleet
status: active
approved_by: human:kaikaikid
approved: 2026-10-31
sources: []
description: >
  执行内核（由康娜调度）：一张票一个 run，主会话规划与验收，宿主自己的子代理执行；
  一个 run 集合的并发上限是 run 1–3（默认 1）、子代理上限 5（实际按 ready 任务数逐个 claim，
  不是目标值），按集合独立计数；
  一次触发连续跑到门点才停。用 `fleet` 控制平面推进（`travel`／`coding` 是兼容别名），不直接改 state.json。
  只走宿主原生子代理，不拉 CLI 进程。由康娜在开工时调用；中文「开个 run」「跑起来」也认。
version: 0.9.0
updated: 2026-11-08
allowed-tools: Read Grep Bash
compatibility: Host-agnostic; host must be able to spawn subagents
---

# fleet —— 执行内核

> 实现：`engine/coding/`，命令入口 `engine/bin/fleet`（`travel`／`coding` 是同一入口的兼容别名）
> 安装：`engine/README.md`

## 这是什么

**开团**与**速推**由康娜触发（工程别名 `/warp`、`/jump`，见下「开团与速推」），本技能只负责施工执行与验收。**你只跟主会话说话**；施工交给宿主自己的子代理，
不拉起 CLI 进程，也不要求挂机。主会话开着，调度就在；关了就停了。

与创作交付（武器集）严格分开：本技能只做代码开发，不调用它们的角色，也不共用状态。

## 铁律

1. **能脚本就脚本**：状态推进、槽位、worktree、touchset、预算、续跑全走 `fleet` 命令；
   **绝不手改 `.coding/runs/*/state.json`**。
2. **插话在会话里，自动在 `fleet auto` 里**：`fleet claim` 输出任务卡，主会话用本宿主的子代理执行；
   `fleet review` 输出审查卡，用只读子代理审查。人不在线时由 `fleet auto` 驱动，它只调
   `.coding/config.json` 的 `worker_cmd`／`reviewer_cmd`（或同名环境变量）配好的宿主命令，
   内核不内置任何厂商适配器；不配就如实报缺件。
3. **只在门点停**：手动挡在 G0／G1／G2 停；**开团**（工程别名 `/warp`）自动挡由门卫子代理自动批门，只在红线或异常时停。
4. **验收读 diff**：子代理报告是 claim，不是事实；`fleet report` 对账 diff，主会话读实际 diff 再裁决。
5. **子会话不发货**：worker 与 reviewer 都不 push／merge；发货只由主会话在门点后执行。
6. **并发是天花板，不是目标**：默认只开 1 个 run；子代理按 ready 任务逐个 claim，机械活一个就够时不拆。

## 流程

每一步的终点写在这条链上；不到终点不进下一步。

```
开团（工程别名 `/warp <任务>`）
  → fleet run "<任务>"                 # 开 run（并发满则 queued）      终点：state 里有 run
  → 拆任务图 → fleet plan              # 每任务：brief/tier/deps/touchset/ac/ui
                                                                      终点：任务图过 G0
  → G0：把任务图给用户看 → fleet gate <run> g0 approve
  → （有 UI）G1：设计规格 → gate <run> g1 approve
  → 循环：
      fleet next                       # 取 ready 任务
      fleet claim <run> <task>         # 原子占位，输出任务卡（不起进程）
      本宿主可写子代理执行任务卡         # 方法：tdd；报告写到卡上的 report_path
      fleet report <run> <task>        # 读文件 + diff 对账
      fleet review <run> <task>        # 输出审查卡
      本宿主只读子代理审查               # 方法：code-review 双轴；报告写到 review_report_path
      fleet verdict <run> <task> --file <path>
                                                                      终点：每个 task 有判词
  → 全部 accepted → gate <run> g2 approve   # merge → 收尾门 → push → 关票
                                                                      终点：远端回读一致、票已关
```

## 方法（按名用宿主中央库原版）

各节点点名方法，本技能不复述正文；宿主中央库没有就按缺件登记，不假装已具备。

| 节点 | 方法 |
|---|---|
| 拆任务图 | `to-tickets`（需求 → 可验收的票与任务卡） |
| 施工 | `tdd`（接缝＝任务 AC 里的验证命令；非代码票不硬写测试） |
| 审查 | `code-review`（只读子代理按 Standards／Spec 双轴读实际 diff） |
| 连续失败 | `diagnosing-bugs`（两轮还不过先造反馈环，不盲改） |
| 术语与决策记录 | `domain-modeling`（涉及新概念或长期结构时） |
| 已有 spec 和票、想一把跑完 | `implement-spec`（上游原版，不开 run）；分流判据：装了 kai-mode 的仓，并发施工与发货归本件的一条 run 制 |

## 任务卡与审查卡

`fleet claim` 输出：`task_id`、`brief`、`worktree`、`touchset`、`ac`、`report_path`、`diff_base`。

- 子代理必须在 `worktree` 里工作，只改 `touchset` 范围内的文件。
- 完成后把报告写到 `report_path`，形状见下方报告契约。

`fleet review` 输出：`task_id`、`worktree`、`diff_base`、`changed_files`、`ac`、`touchset`、
`review_report_path`、`read_only`。

- 必须用**只读**子代理；读实际 diff，对照 AC，输出
  `{verdict: accept|return|defer, defects:[], deferred_items:[], reason:""}`。
- 三态含义：
  - `accept`：验收过，task 进 accepted，依赖放行。
  - `return`：返工（attempts+1，3 次转 blocked）。
  - `defer`：**验收放给AI**——技术验收已过，但有要团长拍板的事（`deferred_items` 必填：
    每条含 `question`/`reason`/`priority`），记入团长队列，task 进 accepted 不阻塞施工；
    等团长唤醒时统一处理。
- 然后 `fleet verdict <run> <task> --file <path>` 写回。

## 报告契约（施工子代理 → 内核）

```json
{"result": "done|partial|blocked",
 "files_changed": ["path — 改了什么"],
 "commit": "<HEAD sha，没有改动则为空>",
 "verification": ["命令 -> 结果"],
 "open_questions": ["..."],
 "notes": "<=100 字"}
```

解析失败＝视为 `partial`，主会话读 diff 自判。

**报告永远让位于 diff。** 子代理会把自己的工作说得很完整；仓库里的事实只有 diff 与测试读数。

## 信封契约（Receipt / Envelope，面向机器的交付信封）

正本：`docs/schema.md`「Receipt / Envelope 字段映射」。
Agent **不写执行状态**：开工／结束／阻塞只引用内核事件（`events[]`），状态机归任务管理器。
信封头三行固定：`schema_version`（严格模式拒未声明字段）、`task_id` ＋ `role_id`（不另造 ID）、
`idempotency_key`（幂等键）；论断进 `claims[]`（`fact`/`inference`/`unknown`/`recommendation`，
`fact` 必带 `evidence_refs`，URI 真实可访问）；成果进 `artifacts[]`（全字段
`artifact_id`/`type`/`format`/`uri`/`version`/`created_by`）；判词只由 reviewer 出
（`accept`/`return`/`defer` ＋ `BLOCKER`/`MAJOR`/`MINOR`/`INFO`）；`defer` 必带
`deferred_items` 进团长队列（`owner_deferred[]` 只追加）；交接用 `fleet confirm`
（`accepted`/`rejected`/`needs_clarification`）。

## 交接

跨 run／跨角色移交责任时，`fleet confirm <run> <handoff_id> <accepted|rejected|needs_clarification>` 确认。
责任转移记事件；重复确认同键幂等；`needs_clarification` 打回澄清，不逆转已终态任务。

## 任务图

```json
{"tasks": [
  {"id": "t1", "title": "短名", "brief": "自包含任务书", "tier": "light|medium|careful|heavy|fable",
   "deps": ["t0"], "touchset": ["src/x/**"], "ac": ["可核的完成定义"], "ui": false}
]}
```

- `touchset` 重叠的任务不会并发；跨 run 重叠也排队。
- `ui: true` 才会触发 G1。
- `deps` 未 accepted／abandoned 时任务不 ready。

**拆分与合并**：拆 task 只允许三种理由——能并行、能独立发货、风险隔离。
touchset 重叠且串行依赖时，默认合成一个 task、多 AC；不要按实现步骤或文件层拆。
规划时标出并行宽度；并行宽度＝1 的拆分视为纯开销。

## 开团与速推（工程别名 `warp`／`jump`，只作兼容）

正文与帮助只写开团／速推；`warp`／`jump` 是工程命令别名，兼容存量 run 与用户习惯，不再当现行主语。

- **开团**（工程别名 `/warp`）＝无人值守自动挡：施工全程主会话自推，门卫代理自动批 G0／G1，G2 留 pending（不发货），
  只在红线或异常时停。普通开团停在验收门，由康娜或人工 `gate g2 approve` 发货。
- **速推**（工程别名 `/jump`）＝加急：走加急预留槽，不抢占普通 run，touchset 重叠时排队到该任务验收；
  跑到底并自动验收发货 = merge → 收尾门 → push → 关票，全脚本化（速推是验收阶段的一条特殊通道，不是独立环节）。
- 用户没显式指定时，先问一次「用速推吗？」，不自行决定。
- 并发节制、槽位、`--ships`／`--crew`／`--fleet` 的用法见
  [`references/concurrency.md`](references/concurrency.md)。
- **Crew / Worker 口径**：Crew＝run 内同时活跃的施工子会话上限（≤5），Worker＝单张任务可拆的子任务上限（≤8）。
  Worker 不突破 Crew：`plan` 可带 `worker_count`（缺省 0＝旧任务），`claim` 按
  `min(worker_count, worker_limit≤8, crew_limit−active_sessions)` 钳制，超钳记
  `worker_clamped` 事件（requested／effective／limits），不静默放行；旧任务不回填。
- **自动超时**：`.coding/config.json` 配 `timeout_minutes`（缺省关闭，保持人工路径）后，
  `claim`／`report` 判 running session 超时：session 标 `timeout`、task 转 failed（原因码 `timeout`）、
  记 `session_timeout` 事件；迟到报告只留 `late_result_ignored` 诊断事件，不复活任务、不自动重派。

## 失败处理

| 现象 | 动作 |
|---|---|
| 子代理超时／崩溃 | 主会话重派该任务一次；再失败转 blocked |
| 报告缺失／解析失败 | 视为 partial，读 diff 自判，不重试 |
| 报告与 diff 不符 | 视为 partial，必须读 diff |
| 连续 return 3 轮 | 转 blocked，叫醒人 |
| merge 冲突 | 脚本自动 rebase 一次；仍冲突 → blocked |
| 发货失败（收尾门红／push 被拒） | run 转 blocked，产出保留 |

同一种失败只允许一次重试；第二次说明不是偶发，转 blocked 并带上「哪一步、什么错、下一步建议」。

## 团长队列（defer 的落点）

`verdict=defer` 的事项写进 `.coding/runs/<run>/state.json` 的 `owner_deferred[]`。
队列只进不出：康娜不开工时不轮询；团长唤醒时（用户上线/新会话/「看看团长队列」）统一处理。
队列条目：`{id, task_id, question, reason, role, priority, recorded_at, status: pending|resolved|dismissed}`。
发货前若队列里还有 `pending`，康娜在收尾报告里如实列出，不阻塞发货。

## 与其他体系

- 创作交付：本技能只管代码；作品走武器集（`/producer` 等）。
- 看板：`fleet status`／`fleet status --html`。
- 宿主必须能起子代理；起不了就如实报缺件，不退化成「自己写代码」。

命令全表见 [`references/commands.md`](references/commands.md)；参数细节以 `fleet --help` 为准。
