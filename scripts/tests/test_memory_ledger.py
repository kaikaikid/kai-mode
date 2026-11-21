"""记忆账本核心测例（Issue #28；ADR-0037 D1–D5/D7/D9）。

断的是可观测行为：
- 只追加：rollback/veto/supersede 不删旧行；
- 证据强制：无证据或自述类证据拒绝；
- 单写者：只有 shaman 能 commit/rollback/veto；
- 幂等：业务键 namespace+kind+subject+content_hash；
- 并发：多连接同时 propose 不丢条目、同内容不重复；
- FTS5：关键词检索 + namespace/kind 过滤 + top-k/token 上限；
- role-memory 兼容：--db 读账本、append 转 propose/commit、JSONL 导入保留 legacy_id。
"""

from __future__ import annotations

import concurrent.futures
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ENGINE_DIR = REPO / "engine"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

from memory.engine import FTS5Engine, OpenVikingEngine, QdrantEngine, build_engine  # noqa: E402
from memory.ledger import (  # noqa: E402
    WRITER_ROLE,
    Ledger,
    MemoryError,
    NotFound,
    PermissionDenied,
)

ROLE_MEMORY = REPO / "scripts" / "role-memory.py"
KAI_ENTRY = ENGINE_DIR / "memory" / "_entry.py"


def open_ledger(db: Path) -> Ledger:
    return Ledger(db, engine=FTS5Engine(db))


def commit(ledger: Ledger, statement: str, *, namespace: str = "shared",
           kind: str = "task_fact", evidence=("tests:x:1",), **kwargs) -> dict:
    return ledger.commit(actor_role=WRITER_ROLE, namespace=namespace, kind=kind,
                         statement=statement, evidence_refs=list(evidence), **kwargs)


def run_cli(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(REPO))


