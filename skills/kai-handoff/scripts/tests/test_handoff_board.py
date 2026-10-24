# -*- coding: utf-8 -*-
"""看板脚本：按项目仓根与配置落卡片；找不到仓就报缺件，不猜目录。"""

import json
import os
import subprocess
import sys

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "handoff-board.py")


def run(args, cwd):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    env.pop("KAI_REPO_ROOT", None)
    return subprocess.run([sys.executable, SCRIPT, *args], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", env=env)


def make_repo(tmp_path, handoff_dir=None):
    repo = tmp_path / "repo"
    (repo / ".ai").mkdir(parents=True)
    cfg = {"schema": 3, "paths": {"handoff_dir": handoff_dir or "handoff"}}
    (repo / ".ai" / "kai-mode.project.json").write_text(
        json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    (repo / (handoff_dir or "handoff") / "60-board" / "open").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo


def test_new_card_uses_project_handoff_dir(tmp_path):
    repo = make_repo(tmp_path, handoff_dir="records/handoff")
    p = run(["new", "--title", "冒烟", "--ticket", "#1", "--role", "机长"], repo)
    assert p.returncode == 0, p.stderr
    cards = list((repo / "records/handoff/60-board/open").glob("*.md"))
    assert len(cards) == 1
    text = cards[0].read_text(encoding="utf-8")
    assert 'ticket: "#1"' in text  # 不加引号会被 YAML 当注释吞掉
    q = run(["list"], repo)
    assert q.returncode == 0
    assert "票=#1" in q.stdout


def test_no_repo_root_is_reported(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    p = run(["list"], plain)
    assert p.returncode == 2
    assert "找不到项目仓" in p.stderr
