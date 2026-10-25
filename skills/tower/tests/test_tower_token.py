#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""塔台令牌脚本的回归网：三态退出码与「不写别人的牌」。

跑法：pytest skills/tower/tests  或  python -m pytest skills/tower/tests
约定：每个用例一个临时仓（真 JSON 实例），只调脚本对外命令，不 import 内部函数。
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "tower-token.py")


def make_repo(interval_min=60, with_instance=True):
    root = tempfile.mkdtemp(prefix="tower-token-test-")
    if with_instance:
        os.makedirs(os.path.join(root, ".ai"), exist_ok=True)
        inst = {
            "schema": 4,
            "project": "t",
            "paths": {"state_dir": ".git/kai-mode"},
            "tower_cron": {"interval_min": interval_min},
        }
        with open(os.path.join(root, ".ai", "kai-mode.project.json"), "w", encoding="utf-8") as f:
            json.dump(inst, f)
    return root


def run(repo, *args):
    p = subprocess.run([sys.executable, SCRIPT, *args, "--repo", repo],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def token_path(repo):
    return os.path.join(repo, ".git", "kai-mode", "tower-token.json")


def test_free_then_acquire():
    repo = make_repo()
    rc, out = run(repo, "who")
    assert rc == 0 and "FREE" in out
    rc, out = run(repo, "acquire", "--holder", "A")
    assert rc == 0 and "ACQUIRED" in out
    data = json.load(open(token_path(repo), encoding="utf-8"))
    assert data["holder"] == "A" and data["acquired_at"] and data["heartbeat_at"]
    assert "ttl_min" in data


def test_second_holder_steps_aside():
    repo = make_repo()
    assert run(repo, "acquire", "--holder", "A")[0] == 0
    rc, out = run(repo, "acquire", "--holder", "B")
    assert rc == 1 and "HELD" in out
    assert json.load(open(token_path(repo), encoding="utf-8"))["holder"] == "A"


def test_non_holder_cannot_heartbeat_or_release():
    repo = make_repo()
    assert run(repo, "acquire", "--holder", "A")[0] == 0
    assert run(repo, "heartbeat", "--holder", "B")[0] == 1
    assert run(repo, "release", "--holder", "B")[0] == 1
    assert os.path.isfile(token_path(repo)), "别人的牌不允许被删"


def test_expired_token_is_taken_over():
    repo = make_repo(interval_min=60)
    assert run(repo, "acquire", "--holder", "A")[0] == 0
    path = token_path(repo)
    data = json.load(open(path, encoding="utf-8"))
    data["heartbeat_at"] = (datetime.now(timezone.utc) - timedelta(minutes=200)).isoformat(timespec="seconds")
    json.dump(data, open(path, "w", encoding="utf-8"))
    rc, out = run(repo, "acquire", "--holder", "B")
    assert rc == 0 and "TAKEOVER" in out
    assert json.load(open(path, encoding="utf-8"))["holder"] == "B"
    assert "200" in out  # 播报里带心跳龄，供日报写「谁接谁的班」


def test_release_by_holder_then_free():
    repo = make_repo()
    assert run(repo, "acquire", "--holder", "A")[0] == 0
    assert run(repo, "release", "--holder", "A")[0] == 0
    assert not os.path.exists(token_path(repo))
    rc, out = run(repo, "who")
    assert rc == 0 and "FREE" in out


def test_ttl_follows_interval():
    repo = make_repo(interval_min=30)
    assert run(repo, "acquire", "--holder", "A")[0] == 0
    assert json.load(open(token_path(repo), encoding="utf-8"))["ttl_min"] == 30 * 2 + 5


def test_missing_instance_reports_three_boxes():
    repo = make_repo(with_instance=False)
    rc, out = run(repo, "acquire", "--holder", "A")
    assert rc == 2
    assert "缺什么" in out and "谁需要" in out and "怎么补" in out


def test_holder_required():
    repo = make_repo()
    p = subprocess.run([sys.executable, SCRIPT, "acquire", "--repo", repo],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert p.returncode == 2
