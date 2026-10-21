# 塔台参考剧本（只排班）

> 项目专用剧本优先。命令占位符从 `.ai/kai-mode.project.json` 的 `runtime` 取；不要在本文件写死项目路径。

## 第 0 步：闸门与令牌

1. 读停机牌 `hold-all`／`hold-tower`；存在 ⇒ 写一行台账后退出，不排班。
2. 领取塔台管理令牌 `<runtime.token> --runway tower --as <班次名> --enforce`；退 1 ⇒ 本跑道有人，整班不干活。
3. 通过后 `--takeover --ticket <首票或 none>`；每进入下一步前刷心跳，holder 不是自己就停。

## 第 1 步：读状态，不抢 Ground 的活

- 读 Group 状态卡、handoff、队列、令牌、Ground 的 ship ledger。
- `need-ship`／待发货 ⇒ **不自己发**；Ground 会处理。Tower 只在状态卡点名。
- `need-schedule`／水位不足／队列空 ⇒ 进入排班。
- 读 `plan.json` 与顺序层；不读票面正文、不读 diff。
- 逐票过 DoR（`playbooks/task-contract.md`）：十字段齐全、AC 可机检、租约逐枚、依赖已清、风险/审批已标；缺项不进 `ready`。
- 票面变化：记 `contract_sha256`；执行中票面变了，Group 会停手，Tower 重新确认合同并决定是否重发租约。

## 第 2 步：清刹车（受控）

- 列出在制树：票号、分支、diff、脏件、marker。
- **只回收**“票 CLOSED＋分支已并/无 diff＋无脏件”的树；脏树、未提交内容、别人的在制树一律不碰，点名留给用户。
- 清账动作（解封/拆刀/补账/摘已完成行）可做机械票；新方向票只进签派单。

## 第 3 步：排班与发租约

- 按 `wip.global` 检查在制；超了先清账，不新开票。
- 按优先级给 Group-A/B 各发一串租约（每票一租约，逐枚文件，不收整片目录）。
- 队列原子写（临时档＋rename），带 `version`/`seq`：

```json
{"schema":1,"lane":"group-a","tickets":[1829,1831],"version":3,"issued_at":"...","issued_by":"tower"}
```

- 同一文件同一时刻只发一个组；新票插入不改正在飞的那张。
- 队列写完 `cat` 回读；没发租约就丢 handoff ＝ 让组空跑。
- 发租约同时把票状态写 `ready → claimed`，落 `task-state-<票>.json` 与 `events.jsonl`。

## 第 4 步：叫组

- 目标组空闲 ⇒ 发 `handoff-tower-group-a.json`，按项目 `activation` 适配器按铃。
- 目标组在岗 ⇒ 只留 handoff，不重复按。
- 全被挡／无机械票可开 ⇒ 写 `blocked`＋原因与 `need-coordinator`；不自行写 `hold-all`。

## 第 5 步：收工

- 写状态卡四格＋台账；释放塔台令牌。
- 日报：排了几张、发了几张租约、卡在哪、要用户拍什么（仅肉眼可见/花钱/对外发布/不可回滚四类）。
- 0 张必须点名原因；数字只出自门/脚本 stdout。
- Loop A 反无限生成：新票必须有父票/证据；同一父票一次最多 3 张后续票；不为凑队列开无 AC 的票。
- 通知只报决策价值事件；普通进度进台账（`playbooks/audit.md`）。
