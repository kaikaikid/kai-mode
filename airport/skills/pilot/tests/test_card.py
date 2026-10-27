# -*- coding: utf-8 -*-
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "card.py"
spec = importlib.util.spec_from_file_location("card", SCRIPT)
card = importlib.util.module_from_spec(spec)
spec.loader.exec_module(card)


def test_card_builder_and_reviewer(tmp_path, capsys):
    data = {"number": 12, "ac": ["甲", "乙"], "allow": ["src/a.py"],
            "deny": ["src/b.py"], "verify": ["pytest -q"]}
    p = tmp_path / "t.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    assert card.main(["--ticket-json", str(p), "--lane", "main"]) == 0
    out = capsys.readouterr().out
    assert "票号：12" in out and "甲" in out and "pytest -q" in out
    assert card.main(["--ticket-json", str(p), "--role", "reviewer", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["role"] == "reviewer"
    assert "只读" in payload["instruction"]
