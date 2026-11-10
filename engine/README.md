# 执行内核（fleet）

> 无人值守：速推（工程别名 `fleet jump "<任务>" --tasks f.json`）一条命令跑完
> claim → 宿主子会话 → report → 审查 → verdict → 发货。宿主命令从
> `.coding/config.json` 的 `worker_cmd` / `reviewer_cmd`（或同名环境变量）读（如 `claude -p {brief} ...`），不配则如实报缺件。

一个 issue 一个 run：主会话规划与验收，宿主自己的子代理执行，每个 run 一个独立工作树，
只在门点停。设计正本见
[`docs/design/2026-10-30-v2-execution-kernel.md`](../docs/design/2026-10-30-v2-execution-kernel.md)。

命令入口是 `fleet`（`travel`、`coding` 是兼容别名，三个 launcher 指向同一入口）。**只走宿主原生子代理，不拉 CLI 进程。**
宿主起不了子代理就不适用；如实报缺件，不退化成「自己写代码」。

## 安装

在仓库根执行：

```bash
# 1. 把 .coding/ 加进 .gitignore（运行期数据不进仓库）
grep -qxF '.coding/' .gitignore 2>/dev/null || echo '.coding/' >> .gitignore

# 2. 把 engine/bin 加到 PATH（可选；也可以直接用 engine/bin/fleet）
export PATH="$PWD/engine/bin:$PATH"
```

## 命令

| 命令 | 作用 |
|---|---|
| `fleet run <issue> [--fleet id] [--ships 1-3] [--crew 1-5] [--urgent] [--base main]` | 开一个 run（`--ships` 可一次开多个） |
| `fleet adopt <issue>` | 晚激活：接管当前未提交改动 |
| `fleet plan <run> --file tasks.json` | 写任务图 |
| `fleet gate <run> g0\|g1\|g2 approve\|reject\|skip` | 过门 |
| `fleet next [run]` | 看下一个可派任务 |
| `fleet claim <run> <task>` | 原子占位，输出任务卡（不起进程） |
| `fleet release <run> <task>` | 释放原生占位，任务回 pending |
| `fleet report <run> <task>` | 读子代理报告并对账 diff |
| `fleet review <run> <task>` | 输出审查卡（只读子代理执行） |
| `fleet verdict <run> <task> --file <path>` | 写回审查裁决（accept/return/defer） |
| `fleet accept\|return\|reopen <run> <task>` | 验收 |
| `fleet resume <run>` | 从 state.json 续跑 |
| 开团（工程别名 `fleet warp <issue> [--ships 1-3] [--tasks f.json]`） | 自动批门 + 施工，**不发货**（停在验收门） |
| 速推（工程别名 `fleet jump <issue> [--ships 1-3]`） | 加急 + 自动验收发货，唯一有发货权的全自动入口 |
| `fleet status [--html]` | 看板 |
| `fleet context <run>` | Context Manifest（任务/门/预算/事件/追踪清单；Token 未回传时如实标未采集） |
| `fleet usage <run> '<json>'` | 追加宿主回传的 usage 行并累计 `used_tokens`（不估算） |
| `fleet dirty [--json]` / `park` / `unpark` | 主树脏件分类与可逆收起 |
| `fleet doctor` | 状态与 git 对账 |
| `fleet gc [--all]` | 清理已收尾资源 |
| `fleet stop <run>` | 停一个 run |
| `fleet assimilate <branch> --approve` | 吞并外部分支（需显式批准） |

## 任务图格式

```json
{"tasks": [
  {"id": "t1", "title": "加导出", "brief": "自包含任务书", "tier": "medium",
   "deps": [], "touchset": ["src/export/**"], "ac": ["测试通过"], "ui": false}
]}
```

## 状态

全部在 `.coding/runs/<run-id>/state.json`，脚本原子写。中断后 `fleet resume` 从
`resume.last_accepted` / `next_action` 接着跑。

## 开团（工程别名 `fleet warp`，只作兼容）

`fleet warp <issue> [--tasks f.json]`：

- 自动批 G0/G1/G2，门卫子代理（`fleet review`）独立只读审查；
- 发货 = 切到 base（默认 `dev`，仓里没有 dev 就用当前分支）→ merge → 收尾门 → push → 关票，全脚本化；
- 收尾门在 `.coding/config.json` 配 `{"finish_cmd": "..."}`，留空则跳过；
- issue 文本里的 `#123` 或 GitHub issue URL 会自动关票，识别不到则跳过；
- 并发：普通槽 2 + 加急槽 1，每 run 1 个子代理，全局 3；排队的 run 槽位空出后自动提升。

## run 集合 / run / 队员

```
run 集合 (fleet, fleet_id = TRAVEL_HOST 或 git config 推断)
├── run 1 — 独立 worktree + 分支 travel/<run-id>
│   └── 子代理槽
├── run 2
│   └── 子代理槽
└── run 3（上限）
    └── 子代理槽
```

| 层级 | 默认 | 范围 | 参数 |
|---|---|---|---|
| 每次拉起的 run 数 | 1（run/开团/速推 一致） | 1–3 | `--ships` |
| 队员数（子代理并发，跨 run 共享） | 5 | 1–5 | `--crew` |

槽位按 run 集合独立计数：不同宿主 / agent 框架互不抢占；默认 1 个 run，只有用户明确要多 run 或确有互不重叠的独立工作流才 `--ships 2-3`。
`--ships N` 会一次创建 N 个 run（各自 worktree + 分支），共享同一个 `fleet_id`；`--tasks` 只规划第一个，其余各自规划。
混搭开团/速推时用 `--fleet <同一ID>` 把它们并入同一 run 集合（总数受 `--ships` 限制）。
用户大白话（「开团 2 个 run」「晚上用 3 个 run」）由康娜解析成 `--ships`。

## 环境变量

| 变量 | 作用 |
|---|---|
| `TRAVEL_HOST` | run 集合 ID 前缀（宿主标识）；缺省从 git config user.name 推断。ID 形如 `<host>-<时间戳><后缀>` |
