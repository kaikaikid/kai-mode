# 0014 配置实例零虚构值：没被问答过的字段一律 null

## Status

accepted —— 2026-10-25 用户令：「再梳理一遍用户得到的配置是否干净，结构化，确保没有漂移」。
补全 [0004](0004-project-config-schema.md) D「set-kai-mode 负责校验」那条一直没实现的口径；不改动 0004 的字段表语义。

## Context

初始化器把模板抄成用户项目的 `.ai/kai-mode.project.json`。实测（从 GitHub 干净 clone 跑 `init-project --yes`）配置面有六处漂移，其中四处是**与我们自己写的判据直接冲突**：

| # | 实测 | 撞的判据 |
|---|---|---|
| 1 | 实例里留着 7 处 `<尖括号>` 占位（`issue.repo`、`registry.playbooks[4]` 整行、`runtime.deps.check_dir_rel`、`tower_cron.job_ids_from` 等） | 模板 `_note_0` 与 0004 D：「占位不落盘」 |
| 2 | `gates` 12 键预置的全是**本仓**的门名（`ready`／`env_doctor`／`worktree_teardown`／`skill_attest`…），十一问只问了 `captain_preflight` 一个；生成项目里 12 个路径 **0 个存在** | `gates._note`：「null＝本项目无此门」；缺件原则：不许猜一个路径写下去 |
| 3 | 宿主有两处：`host.adapter`（第 8 问）与 `execution.preferred`＋`fallbacks`（模板写死 `qoder`/`codex`/`opencode`） | `host._note`：「换宿主时改这一处」＝唯一家 |
| 4 | `runtime.deps.install_cmd = pnpm install --offline`、`check_dir_rel = <frontend-dir>/node_modules`、唤醒周期在 `playbooks[].trigger` 里写死「1 小时轮巡」而正本在 `tower_cron.interval_min` | 0004：机器值/包管理选择不入 tracked 实例；一语义一家 |
| 5 | 88 个叶子键里约 60 个没有活契约读者（`limits` 8、`runtime` 13、`execution` 6、`approval` 3、`acceptance` 2、`audit` 3、`wip` 3、`gates` 9、`issue` 3…）<br>**更正**：这条按裸 token 量的，误伤 `paths.audit_dir`／`dashboard`／`module_cards`、`issue.verdict_marker` 四个确有读者的键；键集终局按 [0015](0015-schema-4-keys-with-consumers.md) 的 `段.键` 取证 | AGENTS：运行时机制（重试/超时/熔断/预算）属宿主运行时，不属文档与实例 |
| 6 | 没有任何门校验生成的实例（0004 D 写了「set-kai-mode 负责校验」，doctor 的解耦门只扫模板与本仓硬路径） | 判据有写、量具没有＝等于没有 |

## Decision

### D1 没被问答过的字段一律 null

模板里凡是十一问填不到的键，缺省值必须是 `null`（或框架自己的常量，如 `day_table_pattern`、`ship_mode`）。
本仓的门名、包管理命令、宿主偏好、目录布局都不算「框架常量」，一律 `null`。消费方读到 `null` 按缺件三格登记，不猜路径。

### D2 占位不落盘改为机械保证

`init-project.py` 抄完模板后扫一遍：值里仍带 `<…>` 的字段（＝没问出答案）改 `null`，并把被抹的键路径打印出来。
不再依赖「装机 agent 记得填」。

### D3 宿主选择的唯一家＝`host.adapter`

`execution.preferred`／`fallbacks` 置 `null`，段内 `_note` 指向 `host.adapter`；换宿主只改一处。

### D4 新增 doctor 的 `config-instance` 项（第 26 项）

实跑 `init-project` 生成临时实例，断言四条：① 叶子键集与模板逐键相等（＝模板必须声明初始化器会写的一切）；
② 值里零 `<占位>`；③ 零机器绝对路径；④ `gates` 里非 null 的键只能来自问答清单（现在只有 `captain_preflight`）。
红＝配置面又在往用户项目里塞虚构值。假仓三条回归用例（预置门红／机器路径红／干净绿）。

### D5 零读者段本轮不删，登记为待拍项 → 已由 0015 执行

`limits`／`wip`／`approval`／`acceptance`／`audit`／`execution`／`runtime.deps` 这批键是 0004 从 schema 2「沿用」来的。
本轮（0.20.0）只做 D1–D4；键集终局见 [0015](0015-schema-4-keys-with-consumers.md)（schema 4；叶子键读数由 0015 D5 的量具生成）。

## Consequences

- 新用户生成的实例里，每个非 null 值要么是他自己答的，要么是框架常量——不再有「照抄了别人项目的门名单」。
- 代价：`gates` 全 null 后，机长/塔台跑到门步骤会如实报缺件（本来就该报），初始化输出的「下一棒」仍提示补门。
- 配置面当时仍有约 60 个零读者键（D5，该数按裸 token 量、已在上表更正）；下一步由 [0015](0015-schema-4-keys-with-consumers.md) 执行。
