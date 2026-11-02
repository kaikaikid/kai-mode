# -*- coding: utf-8 -*-
"""native 占位数据层：claim / release / session mode / status / doctor。

不起真子代理：state.json 直接写进临时仓库根（旧 state 无 integrity，
`st.load` 不做验签），命令按真实 CLI 路径跑。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CODING = REPO / "v2" / "coding_main.py"
PY = sys.executable


def cli(root: Path, *args: str, expect: int = 0) -> subprocess.CompletedProcess:
    r = subprocess.run([PY, str(CODING), *args], cwd=str(root), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    assert r.returncode == expect, (
        f"{args} -> rc={r.returncode} (expected {expect})\n"
        f"STDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}")
    return r


def task(tid: str = "t1", *, status: str = "pending", touchset: list[str] | None = None,
         deps: list[str] | None = None, session_id: str | None = None) -> dict:
    return {
        "id": tid, "title": tid, "brief": f"do {tid}", "tier": "light",
        "deps": deps or [], "touchset": touchset if touchset is not None else [f"{tid}.py"],
        "ac": [f"{tid} ok"], "ui": False, "status": status,
        "attempts": 0, "session_id": session_id,
    }


def write_state(root: Path, *, run_id: str = "r-nat", tasks: list[dict] | None = None,
                sessions: list[dict] | None = None, phase: str = "delegating") -> Path:
    d = root / ".coding" / "runs" / run_id
    d.mkdir(parents=True, exist_ok=True)
    state = {
        "run_id": run_id, "phase": phase, "issue": "#7 native 占位",
        "priority": "normal", "fleet_id": "host-1", "ship_limit": 2, "crew_limit": 5,
        "base_branch": "main", "branch": f"travel/{run_id}",
        "worktree": str(root),
        "gates": {"g0": "approved", "g1": "skipped", "g2": "pending"},
        "tasks": tasks if tasks is not None else [task()],
        "sessions": sessions or [],
        "resume": {"last_accepted": None, "next_action": "plan"},
    }
    p = d / "state.json"
    p.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return p


def read_state(root: Path, run_id: str = "r-nat") -> dict:
    return json.loads((root / ".coding" / "runs" / run_id / "state.json").read_text(encoding="utf-8"))


def claim(root: Path, tid: str = "t1") -> dict:
    return json.loads(cli(root, "claim", "r-nat", tid).stdout)


# ---------------------------------------------------------------------------
# claim


def test_claim_writes_native_session_and_card(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    write_state(root)

    card = claim(root)

    assert set(card) == {"task_id", "brief", "worktree", "touchset", "ac",
                         "report_path", "diff_base"}
    assert card["task_id"] == "t1"
    assert card["brief"] == "do t1"
    assert card["ac"] == ["t1 ok"]
    assert card["touchset"] == ["t1.py"]
    assert card["worktree"] == str(root)
    assert card["diff_base"] == "main"  # 临时目录不是 git 仓库：退回 base 分支名

    st = read_state(root)
    t = st["tasks"][0]
    assert t["status"] == "running"
    sid = t["session_id"]
    assert sid
    assert len(st["sessions"]) == 1
    sess = st["sessions"][0]
    assert sess["id"] == sid
    assert sess["task_id"] == "t1"
    assert sess["mode"] == "native"
    assert sess["adapter"] == "native"
    assert sess["status"] == "running"
    assert isinstance(sess["started_at"], (int, float))
    assert card["report_path"] == f".coding/runs/r-nat/sessions/{sid}/report.json"
    assert (root / card["report_path"]).parent.is_dir(), "session dir must exist for the report"


def test_claim_is_idempotent(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    write_state(root)

    first = claim(root)
    second = claim(root)

    assert second == first, "second claim must return the same card"
    st = read_state(root)
    assert len(st["sessions"]) == 1, "idempotent claim must not add another session"
    assert st["tasks"][0]["status"] == "running"


def test_claim_accepts_ready_and_returned_status(tmp_path):
    for status in ("ready", "returned"):
        root = tmp_path / status
        root.mkdir()
        write_state(root, tasks=[task(status=status)])

        card = claim(root)

        st = read_state(root)
        assert st["tasks"][0]["status"] == "running"
        assert st["tasks"][0]["session_id"] == st["sessions"][0]["id"]
        assert card["task_id"] == "t1"


def test_claim_on_old_state_without_sessions_key(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    p = write_state(root)
    raw = json.loads(p.read_text(encoding="utf-8"))
    del raw["sessions"]  # plan 之后、第一次 spawn 之前的旧 run 没有 sessions 键
    p.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    card = claim(root)

    st = read_state(root)
    assert len(st["sessions"]) == 1
    assert st["sessions"][0]["mode"] == "native"
    assert card["report_path"].endswith(f"{st['sessions'][0]['id']}/report.json")


def test_claim_moves_run_out_of_planning(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    write_state(root, phase="planning")
    claim(root)
    assert read_state(root)["phase"] == "delegating"


def test_claim_rejects_missing_task(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    write_state(root)
    r = cli(root, "claim", "r-nat", "nope", expect=1)
    assert "task not found" in r.stderr


def test_claim_rejects_terminal_run(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    write_state(root, phase="done")
    r = cli(root, "claim", "r-nat", "t1", expect=1)
    assert "terminal" in r.stderr
    assert read_state(root)["tasks"][0]["status"] == "pending"


def test_claim_rejects_cli_session_for_same_task(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    write_state(root,
                tasks=[task(status="running", session_id="s-cli")],
                sessions=[{"id": "s-cli", "task_id": "t1", "adapter": "mock",
                           "pid": 0, "status": "running"}])
    r = cli(root, "claim", "r-nat", "t1", expect=1)
    assert "cli session" in r.stderr
    assert len(read_state(root)["sessions"]) == 1


def test_claim_rejects_touchset_overlap_in_run(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    write_state(root, tasks=[
        task("t1", touchset=["lib/x.py"]),
        task("t2", status="running", touchset=["lib/"]),
    ])
    r = cli(root, "claim", "r-nat", "t1", expect=1)
    assert "touchset overlaps" in r.stderr
    assert read_state(root)["tasks"][0]["status"] == "pending"


def test_claim_rejects_when_slot_taken(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    write_state(root, tasks=[
        task("t1", touchset=["a.py"]),
        task("t2", status="running", touchset=["b.py"]),
    ])
    r = cli(root, "claim", "r-nat", "t1", expect=1)
    assert "cannot claim" in r.stderr


# ---------------------------------------------------------------------------
# release


def test_release_returns_task_to_pending_then_reclaim(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    write_state(root)
    first = claim(root)
    sid1 = read_state(root)["tasks"][0]["session_id"]

    out = json.loads(cli(root, "release", "r-nat", "t1").stdout)
    assert out == {"task_id": "t1", "session": sid1, "mode": "native",
                   "task_status": "pending", "session_status": "released"}

    st = read_state(root)
    assert st["tasks"][0]["status"] == "pending"
    assert st["tasks"][0]["session_id"] is None
    assert st["sessions"][0]["status"] == "released"

    second = claim(root)
    st2 = read_state(root)
    sid2 = st2["tasks"][0]["session_id"]
    assert second["report_path"] == f".coding/runs/r-nat/sessions/{sid2}/report.json"
    assert sid2 != sid1
    assert len(st2["sessions"]) == 2
    assert st2["tasks"][0]["status"] == "running"


def test_release_only_accepts_native_sessions(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    # 旧 state：session 没有 mode 字段 → 按 cli 处理
    write_state(root,
                tasks=[task(status="running", session_id="s-old")],
                sessions=[{"id": "s-old", "task_id": "t1", "adapter": "mock",
                           "pid": 0, "status": "running"}])
    r = cli(root, "release", "r-nat", "t1", expect=1)
    assert "native sessions" in r.stderr
    st = read_state(root)
    assert st["tasks"][0]["status"] == "running"
    assert st["sessions"][0]["status"] == "running"


def test_release_without_session_is_rejected(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    write_state(root)
    r = cli(root, "release", "r-nat", "t1", expect=1)
    assert "has no session" in r.stderr


# ---------------------------------------------------------------------------
# status / doctor 的 mode


def test_old_state_without_mode_reads_as_cli(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    write_state(root,
                tasks=[task(status="running", session_id="s-old")],
                sessions=[{"id": "s-old", "task_id": "t1", "adapter": "mock",
                           "pid": 0, "status": "running"}])

    status = cli(root, "status").stdout
    assert "mode=cli" in status
    assert "s-old" in status

    doc = cli(root, "doctor").stdout
    data = json.loads(doc)
    assert data["problems"] == []
    assert data["sessions"] == [{"run_id": "r-nat", "session": "s-old", "task": "t1",
                                 "mode": "cli", "status": "running"}]


def test_status_and_doctor_show_native_mode(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    write_state(root)
    claim(root)

    status = cli(root, "status").stdout
    assert "mode=native" in status
    assert "status=running" in status

    data = json.loads(cli(root, "doctor").stdout)
    assert data["problems"] == []
    assert [x["mode"] for x in data["sessions"]] == ["native"]


def test_status_doctor_survive_mixed_old_and_new_sessions(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    write_state(root)
    claim(root)
    # 手动追加一条无 mode 的旧 session，模拟升级前留下的记录
    st = read_state(root)
    st["sessions"].append({"id": "s-legacy", "task_id": "t0", "adapter": "mock",
                           "status": "finished"})
    (root / ".coding" / "runs" / "r-nat" / "state.json").write_text(
        json.dumps(st, ensure_ascii=False), encoding="utf-8")

    status = cli(root, "status").stdout
    assert "mode=native" in status and "mode=cli" in status
    data = json.loads(cli(root, "doctor").stdout)
    modes = {x["session"]: x["mode"] for x in data["sessions"]}
    assert modes["s-legacy"] == "cli"
    assert list(modes.values()).count("native") == 1
