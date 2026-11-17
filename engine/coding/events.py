"""事件事实层（ADR-0035 D6）：项目本地 `.coding/events.jsonl`，append-only。

判据：
  · 事件是**事实**，不改任务状态；`fleet emit` 是唯一写入口，宿主适配器只调用它。
  · 去重键 `source + key`：同一来源同一业务键重复上报，返回原事件，不追加第二行。
  · 正文只存引用（`payload_ref`），不落 payload 正文。
  · `hops` 默认 0、上限 8；超过上限的事件仍记账，但记为 `paused`，`tick` 不再列出。

状态机（本刀只写不改）：`pending → routed｜paused｜skipped｜done`。
`tick` 只读 `pending`，不建 run、不派活；改状态是后续刀的事——账本 append-only，
不在原地改写已写入的行。
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from . import EVENT_HOPS_MAX, state as st

EVENT_FILE = "events.jsonl"

#: 事件正文字段（顺序即写盘顺序）。
EVENT_FIELDS = (
    "id",
    "source",
    "key",
    "type",
    "payload_ref",
    "received_at",
    "status",
    "routed_run",
    "hops",
)


def events_path(root: Path | None = None) -> Path:
    """事件账本路径：`.coding/events.jsonl`（与 state.json 同住项目本地）。"""
    return st.coding_dir(root) / EVENT_FILE


def _read_lines(path: Path) -> list[dict[str, Any]]:
    """读账本；坏行跳过（append-only 文件可能被手工截断/写坏，不让一行毒死全表）。"""
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("id") and obj.get("source") is not None:
            out.append(obj)
    return out


def load_events(root: Path | None = None) -> list[dict[str, Any]]:
    """全量事件（只读）。"""
    return _read_lines(events_path(root))


def _dedupe_key(ev: dict[str, Any]) -> tuple[str, str]:
    return (str(ev.get("source", "")), str(ev.get("key", "")))


def _normalize_hops(raw: Any) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, min(value, EVENT_HOPS_MAX))


def emit(
    source: str,
    key: str,
    type: str,
    *,
    payload_ref: str = "",
    run: str | None = None,
    subject: str = "",
    hops: int = 0,
    root: Path | None = None,
) -> dict[str, Any]:
    """追加一条事件；`source+key` 已存在则原样返回旧事件（幂等，不写第二行）。

    `subject` 是短标题（人读用），不是正文；`payload_ref` 才是正文引用。
    `hops` 超上限：仍记账，但状态记 `paused`，不再进入 `tick` 的可路由清单。
    """
    source = str(source or "").strip()
    key = str(key or "").strip()
    type_ = str(type or "").strip()
    if not source or not key or not type_:
        raise ValueError("emit needs non-empty source/key/type")
    path = events_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with st.lock(root):
        existing = _read_lines(path)
        wanted = (source, key)
        for ev in existing:
            if _dedupe_key(ev) == wanted:
                return ev
        raw_hops = 0
        try:
            raw_hops = int(hops)
        except (TypeError, ValueError):
            raw_hops = 0
        capped = _normalize_hops(raw_hops)
        status = "paused" if raw_hops > EVENT_HOPS_MAX else "pending"
        ev: dict[str, Any] = {
            "id": f"ev-{uuid.uuid4().hex[:12]}",
            "source": source,
            "key": key,
            "type": type_,
            "payload_ref": str(payload_ref or ""),
            "received_at": time.time(),
            "status": status,
            "routed_run": run,
            "hops": capped,
        }
        if subject:
            ev["subject"] = str(subject)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False, sort_keys=False) + "\n")
    return ev


def pending_events(root: Path | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    """可路由清单：只取 `status == "pending"` 的事件（只读，不改状态）。"""
    events = [ev for ev in load_events(root) if ev.get("status") == "pending"]
    if limit is not None:
        if limit < 0:
            limit = 0
        events = events[:limit]
    return events


def tick(root: Path | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    """`fleet tick` 的实现：列 pending，不建 run、不派活、不写盘。"""
    return pending_events(root=root, limit=limit)