# ── schema / 真相 ───────────────────────────────────────────────────────────
def test_schema_is_wal_events_plus_current_view(tmp_path):
    db = tmp_path / "ledger.db"
    with open_ledger(db) as ledger:
        mode = ledger.conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"
        names = {r[0] for r in ledger.conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        assert "memory_events" in names
        assert "memory_current" in names
        kinds = dict(ledger.conn.execute(
            "SELECT name, type FROM sqlite_master WHERE name IN "
            "('memory_events','memory_current')"))
        assert kinds == {"memory_events": "table", "memory_current": "view"}
        rec = ledger.propose(actor_role="engineer", namespace="task:run-1",
                             kind="task_fact", statement="候选一条",
                             evidence_refs=["tests:x:1"])
        assert rec["status"] == "proposed"
        assert ledger.current_row(rec["memory_id"])["status"] == "proposed"
        assert ledger.count_events() == 1


# ── propose → commit ────────────────────────────────────────────────────────
def test_propose_then_commit_becomes_active(tmp_path):
    with open_ledger(tmp_path / "l.db") as ledger:
        prop = ledger.propose(actor_role="engineer", namespace="project:demo",
                              kind="failure_lesson", statement="先 reflow 再 merge",
                              evidence_refs=["docs/x.md:9"])
        assert prop["status"] == "proposed"
        rec = ledger.commit(actor_role=WRITER_ROLE, proposal_id=prop["memory_id"])
        assert rec["status"] == "active"
        assert rec["memory_id"] == prop["memory_id"]
        assert rec["committed_by"] == WRITER_ROLE
        assert rec["layer"] is None


def test_evidence_is_mandatory_and_self_report_is_not_evidence(tmp_path):
    with open_ledger(tmp_path / "l.db") as ledger:
        with pytest.raises(MemoryError, match="至少给一个证据引用"):
            ledger.propose(actor_role="engineer", namespace="shared",
                           kind="task_fact", statement="x", evidence_refs=[])
        for fake in ("我确认过", "已确认", "无", "-"):
            with pytest.raises(MemoryError, match="自述类"):
                ledger.propose(actor_role="engineer", namespace="shared",
                               kind="task_fact", statement="x",
                               evidence_refs=[fake])
        with pytest.raises(MemoryError, match="至少给一个证据引用"):
            commit(ledger, "直接写但不给证据", evidence=())
        assert ledger.count_events() == 0


# ── 单写者 ──────────────────────────────────────────────────────────────────
def test_only_shaman_can_commit_rollback_and_veto(tmp_path):
    with open_ledger(tmp_path / "l.db") as ledger:
        prop = ledger.propose(actor_role="engineer", namespace="shared",
                              kind="task_fact", statement="待转正",
                              evidence_refs=["tests:x:1"])
        with pytest.raises(PermissionDenied):
            ledger.commit(actor_role="engineer", proposal_id=prop["memory_id"])
        assert ledger.current_row(prop["memory_id"])["status"] == "proposed"

        rec = ledger.commit(actor_role=WRITER_ROLE, proposal_id=prop["memory_id"])
        for actor in ("engineer", "coordinator", ""):
            with pytest.raises(PermissionDenied):
                ledger.veto(actor_role=actor, target=rec["memory_id"], reason="x")
            with pytest.raises(PermissionDenied):
                ledger.rollback(actor_role=actor, target=rec["memory_id"], reason="x")
        assert ledger.current_row(rec["memory_id"])["status"] == "active"
        assert ledger.count_events() == 2


# ── 业务键幂等 ──────────────────────────────────────────────────────────────
def test_business_key_is_idempotent(tmp_path):
    with open_ledger(tmp_path / "l.db") as ledger:
        first = ledger.propose(actor_role="engineer", namespace="project:demo",
                               kind="task_fact", statement="同一事实",
                               evidence_refs=["a:1"])
        second = ledger.propose(actor_role="coordinator", namespace="project:demo",
                                kind="task_fact", statement="  同一事实  ",
                                evidence_refs=["b:2"])
        assert first["created"] is True
        assert second["created"] is False
        assert second["memory_id"] == first["memory_id"]
        assert ledger.count_events() == 1, "同业务键不追加第二行"

        c1 = ledger.commit(actor_role=WRITER_ROLE, proposal_id=first["memory_id"])
        c2 = ledger.commit(actor_role=WRITER_ROLE, proposal_id=first["memory_id"])
        assert c1["created"] is True and c2["created"] is False
        assert ledger.count_events() == 2, "重复 commit 不追加"

        other = ledger.propose(actor_role="engineer", namespace="project:demo",
                               kind="task_fact", statement="同一事实",
                               evidence_refs=["c:3"], subject="another-source")
        assert other["memory_id"] != first["memory_id"], "subject 是业务键的一部分"


# ── supersede / veto / rollback 不删 ────────────────────────────────────────
def test_supersede_keeps_old_row_and_hides_it(tmp_path):
    with open_ledger(tmp_path / "l.db") as ledger:
        old = commit(ledger, "旧结论：用 JSONL", namespace="project:demo")
        new = commit(ledger, "新结论：用 SQLite 账本", namespace="project:demo",
                     supersedes=old["memory_id"])
        old_now = ledger.current_row(old["memory_id"])
        assert old_now["status"] == "superseded"
        assert old_now["superseded_by"] == new["memory_id"]
        assert old_now["valid_to"]
        assert ledger.current_row(new["memory_id"])["status"] == "active"
        events = ledger.events(old["memory_id"])
        assert [e["event_type"] for e in events] == ["commit", "supersede"]
        assert events[0]["status"] == "active", "旧事件原样保留"
        hits = ledger.retrieve(namespace="project:demo", query="结论")
        assert [r["memory_id"] for r in hits] == [new["memory_id"]]


def test_veto_leaves_a_tombstone(tmp_path):
    with open_ledger(tmp_path / "l.db") as ledger:
        rec = commit(ledger, "会被 veto 的条目")
        out = ledger.veto(actor_role=WRITER_ROLE, target=rec["memory_id"],
                          reason="证据后来被推翻")
        assert out["status"] == "vetoed"
        assert out["reason"] == "证据后来被推翻"
        assert ledger.count_events() == 2, "veto 是追加，不删"
        assert ledger.events(rec["memory_id"])[0]["status"] == "active"
        assert ledger.retrieve(namespace="shared", query="veto") == []


def test_rollback_appends_reverse_record_and_keeps_original(tmp_path):
    with open_ledger(tmp_path / "l.db") as ledger:
        rec = commit(ledger, "原先的判断")
        out = ledger.rollback(actor_role=WRITER_ROLE, target=rec["memory_id"],
                              reason="后面发现证据不支持")
        assert out["status"] == "rolled_back"
        assert "证据不支持" in out["statement"]
        events = ledger.events(rec["memory_id"])
        assert len(events) == 2
        assert events[0]["statement"] == "原先的判断", "原记录必须留着"
        assert events[1]["rollback_of"] == rec["memory_id"]
        assert ledger.retrieve(namespace="shared") == []


def test_rollback_requires_reason_and_existing_target(tmp_path):
    with open_ledger(tmp_path / "l.db") as ledger:
        rec = commit(ledger, "x")
        with pytest.raises(MemoryError, match="--reason"):
            ledger.rollback(actor_role=WRITER_ROLE, target=rec["memory_id"], reason="")
        with pytest.raises(NotFound):
            ledger.rollback(actor_role=WRITER_ROLE, target="m-9999", reason="x")


# ── layer=ego 保留 ──────────────────────────────────────────────────────────
def test_layer_ego_is_preserved_as_metadata(tmp_path):
    with open_ledger(tmp_path / "l.db") as ledger:
        prop = ledger.propose(actor_role=WRITER_ROLE, namespace="shared",
                              kind="task_fact", statement="自我层记忆",
                              evidence_refs=["tests:x:1"], layer="ego")
        rec = ledger.commit(actor_role=WRITER_ROLE, proposal_id=prop["memory_id"])
        assert rec["layer"] == "ego"
        assert ledger.current_rows()[0]["layer"] == "ego"


# ── FTS5 检索 ───────────────────────────────────────────────────────────────
def test_fts_search_filters_namespace_kind_and_short_chinese(tmp_path):
    with open_ledger(tmp_path / "l.db") as ledger:
        a = commit(ledger, "记忆账本使用 FTS5 检索", namespace="project:a",
                   kind="task_fact")
        commit(ledger, "另一个项目的秘密", namespace="project:b", kind="task_fact")
        b = commit(ledger, "ledger search works", namespace="project:a",
                   kind="failure_lesson")

        hits = ledger.retrieve(namespace="project:a", query="检索")
        assert [r["memory_id"] for r in hits] == [a["memory_id"]]

        hits = ledger.retrieve(namespace="project:a", query="账本")
        assert [r["memory_id"] for r in hits] == [a["memory_id"]], "2 字中文走 LIKE 回退"

        hits = ledger.retrieve(namespace="project:a", query="ledger")
        assert [r["memory_id"] for r in hits] == [b["memory_id"]]

        hits = ledger.retrieve(namespace="project:a", kind="failure_lesson")
        assert [r["memory_id"] for r in hits] == [b["memory_id"]]

        assert ledger.retrieve(namespace="project:b", query="检索") == [], "不跨项目泄漏"


def test_retrieve_respects_top_k_and_token_budget(tmp_path):
    with open_ledger(tmp_path / "l.db") as ledger:
        for i in range(5):
            commit(ledger, f"并发写测试条目 {i} " + "补充" * 20,
                   namespace="task:run-1", kind="task_fact")
        assert len(ledger.retrieve(namespace="task:run-1", top_k=2)) == 2
        tight = ledger.retrieve(namespace="task:run-1", top_k=5, max_tokens=10)
        assert len(tight) == 0, "首条就超预算时不硬塞"
        assert len(ledger.retrieve(namespace="task:run-1", top_k=5,
                                   max_tokens=2000)) == 5


def test_index_is_derived_and_rebuildable(tmp_path):
    with open_ledger(tmp_path / "l.db") as ledger:
        rec = commit(ledger, "可以被重建的索引", namespace="shared")
        assert [r["memory_id"] for r in ledger.retrieve(namespace="shared",
                                                        query="重建")] == [rec["memory_id"]]
        ledger.engine.conn.execute("DELETE FROM memory_fts")
        assert ledger.retrieve(namespace="shared", query="重建") == [], "索引没了不影响真相"
        assert ledger.current_row(rec["memory_id"])["status"] == "active"
        ledger.rebuild_index()
        assert [r["memory_id"] for r in ledger.retrieve(namespace="shared",
                                                        query="重建")] == [rec["memory_id"]]


def test_conflict_is_isolated_until_resolved(tmp_path):
    with open_ledger(tmp_path / "l.db") as ledger:
        a = commit(ledger, "冲突记录甲", namespace="shared")
        b = commit(ledger, "冲突记录乙", namespace="shared",
                   conflicts_with=[a["memory_id"]])
        hits = ledger.retrieve(namespace="shared", query="冲突")
        assert [r["memory_id"] for r in hits] == [a["memory_id"]], "冲突条目暂不注入"
        ledger.veto(actor_role=WRITER_ROLE, target=a["memory_id"], reason="甲错")
        hits = ledger.retrieve(namespace="shared", query="冲突")
        assert [r["memory_id"] for r in hits] == [b["memory_id"]], "冲突解除后恢复"


# ── 并发写 ──────────────────────────────────────────────────────────────────
def test_concurrent_proposes_are_serialized(tmp_path):
    db = tmp_path / "l.db"

    def propose_one(i: int):
        with open_ledger(db) as ledger:
            rec = ledger.propose(
                actor_role="engineer", namespace="task:run-1", kind="task_fact",
                statement=f"并发事实 {i}", evidence_refs=[f"tests:{i}"])
            return rec["memory_id"], rec["created"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(propose_one, range(12)))
    assert len({mid for mid, _ in results}) == 12
    assert all(created for _, created in results)
    with open_ledger(db) as ledger:
        assert ledger.count_events() == 12

    def propose_same(_i: int):
        with open_ledger(db) as ledger:
            rec = ledger.propose(
                actor_role="engineer", namespace="task:run-1", kind="task_fact",
                statement="同一件事", evidence_refs=["tests:same"])
            return rec["memory_id"], rec["created"]

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        same = list(pool.map(propose_same, range(8)))
    assert len({mid for mid, _ in same}) == 1, "同业务键只留一条"
    assert sum(1 for _, created in same if created) == 1
    with open_ledger(db) as ledger:
        assert ledger.count_events() == 13


# ── lineage / export / check ────────────────────────────────────────────────
def test_lineage_and_export(tmp_path):
    with open_ledger(tmp_path / "l.db") as ledger:
        rec = commit(ledger, "审计一条")
        ledger.rollback(actor_role=WRITER_ROLE, target=rec["memory_id"], reason="撤")
        lineage = ledger.lineage(rec["memory_id"])
        assert [e["event_type"] for e in lineage] == ["commit", "rollback"]
        assert len(ledger.events()) == 2
        assert ledger.current_rows(status=None)[0]["status"] == "rolled_back"
        with pytest.raises(NotFound):
            ledger.lineage("m-9999")


def test_check_catches_tampered_committer_and_missing_evidence(tmp_path):
    with open_ledger(tmp_path / "l.db") as ledger:
        rec = commit(ledger, "会被手改的一条")
        ledger.conn.execute(
            "UPDATE memory_events SET committed_by = 'engineer', evidence_refs = '[]' "
            "WHERE memory_id = ? AND event_type = 'commit'", (rec["memory_id"],))
        problems = ledger.check()
        assert any("committed_by" in p and "只许 shaman" in p for p in problems)
        assert any("没有证据引用" in p for p in problems)


# ── 引擎接口桩 ──────────────────────────────────────────────────────────────
def test_engine_factory_defaults_to_fts5_and_stubs_are_not_silent(tmp_path):
    eng = build_engine(None, tmp_path / "l.db")
    assert isinstance(eng, FTS5Engine)
    eng.close()
    for name, cls in (("qdrant", QdrantEngine), ("openviking", OpenVikingEngine)):
        stub = build_engine(name, tmp_path / "l.db")
        assert isinstance(stub, cls)
        assert stub.available() is False
        with pytest.raises(NotImplementedError):
            stub.ensure_schema()
    with pytest.raises(MemoryError, match="未知记忆引擎"):
        build_engine("mem0", tmp_path / "l.db")


# ── CLI：kai memory ... ─────────────────────────────────────────────────────
def _kai(*args: str) -> subprocess.CompletedProcess:
    return run_cli(KAI_ENTRY, "memory", *args)


def test_cli_end_to_end(tmp_path):
    db = str(tmp_path / "cli.db")
    p = _kai("--db", db, "propose", "--actor-role", "engineer",
             "--namespace", "project:demo", "--kind", "task_fact",
             "--statement", "CLI 候选", "--evidence", "tests:x:1")
    assert p.returncode == 0, p.stderr
    prop = json.loads(p.stdout)
    assert prop["status"] == "proposed"

    p = _kai("--db", db, "commit", "--actor-role", "engineer",
             "--proposal-id", prop["memory_id"])
    assert p.returncode == 3, "非 shaman 不能 commit"

    p = _kai("--db", db, "commit", "--actor-role", "shaman",
             "--proposal-id", prop["memory_id"])
    assert p.returncode == 0, p.stderr
    rec = json.loads(p.stdout)
    assert rec["status"] == "active"

    p = _kai("--db", db, "retrieve", "--namespace", "project:demo",
             "--query", "CLI", "--json")
    assert p.returncode == 0, p.stderr
    assert [r["memory_id"] for r in json.loads(p.stdout)] == [rec["memory_id"]]

    p = _kai("--db", db, "veto", "--actor-role", "engineer",
             "--target", rec["memory_id"], "--reason", "x")
    assert p.returncode == 3
    p = _kai("--db", db, "veto", "--actor-role", "shaman",
             "--target", rec["memory_id"], "--reason", "错误结论")
    assert p.returncode == 0, p.stderr

    p = _kai("--db", db, "lineage", "--id", rec["memory_id"], "--json")
    assert [e["event_type"] for e in json.loads(p.stdout)] == ["propose", "commit", "veto"]
    p = _kai("--db", db, "export", "--events")
    assert p.returncode == 0 and len(p.stdout.strip().splitlines()) == 3


# ── role-memory.py 兼容 ─────────────────────────────────────────────────────
def test_role_memory_append_show_check_read_ledger(tmp_path):
    db = str(tmp_path / "mem.db")
    p = run_cli(ROLE_MEMORY, "append", "--db", db, "--writer", "shaman",
                "--scope", "task_fact", "--statement", "账本模式一条",
                "--evidence", "scripts/x.py:1")
    assert p.returncode == 0, p.stderr
    rec = json.loads(p.stdout)
    assert rec["writer"] == WRITER_ROLE and rec["layer"] == "ego"

    p = run_cli(ROLE_MEMORY, "show", "--db", db, "--json")
    rows = json.loads(p.stdout)
    assert [r["id"] for r in rows] == [rec["memory_id"]]

    p = run_cli(ROLE_MEMORY, "check", "--db", db, "--json")
    out = json.loads(p.stdout)
    assert out["ok"] is True and out["active"] == [rec["memory_id"]]

    p = run_cli(ROLE_MEMORY, "append", "--db", db, "--writer", "engineer",
                "--scope", "task_fact", "--statement", "越权",
                "--evidence", "scripts/x.py:1")
    assert p.returncode == 3

    p = run_cli(ROLE_MEMORY, "rollback", "--db", db, "--writer", "shaman",
                "--target", rec["memory_id"], "--reason", "测试撤销")
    assert p.returncode == 0, p.stderr
    assert json.loads(run_cli(ROLE_MEMORY, "show", "--db", db, "--json").stdout) == []


def test_role_memory_import_preserves_legacy_id(tmp_path):
    log = tmp_path / "legacy.jsonl"
    records = [
        {"id": "m-0001", "ts": "2026-01-01T00:00:00Z", "writer": "coordinator",
         "scope": "task_fact", "layer": "ego", "statement": "旧写者留下的",
         "evidence_refs": ["scripts/x.py:1"], "before": "", "after": "",
         "conflicts_with": [], "rollback_of": None},
        {"id": "m-0002", "ts": "2026-01-02T00:00:00Z", "writer": "shaman",
         "scope": "failure_lesson", "layer": "ego", "statement": "会被回滚的",
         "evidence_refs": ["scripts/y.py:2"], "before": "", "after": "",
         "conflicts_with": [], "rollback_of": None},
        {"id": "m-0003", "ts": "2026-01-03T00:00:00Z", "writer": "shaman",
         "scope": "failure_lesson", "layer": "ego", "statement": "回滚 m-0002：证据不支持",
         "evidence_refs": ["role-memory:m-0002"], "before": "", "after": "",
         "conflicts_with": [], "rollback_of": "m-0002"},
    ]
    log.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n",
                   encoding="utf-8")
    db = tmp_path / "mem.db"
    p = run_cli(ROLE_MEMORY, "import", "--db", str(db), "--from-jsonl", str(log),
                "--writer", "shaman", "--json")
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)["imported"] == 3

    # 重跑幂等：legacy_id 已存在即跳过。
    p = run_cli(ROLE_MEMORY, "import", "--db", str(db), "--from-jsonl", str(log),
                "--writer", "shaman", "--json")
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)["skipped"] == 3

    con = sqlite3.connect(db)
    legacy = {r[0] for r in con.execute(
        "SELECT legacy_id FROM memory_events WHERE legacy_id IS NOT NULL")}
    assert {"m-0001", "m-0002", "m-0003"} <= legacy
    statuses = dict(con.execute(
        "SELECT memory_id, status FROM memory_current WHERE memory_id IN ('m-0001','m-0002')"))
    layers = dict(con.execute(
        "SELECT memory_id, layer FROM memory_current WHERE memory_id IN ('m-0001','m-0002')"))
    con.close()
    assert statuses == {"m-0001": "active", "m-0002": "rolled_back"}
    assert layers == {"m-0001": "ego", "m-0002": "ego"}, "导入保留 layer=ego"

    p = run_cli(ROLE_MEMORY, "check", "--db", str(db), "--json")
    out = json.loads(p.stdout)
    assert out["ok"] is True, out["problems"]
    assert out["active"] == ["m-0001"]
