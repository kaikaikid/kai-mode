# 记忆服务：daemon + MCP（v1）

裁决：[ADR-0037](adr/0037-memory-ledger-and-engine.md) D6/D7；账本本体见 `docs/memory-ledger.md`。
一句话：**账本只有一个写者（本机 daemon）；HTTP 与 MCP 都是它的薄客户端。**

- 监听只许回环：默认 `127.0.0.1:8788`，拒绝 `0.0.0.0` 等非回环地址。
- 鉴权：每 agent 一把 token；治理动作只认 `role=archivist` 的 token。
- 依赖：只用 Python 标准库（`http.server`、`threading`、`urllib`），不装第三方包。
- MCP 进程不直接碰账本，只把工具调用转发给 daemon；因此两条入口的权限与审计一致。

## 代码落点

| 文件 | 职责 |
|---|---|
| `engine/memory/daemon.py` | 回环 HTTP 服务、单实例锁、`/health`、`/v1/memory/*`、权限把关 |
| `engine/memory/mcp.py` | stdio JSON-RPC 适配器；工具转发到 daemon |
| `engine/memory/tokens.py` | `tokens.json`：每 agent 一条记录，只存 sha256 |
| `engine/memory/cli.py` | `kai memory serve / mcp / key ...` |
| `scripts/tests/test_memory_daemon.py` | 本版验收测例（临时端口、临时库） |

## 数据位置

| 数据 | 默认路径 | 覆盖方式 |
|---|---|---|
| 账本 | `$KAI_MEMORY_DB` → `$KAI_AGENT_DATA_ROOT/kai-mode/memory/ledger.db` → 仓内 `.coding/memory/ledger.db` | `--db` |
| token 表 | `$KAI_MEMORY_TOKENS` → 与账本同目录的 `tokens.json` | `--tokens` |
| 单实例锁 | 与账本同目录的 `<账本名>.lock` | daemon 内部 |

`.coding/` 是运行期数据，不入库。

## token

```bash
# 每个 agent 一把；role 默认等于 agent 名
python engine/bin/kai memory key new --agent engineer
python engine/bin/kai memory key new --agent archivist --role archivist

# 轮换：旧 token 立即失效；删除：该 agent 立刻无法鉴权
python engine/bin/kai memory key rotate --agent engineer
python engine/bin/kai memory key remove --agent engineer

# 只看名字与角色，不看密文
python engine/bin/kai memory key list --json
```

- 明文 token 只在 `key new/rotate` 时打印一次；`tokens.json` 里只有 sha256。
- `role` 统一存小写；治理判定只认精确的 `archivist`。不写角色时角色＝agent 名（小写）。
- POSIX 上文件权限 0600、目录 0700；Windows 的 `os.chmod` 语义有限，实际只做 best-effort，
  安全边界靠“只监听回环 + token 不落明文”。
- 拿到别人的 token 就等于拿到那个角色；换人/换机先 `rotate`。

## 起 daemon

```bash
python engine/bin/kai memory serve --db .coding/memory/ledger.db --port 8788
# Windows: engine\bin\kai.cmd memory serve ...
```

前台运行；同一账本第二次启动会被单实例锁拒绝（`已有 daemon 持有锁`）。
崩溃后直接重启即可：已 commit 的事件在 SQLite WAL 里，索引缺失重建（`dream` 或 `admin rebuild_index`）。

### HTTP 面

除 `/health` 外都要 `Authorization: Bearer <token>`。

| 方法 | 路径 | 角色 | 说明 |
|---|---|---|---|
| GET | `/health` | 无 | 进程、账本事件数、active 数、索引错误、单锁队列的 inflight 数 |
| POST | `/v1/memory/retrieve` | 任何 agent | `{namespace, kind?, query?, top_k?, max_tokens?}` |
| POST | `/v1/memory/propose` | 任何 agent | `{namespace, kind, statement, evidence_refs, ...}` |
| POST | `/v1/memory/commit` | archivist | `{proposal_id}` 或完整字段；可带 `supersedes` |
| POST | `/v1/memory/rollback` | archivist | `{target, reason, evidence_refs?}` |
| POST | `/v1/memory/veto` | archivist | `{target, reason, evidence_refs?}` |
| POST | `/v1/memory/lineage` | 任何 agent | `{memory_id}` |
| POST | `/v1/memory/dream` | archivist | 重建索引、统计状态、报告冲突与审计问题 |
| POST | `/v1/memory/export` | archivist | `{events?}`：当前视图或全部事件 |
| POST | `/v1/memory/admin` | archivist | `{action: check / stats / rebuild_index}` |

