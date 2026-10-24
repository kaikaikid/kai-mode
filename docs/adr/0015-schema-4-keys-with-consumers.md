# 0015 schema 4：配置实例只留有消费者的键

## Status

accepted —— 2026-10-25 用户令「你看着处理」，按 [0014](0014-config-instance-no-invented-values.md) D5 登记的待拍项执行。
推翻 [0004](0004-project-config-schema.md) D2 字段表里「沿用 schema 2」那一行（`execution`／`tower_cron`／`wip`／`limits`／`approval`／`acceptance`／`audit`）；
其余 0004 行不变。`gates`／`issue` 的键集按本文收窄，口径继续遵循 0014 D1。

## Context

逐键取证（只算**活契约**：`skills/*` 的 `install:auto` 正文与脚本、`loops/`、`agents/`、`adapters/`、`scripts/`、`schemas/`、`manifests/`、`AGENTS.md`、`README.md`；
历史 ADR／CHANGELOG／`handoff/` 里的提及不算消费者），按 `段.键` 点号形全量搜：

| 结论 | 键 | 证据 |
|---|---|---|
| **有活读者，保留** | `paths.audit_dir`／`dashboard`／`module_cards`／`state_dir`／`day_tables_dir`／`handoff_dir`／`ideas_dir`／`day_table_pattern`／`lanes`、`gates.captain_preflight`／`scope_check`／`close_gate`、`issue.verdict_marker`／`platform`／`repo`／`boom_summary_ticket`、`registry.*`、`models.agents`、`host.adapter`、`tower_cron.interval_min`、`runtime.main_tree`／`backend_python`／`node` | tower／pilot／copilot／loop／ground-crew／flight-info／kai-handoff／kai-boom-idea-log／set-kai-mode／loop-protocol／agents/README 逐条点名 |
| **零读者，删** | `wip`（3）、`limits`（8）、`approval`（3）、`acceptance`（2）、`audit`（3）、`execution`（6）、`runtime.deps` 里 4 键、`gates` 里 9 键、`tower_cron` 里 4 键 | 全量活契约里没有任何 `段.键` 或键名引用 |
| **上轮误判，纠正** | 0014 把 `paths.audit_dir`／`dashboard`／`module_cards`、`issue.ready_label`… 一并算进「60 个零读者」；取证后 `audit_dir`／`dashboard`／`module_cards`／`verdict_marker` **确有读者**，本轮保留 | 我上轮的量具按裸 token 匹配，把「塔台硬编码 `verdict=pass`」这类没算进引用；本轮改成按 `段.键` 点号形搜活契约 |

另两条硬冲突顺手收掉：
`wip.per_pilot`／`limits.*` 与 `loops/loop-protocol.md` 的同名数值是**同一判据的第二家**（AGENTS 把 fail/retry 名额类判据的家判给 loop-protocol，又把「重试/超时/熔断/预算」判给宿主运行时，两处都不许实例再抄一份）；
`README.md`「上限全部进项目配置 `limits`」这句与 AGENTS 冲突，一并改指 loop-protocol。

## Decision

### D1 schema 4 的唯一键集

```
schema=4  project  repo_root  ship_mode
host.adapter
registry.playbooks[]  registry.skills.project_skills_dir  registry.skills.loop_dir
registry.adrs.dir  registry.rules.dir
paths.day_tables_dir  paths.day_table_pattern  paths.lanes  paths.handoff_dir  paths.ideas_dir
paths.audit_dir  paths.module_cards  paths.dashboard  paths.state_dir
models.agents.<人格>.model            （键集＝盘上 agents/*.md，由第 11 问答）
runtime.main_tree.{discover,env_fallback}
runtime.backend_python.{discover,var,fallback.{discover,rel}}
runtime.node.{discover,rel}
runtime.deps.check_dir_rel
gates.captain_preflight  gates.scope_check  gates.close_gate
issue.platform  issue.repo  issue.verdict_marker  issue.boom_summary_ticket
tower_cron.interval_min
```

叶子键 88 → **44**。段数 19 → 12（`playbooks[]` 按四个字段计，`models.agents` 按盘上六个人格计；量具实跑读数为准）。

### D2 删段不删语义

`wip`／`limits`／`approval`／`acceptance` 承载的判据（在飞名额、失败重试、审查独立、发货风险闸）本来就有家：
`loops/loop-protocol.md`（票级协议数值）、AGENTS（红线与人工闸）、`adapters/<宿主>.md`（宿主工具契约）。
本轮只是把实例里那份**没人读的抄本**拿掉，不新增也不迁移任何判据文字。

### D3 框架缺省值再收一遍

`paths.audit_dir` 与 `paths.state_dir` 原值是别的仓的目录名（`.ai/scope/audit`、`.git/kai-scope`）：
前者按 0014 D1 改 `null`（本项目没有记录面就如实报缺件），后者改框架自己的命名空间 `.git/kai-mode`。
`runtime.deps` 只留 `check_dir_rel`（null＝没问出前端目录），包管理与「不许软链主树」的口径继续写在 `runtime._note` 里，不再做成键。

### D4 迁移（schema 3 → 4）

由 `set-kai-mode` 执行，四步：整包备份（带日期、不入库）→ 按 D1 键集逐字段 diff（多出来的键列清单，用户点头才删）→ 写 `schema: 4` → 复跑初始化器与 `config-instance` 门对账。
**不自动改写用户已生成的实例**：本轮只改模板与新项目的生成结果，存量项目按票走迁移。

## Consequences

- 用户打开配置文件能一眼看完：41 个叶子键，每个非 null 值要么他自己答过，要么是框架常量。
- 代价：`tower_cron` 只留 `interval_min`，定时任务的提示词与授权位回到 `set-kai-mode` 正文（那里本来就是它写的）；
  `gates` 从 12 键缩到 3 键，其余门由项目自己按需扩（`config-instance` 会拦住模板预置）。
- 存量 schema 3 实例不会自动升级（D4），下次装机由 `set-kai-mode` 走迁移段；未迁移的实例多出来的键不会报错，只是没人读。
