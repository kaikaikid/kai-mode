"""记忆账本：SQLite WAL、只追加、可回滚、可审计。

裁决：`docs/adr/0037-memory-ledger-and-engine.md` D1/D3/D4/D7/D9。
数据模型见 `handoff/20-plan/2026-11/2026-11-19-role-memory-convergence-plan.md` §8.3。

三件事必须机械成立，不靠提示词自觉：

1. **只追加**：`memory_events` 只有 INSERT；supersede／veto／rollback 都是再追加一条事件，
   旧行一个字节都不改。`memory_current` 是视图，不是第二份真相。
2. **证据强制**：propose／commit／import 的每条记录至少一个可核验的 `evidence_refs`；
   自述类（「我确认过」「已确认」「无」等）不算证据。
3. **单写者**：任何角色可 propose；只有 `archivist` 能 commit／rollback／veto。

业务键 `namespace + kind + subject + content_hash` 幂等：同键重复 propose 返回旧条目，
不追加第二行。`layer=ego` 是元数据，导入与 role-memory 写入时保留。
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

ARCHIVIST = "archivist"

V1_KINDS = ("task_fact", "failure_lesson", "preference")
ALL_KINDS = V1_KINDS + ("skill", "relationship")

STATUSES = ("proposed", "active", "superseded", "vetoed", "rolled_back")
ACTIVE_STATUS = "active"

EXACT_NAMESPACES = ("user", "shared", "coordinator-private")
NAMESPACE_RE = re.compile(r"^(?:project|task):[A-Za-z0-9][A-Za-z0-9._:-]*$")

# 与 scripts/role-memory.py 同一把尺：自述不是证据。
SELF_EVIDENCE = re.compile(
    r"^(已确认|确认过|自述|无|none|-|n/?a)$"
    r"|^(我|本人|咱)(?![^:：/\\]*[:：/\\])[^:：/\\]{0,12}$",
    re.I,
)

REQUIRED_EVENT_FIELDS = (
    "event_id", "memory_id", "event_type", "ts", "actor_role", "namespace",
    "kind", "subject", "statement", "evidence_refs", "status", "content_hash",
    "business_key",
)


class MemoryError(Exception):
    """账本校验不过（参数、证据、状态、格式）。CLI 退出码 2。"""


class PermissionDenied(MemoryError):
    """写了不该写的东西（非 archivist 治理动作）。CLI 退出码 3。"""


class NotFound(MemoryError):
    """找不到目标条目。"""


class ConflictError(MemoryError):
    """条目处于不可转换的状态。"""


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_statement(text: str) -> str:
    """NFKC + 去首尾空白 + 合并内部空白；content_hash 的唯一输入。"""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text))).strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_statement(text).encode("utf-8")).hexdigest()


def estimate_tokens(text: str) -> int:
    """粗略 token 估算：CJK 按 1 字 1 token，其余按 4 字符 1 token。"""
    cjk = sum(1 for ch in text if ord(ch) > 0x2E80)
    other = len(text) - cjk
    return cjk + max(1, (other + 3) // 4)


def validate_namespace(namespace: str) -> str:
    ns = str(namespace or "").strip()
    if ns in EXACT_NAMESPACES:
        return ns
    if NAMESPACE_RE.match(ns):
        return ns
    raise MemoryError(
        "namespace 必须是 user／shared／coordinator-private／"
        "project:<region-id>／task:<run-id> 之一，收到 %r" % (namespace,))


def validate_kind(kind: str) -> str:
    if kind not in ALL_KINDS:
        raise MemoryError(f"kind 必须是 {ALL_KINDS} 之一，收到 {kind!r}")
    return kind


def clean_evidence(items: Iterable[str] | None) -> list[str]:
    out: list[str] = []
    for raw in items or []:
        s = str(raw).strip()
        if not s:
            continue
        if SELF_EVIDENCE.match(s):
            raise MemoryError(
                f"证据不可为自述类：{s!r}；要可核验的指针（文件:行号、URL、命令输出）")
        out.append(s)
    if not out:
        raise MemoryError("至少给一个证据引用（--evidence）；无证据不得写入")
    return out


def validate_layer(layer: str | None) -> str | None:
    if layer is None:
        return None
    s = str(layer).strip()
    if not s:
        return None
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", s):
        raise MemoryError(f"layer 元数据格式不对：{layer!r}")
    return s


def business_key(namespace: str, kind: str, subject: str, digest: str) -> str:
    return "\x1f".join((namespace, kind, subject, digest))


def _retry_locked(fn, attempts: int = 6, delay: float = 0.05):
    """并发初始化时 PRAGMA/DDL 可能瞬时锁库；退避重试，不吞真正的错误。"""
    for i in range(attempts):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                raise
            if i == attempts - 1:
                raise
            time.sleep(delay * (i + 1))
    raise AssertionError("unreachable")


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=15.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=15000")
    _retry_locked(lambda: conn.execute("PRAGMA journal_mode=WAL"))
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_events (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT NOT NULL UNIQUE,
    memory_id       TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    ts              TEXT NOT NULL,
    actor_role      TEXT NOT NULL,
    session_id      TEXT,
    source          TEXT,
    namespace       TEXT NOT NULL,
    kind            TEXT NOT NULL,
    subject         TEXT NOT NULL,
    statement       TEXT NOT NULL,
    evidence_refs   TEXT NOT NULL,
    before          TEXT NOT NULL DEFAULT '',
    after           TEXT NOT NULL DEFAULT '',
    conflicts_with  TEXT NOT NULL DEFAULT '[]',
    rollback_of     TEXT,
    status          TEXT NOT NULL,
    valid_from      TEXT,
    valid_to        TEXT,
    content_hash    TEXT NOT NULL,
    committed_by    TEXT,
    layer           TEXT,
    legacy_id       TEXT,
    superseded_by   TEXT,
    reason          TEXT,
    business_key    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_memory_events_memory ON memory_events(memory_id);
CREATE INDEX IF NOT EXISTS ix_memory_events_business ON memory_events(business_key);
CREATE INDEX IF NOT EXISTS ix_memory_events_status ON memory_events(status);
CREATE UNIQUE INDEX IF NOT EXISTS ux_memory_business_event
    ON memory_events(business_key, event_type)
    WHERE event_type IN ('propose', 'commit', 'import');
CREATE UNIQUE INDEX IF NOT EXISTS ux_memory_legacy_id
    ON memory_events(legacy_id)
    WHERE legacy_id IS NOT NULL;

CREATE VIEW IF NOT EXISTS memory_current AS
SELECT e.*
FROM memory_events AS e
JOIN (
    SELECT memory_id, MAX(seq) AS seq
    FROM memory_events
    GROUP BY memory_id
) AS latest ON latest.seq = e.seq;
"""


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    for key in ("evidence_refs", "conflicts_with"):
        try:
            d[key] = json.loads(d.get(key) or "[]")
        except (TypeError, ValueError):
            d[key] = []
    return d


