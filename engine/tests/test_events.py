# -*- coding: utf-8 -*-
"""事件事实层（ADR-0035 D6）：去重、8 跳熔断、只存引用、tick 只读 pending。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engine.coding import EVENT_HOPS_MAX, EVENT_STATUSES, events


def _lines(root: Path) -> list[str]:
    p = events.events_path(root)
    return p.read_text(encoding="utf-8").splitlines() if p.is_file() else []


def test_emit_appends_and_dedupes_source_key(tmp_path):
    first = events.emit("openbot", "thread-42", "message.received", root=tmp_path)
    again = events.emit("openbot", "thread-42", "message.received", root=tmp_path)
    assert again["id"] == first["id"]
    assert len(_lines(tmp_path)) == 1
    other = events.emit("openbot", "thread-43", "message.received", root=tmp_path)
    assert other["id"] != first["id"]
    assert len(_lines(tmp_path)) == 2


def test_event_fields_and_status_default(tmp_path):
    ev = events.emit("feishu", "k1", "button.click", run="r-1", subject="确认", root=tmp_path)
    assert set(ev) >= {
        "id", "source", "key", "type", "payload_ref", "received_at",
        "status", "routed_run", "hops",
    }
    assert ev["status"] == "pending"
    assert ev["routed_run"] == "r-1"
    assert ev["hops"] == 0
    assert ev["status"] in EVENT_STATUSES


def test_payload_body_is_not_stored(tmp_path):
    ev = events.emit(
        "openbot", "k2", "message.received",
        payload_ref=".coding/inbox/msg-2.json",
        root=tmp_path,
    )
    assert ev["payload_ref"] == ".coding/inbox/msg-2.json"
    on_disk = json.loads(_lines(tmp_path)[0])
    assert "payload" not in on_disk
    assert "body" not in on_disk
    assert on_disk["payload_ref"] == ".coding/inbox/msg-2.json"


def test_hops_capped_and_over_limit_not_routable(tmp_path):
    ok = events.emit("openbot", "k3", "relay", hops=EVENT_HOPS_MAX, root=tmp_path)
    assert ok["hops"] == EVENT_HOPS_MAX
    assert ok["status"] == "pending"

    over = events.emit("openbot", "k4", "relay", hops=EVENT_HOPS_MAX + 1, root=tmp_path)
    assert over["hops"] == EVENT_HOPS_MAX
    assert over["status"] == "paused"
    pending_ids = {ev["id"] for ev in events.tick(root=tmp_path)}
    assert ok["id"] in pending_ids
    assert over["id"] not in pending_ids


def test_tick_reads_pending_only_and_does_not_write(tmp_path):
    a = events.emit("a", "1", "t", root=tmp_path)
    paused = events.emit("a", "2", "t", hops=EVENT_HOPS_MAX + 1, root=tmp_path)
    c = events.emit("a", "3", "t", root=tmp_path)
    before = events.events_path(tmp_path).read_text(encoding="utf-8")
    got = events.tick(root=tmp_path)
    after = events.events_path(tmp_path).read_text(encoding="utf-8")
    assert [ev["id"] for ev in got] == [a["id"], c["id"]]
    assert paused["id"] not in {ev["id"] for ev in got}
    assert before == after


def test_tick_limit_and_newest_order(tmp_path):
    ids = [events.emit("a", str(i), "t", root=tmp_path)["id"] for i in range(3)]
    assert [ev["id"] for ev in events.tick(root=tmp_path, limit=2)] == ids[:2]
    assert events.tick(root=tmp_path, limit=0) == []


def test_bad_lines_are_skipped(tmp_path):
    path = events.events_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"id":"ev-1","source":"a","key":"1"}\nnot json\n\n', encoding="utf-8")
    good = events.emit("a", "2", "t", root=tmp_path)
    loaded = events.load_events(tmp_path)
    assert [ev["id"] for ev in loaded] == ["ev-1", good["id"]]


def test_emit_requires_fields(tmp_path):
    with pytest.raises(ValueError):
        events.emit("", "k", "t", root=tmp_path)
    with pytest.raises(ValueError):
        events.emit("s", "", "t", root=tmp_path)
    with pytest.raises(ValueError):
        events.emit("s", "k", "", root=tmp_path)
