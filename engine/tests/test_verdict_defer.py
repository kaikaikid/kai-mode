# -*- coding: utf-8 -*-
"""verdict 三态：accept / return / defer（defer 记入团长队列、不阻塞施工）。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CODING = REPO / "engine" / "coding_main.py"
PY = sys.executable


def cli(root: Path, *args: str, expect: int = 0) -> subprocess.CompletedProcess:
    r = subprocess.run([PY, str(CODING), *args], cwd=str(root), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    assert r.returncode == expect, (
        f"{args} -> rc={r.returncode} (expected {expect})\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}")
    return r


def write_state(root: Path, *, phase: str = "reviewing") -> Path:
    d = root / ".coding" / "runs" / "r-def"
    d.mkdir(parents=True, exist_ok=True)
    state = {
        "run_id": "r-def", "phase": phase, "issue": "#9 defer",
        "priority": "normal", "fleet_id": "host-1", "ship_limit": 1, "crew_limit": 5,
        "base_branch": "main", "branch": "travel/r-def", "worktree": str(root),
        "gates": {"g0": "approved", "g1": "skipped", "g2": "pending"},
        "tasks": [{"id": "t1", "title": "t1", "brief": "do t1", "tier": "light",
                   "deps": [], "touchset": ["t1.py"], "ac": ["t1 ok"], "ui": False,
                   "status": "review", "attempts": 0, "session_id": None}],
        "sessions": [],
        "resume": {"last_accepted": None, "next_action": "review"},
    }
    p = d / "state.json"
    p.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    return p


def read_state(root: Path) -> dict:
    return json.loads((root / ".coding" / "runs" / "r-def" / "state.json").read_text(encoding="utf-8"))


def test_defer_accepts_task_and_records_owner_queue(tmp_path: Path):
    write_state(tmp_path)
    vf = tmp_path / "v.json"
    vf.write_text(json.dumps({
        "verdict": "defer",
        "reason": "技术验收已过；配色偏好留团长拍板",
        "deferred_items": [{"question": "主色用琥珀还是墨绿？", "reason": "个人向取舍",
                            "priority": "low"}],
    }, ensure_ascii=False), encoding="utf-8")
    cli(tmp_path, "verdict", "r-def", "t1", "--file", str(vf))
    s = read_state(tmp_path)
    assert s["tasks"][0]["status"] == "accepted"
    q = s.get("owner_deferred") or []
    assert len(q) == 1
    assert q[0]["question"].startswith("主色")
    assert q[0]["status"] == "pending"


def test_defer_without_items_is_rejected(tmp_path: Path):
    write_state(tmp_path)
    vf = tmp_path / "v.json"
    vf.write_text(json.dumps({"verdict": "defer", "reason": "x"}), encoding="utf-8")
    r = cli(tmp_path, "verdict", "r-def", "t1", "--file", str(vf), expect=1)
    assert "deferred_items" in (r.stdout + r.stderr)


def test_return_still_rework(tmp_path: Path):
    write_state(tmp_path)
    vf = tmp_path / "v.json"
    vf.write_text(json.dumps({"verdict": "return", "defects": ["AC1 未满足"]}), encoding="utf-8")
    cli(tmp_path, "verdict", "r-def", "t1", "--file", str(vf))
    s = read_state(tmp_path)
    assert s["tasks"][0]["status"] == "returned"
    assert s["tasks"][0]["attempts"] == 1
