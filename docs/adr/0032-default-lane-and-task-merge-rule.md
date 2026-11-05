# 0032 默认档位收敛：任务合并规则、轻车道放宽、舰队默认 1 船

## Status

**accepted** —— 2026-11-05 用户拍板「把合并规则、轻车道阈值、`--ships` 默认 1 写成 ADR，
并改 fleet/staff/bridge 的对应默认」。

## Context

- **拆得细不等于并行**：真实 run `issue-3` 的 4 个任务里，t1/t2/t3 的 touchset 都含
  `engine/coding/cli.py` 与 `engine/tests/`，t2/t3 还依赖 t1（`.coding/issue-3-tasks.json`）。
  这条链只能串行；4 个任务只多出 t4 一个并行位。把 t1–t3 合成一个多 AC 任务，
  并行宽度不变，却少 2 套 worker/reviewer 与 2 轮审查。
- **每任务固定成本高**：`fleet claim → 派子代理 → report → review 卡 → 只读子代理 → verdict`
  是 5 条控制面命令 + 2 次子代理 + 2 份报告（`engine/skills/fleet/SKILL.md:54`）。
  任务数直接乘这套成本；串行同文件的拆分没有并行收益。
- **没有合并规则**：staff 按 `to-tickets` 的「垂直切片 / 单上下文窗口」出票
  （`core/skills/staff/SKILL.md:40`），但这是切片规则，不是并行/发货规则；
  仓里没有「同文件串行就合并」的阈值，也没有票 → issue → task 的映射规则。
- **默认 2 船会白建树**：`warp/jump` 默认 `--ships 2`（`engine/coding/cli.py:319`），
  同一个 issue 建 2 个 run / 2 棵 worktree；`--tasks` 只写给第一艘
  （`engine/coding/cli.py:329`）。第二艘没有任务图时 `auto` 直接停
  （`engine/coding/auto.py:187`）。这不是并行，是多余资源。
- **轻车道太窄**：bridge 只给小修「≤2 个文件」免票（`core/skills/bridge/SKILL.md:54`）；
  一个单模块、无 UI、需求清楚的 3 文件改动没有轻路径，只能走全套票 + 门。

## Decision

### D1 任务合并规则

一个 task 是**执行与验收的最小单位**，不是实现步骤。拆 task 只允许三种理由：

1. **能并行**：touchset 不重叠，且拆开后确实能同时跑；
2. **能独立发货**：每个 task 可单独验收 / 回滚；
3. **风险隔离**：安全、数据迁移、内核 / 权限等高风险改动需要单独审查。

不满足任一条，尤其「touchset 重叠 + 串行依赖」时，默认合并成一个 task、多个 AC。
禁止按「实现步骤 / 文件层 / 前后端」拆。规划表必须标出并行宽度；
并行宽度 = 1 的拆分视为纯开销。

### D2 轻车道阈值

bridge 的小修门槛从「≤2 个文件」改为「单模块、无可见 UI、无迁移 / 权限 / 数据变更、
一句话能验收」。满足即免票热修：不配脚手架，一个可写子代理 + 验证 + 回报。

需要留验收记录但仍是单模块、需求清楚的，走轻车道：免 staff、免 G0；
开票后舰队默认 1 船、任务图默认 1 个 task（多 AC），一次审查后发货。

### D3 舰队默认 1 船

`fleet run` / `warp` / `jump` 默认 `--ships 1`；只有用户明确说「多船」或确有互不重叠的
独立工作流，才用 2–3。`adopt` 的 `ship_limit` 同步改 1。

`--tasks` 仍只作用于第一艘；多船必须各自规划，不做隐式复制。
`ship_limit` 缺失时的兜底也统一为 1（`engine/coding/scheduler.py`）。

## Consequences

- **好**：常规 issue 少 1 棵空 worktree；同文件串行链不再按步骤拆，少 worker/reviewer
  与报告；单模块清楚需求有可走的轻路径。
- **代价 / 风险**：合并后 diff 变大，审查更难；用 D1 的第 3 条保留高风险拆分，
  风险任务仍逐 task 审。
- **不做**：不改 state schema；不新增自动告警；批量审查（按 issue 审累计 diff）
  留作后续，不在本 ADR 落地。
- **迁移**：已有 run 不受影响；新默认从下一艘船起生效；技能版本随 core/engine 插件升一档。
