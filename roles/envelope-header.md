## 信封规格（机器回执唯一家，渲染时逐字前置）

- 信封头三行：`schema_version`；`task_id`＋`role_id`；`idempotency_key`。
- 论断进 `claims[]`，每条一个 kind：`fact`（带 `evidence_refs`）／`inference`（标依据与置信度）／`unknown`（缺什么证据）／`recommendation`（谁要决策）。
- 成果进 `artifacts[]`：artifact_id／type／format／uri／version／created_by。
- 状态词：完成／部分完成／阻塞／失败；执行状态只引内核 `events[]`，不自写。
- 详细字段与 URI 约束见 `docs/schema.md`；本块只列必须，不复制字段表。

> 唯一家：本文件。canon 不复述，渲染器逐字前置。
