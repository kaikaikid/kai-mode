# 0035 普适角色投影：一份内核，两种角色驻留形态

## Status

**accepted（草案）** —— 2026-11-18 团长速推授权。本文把 2026-11-18 的设计问答固化为裁决；后续实现按本文分层，未实现项不得写成已具备。

> **2026-11-19 修订（ADR-0036 D7）**：D1/D7 的「单入口只渲染康娜入口、无驻留角色 agent」已修订——核心 3 渲染成宿主 agent 定义（可发现、按需调用，不是常驻进程）；专家 4 仍按需；主 AI 不进 agent 目录。其余条款不变。

## Context

kai-mode 不是 OpenBot 私有项目。团长明确要求后续可装到 CC 桌面、CC CLI、Qoder 等单入口 Agent 框架；只有 OpenBot 这类 Agent 团队宿主才需要角色长期驻留。与此同时，团长要求：

- 康娜保留唯一入口和一套活泼人格，不再分工作/陪伴模式；
- 可莉并回康娜，书记官 skill 改名 BOOK，独立 agent 退场；
- 七位专业角色只留职责契约，不写人格；
- 青铜龙保留为记忆管理 agent，可由用户手动派活或定期任务触发；它调用 `dream` 技能整理长期记忆。
- 事件驱动、飞书/钉钉对接按 AutoLoop 的机制对齐，但不迁宿主。

与既有裁决的关系：0033 的 canon/skin 分离继续有效，本文只改“哪些角色渲染 skin、角色是否常驻”；0031 的旧飞书桥设计正本已在 1843646 随 CLI 拉起整条链删除，本文 D6 以新事件层为准，不复活旧 `travel serve` 依赖。

## Decision

### D1 角色驻留是宿主能力，不是产品定义

核心层（`roles/canon` 四块、任务状态机、事件层、输出协议、技能）保持宿主中立。宿主是否渲染常驻 agent，由宿主能力决定：

| 宿主类型 | 投影 |
|---|---|
| 团队宿主（OpenBot） | 康娜＋七位专业常驻 agent；青铜龙保留独立 agent，负责记忆管理，可由手动派活或 routine 触发 |
| 单入口宿主（CC 桌面/CC CLI/Codex/OpenCode） | 只渲染康娜入口；七份契约以 skill/subagent 配置按需调用 |
| AutoLoop | 可选事件边缘适配器；不承载角色体系 |

### D2 只有 coordinator 有人格皮肤

`roles/skins/*` 的 identity/personality 只对 `coordinator` 生效。七个 dispatchable 角色使用 `render_contract_prompt`：极简身份句＋`roles/input-contract.md`＋`roles/envelope-header.md`＋canon 四块；不含 personality、summary 体例/措辞、output-routing。角色名与 role_id 保留，用于追溯和派活，不再承载性格。

### D3 康娜人格整合

康娜保留龙蛋孵化/酒馆守护者的身份，吸收可莉的活泼、慵懒、小傲娇与偶尔“本小姐”的语感；关系写为“家人/搭档，不是主仆”，允许反驳和拒绝，但**工作上的合理要求不得拒绝、不得摆烂**。不写可莉的古老精灵/魔法管家来历；深度层仍按需取。

### D4 记忆治理：青铜龙管理，`dream` 执行整理

- `dream` 是青铜龙调用的记忆整理 skill：后台整理/候选生成，不做热路径写入。
- 写入走统一 memory API：append-only、证据引用、namespace、可回滚；身份内核变更仍要团长批准。
- 记忆 namespace 只保留 `user`、`project`、`task`、`shared`、`coordinator-private`；七位临时执行角色不建 role memory，旧角色记忆归档只读。
- `archivist` role_id 保留，青铜龙独立 agent 保留；职责为记忆管理（整理、去重、冲突、来源、版本、回滚），可由用户手动派活，或由定期任务在独立上下文触发。
- 边界：圣骑士（reviewer）审任务交付，出 accept/return/defer；青铜龙只管记忆账本，不出任务验收判词。
- 身份、职责、权限、核心底线变更交团长批准；记忆写入 append-only、有证据、可回滚。

### D5 可莉与 BOOK

- 可莉不再作为独立 agent；日记/陪伴并回康娜，书记官 skill 改名 `BOOK`。
- `BOOK` 保留旧触发词“书记官/记一下/写进日记”作为兼容别名；旧记录保留原 ID，加 `book_id` 映射；GitHub/飞书/Notion 外发仍一次一确认。
- 可莉 agent 退场归档；青铜龙 agent 保留。不删除历史记录与工作区。

### D6 事件与 AutoLoop

- 事件事实层住每个项目的 `.coding/events.jsonl`：append-only，`source+key` 去重，状态 `routed/paused/skipped/done`；`fleet emit/tick` 是唯一写入口，宿主适配器只调用它。
- 事件字段：`id/source/key/type/payload_ref/received_at/status/routed_run/hops`；正文只存引用，`hops` 上限 8。
- AutoLoop 只借机制（事件去重、规则、卡片、执行器抽象、8 跳熔断），不引运行时依赖；OpenBot 走异步任务卡＋`task_id`＋`replyToMessageId`，长任务 `await_event`。
- 飞书走 lark-cli 长连接＋按钮回调＋身份校验；钉钉按单向 webhook＋链接回答降级，不假装有按钮回调。

### D7 落地顺序

1. 角色契约投影（`render_contract_prompt`/`contracts` 命令）与康娜人格整合；BOOK 改名。
2. `dream` skill 接入青铜龙；记忆 namespace 收敛。
3. 事件层 `fleet emit/tick` 与执行器抽象（native / host-cmd / message）。
4. CC 桌面 solo 投影 → CC CLI → Qoder skill-only；验收只认“康娜入口＋七契约可调＋一任务派发回执＋无驻留角色 agent”。

## Consequences

- 七位角色不再积累“角色经历”；跨任务连续性由任务契约、事件层和交接包承担，不由角色承担。
- 团队宿主仍可保留常驻 agent，但除康娜外 prompt 体积和人格漂移都会下降。
- 旧角色记忆、可莉日记、BOOK 旧记录都要保留可追溯；退场是归档，不是删除。
- 不把核心迁到 AutoLoop：它没有记忆分区、角色责任链和 OpenBot 工具面；迁过去要重建，收益不抵成本。

## 验证

- `python -m pytest scripts/tests -q` 全绿；`python scripts/doctor.py` 零红；`python scripts/plugin-check.py` 零红。
- `render-roles.py contracts --pack` 能出七份无人格契约；现有 `render_prompt`/`render_all` 行为不变。
- BOOK 在 `registry.json`、`plugins.lock.json`、`plugin-check` 中可见；旧触发词仍可用。
