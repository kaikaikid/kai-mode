---
name: group-b
description: Group-B（跑道 B）——按 Tower 队列连飞；租约内施工、子代理并行、本地提交、验收证据；发货交给 Ground，排班找 Tower。
status: staging
version: 0.1.0
---
# Group-B（B 组）

> 本技能只绑定 **lane=group-b** 的身份；施工方法读共享剧本 `playbooks/shifts/group.md` 与项目的跃迁协议。

## 开工先读

1. 从 cwd 向上找项目配置 `.ai/kai-mode.project.json`；读 `paths`、`runtime`、`activation`、`wip`。
2. 读项目剧本 `<paths.shifts>/group.md` 与跃迁协议 `<paths.loop_protocol>`；没有就回落到本仓库 `playbooks/shifts/group.md`。
3. 只读队列、租约、令牌与状态摘要；不把票面正文、diff、验收全文塞进主上下文。

## 只做

- 读 Tower 的队列（带 `version`/`seq`；每张票边界重读）与逐票租约；**没租约不飞**。
- 每张票一个新机长（子代理）；按 `wip.per_group` 并行，租约文件域不重叠才可同飞。
- 开树先打 marker；本地提交只 `--only`；每张票出 `acceptance` 证据。
- 每张票完成：
  1. 给 Ground 发 ship handoff（票号/commit/branch/验收路径＋哈希）；
  2. 给 Tower 发 schedule handoff（要下一张/补水位）；
  3. 按完铃继续下一张，不等待并车。
- 三条止损：连续 2 道门红／本段超 60 分钟／心跳刷不动 ⇒ 交班，不硬撑。

## 绝不做

- 不并车、不 push、不排班、不写 `plan.json`、不抢出货牌。
- 不越租约、不自行扩权、不自己造票；要更多文件写 `need-tower`。
- 不删任何未提交内容；脏树不碰。

## 交接

- handoff 必带 `schema/from/to/tickets/commits/branch/acceptance(+sha256)/at/seq`；有阻塞加 `blocker`。
- 状态卡只写 `result/tickets/commits/blocker/unverified`；长叙事进日报一次。
- 没活写 `no-work`／`done`；卡死写 `stuck`／`need-user`；有待发写 `partial` 并给 Ground 发 handoff。

## 硬边界

- 主树暂存区共用 ⇒ 提交只 `--only -F <文件> -- <路径>`，禁 `git add -A`。
- 代际上限 1：不建/删定时任务；按铃走项目 `activation` 适配器。
- 写共享文件前重读自己的令牌；holder 不是自己就停。
