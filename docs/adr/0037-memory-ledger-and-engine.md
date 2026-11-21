# 0037 记忆地基：账本、引擎适配与 daemon

> **2026-11-20 演变注（ADR-0038 D7）**：namespace 设计意图保持 `user / project:<region-id> / task:<run-id> / shared / coordinator-private`，但 ADR-0038 将“记忆最小单位”上提为项目｜冒险团，并取消独立 role memory；实际物理映射仍按本 ADR 状态与 V3.0 §21.6 解禁门执行，未解禁前不得声称 project/team 隔离已生效。

## Status

**proposed（草案）** —— 2026-11-19 设计会话收敛，待团长复核后转 accepted。
计划：`handoff/20-plan/2026-11/2026-11-19-role-memory-convergence-plan.md`（§八、§九）。

## Context

- kai-vass 已有 127 个记忆模块；当前底座 OpenViking 0.5.x（AGPLv3，localhost HTTP），SQLite/Qdrant/Mem0 并存；Cognee 退役；旧 `memory_records` 退役。
- 记忆系统长期没有真实用户：先造存储、后找消费者。
- kai-mode 已有 persona-layer 的记忆接口（retrieve/propose/commit/rollback）、`role-memory.py` 的 append-only 账本、ADR-0035 D4 的 namespace／单写者。
- 目标：跨 agent 框架、可审计、可回滚、引擎可替换；只自用，暂不对外分发。

## Decision

### D1 真相：append-only 账本

- SQLite WAL `memory_events` + `memory_current` 视图；事件只追加，状态用 supersede／veto／rollback。
- 索引是派生物；任何时候可从账本重建。

### D2 引擎适配（MemoryEngine）

- 默认 Qdrant embedded + SQLite FTS5（Apache-2.0）。
- OpenViking 可选（AGPL，自用）；Mem0／Graphiti 可选。
- 引擎不拥有真相；只做检索／索引。

### D3 数据模型

- namespace：`user` / `project:<region-id>` / `task:<run-id>` / `shared` / `coordinator-private`。
- kind：`task_fact` / `failure_lesson` / `preference`（v1）；`skill`（P1.5）；`relationship`（P2）。
- 字段按计划 §8.3；业务键 `namespace + kind + subject + content_hash`；`session_id` 只做来源。
- `layer=ego` 保留为元数据，供 `persona.ego.refs`。

### D4 写入路径

- 任何角色 propose；archivist 校验证据／去重／冲突后 commit；只有 archivist 能 commit／rollback／veto。
- 证据强制；冲突 `isolate_then_escalate`；不删除，只追加状态。
- `dream` 是唯一后台整理入口。

### D5 检索与注入

- `namespace + kind + status=active`；top-k + 1–2k token；摘要优先。
- reviewer 特例：任务卡 + diff + 测试/CI + `project`/`shared`；工程师报告只当 claim；不读 task 提案／会话。
- 禁止整库注入／跨项目泄漏。

### D6 服务：daemon + MCP

- 本机用户服务；`127.0.0.1:8788`；HTTP JSON + MCP stdio 适配；每 agent token；archivist 专属治理。
- MCP 工具：`memory_retrieve / propose / commit / rollback / veto / lineage / dream / export / admin`。
- 首个客户端：CC 桌面 + MCP。

### D7 并发／幂等／故障

- daemon 单队列 + `BEGIN IMMEDIATE`；propose 可并发；commit 串行。
- 业务键幂等；`memory_outbox` 异步索引；崩溃恢复从 WAL／outbox。

### D8 迁移

- 盘点 → 契约冻结 → 影子双写/双读 → 回填账本/重建索引 → 切写 → 只读归档 + 回滚开关。
- 影子退出：连续 7 天证据覆盖 100%、precision@5 不低于旧路径、p95 可接受、0 未解释冲突。
- 不迁原始会话；只迁证据-backed 长期记忆。

### D9 `role-memory.py`

- v1 兼容读；`append` 变薄客户端；JSONL→SQLite；保留 `legacy_id`；`layer=ego` 保留。
- `persona.ego.refs` 指向账本 id；身份内核变更仍走团长批准。

### D10 AGPL 边界

- 只自用＝单机单用户回环；OpenViking 适配器不进默认安装面／导出链；对外分发前法务复核。

### D11 ADR-0029 边界

- ADR-0029 的「不把 SQLite 当真相源」限监督面（看板／服务）；记忆账本另裁。

### D12 reviewer 输入落地（M3）

- `fleet review` 卡新增 `evidence.test_output_path` / `evidence.ci_output_path` / `memory_refs[]`。
- 施工腿把测试/CI 输出写到 run 目录；`fleet report` 登记；内核按 `memory_refs` 注入 `project`/`shared`。
- reviewer 仍只用 `Read/Grep/Glob`，不自己跑测试；缺证据时 verdict 必须注明「无测试证据」。

## Consequences

- 一个账本、一个写者、八个读过滤器；角色不是分区。
- kai-vass 变客户端；127 模块按需搬治理（veto／visibility／GC／时序）。
- daemon／token 增加运维面；首个客户端 CC。
- v1 三类，`skill`／`relationship` 后补。

## Alternatives

- OpenViking 当真相：否决——AGPL、可编辑上下文、非 append-only。
- 八个角色各建库：否决——碎片化、跨角色不可复用。
- 继续用 `role-memory.py` JSONL：否决——无索引、无并发、难迁移。
- 把 kai-vass 整体搬进来：否决——127 模块耦合、先造存储后找用户的老路。

## 验证

- 证据覆盖 100%；rollback 全通过；业务键幂等；并发写测试；影子 7 天判据；p95 延迟；每次注入 token。
- `python scripts/doctor.py --with-tests` 全绿（或仅既有无关红）。

## 未确认

- kai-vass 外部仓／OpenViking 文档未核。
- CC 桌面 MCP 传输未实测。
- 15k tokenizer 未定。