class Ledger:
    """一个账本文件＝一个真相。所有写操作走 `BEGIN IMMEDIATE` 串行化。"""

    def __init__(self, db_path: str | Path, engine: Any = None):
        self.path = Path(db_path)
        self.conn = _connect(self.path)
        _retry_locked(lambda: self.conn.executescript(SCHEMA))
        self.engine = engine
        self.index_errors: list[str] = []
        if engine is not None:
            try:
                engine.ensure_schema()
            except Exception as exc:  # 索引失败不回滚真相
                self.index_errors.append(f"索引初始化失败：{exc!r}")

    # -- 连接与事务 ---------------------------------------------------------
    def close(self) -> None:
        try:
            self.conn.close()
        finally:
            if self.engine is not None:
                closer = getattr(self.engine, "close", None)
                if callable(closer):
                    closer()

    def __enter__(self) -> "Ledger":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @contextmanager
    def _write(self) -> Iterator[None]:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    # -- 查询 ---------------------------------------------------------------
    def current_row(self, memory_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM memory_current WHERE memory_id = ?", (memory_id,)).fetchone()
        return _row_to_dict(row)

    def events(self, memory_id: str | None = None) -> list[dict[str, Any]]:
        if memory_id is None:
            rows = self.conn.execute(
                "SELECT * FROM memory_events ORDER BY seq").fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM memory_events WHERE memory_id = ? ORDER BY seq",
                (memory_id,)).fetchall()
        return [d for d in (_row_to_dict(r) for r in rows) if d is not None]

    def current_rows(self, namespace: str | None = None, kind: str | None = None,
                     status: str | None = ACTIVE_STATUS) -> list[dict[str, Any]]:
        sql = "SELECT * FROM memory_current WHERE 1=1"
        args: list[Any] = []
        if namespace:
            sql += " AND namespace = ?"
            args.append(namespace)
        if kind:
            sql += " AND kind = ?"
            args.append(kind)
        if status:
            sql += " AND status = ?"
            args.append(status)
        sql += " ORDER BY ts DESC, seq DESC"
        return [d for d in (_row_to_dict(r) for r in self.conn.execute(sql, args))
                if d is not None]

    def count_events(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM memory_events").fetchone()[0])

    def find_by_business_key(self, key: str,
                             event_types: tuple[str, ...] = ("propose", "commit", "import")
                             ) -> dict[str, Any] | None:
        marks = ",".join("?" for _ in event_types)
        row = self.conn.execute(
            f"SELECT * FROM memory_events WHERE business_key = ? "
            f"AND event_type IN ({marks}) ORDER BY seq LIMIT 1",
            (key, *event_types)).fetchone()
        return _row_to_dict(row)

    def find_by_legacy_id(self, legacy_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM memory_events WHERE legacy_id = ? ORDER BY seq LIMIT 1",
            (legacy_id,)).fetchone()
        return _row_to_dict(row)

    def lineage(self, memory_id: str) -> list[dict[str, Any]]:
        rows = self.events(memory_id)
        if not rows:
            raise NotFound(f"账本里没有 {memory_id}")
        return rows

    def is_isolated(self, entry: dict[str, Any]) -> bool:
        """冲突隔离：冲突对象仍 active 时不注入；对方已 veto/rollback/supersede 即视为已解。"""
        conflicts = entry.get("conflicts_with") or []
        for cid in conflicts:
            other = self.current_row(str(cid))
            if other is not None and other.get("status") == ACTIVE_STATUS:
                return True
        return False

    # -- 写：propose --------------------------------------------------------
    def propose(self, *, actor_role: str, namespace: str, kind: str, statement: str,
                evidence_refs: Iterable[str], subject: str | None = None,
                source: str | None = None, session_id: str | None = None,
                before: str = "", after: str = "",
                conflicts_with: Iterable[str] | None = None,
                layer: str | None = None) -> dict[str, Any]:
        actor_role = str(actor_role or "").strip()
        if not actor_role:
            raise MemoryError("actor_role 不能为空")
        namespace = validate_namespace(namespace)
        kind = validate_kind(kind)
        stmt = str(statement or "").strip()
        if not stmt:
            raise MemoryError("statement 不能为空")
        evidence = clean_evidence(evidence_refs)
        layer = validate_layer(layer)
        subject = str(subject or source or "unspecified").strip() or "unspecified"
        digest = content_hash(stmt)
        key = business_key(namespace, kind, subject, digest)
        conflicts = [str(x).strip() for x in (conflicts_with or []) if str(x).strip()]

        existing = self.find_by_business_key(key)
        if existing is not None:
            entry = self.current_row(existing["memory_id"]) or existing
            entry = dict(entry)
            entry["created"] = False
            return entry

        try:
            with self._write():
                existing = self.find_by_business_key(key)
                if existing is not None:
                    entry = dict(self.current_row(existing["memory_id"]) or existing)
                    entry["created"] = False
                    return entry
                memory_id = self._next_memory_id()
                self._insert_event(
                    memory_id=memory_id, event_type="propose", status="proposed",
                    actor_role=actor_role, session_id=session_id, source=source,
                    namespace=namespace, kind=kind, subject=subject, statement=stmt,
                    evidence_refs=evidence, before=before, after=after,
                    conflicts_with=conflicts, rollback_of=None, layer=layer,
                    committed_by=None, legacy_id=None, superseded_by=None,
                    reason=None, content_hash_value=digest, business_key_value=key,
                )
        except sqlite3.IntegrityError:
            existing = self.find_by_business_key(key)
            if existing is None:
                raise
            entry = dict(self.current_row(existing["memory_id"]) or existing)
            entry["created"] = False
            return entry
        entry = dict(self.current_row(memory_id) or {})
        entry["created"] = True
        return entry

    # -- 写：commit ---------------------------------------------------------
    def commit(self, *, actor_role: str, proposal_id: str | None = None,
               namespace: str | None = None, kind: str | None = None,
               statement: str | None = None, evidence_refs: Iterable[str] | None = None,
               subject: str | None = None, source: str | None = None,
               session_id: str | None = None, before: str = "", after: str = "",
               conflicts_with: Iterable[str] | None = None, layer: str | None = None,
               supersedes: str | None = None) -> dict[str, Any]:
        self._require_archivist(actor_role)

        if proposal_id:
            src = self.current_row(proposal_id)
            if src is None:
                raise NotFound(f"找不到候选：{proposal_id}")
            if src["status"] == ACTIVE_STATUS:
                out = dict(src)
                out["created"] = False
                return out
            if src["status"] != "proposed":
                raise ConflictError(
                    f"{proposal_id} 当前状态 {src['status']}，不能再 commit")
            namespace = src["namespace"]
            kind = src["kind"]
            statement = src["statement"]
            evidence_refs = src["evidence_refs"]
            subject = src["subject"]
            source = src["source"]
            session_id = src["session_id"]
            before = src["before"]
            after = src["after"]
            conflicts_with = src["conflicts_with"]
            layer = src["layer"]

        if namespace is None or kind is None or statement is None:
            raise MemoryError("commit 需要 --proposal-id 或完整的 namespace/kind/statement")
        namespace = validate_namespace(namespace)
        kind = validate_kind(kind)
        stmt = str(statement or "").strip()
        if not stmt:
            raise MemoryError("statement 不能为空")
        evidence = clean_evidence(evidence_refs)
        layer = validate_layer(layer)
        subject = str(subject or source or "unspecified").strip() or "unspecified"
        digest = content_hash(stmt)
        key = business_key(namespace, kind, subject, digest)
        conflicts = [str(x).strip() for x in (conflicts_with or []) if str(x).strip()]

        existing = self.find_by_business_key(key, ("commit", "import"))
        if existing is not None:
            out = dict(self.current_row(existing["memory_id"]) or existing)
            out["created"] = False
            if supersedes:
                self._supersede_if_active(supersedes, out["memory_id"], actor_role)
            return out

        # 直接 commit 时若已有同键候选，就把那条候选转正，避免同内容两条记忆。
        proposal = self.find_by_business_key(key, ("propose",))
        memory_id = proposal["memory_id"] if proposal else None
        if supersedes:
            self._assert_supersedable(supersedes, memory_id)

        with self._write():
            existing = self.find_by_business_key(key, ("commit", "import"))
            if existing is not None:
                out = dict(self.current_row(existing["memory_id"]) or existing)
                out["created"] = False
                memory_id = out["memory_id"]
            else:
                if memory_id is None:
                    memory_id = self._next_memory_id()
                self._insert_event(
                    memory_id=memory_id, event_type="commit", status=ACTIVE_STATUS,
                    actor_role=actor_role, session_id=session_id, source=source,
                    namespace=namespace, kind=kind, subject=subject, statement=stmt,
                    evidence_refs=evidence, before=before, after=after,
                    conflicts_with=conflicts, rollback_of=None, layer=layer,
                    committed_by=ARCHIVIST, legacy_id=None, superseded_by=None,
                    reason=None, content_hash_value=digest, business_key_value=key,
                )
        if supersedes:
            self._supersede_if_active(supersedes, memory_id, actor_role)
        self._sync_index(memory_id)
        out = dict(self.current_row(memory_id) or {})
        out["created"] = True
        return out

    # -- 写：veto / rollback ------------------------------------------------
    def veto(self, *, actor_role: str, target: str, reason: str,
             evidence_refs: Iterable[str] | None = None) -> dict[str, Any]:
        self._require_archivist(actor_role)
        reason = str(reason or "").strip()
        if not reason:
            raise MemoryError("veto 必须写 --reason（审计要能看出为什么撤）")
        src = self.current_row(target)
        if src is None:
            raise NotFound(f"找不到要 veto 的条目：{target}")
        if src["status"] == "vetoed":
            out = dict(src)
            out["created"] = False
            return out
        if src["status"] != ACTIVE_STATUS:
            raise ConflictError(f"{target} 当前状态 {src['status']}，不能 veto")
        evidence = self._governance_evidence(evidence_refs, f"ledger:veto:{target}")
        now = utcnow()
        with self._write():
            self._insert_event(
                memory_id=target, event_type="veto", status="vetoed",
                actor_role=actor_role, session_id=src.get("session_id"),
                source=src.get("source"), namespace=src["namespace"],
                kind=src["kind"], subject=src["subject"], statement=src["statement"],
                evidence_refs=evidence, before="", after="",
                conflicts_with=src.get("conflicts_with") or [], rollback_of=None,
                layer=src.get("layer"), committed_by=ARCHIVIST, legacy_id=None,
                superseded_by=None, reason=reason,
                content_hash_value=src["content_hash"],
                business_key_value=src["business_key"], valid_to=now,
            )
        self._sync_index(target, remove=True)
        out = dict(self.current_row(target) or {})
        out["created"] = True
        return out

    def rollback(self, *, actor_role: str, target: str, reason: str,
                 evidence_refs: Iterable[str] | None = None) -> dict[str, Any]:
        self._require_archivist(actor_role)
        reason = str(reason or "").strip()
        if not reason:
            raise MemoryError("回滚必须写 --reason（审计要能看出为什么撤）")
        src = self.current_row(target)
        if src is None:
            raise NotFound(f"找不到要回滚的记录：{target}")
        if src["status"] == "rolled_back":
            out = dict(src)
            out["created"] = False
            return out
        if src["status"] not in (ACTIVE_STATUS, "superseded"):
            raise ConflictError(f"{target} 当前状态 {src['status']}，不能 rollback")
        evidence = self._governance_evidence(evidence_refs, f"ledger:rollback:{target}")
        now = utcnow()
        with self._write():
            self._insert_event(
                memory_id=target, event_type="rollback", status="rolled_back",
                actor_role=actor_role, session_id=src.get("session_id"),
                source=src.get("source"), namespace=src["namespace"],
                kind=src["kind"], subject=src["subject"],
                statement=f"回滚 {target}：{reason}",
                evidence_refs=evidence, before=src.get("after") or "",
                after=src.get("before") or "",
                conflicts_with=src.get("conflicts_with") or [], rollback_of=target,
                layer=src.get("layer"), committed_by=ARCHIVIST, legacy_id=None,
                superseded_by=None, reason=reason,
                content_hash_value=src["content_hash"],
                business_key_value=src["business_key"], valid_to=now,
            )
        self._sync_index(target, remove=True)
        out = dict(self.current_row(target) or {})
        out["created"] = True
        return out

    def _assert_supersedable(self, old_id: str, new_id: str | None) -> None:
        if new_id is not None and old_id == new_id:
            raise ConflictError("supersedes 不能指向自己")
        old = self.current_row(old_id)
        if old is None:
            raise NotFound(f"找不到要 supersede 的条目：{old_id}")
        if old["status"] not in ("active", "superseded"):
            raise ConflictError(f"{old_id} 当前状态 {old['status']}，不能 supersede")

    def _supersede_if_active(self, old_id: str, new_id: str, actor_role: str) -> None:
        if old_id == new_id:
            raise ConflictError("supersedes 不能指向自己")
        old = self.current_row(old_id)
        if old is None:
            raise NotFound(f"找不到要 supersede 的条目：{old_id}")
        if old["status"] == "superseded":
            return
        if old["status"] != ACTIVE_STATUS:
            raise ConflictError(f"{old_id} 当前状态 {old['status']}，不能 supersede")
        with self._write():
            self._insert_event(
                memory_id=old_id, event_type="supersede", status="superseded",
                actor_role=actor_role, session_id=old.get("session_id"),
                source=old.get("source"), namespace=old["namespace"],
                kind=old["kind"], subject=old["subject"], statement=old["statement"],
                evidence_refs=old.get("evidence_refs") or [],
                before="", after="",
                conflicts_with=old.get("conflicts_with") or [], rollback_of=None,
                layer=old.get("layer"), committed_by=ARCHIVIST, legacy_id=None,
                superseded_by=new_id, reason=f"superseded by {new_id}",
                content_hash_value=old["content_hash"],
                business_key_value=old["business_key"], valid_to=utcnow(),
            )
        self._sync_index(old_id, remove=True)

    # -- 写：legacy JSONL 导入 ---------------------------------------------
    def import_legacy(self, records: Iterable[dict[str, Any]]) -> dict[str, int]:
        """导入 `scripts/role-memory.py` 的 JSONL；保留 `legacy_id`，按 legacy_id 幂等。"""
        imported = 0
        skipped = 0
        for rec in records:
            legacy_id = str(rec.get("id") or "").strip()
            if legacy_id and self.find_by_legacy_id(legacy_id) is not None:
                skipped += 1
                continue
            statement = str(rec.get("statement") or "").strip()
            kind = rec.get("scope") or rec.get("kind") or "task_fact"
            if kind not in ALL_KINDS:
                kind = "task_fact"
            namespace = rec.get("namespace") or "shared"
            try:
                namespace = validate_namespace(namespace)
            except MemoryError:
                namespace = "shared"
            actor_role = str(rec.get("writer") or rec.get("actor_role") or ARCHIVIST)
            evidence = [str(x).strip() for x in (rec.get("evidence_refs") or [])
                        if str(x).strip()]
            layer = rec.get("layer")
            try:
                layer = validate_layer(layer)
            except MemoryError:
                layer = None
            subject = str(rec.get("subject") or rec.get("source") or "unspecified")
            digest = content_hash(statement)
            key = business_key(namespace, kind, subject, digest)
            rollback_of = rec.get("rollback_of")
            now = str(rec.get("ts") or utcnow())

            with self._write():
                if rollback_of:
                    target = self._resolve_memory_id(str(rollback_of))
                    if target is not None:
                        tgt = self.current_row(target) or {}
                        self._insert_event(
                            memory_id=target, event_type="rollback",
                            status="rolled_back",
                            actor_role=actor_role,
                            session_id=rec.get("session_id"),
                            source=rec.get("source") or "role-memory-jsonl",
                            namespace=tgt.get("namespace", namespace),
                            kind=tgt.get("kind", kind),
                            subject=tgt.get("subject", subject),
                            statement=statement or f"回滚 {rollback_of}",
                            evidence_refs=evidence,
                            before=tgt.get("after") or "",
                            after=tgt.get("before") or "",
                            conflicts_with=rec.get("conflicts_with") or [],
                            rollback_of=target,
                            layer=tgt.get("layer", layer) or layer,
                            committed_by=ARCHIVIST, legacy_id=legacy_id or None,
                            superseded_by=None, reason=statement or None,
                            content_hash_value=tgt.get("content_hash", digest),
                            business_key_value=tgt.get("business_key", key),
                            ts=now,
                        )
                        imported += 1
                        continue
                memory_id = self._claim_memory_id(legacy_id)
                self._insert_event(
                    memory_id=memory_id, event_type="import", status=ACTIVE_STATUS,
                    actor_role=actor_role, session_id=rec.get("session_id"),
                    source=rec.get("source") or "role-memory-jsonl",
                    namespace=namespace, kind=kind, subject=subject,
                    statement=statement, evidence_refs=evidence,
                    before=str(rec.get("before") or ""),
                    after=str(rec.get("after") or ""),
                    conflicts_with=[str(x) for x in (rec.get("conflicts_with") or [])],
                    rollback_of=None, layer=layer, committed_by=ARCHIVIST,
                    legacy_id=legacy_id or None, superseded_by=None, reason=None,
                    content_hash_value=digest, business_key_value=key, ts=now,
                )
                imported += 1
        self.rebuild_index()
        return {"imported": imported, "skipped": skipped, "events": self.count_events()}

    # -- 检索 ---------------------------------------------------------------
    def retrieve(self, *, namespace: str, kind: str | None = None,
                 query: str | None = None, top_k: int = 5,
                 max_tokens: int = 2000) -> list[dict[str, Any]]:
        namespace = validate_namespace(namespace)
        if kind:
            kind = validate_kind(kind)
        if self.engine is not None:
            return self.engine.search(self, namespace=namespace, kind=kind,
                                      query=query, top_k=top_k,
                                      max_tokens=max_tokens)
        return self._retrieve_sql(namespace, kind, query, top_k, max_tokens)

    def _retrieve_sql(self, namespace: str, kind: str | None, query: str | None,
                      top_k: int, max_tokens: int) -> list[dict[str, Any]]:
        rows = self.current_rows(namespace=namespace, kind=kind)
        if query:
            needle = normalize_statement(query).casefold()
            rows = [r for r in rows
                    if needle in (r["statement"] + " " + r["subject"]).casefold()]
        out: list[dict[str, Any]] = []
        used = 0
        for row in rows:
            if self.is_isolated(row):
                continue
            cost = estimate_tokens(row["statement"])
            if used + cost > max_tokens:
                break
            out.append(row)
            used += cost
            if len(out) >= top_k:
                break
        return out

    # -- 索引 ---------------------------------------------------------------
    def rebuild_index(self) -> None:
        if self.engine is None:
            return
        try:
            self.engine.rebuild(self)
        except Exception as exc:
            self.index_errors.append(f"索引重建失败：{exc!r}")

    def _sync_index(self, memory_id: str, remove: bool = False) -> None:
        if self.engine is None:
            return
        try:
            if remove:
                self.engine.remove(memory_id)
                return
            row = self.current_row(memory_id)
            if row is not None and row.get("status") == ACTIVE_STATUS:
                self.engine.index(row)
            else:
                self.engine.remove(memory_id)
        except Exception as exc:  # 索引失败不回滚真相（ADR-0037 D7）
            self.index_errors.append(f"索引同步失败 {memory_id}：{exc!r}")

    # -- 校验 ---------------------------------------------------------------
    def check(self) -> list[str]:
        problems: list[str] = []
        rows = self.events()
        ids = {r["memory_id"] for r in rows}
        for i, r in enumerate(rows, 1):
            label = r.get("event_id") or f"#{i}"
            for field in REQUIRED_EVENT_FIELDS:
                if r.get(field) in (None, ""):
                    problems.append(f"{label} 缺字段 {field}")
            if r.get("kind") not in ALL_KINDS:
                problems.append(f"{label} 的 kind 非法：{r.get('kind')!r}")
            try:
                validate_namespace(str(r.get("namespace") or ""))
            except MemoryError:
                problems.append(f"{label} 的 namespace 非法：{r.get('namespace')!r}")
            if r.get("status") not in STATUSES:
                problems.append(f"{label} 的 status 非法：{r.get('status')!r}")
            if r.get("event_type") in ("commit", "import") and \
                    r.get("committed_by") != ARCHIVIST:
                problems.append(
                    f"{label} 的 committed_by 是 {r.get('committed_by')!r}，只许 {ARCHIVIST}")
            if r.get("event_type") in ("commit", "import", "propose"):
                ev = r.get("evidence_refs") or []
                if not ev:
                    problems.append(f"{label} 没有证据引用")
                for e in ev:
                    if SELF_EVIDENCE.match(str(e).strip()):
                        problems.append(f"{label} 的证据是自述类：{e!r}")
            if r.get("rollback_of") and r["rollback_of"] not in ids:
                problems.append(f"{label} 回滚了不存在的记录 {r['rollback_of']}")
        return problems

    # -- 内部 ---------------------------------------------------------------
    def _require_archivist(self, actor_role: str) -> None:
        if actor_role != ARCHIVIST:
            raise PermissionDenied(
                f"拒绝写入：记忆的唯一读写改者是 `{ARCHIVIST}`，收到的是 `{actor_role}`。"
                "别的角色只能 propose，不能 commit/rollback/veto（ADR-0037 D4）。")

    def _governance_evidence(self, items: Iterable[str] | None,
                             default: str) -> list[str]:
        out = [str(x).strip() for x in (items or []) if str(x).strip()]
        return out or [default]

    def _next_memory_id(self) -> str:
        rows = self.conn.execute("SELECT memory_id FROM memory_events").fetchall()
        nums = []
        for row in rows:
            m = re.fullmatch(r"m-(\d+)", str(row[0]))
            if m:
                nums.append(int(m.group(1)))
        return f"m-{(max(nums) + 1) if nums else 1:04d}"

    def _claim_memory_id(self, preferred: str | None) -> str:
        if preferred and self.current_row(preferred) is None:
            return preferred
        return self._next_memory_id()

    def _resolve_memory_id(self, wanted: str) -> str | None:
        if self.current_row(wanted) is not None:
            return wanted
        hit = self.find_by_legacy_id(wanted)
        return hit["memory_id"] if hit else None

    def _insert_event(self, *, memory_id: str, event_type: str, status: str,
                      actor_role: str, session_id: str | None, source: str | None,
                      namespace: str, kind: str, subject: str, statement: str,
                      evidence_refs: list[str], before: str, after: str,
                      conflicts_with: list[str], rollback_of: str | None,
                      layer: str | None, committed_by: str | None,
                      legacy_id: str | None, superseded_by: str | None,
                      reason: str | None, content_hash_value: str,
                      business_key_value: str, ts: str | None = None,
                      valid_to: str | None = None) -> None:
        now = ts or utcnow()
        self.conn.execute(
            """
            INSERT INTO memory_events
              (event_id, memory_id, event_type, ts, actor_role, session_id, source,
               namespace, kind, subject, statement, evidence_refs, before, after,
               conflicts_with, rollback_of, status, valid_from, valid_to,
               content_hash, committed_by, layer, legacy_id, superseded_by, reason,
               business_key)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "e-" + uuid.uuid4().hex, memory_id, event_type, now, actor_role,
                session_id, source, namespace, kind, subject, statement,
                json.dumps(evidence_refs, ensure_ascii=False), before, after,
                json.dumps(conflicts_with, ensure_ascii=False), rollback_of, status,
                now, valid_to, content_hash_value, committed_by, layer, legacy_id,
                superseded_by, reason, business_key_value,
            ),
        )
