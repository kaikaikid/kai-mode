"""记忆检索适配器（ADR-0037 D2）。

引擎不拥有真相，只做检索/索引；任何时候都能从账本重建。v1 默认 SQLite FTS5。
Qdrant embedded 与 OpenViking 只留接口桩——不引入任何第三方依赖，也不在导入时联网。
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from .ledger import MemoryError, _retry_locked, estimate_tokens, normalize_statement


class MemoryEngine:
    """检索/索引接口。实现方只读账本派生物，不写真相。"""

    name = "base"

    def available(self) -> bool:
        return False

    def ensure_schema(self) -> None:
        raise NotImplementedError

    def index(self, entry: dict[str, Any]) -> None:
        raise NotImplementedError

    def remove(self, memory_id: str) -> None:
        raise NotImplementedError

    def rebuild(self, ledger: Any) -> None:
        raise NotImplementedError

    def search(self, ledger: Any, *, namespace: str, kind: str | None = None,
               query: str | None = None, top_k: int = 5,
               max_tokens: int = 2000) -> list[dict[str, Any]]:
        raise NotImplementedError

    def close(self) -> None:
        pass


class FTS5Engine(MemoryEngine):
    """SQLite FTS5；中文用 trigram，短查询回退 LIKE 子串。"""

    name = "fts5"

    def __init__(self, db_path: str | Path):
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), timeout=15.0, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout=15000")
        _retry_locked(lambda: self.conn.execute("PRAGMA journal_mode=WAL"))
        self.tokenizer = "trigram"
        self._available = False

    def available(self) -> bool:
        return self._available

    def ensure_schema(self) -> None:
        if self._available:
            return
        try:
            _retry_locked(lambda: self.conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5("
                "memory_id UNINDEXED, namespace UNINDEXED, kind UNINDEXED, "
                "subject, statement, tokenize='trigram')"))
        except sqlite3.OperationalError as exc:
            if "trigram" not in str(exc).lower():
                raise
            self.tokenizer = "unicode61"
            _retry_locked(lambda: self.conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5("
                "memory_id UNINDEXED, namespace UNINDEXED, kind UNINDEXED, "
                "subject, statement)"))
        self._available = True

    def index(self, entry: dict[str, Any]) -> None:
        self.ensure_schema()
        self.conn.execute("DELETE FROM memory_fts WHERE memory_id = ?",
                          (entry["memory_id"],))
        self.conn.execute(
            "INSERT INTO memory_fts (memory_id, namespace, kind, subject, statement) "
            "VALUES (?,?,?,?,?)",
            (entry["memory_id"], entry["namespace"], entry["kind"],
             entry.get("subject") or "", entry.get("statement") or ""))

    def remove(self, memory_id: str) -> None:
        self.ensure_schema()
        self.conn.execute("DELETE FROM memory_fts WHERE memory_id = ?", (memory_id,))

    def rebuild(self, ledger: Any) -> None:
        self.ensure_schema()
        self.conn.execute("DELETE FROM memory_fts")
        for row in ledger.current_rows(status="active"):
            self.index(row)

    def search(self, ledger: Any, *, namespace: str, kind: str | None = None,
               query: str | None = None, top_k: int = 5,
               max_tokens: int = 2000) -> list[dict[str, Any]]:
        self.ensure_schema()
        allowed = {row["memory_id"]: row
                   for row in ledger.current_rows(namespace=namespace, kind=kind)}
        if not allowed:
            return []

        if query:
            ordered_ids = self._match_ids(query)
            ordered_ids = [mid for mid in ordered_ids if mid in allowed]
        else:
            ordered_ids = sorted(
                allowed, key=lambda mid: (allowed[mid].get("ts") or ""), reverse=True)

        out: list[dict[str, Any]] = []
        used = 0
        for memory_id in ordered_ids:
            row = allowed[memory_id]
            if ledger.is_isolated(row):
                continue
            cost = estimate_tokens(row.get("statement") or "")
            if used + cost > max_tokens:
                break
            out.append(row)
            used += cost
            if len(out) >= top_k:
                break
        return out

    def _match_ids(self, query: str) -> list[str]:
        q = normalize_statement(query)
        if not q:
            return []
        ids: list[str] = []
        tokens = [t for t in re.split(r"\s+", q) if t]
        expression = " AND ".join('"' + t.replace('"', '""') + '"' for t in tokens)
        if expression:
            try:
                ids = [r[0] for r in self.conn.execute(
                    "SELECT memory_id FROM memory_fts WHERE memory_fts MATCH ? "
                    "ORDER BY rank", (expression,))]
            except sqlite3.OperationalError:
                ids = []
        if not ids:
            like = f"%{q}%"
            ids = [r[0] for r in self.conn.execute(
                "SELECT memory_id FROM memory_fts WHERE statement LIKE ? OR subject LIKE ? "
                "ORDER BY memory_id", (like, like))]
        seen: set[str] = set()
        out: list[str] = []
        for mid in ids:
            if mid not in seen:
                seen.add(mid)
                out.append(mid)
        return out

    def close(self) -> None:
        try:
            self.conn.close()
        except sqlite3.Error:
            pass


class QdrantEngine(MemoryEngine):
    """Qdrant embedded 适配器桩：v1 不装依赖、不实现。"""

    name = "qdrant"

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = db_path

    def available(self) -> bool:
        return False

    def ensure_schema(self) -> None:
        raise NotImplementedError("Qdrant 适配器未实现：v1 默认使用 FTS5")


class OpenVikingEngine(MemoryEngine):
    """OpenViking 适配器桩：AGPL，只自用可选；不进默认安装面。"""

    name = "openviking"

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = db_path

    def available(self) -> bool:
        return False

    def ensure_schema(self) -> None:
        raise NotImplementedError("OpenViking 适配器未实现：v1 默认使用 FTS5")


def build_engine(name: str | None, db_path: str | Path) -> MemoryEngine:
    """按名字建引擎；默认 FTS5。未实现的适配器如实报错，不退化成静默空检索。"""
    key = (name or "fts5").strip().lower()
    if key in ("fts5", "sqlite", "default"):
        return FTS5Engine(db_path)
    if key == "qdrant":
        return QdrantEngine(db_path)
    if key == "openviking":
        return OpenVikingEngine(db_path)
    raise MemoryError(f"未知记忆引擎：{name!r}（v1 可用 fts5）")
