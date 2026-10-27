# -*- coding: utf-8 -*-
"""唯一直接接触 SQLite 的模块。

其他模块（采集 / 判据 / 渲染）一律通过本模块的接口读写，不自己拼 SQL、
不自己开连接。换存储后端时只改这里。

约定：
- 一板一库：`<板库根>/<板名>/board.db`
- 每次采集一个 `run_id`（ISO 时间戳），同一个 run 内的行共享它
- `v_flight` 视图只认「最新 run 出现过的航班」，避免残留旧票
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone

SCHEMA_VERSION = "1"
DB_FILENAME = "board.db"

# 口径刀（2026-10-26）新增列：SQLite 的 ALTER 不认 IF NOT EXISTS，
# 所以补列走 Python 侧幂等确保（PRAGMA 查一下再决定加不加），不写进 .sql。
ENSURE_COLUMNS = {
    "flight": (
        ("owner_from", "TEXT"),     # lane | assignee | infer | ""（掌机是事实还是推断）
        ("prev_stage", "TEXT"),     # 被降级成「停滞」前原本在哪一阶段
        ("stale_days", "INTEGER"),  # 距上次更新几天（渲染期也会现算，这里留痕）
    ),
}


def _ensure_columns(conn) -> list[str]:
    """给已存在的表补新列（幂等）。返回实际补上的列名。"""
    added = []
    for table, cols in ENSURE_COLUMNS.items():
        have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        if not have:                       # 表还没建（首次 migrate 前）→ 交给 .sql
            continue
        for name, typ in cols:
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {typ}")
                added.append(f"{table}.{name}")
    conn.commit()
    return added


def now_iso() -> str:
    """本地时区的 ISO 秒级时间戳（人读友好；排序仍单调）。"""
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def new_run_id() -> str:
    """一轮采集的 id。同级格式保证字符串排序＝时间排序。"""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def db_path(board_dir: str) -> str:
    return os.path.join(board_dir, DB_FILENAME)


def connect(path: str) -> sqlite3.Connection:
    """开库并确保目录存在。调用方负责 close。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate(conn: sqlite3.Connection, schema_dir: str) -> list[str]:
    """按文件名顺序跑 schema/*.sql（幂等）。返回本次实际读到的文件。

    补列先于建视图：`v_flight` 要 SELECT 新列，列不在就会在查询期炸。
    """
    if not os.path.isdir(schema_dir):
        raise FileNotFoundError(f"schema 目录不存在：{schema_dir}")
    _ensure_columns(conn)
    applied = []
    for fn in sorted(os.listdir(schema_dir)):
        if not fn.endswith(".sql"):
            continue
        with open(os.path.join(schema_dir, fn), encoding="utf-8") as f:
            conn.executescript(f.read())
        applied.append(fn)
    conn.commit()
    return applied


def schema_version(conn: sqlite3.Connection) -> str | None:
    try:
        row = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()
        return row["value"] if row else None
    except sqlite3.OperationalError:
        return None


# ── 采集记账 ────────────────────────────────────────────────────────

def record_source(conn, run_id, source_id, type_, status, row_count=0, detail=None):
    conn.execute(
        "INSERT INTO source_run(run_id, source_id, type, status, row_count, detail, at)"
        " VALUES (?,?,?,?,?,?,?)",
        (run_id, source_id, type_, status, int(row_count), detail, now_iso()),
    )


# ── 航班写入 ────────────────────────────────────────────────────────

_FLIGHT_COLS = (
    "uid", "ticket", "title", "stage", "stage_label", "owner", "persona",
    "milestone", "planned", "why", "source", "url", "labels", "open",
    "updated_at", "closed_at", "seen_run",
    "owner_from", "prev_stage", "stale_days",
)


def upsert_flight(conn, rec: dict, run_id: str) -> None:
    """按 uid 覆盖写。缺的列走默认值；list 字段落成逗号分隔。"""
    row = {c: rec.get(c) for c in _FLIGHT_COLS}
    row["labels"] = ",".join(rec.get("labels") or []) or None
    row["source"] = rec.get("source") or "unknown"
    row["stage"] = rec.get("stage") or "undefined"
    row["stage_label"] = rec.get("stage_label") or row["stage"]
    if not row.get("title"):
        row["title"] = rec.get("ticket") or rec.get("uid") or "（无标题）"
    row["seen_run"] = run_id
    row["planned"] = 1 if rec.get("planned") else 0
    row["open"] = 0 if (rec.get("closed") or rec.get("open") is False) else 1
    row["updated_at"] = rec.get("updated_at") or now_iso()
    conn.execute(
        "INSERT INTO flight(uid, ticket, title, stage, stage_label, owner, persona,"
        " milestone, planned, why, source, url, labels, open, updated_at, closed_at,"
        " seen_run, owner_from, prev_stage, stale_days)"
        " VALUES (:uid,:ticket,:title,:stage,:stage_label,:owner,:persona,"
        " :milestone,:planned,:why,:source,:url,:labels,:open,:updated_at,:closed_at,"
        " :seen_run,:owner_from,:prev_stage,:stale_days)"
        " ON CONFLICT(uid) DO UPDATE SET"
        " ticket=excluded.ticket, title=excluded.title, stage=excluded.stage,"
        " stage_label=excluded.stage_label, owner=excluded.owner, persona=excluded.persona,"
        " milestone=excluded.milestone, planned=excluded.planned, why=excluded.why,"
        " source=excluded.source, url=excluded.url, labels=excluded.labels,"
        " open=excluded.open, updated_at=excluded.updated_at,"
        " closed_at=COALESCE(excluded.closed_at, flight.closed_at),"
        " seen_run=excluded.seen_run, owner_from=excluded.owner_from,"
        " prev_stage=excluded.prev_stage, stale_days=excluded.stale_days",
        row,
    )


