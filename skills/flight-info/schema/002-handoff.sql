-- 交接日报索引（schema 2）。可重复执行。
-- 一块板读最近 N 份 handoff，只存「索引行」（槽位/路径/标题/日期），不存正文——
-- 正文是纸条层，正本在文件里，板只做入口。
CREATE TABLE IF NOT EXISTS handoff_doc (
    run_id   TEXT    NOT NULL,
    slot     TEXT    NOT NULL,          -- 10-session / 20-plan / ...
    rel_path TEXT    NOT NULL,          -- 相对仓根，可点开
    title    TEXT,
    doc_date TEXT,                      -- YYYY-MM-DD（取自文件名）
    ord      INTEGER NOT NULL DEFAULT 0, -- 渲染顺序（0=最新）
    PRIMARY KEY (run_id, rel_path)
);
CREATE INDEX IF NOT EXISTS idx_handoff_run ON handoff_doc(run_id, ord);
