#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""restore-guard 的回归网：clean / safe / not-in-history / missing 四态与退出码。

跑法：pytest airport/skills/pilot/tests
约定：每个用例一个临时 git 仓，只调脚本对外命令，不碰真仓。
"""
import json
import os
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "restore-guard.py")


def run(*args):
    p = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def make_repo():
    root = tempfile.mkdtemp(prefix="restore-guard-test-")
    git = lambda *a: subprocess.run(["git", "-C", root, *a], capture_output=True, text=True)
    git("init", "-q")
    git("checkout", "-q", "-b", "dev")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    return root, git


def commit(git, root, name, body):
    with open(os.path.join(root, name), "w", encoding="utf-8") as f:
        f.write(body)
    git("add", name)
    git("commit", "-q", "-m", f"add {name}")


def test_clean_when_working_tree_matches_head():
    root, git = make_repo()
    commit(git, root, "a.txt", "v1\n")
    rc, out = run("check", "--repo", root, "a.txt")
    assert rc == 0, out
    assert out.split("\t")[0] == "clean"


def test_safe_when_content_exists_in_history():
    root, git = make_repo()
    commit(git, root, "a.txt", "v1\n")
    commit(git, root, "a.txt", "v2\n")
    with open(os.path.join(root, "a.txt"), "w", encoding="utf-8") as f:
        f.write("v1\n")  # 工作区退回旧版本：历史里逐字存在 ⇒ safe
    rc, out = run("check", "--repo", root, "a.txt")
    assert rc == 0, out
    assert out.split("\t")[0] == "safe"


def test_not_in_history_is_red():
    root, git = make_repo()
    commit(git, root, "a.txt", "v1\n")
    with open(os.path.join(root, "a.txt"), "w", encoding="utf-8") as f:
        f.write("someone else's work in progress\n")
    rc, out = run("check", "--repo", root, "a.txt")
    assert rc == 1, out
    assert out.split("\t")[0] == "not-in-history"


def test_missing_path_is_red():
    root, git = make_repo()
    commit(git, root, "a.txt", "v1\n")
    rc, out = run("check", "--repo", root, "nope.txt")
    assert rc == 1, out
    assert out.split("\t")[0] == "missing"


def test_json_shape_and_summary():
    root, git = make_repo()
    commit(git, root, "a.txt", "v1\n")
    rc, out = run("check", "--repo", root, "--json", "a.txt")
    assert rc == 0, out
    data = json.loads(out)
    assert data["ref"] == "dev"
    assert data["files"][0]["verdict"] == "clean"
    assert data["files"][0]["blob"]
