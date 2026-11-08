# 配置实例（schema 5）

schema 5 删掉了 V1 的任务表、工作树槽位、定时器与三键门禁；保留而且**只有活读者**的键：

| 段 | 键 | 读者 |
|---|---|---|
| `project` | 项目名 | 安装器、脚本 |
| `host` | `adapter` | 安装器选宿主适配 |
| `registry` | `playbooks[]`、`adrs.dir`、`rules.dir`、`skills.project_skills_dir` | 入口与安装器 |
| `paths` | `handoff_dir`、`ideas_dir`、`audit_dir`、`module_cards`、`dashboard`、`state_dir` | 接交、想法池、看板、运行态 |
| `runtime` | `backend_python`、`node`、`deps.check_dir_rel` | worktree 自检 |
| `gates` | `finish_cmd` | 发货收尾门 |
| `issue` | `platform`、`repo`、`boom_summary_ticket` | 开票、关票、想法池 |

**已删除（schema 4 → 5）**：`ship_mode`、`paths.day_tables_dir`、`paths.day_table_pattern`、`paths.lanes`、
`tower_cron`、`issue.verdict_marker`、`registry.skills.loop_dir`、`gates.captain_preflight`、
`gates.scope_check`、`gates.close_gate`。 <!-- canon:allow-retired -->

迁移时逐字段 diff 留档；多出来的键逐条列给用户，点头才删。
