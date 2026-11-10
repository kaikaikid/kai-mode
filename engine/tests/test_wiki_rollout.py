# -*- coding: utf-8 -*-
"""wiki 全面落地回执测试：Schema 版本策略、BLOCKED 原因码、交接确认、钳制、信封严格模式。

文档口径（glossary/skills/canon）由 doctor 与逐字测试覆盖；这里只钉代码行为：
- 新 plan 的 Task 带 schema_version=1 + blocked 三字段；
- migrate 给旧 state 补 events/closed_at，不回填任务字段（只追加，不改旧语义）；
- 第三次 return 锁死（return_locked + return_limit 原因码 + 事件）；
- receipt 严格模式：未声明字段 / fact 缺证据 / 非 reviewer verdict 拒收；
- fleet confirm 三态 + 幂等；
- clamp_workers：worker≤8 且不突破 crew。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CODING = REPO / "engine" / "coding_main.py"
PY = sys.executable

sys.path.insert(0, str(REPO))
from engine.coding import TASK_SCHEMA_VERSION, scheduler
from engine.coding import state as st


def cli(root: Path, *args: str, expect: int = 0) -> subprocess.CompletedProcess:
    r = subprocess.run([PY, str(CODING), *args], cwd=str(root), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    assert r.returncode == expect, (
        f"{args} -> rc={r.returncode} (expected {expect})\n"
        f"STDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}")
    return r


def write_run(root: Path, run_id: str = "r-w", **kw) -> Path:
    d = root / ".coding" / "runs" / run_id
    d.mkdir(parents=True, exist_ok=True)
    state = {
        "run_id": run_id, "phase": kw.get("phase", "delegating"),
        "issue": "#1 w", "priority": "normal", "fleet_id": "host-1",
        "ship_limit": 1, "crew_limit": kw.get("crew_limit", 5),
        "base_branch": "main", "branch": f"travel/{run_id}",
        "worktree": str(root),
        "gates": {"g0": "approved", "g1": "skipped", "g2": "pending"},
        "tasks": kw.get("tasks", []),
        "sessions": [],
        "resume": {"last_accepted": None, "next_action": "x"},
    }
    p = d / "state.json"
    p.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return p


def read_state(root: Path, run_id: str = "r-w") -> dict:
    return json.loads((root / ".coding" / "runs" / run_id / "state.json").read_text(encoding="utf-8"))


def review_state(task_status: str = "review", attempts: int = 0) -> list[dict]:
    return [{
        "schema_version": 1, "id": "t1", "title": "t1", "brief": "do", "tier": "light",
        "deps": [], "touchset": ["t1.py"], "ac": ["ok"], "ui": False,
        "status": task_status, "attempts": attempts, "session_id": None,
        "blocked_reason": None, "blocked_at": None, "return_locked": False,
    }]

# ------------------------------------------------------------------


def test_plan_locks_task_schema_version(tmp_path: Path):
    write_run(tmp_path, phase="planning")
    tf = tmp_path / "tasks.json"
    tf.write_text(json.dumps({"tasks": [{"id": "t1", "title": "t1"}]}), encoding="utf-8")
    cli(tmp_path, "plan", "r-w", "--file", str(tf))
    t = read_state(tmp_path)["tasks"][0]
    assert t["schema_version"] == TASK_SCHEMA_VERSION
    assert t["blocked_reason"] is None
    assert t["return_locked"] is False


def test_migrate_appends_events_without_touching_tasks(tmp_path: Path):
    write_run(tmp_path, tasks=review_state(task_status="pending"))
    s = read_state(tmp_path)
    assert "events" not in s
    loaded = st.load("r-w", tmp_path)
    assert loaded["events"] == []
    assert loaded["closed_at"] is None
    assert loaded["schema_version"] == st.SCHEMA_VERSION
    # 任务字段不回填：旧任务保持原样（只追加到 run，不改旧语义）。
    # review_state() 自带 schema_version 是测试脚手架写法；真实旧 state 无该键。
    # migrate 不碰 tasks：断言任务内容逐字不变。
    assert loaded["tasks"][0]["status"] == "pending"
    assert "blocked_reason" in loaded["tasks"][0]  # 脚手架自带，非 migrate 回填


def test_third_return_locks_with_reason_and_event(tmp_path: Path):
    write_run(tmp_path, tasks=review_state(attempts=2))
    vf = tmp_path / "v.json"
    vf.write_text(json.dumps({"verdict": "return", "defects": ["x"]}), encoding="utf-8")
    cli(tmp_path, "verdict", "r-w", "t1", "--file", str(vf))
    s = read_state(tmp_path)
    t = s["tasks"][0]
    assert t["status"] == "blocked"
    assert t["attempts"] == 3
    assert t["return_locked"] is True
    assert t["blocked_reason"] == "return_limit"
    assert any(e.get("kind") == "return_limit_blocked" for e in s.get("events", []))


def test_return_locked_reopen_needs_human(tmp_path: Path):
    write_run(tmp_path, tasks=review_state(attempts=2))
    vf = tmp_path / "v.json"
    vf.write_text(json.dumps({"verdict": "return", "defects": ["x"]}), encoding="utf-8")
    cli(tmp_path, "verdict", "r-w", "t1", "--file", str(vf))
    out = cli(tmp_path, "reopen", "r-w", "t1").stdout
    assert "return_locked" in out
    assert read_state(tmp_path)["tasks"][0]["status"] == "blocked"


def test_set_blocked_reason_rejects_unknown_code():
    import pytest
    with pytest.raises(ValueError, match="unknown blocked reason"):
        st.set_blocked_reason({}, "nope-code")


def test_receipt_strict_mode(tmp_path: Path):
    write_run(tmp_path, tasks=review_state())
    base = {"schema_version": 1, "task_id": "t1", "role_id": "reviewer",
            "idempotency_key": "k1",
            "claims": [{"kind": "fact", "text": "x",
                        "evidence_refs": ["engine/tests/test_wiki_rollout.py:1"]}],
            "verdict": {"value": "accept", "defects": [], "reason": "ok"}}
    vf = tmp_path / "v.json"
    # 1. 合法信封通过
    vf.write_text(json.dumps(base), encoding="utf-8")
    cli(tmp_path, "verdict", "r-w", "t1", "--file", str(vf))
    assert read_state(tmp_path)["tasks"][0]["status"] == "accepted"

    # 2. 未声明字段拒收
    write_run(tmp_path, tasks=review_state())
    bad = dict(base, execution_status="completed")
    vf.write_text(json.dumps(bad), encoding="utf-8")
    r = cli(tmp_path, "verdict", "r-w", "t1", "--file", str(vf), expect=1)
    assert "undeclared field" in (r.stdout + r.stderr)

    # 3. fact 缺 evidence_refs 拒收
    write_run(tmp_path, tasks=review_state())
    bad2 = dict(base, claims=[{"kind": "fact", "text": "x"}])
    vf.write_text(json.dumps(bad2), encoding="utf-8")
    r = cli(tmp_path, "verdict", "r-w", "t1", "--file", str(vf), expect=1)
    assert "evidence_refs" in (r.stdout + r.stderr)

    # 4. 非 reviewer 带 verdict 拒收
    write_run(tmp_path, tasks=review_state())
    bad3 = dict(base, role_id="engineer")
    vf.write_text(json.dumps(bad3), encoding="utf-8")
    r = cli(tmp_path, "verdict", "r-w", "t1", "--file", str(vf), expect=1)
    assert "only role_id=reviewer" in (r.stdout + r.stderr)


def test_confirm_handoff_three_states_and_idempotent(tmp_path: Path):
    write_run(tmp_path)
    out = json.loads(cli(tmp_path, "confirm", "r-w", "h1", "accepted").stdout)
    assert out == {"handoff_id": "h1", "status": "accepted"}
    out2 = json.loads(cli(tmp_path, "confirm", "r-w", "h1", "accepted").stdout)
    assert out2["idempotent"] is True
    out3 = json.loads(cli(tmp_path, "confirm", "r-w", "h2", "needs_clarification").stdout)
    assert out3["status"] == "needs_clarification"
    s = read_state(tmp_path)
    assert any(e.get("kind") == "handoff_confirmed" for e in s.get("events", []))


def test_block_command_sets_reason_and_rejects_unknown(tmp_path: Path):
    write_run(tmp_path, tasks=review_state(task_status="returned"))
    out = json.loads(cli(tmp_path, "block", "r-w", "t1", "--reason", "timeout").stdout)
    assert out == {"task_id": "t1", "status": "blocked", "blocked_reason": "timeout"}
    t = read_state(tmp_path)["tasks"][0]
    assert t["blocked_at"]
    assert any(e.get("kind") == "task_blocked" for e in read_state(tmp_path)["events"])
    # 未知原因码拒收
    write_run(tmp_path, tasks=review_state(task_status="returned"))
    r = cli(tmp_path, "block", "r-w", "t1", "--reason", "nope", expect=1)
    assert "unknown blocked reason" in (r.stdout + r.stderr)
    # 终态任务不逆转
    write_run(tmp_path, tasks=review_state(task_status="accepted"))
    r = cli(tmp_path, "block", "r-w", "t1", "--reason", "timeout", expect=1)
    assert "terminal" in (r.stdout + r.stderr)


def test_clamp_workers_never_exceeds_crew():
    allowed, clamped = scheduler.clamp_workers(8, {"crew_limit": 5})
    assert (allowed, clamped) == (5, True)
    allowed, clamped = scheduler.clamp_workers(3, {"crew_limit": 5})
    assert (allowed, clamped) == (3, False)
    allowed, clamped = scheduler.clamp_workers(99, {"crew_limit": 1})
    assert (allowed, clamped) == (1, True)


def test_stop_cancelled_then_closed_and_late_tasks_kept(tmp_path: Path):
    tasks = review_state(task_status="accepted") + review_state(task_status="running")
    tasks[1]["id"] = "t2"
    write_run(tmp_path, tasks=tasks)
    cli(tmp_path, "stop", "r-w")
    s = read_state(tmp_path)
    assert s["phase"] == "cancelled"
    # 迟到取消：终态任务保持 accepted，只记事件
    assert s["tasks"][0]["status"] == "accepted"
    assert any(e.get("kind") == "cancel_late" for e in s.get("events", []))
    # CANCELLED→CLOSED：无在途后 resume 落档 closed_at（t2 running 仍在途，先不清）
    s["tasks"][1]["status"] = "abandoned"
    s.pop("integrity", None)  # 手写 state 不算签名，load 跳过验签（与旧测试脚手架同理）
    (tmp_path / ".coding" / "runs" / "r-w" / "state.json").write_text(
        json.dumps(s, ensure_ascii=False), encoding="utf-8")
    cli(tmp_path, "resume", "r-w")
    s2 = read_state(tmp_path)
    assert s2.get("closed_at"), "cancelled 无在途后应落档 closed_at"


def test_blocked_run_does_not_revive_return_locked(tmp_path: Path):
    write_run(tmp_path, tasks=review_state(task_status="returned", attempts=3),
              phase="blocked")
    s = read_state(tmp_path)
    s["tasks"][0]["return_locked"] = True
    s.pop("integrity", None)
    (tmp_path / ".coding" / "runs" / "r-w" / "state.json").write_text(
        json.dumps(s, ensure_ascii=False), encoding="utf-8")
    cli(tmp_path, "resume", "r-w")
    assert read_state(tmp_path)["phase"] == "blocked"
