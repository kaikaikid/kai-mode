#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""待发货队列脚本的回归网：派生、增量、重验与「失败不等于零」。

跑法：pytest airport/skills/tower/tests
约定：每个用例一个临时仓（真 JSON 实例）＋离线夹具，只调脚本对外命令，不联网、不碰真 git。
"""
import json
import os
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "scripts", "ship-queue.py")


def make_repo(with_instance=True):
    root = tempfile.mkdtemp(prefix="ship-queue-test-")
    if with_instance:
        os.makedirs(os.path.join(root, ".ai"), exist_ok=True)
        inst = {"schema": 4, "project": "t",
                "paths": {"state_dir": ".git/kai-mode", "day_tables_dir": "tables"}}
        with open(os.path.join(root, ".ai", "kai-mode.project.json"), "w", encoding="utf-8") as f:
            json.dump(inst, f)
    return root


def fixture(repo, data):
    path = os.path.join(repo, "fixture.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


def run(repo, action, *args, fx=None, as_json=False):
    cmd = [sys.executable, SCRIPT, action, "--repo", repo]
    if fx:
        cmd += ["--fixture", fx]
    if as_json:
        cmd.append("--json")
    cmd += list(args)
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def issue(n, body="- [ ] a\n- [ ] b", updated="2026-10-27T08:00:00Z", **kw):
    d = {"number": n, "state": "open", "updated_at": updated, "body": body}
    d.update(kw)
    return d


def pass_comment(cid=1, ac="2/2", sha="abc1234", branch="feat/x", urgent=False):
    body = f"verdict=pass\nac={ac}\nbranch={branch}\ncommit={sha}"
    if urgent:
        body = "加急·待发货\n" + body
    return {"id": cid, "body": body}


def state_path(repo):
    return os.path.join(repo, ".git", "kai-mode", "ship-queue.json")


def test_pass_ticket_enters_queue():
    repo = make_repo()
    fx = fixture(repo, {"issues": [issue(1877)], "comments": {"1877": [pass_comment()]},
                        "commits": ["abc1234"]})
    rc, out = run(repo, "peek", fx=fx)
    assert rc == 0
    assert "pending=1" in out and "#1877" in out and "verified=yes" in out


def test_fail_verdict_not_queued():
    repo = make_repo()
    c = {"id": 2, "body": "verdict=fail\nac=1/2\n证据：x"}
    fx = fixture(repo, {"issues": [issue(1877)], "comments": {"1877": [c]}})
    rc, out = run(repo, "peek", fx=fx)
    assert rc == 0 and "pending=0" in out


def test_ac_mismatch_is_invalid():
    repo = make_repo()
    fx = fixture(repo, {"issues": [issue(1877, body="- [ ] a\n- [ ] b\n- [ ] c")],
                        "comments": {"1877": [pass_comment(ac="2/2")]},
                        "commits": ["abc1234"]})
    rc, out = run(repo, "peek", fx=fx)
    assert rc == 0 and "pending=0" in out and "invalid=1" in out and "ac-mismatch" in out


def test_ac_missing_is_invalid():
    repo = make_repo()
    c = {"id": 1, "body": "verdict=pass\nbranch=feat/x\ncommit=abc1234"}
    fx = fixture(repo, {"issues": [issue(1877)], "comments": {"1877": [c]},
                        "commits": ["abc1234"]})
    rc, out = run(repo, "peek", fx=fx)
    assert rc == 0 and "ac-missing" in out


def test_ac_partial_is_invalid():
    repo = make_repo()
    fx = fixture(repo, {"issues": [issue(1877, body="- [ ] a\n- [ ] b\n- [ ] c")],
                        "comments": {"1877": [pass_comment(ac="2/3")]},
                        "commits": ["abc1234"]})
    rc, out = run(repo, "peek", fx=fx)
    assert rc == 0 and "ac-partial" in out


def test_no_sha_still_queued_but_flagged():
    repo = make_repo()
    c = {"id": 1, "body": "verdict=pass\nac=2/2\nbranch=feat/x"}
    fx = fixture(repo, {"issues": [issue(1877)], "comments": {"1877": [c]}})
    rc, out = run(repo, "peek", fx=fx)
    assert rc == 0 and "pending=1" in out and "verified=no-sha" in out


def test_urgent_sorts_first():
    repo = make_repo()
    fx = fixture(repo, {
        "issues": [issue(1800), issue(1900, body="加急·待发货\n- [ ] a\n- [ ] b")],
        "comments": {"1800": [pass_comment(cid=1)],
                     "1900": [pass_comment(cid=2)]},
        "commits": ["abc1234"]})
    rc, out = run(repo, "peek", fx=fx)
    assert rc == 0
    assert out.index("#1900") < out.index("#1800")
    assert "urgent=1" in out


def test_hotfix_from_ace():
    repo = make_repo()
    ace = "H-20261027-1 修空指针 verdict=pass commit=aaa1111\nH-20261027-2 未过 verdict=fail"
    fx = fixture(repo, {"issues": [], "comments": {}, "commits": ["aaa1111"],
                        "ace_text": ace})
    rc, out = run(repo, "peek", fx=fx)
    assert rc == 0 and "hotfix=1" in out and "H-20261027-1" in out and "H-20261027-2" not in out


def test_sync_persists_and_is_idempotent():
    repo = make_repo()
    fx = fixture(repo, {"issues": [issue(1877)], "comments": {"1877": [pass_comment()]},
                        "commits": ["abc1234"]})
    assert run(repo, "sync", fx=fx)[0] == 0
    first = json.load(open(state_path(repo), encoding="utf-8"))
    assert first["pending"]["1877"]["sha"] == "abc1234"
    assert first["cursor_updated_at"] == "2026-10-27T08:00:00Z"
    assert run(repo, "sync", fx=fx)[0] == 0
    second = json.load(open(state_path(repo), encoding="utf-8"))
    assert list(second["pending"]) == ["1877"], "重复 sync 不得重复入队"


def test_absent_verdict_in_incremental_window_keeps_entry():
    """增量窗口里没有判词 ≠ 判词失效，旧条目必须保留（防漏票）。"""
    repo = make_repo()
    fx1 = fixture(repo, {"issues": [issue(1877)], "comments": {"1877": [pass_comment()]},
                         "commits": ["abc1234"]})
    assert run(repo, "sync", fx=fx1)[0] == 0
    fx2 = fixture(repo, {"issues": [issue(1877, updated="2026-10-27T09:00:00Z")],
                         "comments": {"1877": []}, "commits": ["abc1234"]})
    rc, out = run(repo, "peek", fx=fx2)
    assert rc == 0 and "pending=1" in out


def test_done_removes_and_is_idempotent():
    repo = make_repo()
    fx = fixture(repo, {"issues": [issue(1877)], "comments": {"1877": [pass_comment()]},
                        "commits": ["abc1234"]})
    assert run(repo, "sync", fx=fx)[0] == 0
    rc, out = run(repo, "done", "--ticket", "1877")
    assert rc == 0 and "removed=1" in out
    assert json.load(open(state_path(repo), encoding="utf-8"))["pending"] == {}
    rc, out = run(repo, "done", "--ticket", "1877")
    assert rc == 0 and "removed=0" in out


def test_hold_marks_then_new_verdict_clears():
    repo = make_repo()
    fx = fixture(repo, {"issues": [issue(1877)], "comments": {"1877": [pass_comment(cid=1)]},
                        "commits": ["abc1234"]})
    assert run(repo, "sync", fx=fx)[0] == 0
    rc, out = run(repo, "hold", "--ticket", "1877", "--reason", "退回：冲突")
    assert rc == 0 and "HOLD" in out
    rc, out = run(repo, "peek", fx=fx)
    assert "held=退回：冲突" in out
    fx2 = fixture(repo, {"issues": [issue(1877, updated="2026-10-27T09:00:00Z")],
                         "comments": {"1877": [pass_comment(cid=99)]},
                         "commits": ["abc1234"]})
    assert run(repo, "sync", fx=fx2)[0] == 0
    rc, out = run(repo, "peek", fx=fx2)
    assert "held=" not in out and "pending=1" in out


def test_hold_requires_pending():
    repo = make_repo()
    rc, out = run(repo, "hold", "--ticket", "9999", "--reason", "x")
    assert rc == 1 and "NOT_PENDING" in out


def test_shipped_ticket_retired():
    repo = make_repo()
    fx1 = fixture(repo, {"issues": [issue(1877)], "comments": {"1877": [pass_comment()]},
                         "commits": ["abc1234"]})
    assert run(repo, "sync", fx=fx1)[0] == 0
    fx2 = fixture(repo, {"issues": [], "comments": {}, "commits": ["abc1234"],
                         "shipped": ["abc1234"]})
    rc, out = run(repo, "sync", fx=fx2)
    assert rc == 0 and "pending=0" in out and "retired=1" in out
    assert json.load(open(state_path(repo), encoding="utf-8"))["pending"] == {}


def test_closed_ticket_retired():
    repo = make_repo()
    fx1 = fixture(repo, {"issues": [issue(1877)], "comments": {"1877": [pass_comment()]},
                         "commits": ["abc1234"]})
    assert run(repo, "sync", fx=fx1)[0] == 0
    fx2 = fixture(repo, {"issues": [], "comments": {}, "commits": ["abc1234"],
                         "closed": [1877]})
    rc, out = run(repo, "sync", fx=fx2)
    assert rc == 0 and "pending=0" in out and "retired=1" in out


def test_json_output_shape():
    repo = make_repo()
    fx = fixture(repo, {"issues": [issue(1877)], "comments": {"1877": [pass_comment()]},
                        "commits": ["abc1234"]})
    rc, out = run(repo, "peek", fx=fx, as_json=True)
    assert rc == 0
    data = json.loads(out)
    assert set(data) == {"pending", "invalid", "hotfix", "retired", "cursor"}
    assert data["pending"]["1877"]["ac"] == "2/2"


def test_missing_instance_reports_three_boxes():
    repo = make_repo(with_instance=False)
    rc, out = run(repo, "peek")
    assert rc == 2 and "缺什么" in out and "谁需要" in out and "怎么补" in out


def test_probe_failure_never_reports_zero_pending():
    """没有 git 远端/gh 时必须 rc=3 且不得输出 pending=0。"""
    repo = make_repo()  # 有实例，但不是 git 仓
    rc, out = run(repo, "peek")
    assert rc == 3
    assert "ERROR" in out
    assert "pending=0" not in out
