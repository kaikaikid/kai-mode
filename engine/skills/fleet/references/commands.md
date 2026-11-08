# 命令全表

参数细节以 `fleet --help` 为准，本表不抄全量。

| 命令 | 作用 |
|---|---|
| `fleet run <issue> [--fleet id] [--ships 1-3] [--crew 1-5] [--urgent] [--base main] [--depends r-x]` | 开 run |
| `fleet adopt <issue>` | 晚激活：接管当前未提交改动为 baseline |
| `fleet plan <run> --file tasks.json` | 写任务图 |
| `fleet gate <run> g0\|g1\|g2 approve\|reject\|skip` | 过门；reject 有回流 |
| `fleet next [run]` | 下一个可派任务（含 touchset／槽位判断） |
| `fleet claim <run> <task>` | 原子占位，输出任务卡（不 spawn） |
| `fleet release <run> <task>` | 释放原生占位，任务回 pending |
| `fleet report <run> <task>` | 读子代理报告，校验 files_changed ⊆ git diff |
| `fleet review <run> <task>` | 输出审查卡（只读子代理执行） |
| `fleet verdict <run> <task> --file <path>` | 写回审查裁决（accept／return） |
| `fleet accept\|return\|reopen <run> <task>` | 验收／打回／撤销 |
| `fleet resume <run>` | 从 state.json 续跑 |
| `fleet status [--html]` | 看板（在做／在等／已完成） |
| `fleet dirty [--json]` / `park` / `unpark` | 主树脏件分类与可逆收起 |
| `fleet stop <run>` / `fleet gc [--all]` | 停 run／清已收尾资源 |
| `fleet doctor` | 状态与 git 对账 |
| `fleet warp <issue> [--ships 1-3] [--tasks f.json] [--no-auto]` | 曲速：自动批门 ＋ 施工，**不发货**（停在 closing） |
| `fleet jump <issue> [--ships 1-3] [--no-auto]` | 跃迁：加急 ＋ 自动发货 |
| `fleet auto <run> [--worker-cmd ...] [--reviewer-cmd ...]` | 无人值守循环：claim → 派子会话 → report → 审查 → verdict |
| `fleet assimilate <branch> --approve` | 吞并外部分支（必须显式 `--approve`） |
