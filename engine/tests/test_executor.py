# -*- coding: utf-8 -*-
"""执行器抽象（ADR-0035 D6）：三实现返回形状 + auto 接线 + 旧行为不回归。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engine.coding import auto, executor, state as st


CARD = {"task_id": "t1", "report_path": "r.json"}


def test_native_executor_shape():
    out = executor.NativeExecutor().run(dict(CARD))
    assert out == {"_needs_subagent": True, "card": CARD}


def test_message_executor_shape():
    out = executor.MessageExecutor().run(dict(CARD))
    assert out["_needs_message"] is True
    assert out["card"] == CARD


def test_host_cmd_executor_delegates_to_spawn_worker(monkeypatch):
    seen = {}

    def fake_spawn(card, cmd):
        seen["card"] = card
        seen["cmd"] = cmd
        return {"result": "done"}

    monkeypatch.setattr(auto, "_spawn_worker", fake_spawn)
    out = executor.HostCommandExecutor("py w.py {brief}").run(dict(CARD))
    assert out == {"result": "done"}
    assert seen["cmd"] == "py w.py {brief}"
    assert seen["card"] == CARD


def test_host_cmd_executor_empty_cmd_needs_subagent():
    out = executor.HostCommandExecutor("").run(dict(CARD))
    assert out["_needs_subagent"] is True
    assert out["card"] == CARD


def test_get_executor_names_and_unknown():
    assert executor.get_executor("native").name == "native"
    assert executor.get_executor("host-cmd", "x").host_cmd == "x"
    assert executor.get_executor("message").name == "message"
    with pytest.raises(ValueError):
        executor.get_executor("shell")


def _prime_run(tmp_path: Path) -> None:
    run_dir = tmp_path / ".coding" / "runs" / "r-test"
    run_dir.mkdir(parents=True)
    (run_dir / "state.json").write_text(json.dumps({
        "run_id": "r-test", "phase": "delegating",
        "tasks": [{"id": "t1", "status": "running"}],
        "resume": {}, "gates": {"g0": "approved", "g1": "skipped", "g2": "pending"},
    }), encoding="utf-8")


def _fake_cmds(tmp_path: Path):
    calls = []

    def fake_run_cmd(args, cwd=None):
        calls.append(args[0])
        if args[0] == "next":
            return [{"run_id": "r-test", "task_id": "t1"}]
        if args[0] == "claim":
            return {"task_id": "t1", "report_path": str(tmp_path / "report.json"),
                    "worktree": str(tmp_path), "brief": "b", "touchset": [], "ac": []}
        if args[0] == "review":
            return {"review_report_path": str(tmp_path / "verdict.json"), "worktree": str(tmp_path)}
        return {}

    return calls, fake_run_cmd


def test_drive_message_executor_returns_pending_card(tmp_path, monkeypatch, capsys):
    _prime_run(tmp_path)
    monkeypatch.setattr(auto, "_root", lambda: tmp_path)
    monkeypatch.setattr(st, "repo_root", lambda: tmp_path)
    calls, fake_run_cmd = _fake_cmds(tmp_path)
    monkeypatch.setattr(auto, "_run_cmd", fake_run_cmd)

    result = auto.drive("r-test", worker_cmd="", reviewer_cmd="", executor="message")
    assert result["phase"] == "messaging"
    assert result["pending_card"]["task_id"] == "t1"
    assert "message t1" == result["next_action"]
    # 只交卡，不发送、不写 report/verdict
    assert "report" not in calls
    assert "verdict" not in calls
    printed = json.loads(capsys.readouterr().out)
    assert printed["phase"] == "messaging"


def test_drive_native_executor_matches_legacy_shape(tmp_path, monkeypatch, capsys):
    _prime_run(tmp_path)
    monkeypatch.setattr(auto, "_root", lambda: tmp_path)
    monkeypatch.setattr(st, "repo_root", lambda: tmp_path)
    calls, fake_run_cmd = _fake_cmds(tmp_path)
    monkeypatch.setattr(auto, "_run_cmd", fake_run_cmd)

    result = auto.drive("r-test", worker_cmd="", reviewer_cmd="", executor="native")
    assert result["phase"] == "delegating"
    assert result["pending_card"]["task_id"] == "t1"
    capsys.readouterr()


def test_drive_default_keeps_legacy_spawn_worker(tmp_path, monkeypatch, capsys):
    """executor 缺省 = 老行为：直接调 _spawn_worker，不经过 executor 抽象。"""
    _prime_run(tmp_path)
    monkeypatch.setattr(auto, "_root", lambda: tmp_path)
    monkeypatch.setattr(st, "repo_root", lambda: tmp_path)
    calls, fake_run_cmd = _fake_cmds(tmp_path)
    monkeypatch.setattr(auto, "_run_cmd", fake_run_cmd)

    used = {"n": 0}

    def fake_spawn(card, cmd):
        used["n"] += 1
        return {"_needs_subagent": True, "card": card}

    monkeypatch.setattr(auto, "_spawn_worker", fake_spawn)
    result = auto.drive("r-test", worker_cmd="", reviewer_cmd="")
    assert used["n"] == 1
    assert result["phase"] == "delegating"
    capsys.readouterr()
