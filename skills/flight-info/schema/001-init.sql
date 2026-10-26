-- flight-info 数据契约（schema 1）
-- 只依赖 SQLite 标准语法；可重复执行（IF NOT EXISTS + INSERT OR IGNORE）。
-- 语义：一块板 = 一个 SQLite 库。板是"某时刻的航班状态快照 + 生命周期流水"。

PRAGMA foreign_keys = ON;

-- ── 版本与元数据 ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT OR IGNORE INTO schema_meta(key, value) VALUES ('schema_version', '1');


-- ── 一次采集 = 一行（数据可信度的唯一判据）─────────────────────
-- 出板时只看这张表：status 不是 ok 的源，其数据一律降级展示，不冒充完整。
CREATE TABLE IF NOT EXISTS source_run (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     TEXT    NOT NULL,          -- 同一轮采集共享（ISO 时间戳）
    source_id  TEXT    NOT NULL,          -- 板配置 sources[].id
    type       TEXT    NOT NULL,          -- board-cards / tasks-table / github-issues / git-worktrees
    status     TEXT    NOT NULL           -- ok | absent | skipped | fail
               CHECK (status IN ('ok','absent','skipped','fail')),
    row_count  INTEGER NOT NULL DEFAULT 0,
    detail     TEXT,                      -- 降级原因（人话，一句话）
    at         TEXT    NOT NULL           -- ISO8601
);
CREATE INDEX IF NOT EXISTS idx_source_run_run ON source_run(run_id);


-- ── 航班 = 一张票 / 一个任务 ────────────────────────────────────
-- uid 是跨源稳定标识：#12 用 'issue:12'，无票卡片用 'card:20261024-01'。
CREATE TABLE IF NOT EXISTS flight (
    uid         TEXT PRIMARY KEY,
    ticket      TEXT,                     -- '#12'；无票为 NULL
    title       TEXT NOT NULL,
    stage       TEXT NOT NULL,            -- 阶段 key（板配置 stages[].key）
    stage_label TEXT,
    owner       TEXT,                     -- 掌机：地勤/塔台/机长/副机长
    persona     TEXT,                     -- 人格（委派能力）：worker/...
    milestone   TEXT,
    planned     INTEGER NOT NULL DEFAULT 0,   -- 是否已进日表
    why         TEXT,                     -- 判据说明（为什么判成这个阶段）
    source      TEXT NOT NULL,            -- 首见来源
    url         TEXT,
    labels      TEXT,                     -- 逗号分隔
    open        INTEGER NOT NULL DEFAULT 1,
    updated_at  TEXT NOT NULL,
    closed_at   TEXT,
    seen_run    TEXT NOT NULL,            -- 最后一次出现在哪一轮采集
    owner_from  TEXT,                     -- lane | assignee | infer（掌机是事实还是推断）
    prev_stage  TEXT,                     -- 被判成「停滞」前原本在哪一阶段
    stale_days  INTEGER                   -- 距上次更新几天（不知道＝NULL，绝不写 0）
);
CREATE INDEX IF NOT EXISTS idx_flight_stage ON flight(stage);
CREATE INDEX IF NOT EXISTS idx_flight_open  ON flight(open);


-- ── 阶段判据证据（可追溯：为什么判成这个阶段）────────────────────
CREATE TABLE IF NOT EXISTS evidence (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    uid       TEXT NOT NULL,
    kind      TEXT NOT NULL,              -- card / branch / comment / label / table_note / assignee
    value     TEXT,
    at        TEXT NOT NULL,
    run_id    TEXT NOT NULL,
    FOREIGN KEY (uid) REFERENCES flight(uid) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_evidence_uid ON evidence(uid);


-- ── 日表快照（排班视图，塔台唯一写者；这里只读）──────────────────
CREATE TABLE IF NOT EXISTS schedule_row (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    lane      TEXT NOT NULL,              -- main | copilot
    table_date TEXT NOT NULL,             -- YYYY-MM-DD
    line_no   INTEGER NOT NULL,
    ticket    TEXT,
    summary   TEXT,
    note      TEXT,
    run_id    TEXT NOT NULL,
    UNIQUE (lane, table_date, line_no)
);


-- ── 每次出板 = 一行（生命周期流水，历史可追）──────────────────────
CREATE TABLE IF NOT EXISTS board_run (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL,
    at           TEXT NOT NULL,
    kpi_json     TEXT NOT NULL,           -- {"in_flight":3,...}
    sources_json TEXT NOT NULL,           -- {"issues":"ok","tasks":"ok"}
    board_sha256 TEXT,
    html_sha256  TEXT
);
CREATE INDEX IF NOT EXISTS idx_board_run_at ON board_run(at);


-- ── 视图：当前航班（出板只用这个，不直接碰基表）─────────────────
-- 只认「最近一次写入出现的航班」，避免残留旧票；用 flight 自己的 MAX(seen_run)，
-- 这样即使某一轮没有任何 source_run 记录也不会整视图空掉。
DROP VIEW IF EXISTS v_flight;
CREATE VIEW v_flight AS
SELECT f.uid, f.ticket, f.title, f.stage, f.stage_label, f.owner, f.persona,
       f.milestone, f.planned, f.why, f.source, f.url, f.labels,
       f.open, f.updated_at, f.closed_at,
       f.owner_from, f.prev_stage, f.stale_days
FROM flight f
WHERE f.seen_run = (SELECT MAX(seen_run) FROM flight);
