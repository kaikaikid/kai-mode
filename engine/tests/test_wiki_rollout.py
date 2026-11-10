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
import time
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
    # 无 --unlock：拒绝并给显式出路
    out = json.loads(cli(tmp_path, "reopen", "r-w", "t1").stdout)
    assert out["return_locked"] is True
    assert "--unlock" in out["hint"]
    assert read_state(tmp_path)["tasks"][0]["status"] == "blocked"
    # --unlock：显式人工解锁，回 pending，清锁与原因码，记事件
    out2 = cli(tmp_path, "reopen", "r-w", "t1", "--unlock").stdout
    assert "reopened t1" in out2
    t = read_state(tmp_path)["tasks"][0]
    assert t["status"] == "pending"
    assert t["return_locked"] is False
    assert t["blocked_reason"] is None
    assert any(e.get("kind") == "return_lock_unlocked" for e in read_state(tmp_path)["events"])


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

    # 5. 信封缺 verdict 一律拒收（不默认 accept）
    write_run(tmp_path, tasks=review_state())
    bad4 = {"schema_version": 1, "task_id": "t1", "role_id": "reviewer",
            "idempotency_key": "k1",
            "claims": [{"kind": "fact", "text": "x",
                        "evidence_refs": ["engine/tests/test_wiki_rollout.py:1"]}],
            "artifacts": []}
    vf.write_text(json.dumps(bad4), encoding="utf-8")
    r = cli(tmp_path, "verdict", "r-w", "t1", "--file", str(vf), expect=1)
    assert "must carry a verdict" in (r.stdout + r.stderr)
    assert read_state(tmp_path)["tasks"][0]["status"] == "review"


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
    r = scheduler.clamp_workers(8, {"crew_limit": 5})
    assert (r["effective"], r["clamped"]) == (5, True)
    r = scheduler.clamp_workers(3, {"crew_limit": 5})
    assert (r["effective"], r["clamped"]) == (3, False)
    r = scheduler.clamp_workers(99, {"crew_limit": 1})
    assert (r["effective"], r["clamped"]) == (1, True)
    # crew 满员：free=0 → effective=0
    r = scheduler.clamp_workers(3, {"crew_limit": 5}, active_sessions=5)
    assert (r["effective"], r["clamped"]) == (0, True)
    # 旧任务（worker_count 未请求）
    r = scheduler.clamp_workers(0, {"crew_limit": 5})
    assert r["requested"] == 0 and r["clamped"] is False


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


def test_context_manifest_same_source_and_no_fake_tokens(tmp_path: Path):
    write_run(tmp_path, tasks=review_state(task_status="pending"))
    s = read_state(tmp_path)
    s["budget"] = {"max_tokens": 200000, "used_tokens": 0}
    s["events"] = [{"kind": "handoff_confirmed", "at": 1.0}]
    s.pop("integrity", None)
    (tmp_path / ".coding" / "runs" / "r-w" / "state.json").write_text(
        json.dumps(s, ensure_ascii=False), encoding="utf-8")
    m = json.loads(cli(tmp_path, "context", "r-w").stdout)
    assert m["run_id"] == "r-w"
    assert m["schema_version"] == st.SCHEMA_VERSION
    assert [t["id"] for t in m["tasks"]] == ["t1"]
    assert m["gates"] == {"g0": "approved", "g1": "skipped", "g2": "pending"}
    assert m["budget"]["max_tokens"] == 200000
    assert m["budget"]["used_tokens"] == 0
    assert m["budget"]["token_usage_collected"] is False
    assert m["events"][0]["kind"] == "handoff_confirmed"


def test_report_secret_is_quarantined(tmp_path: Path):
    tasks = review_state(task_status="running")
    tasks[0]["session_id"] = "s-1"
    write_run(tmp_path, tasks=tasks)
    s = read_state(tmp_path)
    s["sessions"] = [{"id": "s-1", "task_id": "t1", "adapter": "native",
                      "mode": "native", "status": "running", "pid": None}]
    s.pop("integrity", None)
    (tmp_path / ".coding" / "runs" / "r-w" / "state.json").write_text(
        json.dumps(s, ensure_ascii=False), encoding="utf-8")
    sdir = tmp_path / ".coding" / "runs" / "r-w" / "sessions" / "s-1"
    sdir.mkdir(parents=True)
    raw = {"result": "done", "files_changed": [],
           "verification": ["cmd -> ok"], "open_questions": [],
           "notes": "token=sk-abcdefghijklmnopqrstuvwx"}
    (sdir / "report.json").write_text(json.dumps(raw), encoding="utf-8")
    out = json.loads(cli(tmp_path, "report", "r-w", "t1").stdout)
    assert out["result"] == "partial"
    assert "quarantined" in out["notes"]
    assert "api_key_sk" in out["notes"]  # 只报模式名，不回显密钥内容
    assert "sk-abcdefghijklmnopqrstuvwx" not in out["notes"]
    persisted = (tmp_path / ".coding" / "runs" / "r-w" / "sessions" / "t1.report.json").read_text(
        encoding="utf-8")
    assert "sk-abcdefghijklmnopqrstuvwx" not in persisted
    assert any(e.get("kind") == "secret_detected" for e in read_state(tmp_path)["events"])


