-- V2 执行内核的 run 快照（coding-runs 源）。
-- 航班表只放阶段判据；这里放监工面要用的任务/gate/session 摘要。
CREATE TABLE IF NOT EXISTS coding_run (
    run_id         TEXT PRIMARY KEY,
    issue          TEXT,
    phase          TEXT,
    stage          TEXT,
    priority       TEXT,
    fleet_id       TEXT,
    ship_limit     INTEGER NOT NULL DEFAULT 0,
    crew_limit     INTEGER NOT NULL DEFAULT 0,
    gates_json     TEXT,
    tasks_total    INTEGER NOT NULL DEFAULT 0,
    tasks_done     INTEGER NOT NULL DEFAULT 0,
    tasks_running  INTEGER NOT NULL DEFAULT 0,
    tasks_blocked  INTEGER NOT NULL DEFAULT 0,
    sessions_json  TEXT,
    ship_json      TEXT,
    next_action    TEXT,
    updated_at     TEXT,
    age_min        INTEGER,
    branch         TEXT,
    worktree       TEXT,
    seen_run       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_coding_run_seen ON coding_run(seen_run);
