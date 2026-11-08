# -*- coding: utf-8 -*-
"""ADR-0032：默认档位的机械回归。

命令默认 1 个 run、adopt 不占第二槽、scheduler 旧状态兜底也是 1。
不建真 worktree，只用源码文本与纯函数检查。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engine.coding import scheduler


def _kernel_text(name: str) -> str:
    return (Path(__file__).resolve().parents[1] / "coding" / name).read_text(encoding="utf-8")


def test_warp_default_is_one_ship():
    text = _kernel_text("cli.py")
    assert "args.ships = 1" in text
    assert "args.ships = 2" not in text


def test_cli_help_says_default_one_ship():
    text = _kernel_text("cli.py")
    assert text.count('help="run count 1-3 (default 1)"') == 3
    assert "(default 2)" not in text


def test_adopt_uses_one_ship_limit():
    text = _kernel_text("cli.py")
    assert '"ship_limit": 1,' in text


def test_scheduler_missing_ship_limit_defaults_to_one(monkeypatch):
    """旧 state 无 ship_limit 时只允许一个 run 施工中；第二个排队。"""
    monkeypatch.setattr(scheduler.st, "load", lambda *_args, **_kw: {"phase": "done"})
    monkeypatch.setattr(scheduler, "slot_usage",
                        lambda *_args, **_kw: {"normal": 0, "urgent": 0, "sessions": 0})
    run = {"fleet_id": "host-1", "depends_on_runs": []}
    assert scheduler.can_start(run) == (True, "ok")

    monkeypatch.setattr(scheduler, "slot_usage",
                        lambda *_args, **_kw: {"normal": 1, "urgent": 0, "sessions": 0})
    assert scheduler.can_start(run)[0] is False
