#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hotfix-lint 的回归网：分支名 / 提交标识 / 日表行三件，缺一判 fail。

跑法：pytest airport/skills/ace/tests
约定：每个用例一个临时 git 仓 ＋ 一份假 `-ace.md`，只调脚本对外命令。
"""
import json
import os
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "hotfix-lint.py")
BRANCH = "hotfix/ace-20261028-1-fix-x"


def run(*args):
    p = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout + p.stderr


def make_repo(subject="H-2026-10-28-1 修好空指针", branch=BRANCH):
    root = tempfile.mkdtemp(prefix="hotfix-lint-test-")
    git = lambda *a: subprocess.run(["git", "-C", root, *a], capture_output=True, text=True)
    git("init", "-q")
    git("checkout", "-q", "-b", branch)
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    with open(os.path.join(root, "a.txt"), "w", encoding="utf-8") as f:
        f.write("x\n")
    git("add", "a.txt")
    git("commit", "-q", "-m", subject)
    return root, git


def write_table(root, row):
    path = os.path.join(root, "2026-10-28-ace.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("| 序 | 票号 | 里程碑 | 一句话 | 王牌备注 |\n|---|---|---|---|---|\n")
        f.write(row + "\n")
    return path


GOOD_ROW = f"| 1 | H-1 | - | 修空指针 | {BRANCH} · verdict=pass · rc=0 |"


def test_all_three_pass():
    root, _ = make_repo()
    table = write_table(root, GOOD_ROW)
    rc, out = run("--repo", root, "--day-table", table, "--branch", BRANCH)
    assert rc == 0, out
    assert out.strip().splitlines()[-1] == "verdict=pass"


def test_bad_branch_name_is_red():
    root, _ = make_repo(branch="hotfix/fix-x")
    table = write_table(root, "| 1 | H-1 | - | 修 | hotfix/fix-x · verdict=pass · rc=0 |")
    rc, out = run("--repo", root, "--day-table", table, "--branch", "hotfix/fix-x")
    assert rc == 1, out
    assert "branch-name" in out


def test_missing_commit_marker_is_red():
    root, _ = make_repo(subject="修好空指针")
    table = write_table(root, GOOD_ROW)
    rc, out = run("--repo", root, "--day-table", table, "--branch", BRANCH)
    assert rc == 1, out
    assert "commit-marker" in out


def test_row_without_readout_is_red():
    root, _ = make_repo()
    table = write_table(root, f"| 1 | H-1 | - | 修 | {BRANCH} · verdict=pass |")
    rc, out = run("--repo", root, "--day-table", table, "--branch", BRANCH)
    assert rc == 1, out
    assert "day-table-row" in out


def test_missing_table_is_red():
    root, _ = make_repo()
    rc, out = run("--repo", root, "--day-table", os.path.join(root, "nope.md"), "--branch", BRANCH)
    assert rc == 1, out


def test_json_shape():
    root, _ = make_repo()
    table = write_table(root, GOOD_ROW)
    rc, out = run("--repo", root, "--day-table", table, "--branch", BRANCH, "--json")
    assert rc == 0, out
    data = json.loads(out)
    assert data["verdict"] == "pass"
    assert {c["check"] for c in data["checks"]} == {"branch-name", "commit-marker", "day-table-row"}
