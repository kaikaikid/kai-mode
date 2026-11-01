"""账本：事件去重、会话绑定、限速计数、run 绑定、出站队列。全部 stdlib sqlite3。"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  dedup_key TEXT PRIMARY KEY,
  bot TEXT, kind TEXT, received_at REAL, payload TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
  binding TEXT PRIMARY KEY,          -- 飞书会话：bot|chat|thread 或 bot|open_id
  bot TEXT, host_session TEXT, adapter TEXT,
  created_at REAL, last_used REAL, turns INTEGER DEFAULT 0, tokens INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS counters (
  bucket TEXT, window TEXT, value INTEGER DEFAULT 0,
  PRIMARY KEY (bucket, window)
);
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY, bot TEXT, chat_id TEXT, message_id TEXT, created_at REAL
);
CREATE TABLE IF NOT EXISTS outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  idem TEXT UNIQUE, bot TEXT, chat_id TEXT, payload TEXT,
  status TEXT DEFAULT 'pending', attempts INTEGER DEFAULT 0,
  created_at REAL, sent_at REAL, error TEXT
);
"""


class Ledger:
    def __init__(self, path: "Path | str", clock=None):
        self.path = Path(path)
        self.clock = clock or time.time
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # 桥在多个 consumer 线程里调用它：连接跨线程共享，写操作用锁串行。
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self.db.executescript(SCHEMA)
        self.db.commit()

    def _write(self, sql: str, params=()) -> "sqlite3.Cursor":
        with self._lock:
            cur = self.db.execute(sql, params)
            self.db.commit()
            return cur

    def close(self) -> None:
        try:
            self.db.close()
        except Exception:
            pass

    # ── 事件去重 ──────────────────────────────────────────────
    def remember_event(self, dedup_key: str, bot: str, kind: str, payload: str = "") -> bool:
        """首次见到返回 True；重复返回 False（只记一笔，不重复执行）。"""
        cur = self._write(
            "INSERT OR IGNORE INTO events(dedup_key, bot, kind, received_at, payload) VALUES(?,?,?,?,?)",
            (dedup_key, bot, kind, self.clock(), payload))
        return cur.rowcount == 1

    def has_event(self, dedup_key: str) -> bool:
        return self.db.execute("SELECT 1 FROM events WHERE dedup_key=?", (dedup_key,)).fetchone() is not None

    # ── 会话绑定（对话模式）────────────────────────────────────
    def session(self, binding: str) -> "dict[str, Any] | None":
        row = self.db.execute("SELECT * FROM sessions WHERE binding=?", (binding,)).fetchone()
        return dict(row) if row else None

    def bind_session(self, binding: str, bot: str, host_session: str, adapter: str) -> None:
        now = self.clock()
        self._write(
            "INSERT INTO sessions(binding, bot, host_session, adapter, created_at, last_used, turns, tokens)"
            " VALUES(?,?,?,?,?,?,0,0)"
            " ON CONFLICT(binding) DO UPDATE SET host_session=excluded.host_session,"
            " adapter=excluded.adapter, created_at=excluded.created_at, last_used=excluded.last_used,"
            " turns=0, tokens=0",
            (binding, bot, host_session, adapter, now, now))

    def touch_session(self, binding: str, turns: int = 1, tokens: int = 0) -> None:
        self._write(
            "UPDATE sessions SET last_used=?, turns=turns+?, tokens=tokens+? WHERE binding=?",
            (self.clock(), turns, tokens, binding))

    def drop_session(self, binding: str) -> None:
        self._write("DELETE FROM sessions WHERE binding=?", (binding,))

    # ── 计数（限速 / 每日预算）────────────────────────────────
    def bump(self, bucket: str, window: str, amount: int = 1) -> int:
        self._write(
            "INSERT INTO counters(bucket, window, value) VALUES(?,?,?)"
            " ON CONFLICT(bucket, window) DO UPDATE SET value=value+excluded.value",
            (bucket, window, amount))
        row = self.db.execute("SELECT value FROM counters WHERE bucket=? AND window=?",
                              (bucket, window)).fetchone()
        return int(row["value"]) if row else amount

    def count(self, bucket: str, window: str) -> int:
        row = self.db.execute("SELECT value FROM counters WHERE bucket=? AND window=?",
                              (bucket, window)).fetchone()
        return int(row["value"]) if row else 0

    # ── run 绑定：飞书发起的 run 回到原会话 ────────────────────
    def bind_run(self, run_id: str, bot: str, chat_id: str, message_id: str) -> None:
        self._write(
            "INSERT OR REPLACE INTO runs(run_id, bot, chat_id, message_id, created_at) VALUES(?,?,?,?,?)",
            (run_id, bot, chat_id, message_id, self.clock()))

    def run_target(self, run_id: str) -> "dict[str, Any] | None":
        row = self.db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    # ── 出站队列 ──────────────────────────────────────────────
    def enqueue(self, idem: str, bot: str, chat_id: str, payload: str) -> bool:
        cur = self._write(
            "INSERT OR IGNORE INTO outbox(idem, bot, chat_id, payload, created_at) VALUES(?,?,?,?,?)",
            (idem, bot, chat_id, payload, self.clock()))
        return cur.rowcount == 1

    def pending(self, limit: int = 20) -> "list[dict[str, Any]]":
        rows = self.db.execute(
            "SELECT * FROM outbox WHERE status='pending' ORDER BY id LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def mark_sent(self, row_id: int) -> None:
        self._write("UPDATE outbox SET status='sent', sent_at=?, attempts=attempts+1 WHERE id=?",
                    (self.clock(), row_id))

    def mark_failed(self, row_id: int, error: str) -> None:
        self._write("UPDATE outbox SET attempts=attempts+1, error=? WHERE id=?", (error[:400], row_id))

    def bury(self, row_id: int, error: str) -> None:
        self._write("UPDATE outbox SET status='dead', attempts=attempts+1, error=? WHERE id=?",
                    (error[:400], row_id))
