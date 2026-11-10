"""执行内核：控制平面。

设计正本：docs/design/2026-10-30-v2-execution-kernel.md
"""

__version__ = "0.1.0"
SCHEMA_VERSION = 3  # run 实体版本；Task/Artifact/Receipt 另见下三常量
TASK_SCHEMA_VERSION = 1
ARTIFACT_SCHEMA_VERSION = 1
RECEIPT_SCHEMA_VERSION = 1

# BLOCKED 原因码（docs/schema.md）：任务／run 转 blocked 时 blocked_reason 只能取其一。
BLOCKED_REASON_CODES = frozenset({
    "return_limit", "auto_fail_limit", "read_only_violation",
    "merge_conflict", "ship_failed", "timeout",
    "cancel_late", "worker_clamped", "missing_capability",
})

# 单张任务可拆 Worker 上限；Worker 不突破 Crew——实际可派按 min(worker 上限, crew_limit)。
TASK_MAX_WORKERS = 8
