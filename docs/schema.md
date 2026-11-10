# schema —— 字段映射与版本策略

版本策略正本见 `GLOSSARY.md`「Schema 版本策略」；本文是四类实体的**字段映射表**。
升级规则：只追加字段／枚举，不删旧字段；创建时锁定 `schema_version`，运行中不静默升级；
旧任务按锁定版本执行；至少保留上一版只读兼容；信封严格模式拒收未声明字段。

## 版本一览

| 实体 | 代码键 | 当前版本 | 定义位置 |
|---|---|---|---|
| Run | `state["schema_version"]` | 2 | `engine/coding/__init__.py`（`SCHEMA_VERSION`） |
| Task | `task["schema_version"]` | 1 | `engine/coding/__init__.py`（`TASK_SCHEMA_VERSION`） |
| Artifact | `artifact["schema_version"]` | 1 | 同上（`ARTIFACT_SCHEMA_VERSION`） |
| Receipt（Envelope） | `receipt["schema_version"]` | 1 | 同上（`RECEIPT_SCHEMA_VERSION`） |

Receipt 与 Envelope 是同一件（面向机器的交付信封），代码键统一用 `receipt`。

## Task 字段映射（run 的 tasks[] 元素）

| 字段 | 类型 | 来源 | 自版本 |
|---|---|---|---|
| `id` | str | plan 写入（`cmd_plan`） | run schema 1 |
| `title` | str | plan | 1 |
| `brief` | str | plan | 1 |
| `tier` | str | plan（`light|medium|careful|heavy|fable`） | 1 |
| `deps` | list[str] | plan | 1 |
| `touchset` | list[str] | plan | 1 |
| `ac` | list[str] | plan | 1 |
| `ui` | bool | plan | 1 |
| `status` | str | 内核推进（`pending|ready|running|review|returned|accepted|abandoned|blocked|failed`） | 1 |
| `attempts` | int | 内核（return 计数，≥3 转 blocked 并锁定） | 1 |
| `session_id` | str \| null | claim 占位 | 1 |
| `defects` | str | return／verdict 写回 | 1 |
| `review` | object | verdict 写回（`{verdict, defects, reason, session}`） | 2 |
| `auto_fails` | int | `fleet auto` 失败计数 | 2 |
| `blocked_reason` | str \| null | 内核 | **3**（新增） |
| `blocked_at` | float \| null | 内核 | **3** |
| `return_locked` | bool | 内核（第三次 return 后不再自动重开） | **3** |
| `schema_version` | int | plan 写入时锁定（`TASK_SCHEMA_VERSION`） | **3** |

## Artifact 字段映射（交付成果引用）

| 字段 | 类型 | 含义 | 自版本 |
|---|---|---|---|
| `artifact_id` | str | 稳定标识 | 1 |
| `type` | str | `report|table|diagram|visualization|code|dataset|dashboard|image|video|html|svg|mermaid|markdown` | 1 |
| `format` | str | `markdown|json|csv|xlsx|html|svg|png|mp4|...` | 1 |
| `uri` | str | 真实可访问路径／URL；不把大文件塞进 JSON | 1 |
| `version` | str | 成果自身版本 | 1 |
| `created_by` | str | `role_id`（哪个角色产出） | 1 |
| `schema_version` | int | 创建时锁定 | 1 |

内核当前不生成 Artifact 实体；本表是契约预留，首个写入方必须带全字段。

## Receipt / Envelope 字段映射（面向机器的交付信封）

