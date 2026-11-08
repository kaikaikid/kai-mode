# 命令速查

只列康娜真会敲的。参数细节以 `fleet --help` 为准，本表不抄全量。

| 命令 | 作用 |
|---|---|
| `fleet warp <任务> [--ships 1-3] [--no-auto]`（酒馆名**开团**） | 开团：开工到验收门（不发货） |
| `fleet jump <任务> [--ships 1-3] [--no-auto]`（酒馆名**速推**） | 速推：加急 ＋ 自动验收发货 |
| `fleet auto <run>` | 无人值守循环：claim → report → 审查 → verdict，不等人敲命令 |
| `fleet status [--html]` | 现在有哪些 run、到哪一步 |
| `fleet resume <run>` | 从断点续跑 |
| `fleet dirty [--json]` | 主树脏件分类 |
| `fleet park [-m 理由]` | 收起无关产品改动（可逆） |
| `fleet unpark [ref] [--list]` | 放回收起的改动 |
| `fleet gate <run> <g0\|g1\|g2> approve` | 手动批门点（**开团** `warp` 停在验收门时用它发货） |
| `fleet gc [--all]` | 清理已收尾的 worktree 与分支 |
| `fleet doctor` | 状态与 git 对账 |
| `gh issue create --repo <owner/name> ...` | 开票，**必须显式带 `--repo`** |

## 数量节制

- 并发 run：默认 1，只在用户明确要多、或确有独立工作流时才 2–3。
- 并发子代理：上限 5，按 run 集合独立计数；实际按 ready 任务逐个 claim，通常 1–2，并发是天花板不是目标。
- 子代理默认 0：康娜当前会话能做完的不派；派之前一句话报「几个、为什么、上限几」。
- 用户说「开团 2 队」「晚上用 3 队」→ 翻译成 `--ships N`，不问第二遍。
- 混搭（开团 2 ＋ 速推 1）→ 多条命令传同一个 `--fleet <ID>`，总数仍受上限约束。

## 交接落点

| 内容 | 落点 |
|---|---|
| 需求与验收标准 | 项目仓 Issue（票面六件套） |
| 施工状态与断点 | `.coding/runs/<run>/state.json`（只由内核写） |
| 收起的脏件 | `.coding/parked/<时间>.json`（stash ref ＋ 恢复命令） |
| 给用户的回话 | 对话；结论先写，三行以内 |
| 想法 | 项目想法目录 ＋ 想法池汇总票（有则用） |
