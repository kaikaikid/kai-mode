-- 运行态快照（schema 3）：塔台队列与令牌这类「不是票、但板上要看」的读数。
-- 一轮一行，整体替换（幂等）；渲染层只读最新一轮。
CREATE TABLE IF NOT EXISTS runtime_state (
    run_id  TEXT PRIMARY KEY,
    at      TEXT NOT NULL,
    payload TEXT NOT NULL          -- JSON：{"queue": {...} | null, "tower": {...} | null}
);
