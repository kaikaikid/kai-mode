## 信封规格（机器回执唯一家，渲染时逐字前置）

信封（面向机器的交付信封）头三行固定：

- `schema_version`：信封版本，严格模式拒收未声明字段。
- `task_id` ＋ `role_id`：身份标识；不另造 ID。
- `idempotency_key`：幂等键；重复提交按同键去重。

论断一律进 `claims[]`，每条一个 `kind`，四段分开写、不合并：

- `fact`：已验证的事实，每条带证据引用（文件位置、命令与结果、来源链接）。
- `inference`：推断，标明依据与置信度；不得写成「已完成」「已验证」。
- `unknown`：未验证项与缺什么证据。
- `recommendation`：建议与下一步，标明哪些需要用户决策。

`fact` 必带 `evidence_refs`（URI 真实可访问），缺证据拒收。

成果进 `artifacts[]`（每个含 `artifact_id`／`type`／`format`／`uri`／`version`／`created_by`）。
执行状态不自写，只引用内核事件 `events[]`。

状态词只用四个：完成 / 部分完成 / 阻塞 / 失败。

> 唯一家：本文件。canon 只写各角色自己的专属字段，不复述本段；渲染器在输入契约之后、载体路由之前逐字前置本块。
