# 记忆账本核心（v1）

裁决：[ADR-0037](adr/0037-memory-ledger-and-engine.md) D1–D5/D7/D9。
规划：`handoff/20-plan/2026-11/2026-11-19-role-memory-convergence-plan.md` §8.3–§8.6、§8.12。

一句话：**SQLite WAL 里一张只追加的事件表是唯一真相；FTS5 只是可重建的索引。**
本文件只讲账本核心；daemon、MCP、token 见 `docs/memory-service.md`。
Qdrant、OpenViking 仍是后续里程碑。

## 代码落点

| 文件 | 职责 |
|---|---|
| `engine/memory/ledger.py` | 账本：`memory_events` 表、`memory_current` 视图、propose/commit/rollback/veto、幂等、并发串行化、JSONL 导入 |
| `engine/memory/engine.py` | `MemoryEngine` 接口；默认 `FTS5Engine`；Qdrant/OpenViking 只留桩 |
| `engine/memory/cli.py` | `kai memory ...` 命令面 |
| `engine/memory/daemon.py` · `mcp.py` · `tokens.py` | 本机 daemon、MCP stdio、token 表；见 `docs/memory-service.md` |
| `engine/bin/kai` · `engine/bin/kai.cmd` | 无安装 launcher |
| `scripts/role-memory.py` | v0 JSONL 兼容读；`--db` 时 append 转 propose/commit；`import` 导入旧日志 |
| `scripts/tests/test_memory_ledger.py` · `test_memory_daemon.py` | 账本核心与 daemon/MCP 验收测例 |

## 数据模型

每条事件都有：`memory_id`、`event_type`（propose/commit/supersede/veto/rollback/import）、
`actor_role`、`session_id`、`source`、`namespace`、`kind`、`subject`、`statement`、
`evidence_refs[]`、`before`、`after`、`conflicts_with[]`、`rollback_of`、`status`、
`valid_from`、`valid_to`、`content_hash`、`committed_by`、`layer`、`legacy_id`、
`superseded_by`、`reason`、`business_key`。

- `memory_events`：只 INSERT。supersede／veto／rollback 都是再追加一条事件。
- `memory_current`：视图，取每个 `memory_id` 的最后一条事件；不是第二份真相。
- 业务键：`namespace + kind + subject + content_hash`；同键重复 propose 返回旧条目。
  `content_hash = sha256(NFKC + 去首尾空白 + 合并内部空白后的 statement)`。
- `namespace`：`user` / `shared` / `coordinator-private` / `project:<region-id>` / `task:<run-id>`。
- `kind`：v1 三类 `task_fact` / `failure_lesson` / `preference`；`skill` / `relationship`
  为后续类型，账本与导入先接受。
- `status`：`proposed` / `active` / `superseded` / `vetoed` / `rolled_back`。
- `layer=ego` 只是元数据，导入与 `role-memory.py` 写入时保留，供 `persona.ego.refs` 继续引用。

## 命令

```bash
# 任何角色提候选（不生效）
python engine/bin/kai memory --db .coding/memory/ledger.db propose \
  --actor-role engineer --namespace project:demo --kind failure_lesson \
  --statement "并发写要 BEGIN IMMEDIATE" --evidence "scripts/x.py:42"

# 只有 archivist 能转正／回滚／否决
python engine/bin/kai memory --db .coding/memory/ledger.db commit \
  --actor-role archivist --proposal-id m-0001
python engine/bin/kai memory --db .coding/memory/ledger.db commit \
  --actor-role archivist --namespace project:demo --kind task_fact \
  --statement "新结论" --evidence "docs/y.md:7" --supersedes m-0001
python engine/bin/kai memory --db .coding/memory/ledger.db veto \
  --actor-role archivist --target m-0001 --reason "证据被推翻"
python engine/bin/kai memory --db .coding/memory/ledger.db rollback \
  --actor-role archivist --target m-0001 --reason "后面发现证据不支持"

# 检索：必须给 namespace，按 kind + status=active 过滤；top-k 与 token 上限
python engine/bin/kai memory --db .coding/memory/ledger.db retrieve \
  --namespace project:demo --kind failure_lesson --query "并发" --top-k 5 --max-tokens 1200

# 审计与导出
python engine/bin/kai memory --db .coding/memory/ledger.db lineage --id m-0001 --json
python engine/bin/kai memory --db .coding/memory/ledger.db export --events --out /tmp/memory.jsonl
```

默认账本路径：`$KAI_MEMORY_DB` → `$KAI_AGENT_DATA_ROOT/kai-mode/memory/ledger.db` →
仓内 `.coding/memory/ledger.db`（运行期数据，不入库）。检索引擎默认 `fts5`。

## role-memory.py 兼容

```bash
# v1：读写账本；append 内部是 propose + archivist commit
python scripts/role-memory.py append --db .coding/memory/ledger.db \
  --writer archivist --scope task_fact --statement "…" --evidence "scripts/x.py:42"
python scripts/role-memory.py show  --db .coding/memory/ledger.db --json
python scripts/role-memory.py check --db .coding/memory/ledger.db --json

# 旧 JSONL 导入账本：保留 legacy_id、writer→actor_role、scope→kind、layer=ego
python scripts/role-memory.py import --db .coding/memory/ledger.db \
  --from-jsonl .coding/role-memory.jsonl --writer archivist

# v0 兼容路径仍可用：--log 指向 JSONL 时行为与旧版一致
python scripts/role-memory.py append --log .coding/role-memory.jsonl …
```

## 硬保证

1. **证据强制**：propose／commit／import 至少一个可核验 `evidence_refs`；自述类不算。
2. **单写者**：任何角色可 propose；commit／rollback／veto 只收 `archivist`，越权返回非零。
3. **不删除**：supersede／veto／rollback 只追加状态；旧事件原样保留，`lineage` 可全程审计。
4. **幂等**：同业务键重复 propose／commit 返回旧条目，不追加第二行。
5. **并发**：写路径 `BEGIN IMMEDIATE` 串行化；读走 WAL 快照。
6. **索引是派生物**：FTS 失败不回滚真相；任何时候可从账本重建。
7. **冲突隔离**：`conflicts_with` 指向的条目仍 active 时不注入；对方被 veto/rollback 后恢复。

## v1 不做

Qdrant/OpenViking 实现、自动摘要、图谱、写入 UI、跨机同步。
`MemoryEngine` 的 Qdrant/OpenViking 适配器只留接口桩，调用即如实报未实现。
daemon / MCP / HTTP 的用法与边界见 `docs/memory-service.md`。
