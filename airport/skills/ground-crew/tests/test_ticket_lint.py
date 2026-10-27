# -*- coding: utf-8 -*-
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "ticket-lint.py"
spec = importlib.util.spec_from_file_location("ticket_lint", SCRIPT)
lint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lint)

GOOD = """## 目标
做完。

## AC
- 第一条

## 允许修改
- src/a.py

## 禁止修改
- src/b.py

## 验证命令
- `pytest -q`

## 依赖 / 红线
- 无
"""


def test_lint_good_and_missing(tmp_path, capsys):
    p = tmp_path / "t.md"
    p.write_text(GOOD, encoding="utf-8")
    assert lint.main(["--body-file", str(p), "--labels", "ready-for-agent",
                      "--require-label", "ready-for-agent", "--json"]) == 0
    bad = GOOD.replace("## 验证命令\n- `pytest -q`\n", "")
    p.write_text(bad, encoding="utf-8")
    assert lint.main(["--body-file", str(p), "--json"]) == 1
    assert "验证命令" in capsys.readouterr().out
