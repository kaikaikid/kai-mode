"""记忆账本核心（ADR-0037 D1–D5/D7/D9）。

- `ledger`：SQLite WAL 追加式账本；`memory_events` 是真相，`memory_current` 是派生视图。
- `engine`：检索/索引适配器；默认 FTS5，Qdrant/OpenViking 只留接口桩。
- `cli`：`kai memory ...` 命令面。

真相在账本，索引随时可重建；本包不含 daemon、Qdrant 与网络传输。
"""

__all__ = ["ledger", "engine", "cli"]