错误形状：`{"error": {"type": "...", "message": "..."}}`；状态码
400 参数/证据不过、401 缺 token、403 越权、404 找不到、409 状态冲突、500 内部错。

curl 示例（未实测，仅示意参数形状）：

```bash
TOKEN=...   # key new 打印的明文
curl -s http://127.0.0.1:8788/health

curl -s -X POST http://127.0.0.1:8788/v1/memory/propose \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"namespace":"project:demo","kind":"failure_lesson",
       "statement":"并发写要 BEGIN IMMEDIATE","evidence_refs":["docs/x.md:9"]}'

curl -s -X POST http://127.0.0.1:8788/v1/memory/retrieve \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"namespace":"project:demo","query":"并发"}'
```

## MCP（stdio）

```bash
python engine/bin/kai memory mcp --url http://127.0.0.1:8788 --token <token>
# token 也可放 KAI_MEMORY_TOKEN；地址放 KAI_MEMORY_URL
```

- 传输：stdio，一行一条 JSON-RPC 2.0 消息；协议版本 `2024-11-05`。
- 方法：`initialize`、`notifications/initialized`、`tools/list`、`tools/call`、`ping`。
- 工具（与 HTTP 一一对应）：`memory_retrieve` / `memory_propose` / `memory_commit` /
  `memory_rollback` / `memory_veto` / `memory_lineage` / `memory_dream` /
  `memory_export` / `memory_admin`。
- daemon 不可达或 token 缺失时，工具调用返回 `isError: true` 的文本，不会静默成功。

### CC 桌面配置示例（**未实测**）

ADR-0037 写明“CC 桌面 MCP 传输未实测”；下面是配置形状，装好后需要在客户端里实际跑一次
`initialize → tools/list → memory_retrieve` 才算验证。

POSIX：

```json
{
  "mcpServers": {
    "kai-memory": {
      "command": "python",
      "args": [
        "/absolute/path/to/kai-mode/engine/memory/mcp.py",
        "--url", "http://127.0.0.1:8788"
      ],
      "env": { "KAI_MEMORY_TOKEN": "<该 agent 的 token>" }
    }
  }
}
```

Windows：

```json
{
  "mcpServers": {
    "kai-memory": {
      "command": "python",
      "args": [
        "D:\\absolute\\path\\to\\kai-mode\\engine\\memory\\mcp.py",
        "--url", "http://127.0.0.1:8788"
      ],
      "env": { "KAI_MEMORY_TOKEN": "<该 agent 的 token>" }
    }
  }
}
```

注意：`engine/bin/kai` 是 bash 脚本，不能直接交给 `python`；MCP 配置一律指向 `mcp.py`。
配置里含明文 token，文件权限按客户端凭据处理（不要入库、不要贴到公开处）。

## 权限矩阵

| 动作 | 任何 agent | archivist |
|---|---|---|
| retrieve / propose / lineage | 可以 | 可以 |
| commit / rollback / veto | 拒绝（403） | 可以 |
| dream / export / admin | 拒绝（403） | 可以 |

角色取自 token 记录，请求体里的 `actor_role` 一律忽略；账本事件里记录的也是 token 角色。
治理动作仍由账本再验一次 `committed_by=archivist`，两道闸不互相替代。

## v1 的边界与未确认项

- **未实测**：CC 桌面作为 MCP 客户端连本机 daemon；curl 示例；Windows 文件权限是否真的 0600。
- `dream` 目前只做机械整理：重建索引、统计状态、列出冲突隔离与审计问题；不做语义摘要/合并。
- 没有 TLS、限流、远程访问；只用于单机单用户回环（ADR-0037 D10）。
- 没有 `memory_outbox` 异步索引：索引同步失败只记 `index_errors`，真相不回滚，之后用
  `dream` / `admin rebuild_index` 补齐。
- 审计：commit/rollback/veto 的 `actor_role`、`reason`、`evidence_refs` 都在账本事件里；
  `dream` / `export` / `admin` 不改真相，v1 没有单独的访问日志文件。
- Qdrant / OpenViking 仍是接口桩，未实现。
