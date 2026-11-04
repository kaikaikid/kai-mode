# -*- coding: utf-8 -*-
"""auto 腿：无人值守循环的状态与宿主命令行为。

不测真子代理（不起宿主进程）；只测：
1. 宿主命令缺省时如实报缺件；
2. drive() 遇到终态/排队/blocked 立即停；
3. drive() 有 ready 任务时按 claim→worker→report→review→verdict 顺序调现有命令。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engine.coding import auto, state as st


def test_no_worker_cmd_reports_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("TRAVEL_WORKER_CMD", "")
    monkeypatch.setenv("TRAVEL_REVIEWER_CMD", "")
    card = {"task_id": "t1", "report_path": str(tmp_path / "r.json")}
    out = auto._spawn_worker(card, "")
    assert "no worker command" in out["_error"]


def test_no_reviewer_cmd_reports_missing(tmp_path):
    card = {"task_id": "t1", "review_report_path": str(tmp_path / "r.json")}
    out = auto._spawn_reviewer(card, "")
    assert "no reviewer command" in out["_error"]


def test_worker_cmd_not_found_reports_missing(tmp_path):
    card = {"task_id": "t1", "report_path": str(tmp_path / "r.json")}
    out = auto._spawn_worker(card, "definitely-not-a-real-binary-{brief}")
    assert "not found" in out["_error"]


def test_drive_stops_on_terminal_phase(tmp_path, monkeypatch, capsys):
    run_dir = tmp_path / ".coding" / "runs" / "r-test"
    run_dir.mkdir(parents=True)
    (run_dir / "state.json").write_text(json.dumps({
        "run_id": "r-test", "phase": "done", "tasks": [], "resume": {},
    }), encoding="utf-8")
    monkeypatch.setattr(auto, "_root", lambda: tmp_path)
    monkeypatch.setattr(st, "repo_root", lambda: tmp_path)
    result = auto.drive("r-test", worker_cmd="python w.py {brief}", reviewer_cmd="python r.py {brief}")
    assert result["phase"] == "done"
    assert "terminal" in result["log"][-1]


def test_drive_stops_on_blocked(tmp_path, monkeypatch):
    run_dir = tmp_path / ".coding" / "runs" / "r-test"
    run_dir.mkdir(parents=True)
    (run_dir / "state.json").write_text(json.dumps({
        "run_id": "r-test", "phase": "blocked", "tasks": [],
        "resume": {"next_action": "merge conflict"},
    }), encoding="utf-8")
    monkeypatch.setattr(auto, "_root", lambda: tmp_path)
    monkeypatch.setattr(st, "repo_root", lambda: tmp_path)
    result = auto.drive("r-test", worker_cmd="python w.py {brief}", reviewer_cmd="python r.py {brief}")
    assert result["phase"] == "blocked"
    assert "blocked" in result["log"][-1]


def test_drive_calls_commands_in_order(tmp_path, monkeypatch):
    """有 ready 任务时，循环按 claim→worker→report→review→verdict 调命令，不改状态。"""
    run_dir = tmp_path / ".coding" / "runs" / "r-test"
    run_dir.mkdir(parents=True)
    state = {
        "run_id": "r-test", "phase": "delegating",
        "tasks": [{"id": "t1", "status": "running"}],
        "resume": {}, "gates": {"g0": "approved", "g1": "skipped", "g2": "pending"},
    }
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(auto, "_root", lambda: tmp_path)
    monkeypatch.setattr(st, "repo_root", lambda: tmp_path)

    calls = []

    def fake_run_cmd(cmd_args, cwd=None):
        calls.append(cmd_args[0])
        if cmd_args[0] == "next":
            return [{"run_id": "r-test", "task_id": "t1"}]
        if cmd_args[0] == "claim":
            return {"task_id": "t1", "report_path": str(tmp_path / "report.json"),
                    "worktree": str(tmp_path), "brief": "b", "touchset": [], "ac": []}
        if cmd_args[0] == "review":
            return {"review_report_path": str(tmp_path / "verdict.json"),
                    "worktree": str(tmp_path)}
        return {}

    def fake_worker(card, cmd):
        (tmp_path / "report.json").write_text(json.dumps({"result": "done"}), encoding="utf-8")
        return {"result": "done"}

    def fake_reviewer(card, cmd):
        (tmp_path / "verdict.json").write_text(json.dumps({"verdict": "accept"}), encoding="utf-8")
        return {"verdict": "accept"}

    monkeypatch.setattr(auto, "DEFAULT_WORKER", "python w.py {brief}")
    monkeypatch.setattr(auto, "DEFAULT_REVIEWER", "python r.py {brief}")
    auto.DEFAULT_WORKER = "python w.py {brief}"
    auto.DEFAULT_REVIEWER = "python r.py {brief}"
    monkeypatch.setattr(auto, "_run_cmd", fake_run_cmd)
    monkeypatch.setattr(auto, "_spawn_worker", fake_worker)
    monkeypatch.setattr(auto, "_spawn_reviewer", fake_reviewer)

    auto.drive("r-test", worker_cmd="python w.py {brief}", reviewer_cmd="python r.py {brief}", max_rounds=2)
    assert "claim" in calls
    assert "report" in calls
    assert "review" in calls
    assert "verdict" in calls
    idx = [calls.index(c) for c in ("claim", "report", "review", "verdict")]
    assert idx == sorted(idx)
