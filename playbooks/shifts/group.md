# Group-A/B 参考剧本（跃迁 · 班内连飞 · 组内并行）

> 项目专用剧本与跃迁协议优先。命令占位符从 `.ai/kai-mode.project.json` 的 `runtime`/`wip` 取。
> 本剧本只写组怎么飞；排班归 Tower，发货归 Ground。

## 第 0 步：令牌、队列、租约

1. 读停机牌 `hold-all`／`hold-<lane>`；存在 ⇒ 一行台账后退出。
2. 领本组令牌 `<runtime.token> --runway <lane> --as <班次名> --enforce`；退 1 ⇒ 已换人，整班不干活。
3. 读队列 `<state>/dispatch-queue-<lane>.json`（带 `version`/`seq`）与逐票租约。
   **没有租约＝没有职权**；不自行扩权、不自己造票。
4. 队列空／无租约 ⇒ 给 Tower 发 `need-schedule` handoff；释放令牌；退出。不跑巡检、不派子代理。

## 第 1 步：组内派工（并行有界）

- 每张票一个**新机长**（子代理，fresh context）；组内并行 `wip.per_group`（先取 2）。
- 只有**租约文件域不重叠**的票可同飞；冲突 ⇒ 停手写 `need-tower`，不自行裁决。
- 组的主上下文只做编排：读队列/租约/回执，不读票面正文、不读 diff；派工卡与回执走文件。
- 派工卡必带：租约逐枚清单、禁改清单、止损三句（主体 60/30、差量 35/20、只读 15–20）、回执 ≤25 行、`scope-check check`＋`commit --only` 两格。
- 组内按需启动三职：`researcher`（先查）／`implementer`（租约内实现）／`reviewer`（独立验收）；写代码的人不能给自己出 `pass`（`playbooks/execution-roles.md`）。
- 上下文 >65% 写检查点，>80% 停手交新上下文；旧检查点只是线索（`playbooks/context.md`）。

## 第 2 步：每张票的闭环

1. 建树；**第一件事打 marker 空提交**（没有 marker 的零提交树会被收尾门当可拆）。
2. 机长只动租约内文件；先写测再写实现；跑派工卡给的定向命令。
3. 本地提交只 `git commit --only -F <文件> -- <路径>`；禁 `git add -A`。
4. 交**新上下文 reviewer** 验收（不是写代码的那个）：机检＋逐条 AC＋截图/VLM；产出 `acceptance-<票>.json`。
5. 验收 `verdict=pass` 且 `unverified=[]` 才可发 ship handoff；否则写 `partial`/`blocked`，不硬发。
5续. 不过且 `attempt < max_attempts` ⇒ `validating → repairing`：新 attempt、新上下文、同合同；同一错误签名 2 次即停（`playbooks/reliability.md`）。
6. 发两张 handoff：
   - `group → ground`：票号/commit/branch/验收路径＋哈希；
   - `group → tower`：要下一张/补水位。
7. 按完铃**继续下一张**，不等待并车；Ground 并车与组下一张可并行。
8. 每次状态转移写 `task-<票>.json` 与 `events.jsonl`；提交/验收/阻塞都要有事件，没有事件 = 没发生。

## 第 3 步：活队列（新任务可插入）

- 每张票边界**重读队列**（按 `version`/`seq`）；Tower 插入的新票在下一张生效，不打断正在飞的那张。
- 队列新增与已飞票文件域重叠 ⇒ 不飞新票，写 `need-tower` 让 Tower 重发租约。
- 到达 `wip` 上限或 8 张/60 分钟 ⇒ 写 `handoff`，交下一班。

## 第 4 步：止损与交班

三条硬止损（任一命中即交班，不硬撑）：① 连续 2 道门红；② 本段超 60 分钟；③ 心跳刷不动（换人）。

- 没活：`no-work`；库存够且无待发：`done`；有未发：`partial`；卡死：`stuck`／`need-user`。
- 收工：写状态卡四格＋台账；释放本组令牌；逐票销租约；交班条 note 逐张列 `#票号 commit sha`，不藏多做的票。
- **不并车、不 push、不排班、不写 `plan.json`、不抢出货牌。**

## token 预算（用户 2026-10-21 令）

- handoff ≤500 B；只放 ID/路径/哈希；不写票名、AC 原文、diff、小作文。
- 状态卡 ≤四格；长叙事进日报一次。
- 子代理回执 ≤25 行；主上下文不复读回执过程。
- 验收只读摘要（`verdict`/`unverified`），失败才读细节；不把验收全文塞进主上下文。
