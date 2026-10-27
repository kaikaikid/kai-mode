# -*- coding: utf-8 -*-
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "round.py"
spec = importlib.util.spec_from_file_location("round", SCRIPT)
round_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(round_mod)


def test_plan_keeps_overlapping_tickets_apart():
    tickets = [
        {"ticket": 1, "files": ["a.py"]},
        {"ticket": 2, "files": ["a.py"]},
        {"ticket": 3, "files": ["b.py"]},
    ]
    out = round_mod.plan(tickets, 5)
    assert out["counts"]["tickets"] == 3
    assert len(out["batches"]) >= 2
    for batch in out["batches"]:
        assert 1 <= len(batch["tickets"]) <= 5


def test_plan_urgent_first():
    tickets = [
        {"ticket": 1, "files": ["a.py"]},
        {"ticket": 2, "files": ["b.py"], "urgent": True},
    ]
    out = round_mod.plan(tickets, 5)
    assert out["batches"][0]["tickets"] == [2]


def test_budget_levels():
    assert round_mod.budget(10, 100)["status"] == "ok"
    assert round_mod.budget(90, 100)["status"] == "warn"
    assert round_mod.budget(101, 100)["status"] == "over"
