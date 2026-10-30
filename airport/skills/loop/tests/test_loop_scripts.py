# -*- coding: utf-8 -*-
"""loop 技能脚本的单元测试：只测纯函数与本地校验，不联网、不建工作树。"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ticket = load("ticket")
protocol = load("protocol")
worktree = load("worktree")


BODY = """## 目标
把某件事做完。

## AC（逐条可机检）
- [ ] 第一条
1. 第二条
- 第三条

## 允许修改
- src/a.py

## 禁止修改
- src/b.py

## 验证命令
- `python -m pytest -q`
"""


def test_parse_ticket_counts_and_fields():
    info = ticket.parse_ticket({"number": 7, "title": "t", "state": "OPEN",
                                "labels": [{"name": "ready-for-agent"}],
                                "body": BODY, "comments": []})
    assert info["ac"] == ["第一条", "第二条", "第三条"]
    assert info["allow"] == ["src/a.py"]
    assert info["deny"] == ["src/b.py"]
    assert info["verify"] == ["python -m pytest -q"]
    assert info["labels"] == ["ready-for-agent"]


def test_parse_verdict_ok_and_bad():
    ok = ticket.parse_verdict("verdict=pass\nac=3/3\n证据 file:1")
    assert ok["verdict"] == "pass" and ok["passed"] == 3 and not ok["problems"]
    bad = ticket.parse_verdict("pass\n3/3")
    assert bad["problems"]


def test_receipt_requires_fields(tmp_path):
    good = {
        "ticket": 7, "role": "builder", "verdict": "done", "files": ["a"],
        "commits": ["abc"], "checks": {"tests": "pass 1/1"}, "summary": ["x"],
        "evidence": ["a:1"], "risks": [], "next": "review",
    }
    p = tmp_path / "r.json"
    p.write_text(json.dumps(good), encoding="utf-8")
    assert ticket.main(["receipt", "--file", str(p), "--json"]) == 0
    good.pop("evidence")
    p.write_text(json.dumps(good), encoding="utf-8")
    assert ticket.main(["receipt", "--file", str(p), "--json"]) == 1


def test_pointer_requires_four_keys():
    text = "等什么：子代理\n下一步第一个动作：跑审查\n在飞面：票 7\n验证命令：pytest -q"
    assert ticket.main(["pointer", "--text", text, "--json"]) == 0
    assert ticket.main(["pointer", "--text", "等什么：子代理", "--json"]) == 1


def test_protocol_section_and_list(capsys):
    assert protocol.main(["--list"]) == 0
    out = capsys.readouterr().out
    assert "三、单票闭环" in out
    assert protocol.main(["--section", "三"]) == 0
    section = capsys.readouterr().out
    assert "单票闭环" in section and "判词格式" in section
    assert protocol.main(["--section", "不存在的节"]) == 1


def test_worktree_parse_and_classify(tmp_path):
    root = str(tmp_path)
    text = (
        f"worktree {root}/.worktrees/lane-main\nHEAD abc123\nbranch refs/heads/dev\n\n"
        f"worktree {root}/.worktrees/lane-main-b\nHEAD bbb222\nbranch refs/heads/dev\n\n"
        f"worktree {root}/.worktrees/lane-ace\nHEAD def456\ndetached\n\n"
        f"worktree {root}/_push\nHEAD 111\ndetached\n"
    )
    items = worktree.parse_porcelain(text)
    assert len(items) == 4
    assert items[2]["detached"] is True
    # 旧槽 lane-main 视为 -a；正常车道第二槽是 -b；王牌仍一棵 lane-ace
    assert worktree.classify(items[0]["path"], root) == "lane-main-a"
    assert worktree.classify(items[1]["path"], root) == "lane-main-b"
    assert worktree.classify(items[2]["path"], root) == "lane-ace"
    assert worktree.classify(items[3]["path"], root) == "push-station"
    assert worktree.is_legacy(items[0]["path"], root) is True
    assert worktree.is_legacy(items[1]["path"], root) is False
    assert Path(worktree.slot_path(root, "main", "b")).name == "lane-main-b"
