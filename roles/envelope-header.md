# 信封头三行（机器回执唯一家）

- `schema_version`：信封版本，严格模式拒收未声明字段。
- `task_id` ＋ `role_id`：身份标识；不另造 ID。
- `idempotency_key`：幂等键；重复提交按同键去重。
- 论断一律进 `claims[]`，每条一个 `kind`（`fact`/`inference`/`unknown`/`recommendation`），`fact` 必带 `evidence_refs`（URI 真实可访问，缺证据拒收）。
- 成果进 `artifacts[]`（全字段 `artifact_id`/`type`/`format`/`uri`/`version`/`created_by`）；执行状态不自写，只引用内核事件 `events[]`。

> 唯一家：本文件。canon output_contract 不复述头三行七种写法，只写“信封头三行见 `roles/envelope-header.md`，专属字段见下”。