def add_evidence(conn, uid: str, kind: str, value: str | None, run_id: str) -> None:
    conn.execute(
        "INSERT INTO evidence(uid, kind, value, at, run_id) VALUES (?,?,?,?,?)",
        (uid, kind, value, now_iso(), run_id),
    )


def replace_schedules(conn, run_id: str, rows: list[dict]) -> int:
    """一轮采集的日表快照整体替换（幂等，不累加）。"""
    conn.execute("DELETE FROM schedule_row WHERE run_id = ?", (run_id,))
    for i, r in enumerate(rows, 1):
        conn.execute(
            "INSERT OR REPLACE INTO schedule_row"
            "(lane, table_date, line_no, ticket, summary, note, run_id)"
            " VALUES (?,?,?,?,?,?,?)",
            (r["lane"], r["table_date"], r.get("line_no", i),
             r.get("ticket"), r.get("summary"), r.get("note"), run_id),
        )
    return len(rows)


def record_board_run(conn, run_id, kpi: dict, sources: dict,
                     board_sha256: str | None = None,
                     html_sha256: str | None = None) -> None:
    import json
    conn.execute(
        "INSERT INTO board_run(run_id, at, kpi_json, sources_json, board_sha256, html_sha256)"
        " VALUES (?,?,?,?,?,?)",
        (run_id, now_iso(), json.dumps(kpi, ensure_ascii=False),
         json.dumps(sources, ensure_ascii=False), board_sha256, html_sha256),
    )


def replace_runtime(conn, run_id: str, payload: dict) -> None:
    """一轮一条运行态快照（队列＋令牌）；只留最近 N 轮，治库无限涨。"""
    import json
    conn.execute("INSERT OR REPLACE INTO runtime_state(run_id, at, payload)"
                 " VALUES (?,?,?)",
                 (run_id, now_iso(), json.dumps(payload, ensure_ascii=False)))
    conn.execute("DELETE FROM runtime_state WHERE run_id NOT IN"
                 " (SELECT run_id FROM runtime_state ORDER BY run_id DESC LIMIT ?)",
                 (RUNTIME_KEEP,))


def fetch_runtime(conn) -> dict:
    import json
    row = conn.execute("SELECT payload FROM runtime_state"
                       " ORDER BY run_id DESC LIMIT 1").fetchone()
    if not row:
        return {}
    try:
        data = json.loads(row["payload"])
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


RUNTIME_KEEP = 20


def replace_handoffs(conn, run_id: str, rows: list[dict]) -> int:
    """一轮采集的交接索引整体替换（幂等，不累加）。"""
    conn.execute("DELETE FROM handoff_doc WHERE run_id = ?", (run_id,))
    for i, r in enumerate(rows):
        conn.execute(
            "INSERT OR REPLACE INTO handoff_doc"
            "(run_id, slot, rel_path, title, doc_date, ord) VALUES (?,?,?,?,?,?)",
            (run_id, r.get("slot"), r.get("rel_path"), r.get("title"),
             r.get("doc_date"), r.get("ord", i)),
        )
    return len(rows)


# ── 读取（渲染层只用这些）─────────────────────────────────────────

def latest_run(conn) -> str | None:
    row = conn.execute("SELECT MAX(run_id) AS r FROM source_run").fetchone()
    return row["r"] if row and row["r"] else None


def fetch_flights(conn, includes: list[str] | None = None) -> list[dict]:
    sql = "SELECT * FROM v_flight"
    args: list = []
    if includes:
        sql += " WHERE stage IN (%s)" % ",".join("?" * len(includes))
        args = list(includes)
    sql += " ORDER BY stage, updated_at DESC"
    return [dict(r) for r in conn.execute(sql, args)]


def fetch_schedules(conn, run_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM schedule_row WHERE run_id = ? "
        "ORDER BY table_date DESC, lane, line_no", (run_id,)
    )]


def fetch_handoffs(conn, run_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM handoff_doc WHERE run_id = ? ORDER BY ord", (run_id,)
    )]


def fetch_sources(conn) -> dict:
    run = latest_run(conn)
    if not run:
        return {}
    return {r["source_id"]: {"status": r["status"], "rows": r["row_count"],
                             "detail": r["detail"]}
            for r in conn.execute(
                "SELECT * FROM source_run WHERE run_id = ?", (run,))}


def commit(conn) -> None:
    conn.commit()


if __name__ == "__main__":  # 手工建库／查版本
    import argparse
    ap = argparse.ArgumentParser(description="flight-info 库维护")
    ap.add_argument("--db", required=True, help="board.db 路径")
    ap.add_argument("--schema", required=True, help="schema 目录")
    a = ap.parse_args()
    c = connect(a.db)
    files = migrate(c, a.schema)
    print(f"已应用：{', '.join(files)}")
    print(f"schema_version = {schema_version(c)}")
    c.close()