| 字段 | 类型 | 含义 | 自版本 |
|---|---|---|---|
| `schema_version` | int | 创建时锁定；严格模式拒收未声明字段 | 1 |
| `task_id` | str | 任务标识 | 1 |
| `role_id` | str | 交付角色的稳定 role_id（不另造 ID） | 1 |
| `idempotency_key` | str | 幂等键；重复提交按同键去重 | 1 |
| `claims[]` | list[object] | 每条 `{kind: fact|inference|unknown|recommendation, text, evidence_refs[]}`；fact 必带 `evidence_refs`，缺证据拒收 | 1 |
| `evidence_refs[]` | list[str] | 来源／文件／日志／命令输出的 URI，必须真实可访问 | 1 |
| `artifacts[]` | list[object] | 上方 Artifact 全字段 | 1 |
| `verdict` | object \| null | **仅 reviewer 输出**：`{value: accept|return|defer, defects[], deferred_items[], reason}`；旧 `PASS` 等禁用 | 1 |
| `defects[]` | list[object] | `{severity: BLOCKER|MAJOR|MINOR|INFO, location, evidence, suggestion}` | 1 |
| `deferred_items[]` | list[object] | defer 必填：`{question, reason, priority}` | 1 |
| `owner_deferred[]` | list[object] | 只追加、不阻塞：进 run 的团长队列 | 1 |
| `handoff` | object \| null | `{from, to, status: accepted|rejected|needs_clarification, at}` | 1 |
| `events[]` | list[str] | 执行过程只引用事件 ID（内核写状态，Agent 不写） | 1 |
| `blocked_reason` | str \| null | BLOCKED 原因码（见下） | 1 |

**信封里没有 `execution_status`**：执行状态只由任务管理器（内核）写进 state.json；
Agent 侧的开始／结束／阻塞只作事件引用（`events[]`），不自写 `completed|blocked|failed`。

## BLOCKED 原因码

任务或 run 转 blocked 时，`blocked_reason` 必须取下列之一（写入方负责，doctor 可核）：

| 原因码 | 触发 |
|---|---|
| `return_limit` | 第三次 return（attempts ≥ 3，此后 `return_locked=true` 不自动重开） |
| `auto_fail_limit` | `fleet auto` 同一任务失败 2 次 |
| `read_only_violation` | 只读会话在树上留了改动 |
| `merge_conflict` | 自动 rebase 后仍冲突 |
| `ship_failed` | 收尾门红／push 被拒 |
| `timeout` | 子代理超时（重派一次后仍超时） |
| `cancel_late` | 取消请求到达时任务已在终态（迟到取消，只记录不逆转） |
| `worker_clamped` | Worker 数被 crew_limit 钳制（记事件，不阻塞） |
| `missing_capability` | 宿主起不了子代理等缺件 |

## CANCELLED→CLOSED

`fleet stop` 把 run 相位写成 `cancelled`（已存在）；`closed` 是取消后的确认落档相位：
cancelled 的 run 不再有 live session 时视为 closed 候选，由 `fleet gc` 收口（资源清理由它负责）。
任务侧取消：运行中任务的取消与迟到取消都记事件（`events[]`），终态任务不逆转。

## 可观测：关联 ID 与脱敏（部分未实现，如实标记）

已实现、可测的关联键：

| 关联 | 键 |
|---|---|
| task → run | `state.json` 路径 `.coding/runs/<run_id>/` ＋ `fleet <run> <task>` 参数 |
| session → task | `session.task_id` ＋ `task.session_id` |
| 事件 → run | `state["events"][]`（`worker_clamped`／`handoff_confirmed`／`cancel_late`／`task_blocked`／`return_limit_blocked`／`auto_fail_limit_blocked`／`ship_failed`） |
| 交接 → run | `state["handoffs"][]`（`fleet confirm` 三态） |
| 团长队列 → task | `owner_deferred[].task_id` |

未实现（缺证据，标未验证，不宣称完成）：

- `trace_id`／`span_id` 全链路透传：当前无写入方，预留键名，待实现。
- Token 来源标注与注入账单：`run.budget = {max_tokens, used_tokens}` 已有槽位，
  但 `used_tokens` 当前无写入方（`grep used_tokens engine/` 只有两处初始化 0）；账单待实现。
- 脱敏：规则是 state.json／session 报告不得含密钥（密钥只走环境变量与 Vault），
  但强制扫描与拒收当前无实现；待实现。
- Context Manifest（上下文组装清单）：预留形状
  `{run_id, schema_version, tasks[], gates, budget, events[]}`，
  与 `fleet resume`／`status` 输出同源；独立 `fleet context` 命令待实现。

## 固定案例与 COM（未实现，如实标记）

- 固定评估案例集：待建。建成后每例含输入任务图、期望终态、回归断言，进 `engine/tests/`。
- COM（大白话能力考）：只考康娜——验收形态是给 coordinator 角色的转述抽查，
  七个专业角色考专业直述，不考小白话。题库与评分器待建，不虚构通过数。
