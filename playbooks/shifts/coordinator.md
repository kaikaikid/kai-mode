# 通报协调参考剧本（低频看门狗，只调度）

> 正常链路是角色直接 handoff；本角色只在异常、停机牌/闸门变化、链断时出现。
> 频率：30–60 分钟一醒或事件触发；**不再每 15–20 分钟轮询**。

## 第 0 步：先看全局停止信号

1. 读 `hold-all`／`hold-<role>`；存在 ⇒ 一行台账后退出，不叫班、不清牌。
2. 读闸门 `gate-state.json`：只查一次；必要时更新 `checked_at` 与状态。
   闸门关闭 ⇒ 不叫任何班；闸门状态变化 ⇒ 只唤醒 Tower 一次。
3. 读各角色令牌：holder 非空且心跳新鲜 ⇒ 该角色在岗，不叫。

## 第 1 步：算“有没有异常”

按顺序（项目若有确定性决策脚本，以脚本输出为准）：

1. 有 handoff 且目标角色不在岗、且超过一个冷却窗未被按铃 ⇒ 叫目标（`dispatch`）。
2. 链断：某角色 `working` 心跳超时，或 handoff 已写但目标从未启动，超过 `chain_stale_min` ⇒ 叫目标。
3. 连续失败：同一目标连续 3 次启动失败 ⇒ 写 `hold-<target>`，停。
4. 全仓无活：所有组 `done`/`no-work`，Tower 无队列可发 ⇒ 不叫，记 `idle`。
5. 仅“有待发货/有待排班”但目标已由 Group 直接按铃 ⇒ 不重复叫，记 `already-dispatched`。

**正常 handoff 不经过 Coordinator**；它只补“发令失败/链断/停机”的口。

## 第 2 步：按铃（只按异常）

- 写 `dispatch-plan.json`（目标、原因、handoff 引用、冷却）。
- 走项目 `activation` 适配器；Qoder 推荐“只按铃子会话”（`create_chat_session` → 子会话 `qoder_cron run`）。
- 按完只写 `activation-receipt-<ts>.json`；**不等待目标跑完**。
- 判“起来了没有”只认目标令牌 holder 非空或 `runningAt` 非空；只看 `run` 请求成功＝没起。

## 第 3 步：收工

- 台账一行：叫了谁、为什么、结果（`dispatched`／`already-running`／`activation-failed`／`no-launcher`／`idle`）。
- 不写日报、不改 handoff、不写票面、不施工。
- 缺启动口 ⇒ `no-launcher`，不假装已恢复；由用户/装配台补适配器。

## 硬边界

- 不施工、不排班、不发货、不抢任何令牌、不碰别人的工作树。
- 不建/删定时任务（代际上限 1）；只按现有任务。
- 停机牌只有用户能清；`resume` 只清牌，不替用户改方向。
- 单点风险：心跳停止即机场停；`/set-kai-mode doctor` 巡检，备胎检查由用户另拍。
