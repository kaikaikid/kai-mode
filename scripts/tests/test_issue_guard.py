# -*- coding: utf-8 -*-
"""开票归属守卫的回归网：缺 --repo 即拒、有 --repo 放行、非开票命令放行、仓库从实例读。"""
import importlib.util
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SCRIPT = os.path.join(REPO, "core", "skills", "set-kai-mode", "scripts", "issue-guard.py")

sys.dont_write_bytecode = True


def _load():
    spec = importlib.util.spec_from_file_location("kai_mode_issue_guard", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


g = _load()


def _instance(tmp_path, repo=None):
    os.makedirs(tmp_path / ".ai", exist_ok=True)
    issue = {"platform": "github", "verdict_marker": "verdict=pass", "boom_summary_ticket": None}
    if repo:
        issue["repo"] = repo
    with open(tmp_path / ".ai" / "kai-mode.project.json", "w", encoding="utf-8") as f:
        json.dump({"schema": 4, "issue": issue}, f)


def test_self_test_passes():
    assert g._self_test() == 0


def test_rejects_create_without_repo():
    assert g.CREATE_RE.search("gh issue create --title x")
    assert not g.REPO_FLAG_RE.search("gh issue create --title x")


def test_repo_forms_are_recognized():
    for cmd in ("gh issue create --repo a/b --title x",
                "gh pr create -R a/b --title x",
                "gh issue create --repo=a/b --title x"):
        assert g.REPO_FLAG_RE.search(cmd), cmd


def test_non_create_commands_pass():
    for cmd in ("gh issue list --state open", "git status", "gh pr view 12"):
        assert not g.CREATE_RE.search(cmd), cmd


def test_help_passes():
    assert g.HELP_RE.search("gh issue create --help")


def test_desired_repo_from_instance(tmp_path):
    _instance(tmp_path, "o/r")
    want, how = g.desired_repo([], str(tmp_path))
    assert want == "o/r" and how == "实例"


def test_desired_repo_missing_instance(tmp_path):
    want, how = g.desired_repo([], str(tmp_path / "nope"))
    assert want is None and how == "实例读不到"


def test_desired_repo_without_repo_key(tmp_path):
    _instance(tmp_path, None)
    want, how = g.desired_repo([], str(tmp_path))
    assert want is None and "issue.repo" in how


def test_main_rejects_then_accepts(tmp_path, monkeypatch, capsys):
    _instance(tmp_path, "o/r")
    monkeypatch.setattr(sys, "argv", ["issue-guard.py", "--repo", str(tmp_path),
                                      "--command", "gh issue create --title x"])
    assert g.main() == 2
    assert "o/r" in capsys.readouterr().err
    monkeypatch.setattr(sys, "argv", ["issue-guard.py", "--repo", str(tmp_path),
                                      "--command", "gh issue create --repo o/r --title x"])
    assert g.main() == 0