# ------------------------------------------------------------------
# W1.1 Worker 钳制接线


def test_plan_keeps_old_tasks_without_worker_count(tmp_path: Path):
    write_run(tmp_path, phase="planning")
    tf = tmp_path / "tasks.json"
    tf.write_text(json.dumps({"tasks": [{"id": "t1", "title": "t1"}]}), encoding="utf-8")
    cli(tmp_path, "plan", "r-w", "--file", str(tf))
    t = read_state(tmp_path)["tasks"][0]
    assert t.get("worker_count", 0) == 0  # 旧任务：0，不参与钳制


def test_claim_worker_clamped_records_event(tmp_path: Path):
    # worker_count=8、crew_limit=5：钳到 ≤5 且记事件（含 requested/effective/limits/at）
    tasks = review_state(task_status="pending")
    tasks[0]["worker_count"] = 8
    write_run(tmp_path, tasks=tasks, crew_limit=5)
    s = read_state(tmp_path)
    s["gates"] = {"g0": "approved", "g1": "skipped", "g2": "pending"}
    s.pop("integrity", None)
    (tmp_path / ".coding" / "runs" / "r-w" / "state.json").write_text(
        json.dumps(s, ensure_ascii=False), encoding="utf-8")
    out = json.loads(cli(tmp_path, "claim", "r-w", "t1").stdout)
    assert out["task_id"] == "t1"
    evs = read_state(tmp_path)["events"]
    wc = next((e for e in evs if e.get("kind") == "worker_clamped"), None)
    assert wc, "worker_clamped 事件必须落盘"
    assert wc["requested"] == 8
    assert wc["effective"] <= 5
    assert wc["worker_limit"] == 8 and wc["crew_limit"] == 5
    assert "at" in wc
    assert read_state(tmp_path)["tasks"][0]["worker_effective"] <= 5


def test_claim_worker_respects_crew_free(tmp_path: Path):
    # crew_limit=5 且已有 4 个活跃会话：free=1，worker_count=3 → effective=1
    tasks = review_state(task_status="pending")
    tasks[0]["worker_count"] = 3
    write_run(tmp_path, tasks=tasks, crew_limit=5)
    s = read_state(tmp_path)
    s["gates"] = {"g0": "approved", "g1": "skipped", "g2": "pending"}
    # 造 4 个其他 run 的 running 会话占位
    others = []
    for i in range(4):
        rid = f"r-other{i}"
        write_run(tmp_path, run_id=rid, tasks=[])
        o = read_state(tmp_path, run_id=rid)
        o["fleet_id"] = "host-1"
        o["tasks"] = [{"id": f"x{i}", "status": "running", "touchset": [f"x{i}.py"],
                       "session_id": f"so-{i}", "attempts": 0}]
        o["sessions"] = [{"id": f"so-{i}", "task_id": f"x{i}", "status": "running",
                          "mode": "native", "pid": None}]
        o.pop("integrity", None)
        (tmp_path / ".coding" / "runs" / rid / "state.json").write_text(
            json.dumps(o, ensure_ascii=False), encoding="utf-8")
        others.append(rid)
    s.pop("integrity", None)
    (tmp_path / ".coding" / "runs" / "r-w" / "state.json").write_text(
        json.dumps(s, ensure_ascii=False), encoding="utf-8")
    cli(tmp_path, "claim", "r-w", "t1")
    wc = next((e for e in read_state(tmp_path)["events"] if e.get("kind") == "worker_clamped"), None)
    assert wc is not None and wc["effective"] == 1, wc


# ------------------------------------------------------------------
# W1.2 自动超时


def _write_running_session(tmp_path: Path, started_ago_s: float, timeout_min: int | None):
    tasks = review_state(task_status="running")
    tasks[0]["session_id"] = "s-t"
    write_run(tmp_path, tasks=tasks)
    s = read_state(tmp_path)
    s["sessions"] = [{"id": "s-t", "task_id": "t1", "adapter": "native", "mode": "native",
                      "status": "running", "pid": None,
                      "started_at": time.time() - started_ago_s}]
    s.pop("integrity", None)
    (tmp_path / ".coding" / "runs" / "r-w" / "state.json").write_text(
        json.dumps(s, ensure_ascii=False), encoding="utf-8")
    if timeout_min is not None:
        (tmp_path / ".coding" / "config.json").write_text(
            json.dumps({"timeout_minutes": timeout_min}), encoding="utf-8")


def test_timeout_marks_failed_and_events(tmp_path: Path):
    _write_running_session(tmp_path, started_ago_s=7200, timeout_min=1)
    r = cli(tmp_path, "claim", "r-w", "t1", expect=1)
    assert "timed out" in (r.stdout + r.stderr) or "task t1 is failed" in (r.stdout + r.stderr)
    s = read_state(tmp_path)
    assert s["tasks"][0]["status"] == "failed"
    assert s["tasks"][0]["blocked_reason"] == "timeout"
    assert s["sessions"][0]["status"] == "timeout"
    assert any(e.get("kind") == "session_timeout" for e in s["events"])


