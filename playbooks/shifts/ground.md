# 地面管制参考剧本（只发货）

> 项目专用剧本优先。命令占位符从 `.ai/kai-mode.project.json` 的 `runtime` 取。

## 第 0 步：闸门与出货牌

1. 读停机牌 `hold-all`／`hold-ground`；存在 ⇒ 一行台账后退出。
2. 领全局出货牌 `<runtime.token> --as <班次名> --enforce`；退 1 ⇒ 有人在出货，不抢、写状态退出。
3. 通过后 `--takeover --ticket <批次首票>`；每步刷心跳，holder 不是自己就停。

## 第 1 步：收 ship handoff，先验门

逐份读 `handoff-group-*-ground.json`，按顺序核验：

1. schema 与必带字段齐全；
2. 每个 commit 存在且在该分支可达（`git cat-file -e <sha>^{commit}`；`git merge-base --is-ancestor <sha> <branch>`）；
3. `acceptance.verdict=pass` 且 `unverified=[]`；验收文件哈希与 handoff 一致；
4. 票号／租约归属、在制 marker、文件域不重叠；
5. handoff 的 `to=ground`，目标注册档有 ground。
6. 风险/审批：`risk=high` 必须有有效审批（票号+范围+风险+有效期）；`ship_mode=pr` 走 PR，不直接 push dev；`direct` 只自动落 low/medium。
7. reviewer 独立性：`acceptance.reviewer` 非空且与 `implementer` 不同；代码/schema 票的状态卡 `subagents` 里必须有 reviewer。不过 ⇒ 不接 ship handoff。

任一不过 ⇒ 不并车；写 `partial`／`blocked`＋原因，给发起组回一个拒绝 handoff（或状态卡点名），不替作者补代码。

## 第 2 步：凑批与预检

- 批次规则（项目配置优先；默认）：2–3 张或 15 分钟一发；单批 ≤3；单张 ≤30 分钟；P0/红门单发；班末有货就发。
- 零副作用预检：`git fetch`、merge-tree 冲突预演、主树暂存区是否干净、每笔提交票号/租约、在制 marker。
- **只跑一次真门**：pre-push 门自己跑 `push-preflight --apply`；不要在预检里手动跑第二遍。
- 红批拆半：先发前半定位；被红的那张退回组并写 `need-tower`，别让一张坏票压住整批。

## 第 3 步：并车 → 门 → push → 关票

- 只并已验收的 exec 分支；按票逐笔审、逐笔 `is-ancestor`；不跳笔。
- 走项目收尾门；任何一门红就停手，贴红原文，不绕钩、不 `--no-verify`、不 force。
- push 成败只认两路回读（`ls-remote`＋`gh api`），不看命令 exit code。
- `close-gate --ticket <n> --submitted-commit <sha>` 通过后再关票；关票评论带验收文件、门读数、push sha。
- 写 `ship-ledger.jsonl` 一行：批次/票号/commit/push sha/门读数/关票结果。
- 状态转移：`ship_ready → landed`（push/PR 合并成功）→ `closed`（close-gate+票面留证）；每次落 `task-state-<票>.json` + `events.jsonl`。
- 幂等：push 前 `ls-remote`；开 PR 前查同 head 分支；关票前回读 state；已做过的不重复做。

## 第 4 步：清场

- 成功 push 后回收**已并、无脏件**的工作树；脏树、未提交内容、别人的在制树一律不碰，点名留给用户。
- 台账记“回收了哪棵、为什么安全”；不把“没回收”写成“已清”。

## 第 5 步：叫塔台补排班

- 库存下降／队列见底／需要清账 ⇒ 给 Tower 发 `handoff-ground-tower.json`，按 `activation` 适配器按铃。
- 目标 Tower 在岗 ⇒ 只留 handoff，不重复按。
- 写状态卡四格（`result/tickets/commits/blocker`）＋台账；释放出货牌。
- 日报：发了几张、push sha、关了几张、卡在哪、要用户拍什么（仅四类）。
- 通知只发决策价值事件（完成/待审批/连续失败/长期阻塞/预算/安全）；进度进日志（`playbooks/audit.md`）。