def test_late_report_ignored_after_timeout(tmp_path: Path):
    _write_running_session(tmp_path, started_ago_s=7200, timeout_min=1)
    cli(tmp_path, "claim", "r-w", "t1", expect=1)  # 触发超时判定
    sdir = tmp_path / ".coding" / "runs" / "r-w" / "sessions" / "s-t"
    sdir.mkdir(parents=True, exist_ok=True)
    (sdir / "report.json").write_text(json.dumps({"result": "done", "files_changed": [],
                                                  "verification": [], "open_questions": [],
                                                  "notes": "late"}), encoding="utf-8")
    r = cli(tmp_path, "report", "r-w", "t1", expect=1)
    assert "late report ignored" in (r.stdout + r.stderr) or "has no session" in (r.stdout + r.stderr)
    s = read_state(tmp_path)
    assert s["tasks"][0]["status"] == "failed"  # 迟到结果不改状态
    assert any(e.get("kind") == "late_result_ignored" for e in s["events"])


def test_advance_path_checks_timeout_on_resume(tmp_path: Path):
    # resume 走 advance：超时在推进入口也落账（不只 claim/report）
    _write_running_session(tmp_path, started_ago_s=7200, timeout_min=1)
    cli(tmp_path, "resume", "r-w")
    s = read_state(tmp_path)
    assert s["tasks"][0]["status"] == "failed"
    assert any(e.get("kind") == "session_timeout" for e in s["events"])


def test_no_timeout_config_keeps_manual_path(tmp_path: Path):
    _write_running_session(tmp_path, started_ago_s=999999, timeout_min=None)
    out = json.loads(cli(tmp_path, "claim", "r-w", "t1").stdout)  # 幂等重放，不超时
    assert out["task_id"] == "t1"
    s = read_state(tmp_path)
    assert s["tasks"][0]["status"] == "running"
    assert not any(e.get("kind") == "session_timeout" for e in s.get("events", []))


# ------------------------------------------------------------------
# W2.1 trace / W2.2 账单


def test_trace_ids_chain_session_and_review(tmp_path: Path):
    write_run(tmp_path, tasks=review_state(task_status="pending"))
    s = read_state(tmp_path)
    s["gates"] = {"g0": "approved", "g1": "skipped", "g2": "pending"}
    s.pop("integrity", None)
    (tmp_path / ".coding" / "runs" / "r-w" / "state.json").write_text(
        json.dumps(s, ensure_ascii=False), encoding="utf-8")
    cli(tmp_path, "claim", "r-w", "t1")
    s = read_state(tmp_path)
    assert s.get("trace_id") and s.get("run_span_id")
    assert s.get("trace_supported") is False  # 宿主无真实 tracing，不假造
    sess = s["sessions"][-1]
    assert sess.get("span_id") and sess.get("parent_span_id") == s["run_span_id"]
    assert any(sp.get("kind") == "session" and sp.get("span_id") == sess["span_id"]
               for sp in s.get("spans", []))


def test_usage_ledger_accumulates_and_context_reports(tmp_path: Path):
    write_run(tmp_path, tasks=review_state(task_status="accepted"))
    cli(tmp_path, "usage", "r-w",
        json.dumps({"source": "worker", "model_ref": "m1", "input_tokens": 10,
                    "output_tokens": 5, "task_id": "t1"}))
    cli(tmp_path, "usage", "r-w",
        json.dumps({"source": "reviewer", "model_ref": "m1", "input_tokens": 20,
                    "output_tokens": 0}))
    s = read_state(tmp_path)
    assert s["budget"]["used_tokens"] == 35
    assert len(s["usage_log"]) == 2
    m = json.loads(cli(tmp_path, "context", "r-w").stdout)
    assert m["budget"]["used_tokens"] == 35
    assert m["budget"]["token_usage_collected"] is True
    assert m["budget"]["usage_by_source"] == {"worker": 15, "reviewer": 20}
    assert m["trace_id"] == s["trace_id"]


def test_usage_rejects_missing_fields(tmp_path: Path):
    write_run(tmp_path)
    r = cli(tmp_path, "usage", "r-w", json.dumps({"source": "worker"}), expect=1)
    assert "missing required field" in (r.stdout + r.stderr)


# ------------------------------------------------------------------
# W3.1 脱敏扩口


def test_record_event_redacts_secret_fields():
    from engine.coding import state as _st
    state: dict = {}
    _st.record_event(state, "task_blocked", task_id="t1",
                     reason="leaked sk-abcdefghijklmnop1234")
    assert state["events"][0]["reason"] == "[redacted:api_key_sk]"
    assert state["events"][1]["kind"] == "secret_detected"


def test_claim_blocks_after_timeout(tmp_path: Path):
    _write_running_session(tmp_path, started_ago_s=7200, timeout_min=1)
    cli(tmp_path, "claim", "r-w", "t1", expect=1)
    r = cli(tmp_path, "claim", "r-w", "t1", expect=1)
    assert "timed out" in (r.stdout + r.stderr) or "task t1 is failed" in (r.stdout + r.stderr)
