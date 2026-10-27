#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""钩子链路与保留策略的回归网：脏标记、max-age 兜底、无黑窗入口、库修剪。

跑法：pytest board/skills/flight-info/tests
约定：每个用例一个临时 git 仓，不联网（issues 源一律 state=none）。
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
if SKILL_ROOT not in sys.path:
    sys.path.insert(0, SKILL_ROOT)

from flightinfo import db  # noqa: E402

SCRIPTS = os.path.join(SKILL_ROOT, "scripts")


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


def make_repo(hooks_path: str | None = None):
    repo = tempfile.mkdtemp(prefix="fi-hook-test-")
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "t@t")
    git(repo, "config", "user.name", "t")
    if hooks_path:
        git(repo, "config", "core.hooksPath", hooks_path)
    os.makedirs(os.path.join(repo, "tables"), exist_ok=True)
    os.makedirs(os.path.join(repo, ".ai"), exist_ok=True)
    inst = {"schema": 4,
            "paths": {"state_dir": ".git/kai-mode", "day_tables_dir": "tables"},
            "tower_cron": {"interval_min": 60}}
    json.dump(inst, open(os.path.join(repo, ".ai", "kai-mode.project.json"), "w"))
    cfg = {"schema": "flight-info-board/1", "name": "flight", "title": "T",
           "output": {"root": "boards"},
           "sources": [{"id": "issues", "type": "github-issues", "state": "none"}],
           "stages": [{"key": "queued", "label": "排队"},
                      {"key": "closed", "label": "已收尾"}],
           "stage_rules": [{"when": "state_closed", "stage": "closed"},
                           {"when": "else", "stage": "queued"}]}
    cfg_path = os.path.join(repo, "board.config.json")
    json.dump(cfg, open(cfg_path, "w"))
    return repo, cfg_path


def run(script, *args, cwd=None):
    p = subprocess.run([sys.executable, os.path.join(SCRIPTS, script), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=cwd)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


class TestInstallHook(unittest.TestCase):
    def test_hooks_land_in_core_hookspath(self):
        """设了 core.hooksPath 就必须装到那里——旧版硬编码 .git/hooks，钩子永不触发。"""
        repo, _ = make_repo(hooks_path=".githooks")
        rc, out = run("install_hook.py", "--repo-root", repo, "--apply")
        self.assertEqual(rc, 0, out)
        for name in ("post-commit", "post-merge", "post-checkout"):
            self.assertTrue(os.path.isfile(os.path.join(repo, ".githooks", name)), name)
            self.assertFalse(os.path.isfile(os.path.join(repo, ".git", "hooks", name)), name)

    def test_three_hooks_installed(self):
        repo, _ = make_repo()
        rc, out = run("install_hook.py", "--repo-root", repo, "--apply")
        self.assertEqual(rc, 0, out)
        for name in ("post-commit", "post-merge", "post-checkout"):
            self.assertTrue(os.path.isfile(os.path.join(repo, ".git", "hooks", name)), name)

    def test_foreign_hook_not_overwritten(self):
        repo, _ = make_repo()
        p = os.path.join(repo, ".git", "hooks", "post-commit")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write("#!/bin/sh\necho mine\n")
        rc, out = run("install_hook.py", "--repo-root", repo, "--apply")
        self.assertEqual(rc, 3)
        self.assertIn("拒绝覆盖", out)
        self.assertIn("echo mine", open(p, encoding="utf-8").read())


class TestDirtyMarker(unittest.TestCase):
    def test_commit_writes_marker_and_commit_not_blocked(self):
        repo, _ = make_repo()
        run("install_hook.py", "--repo-root", repo, "--apply")
        open(os.path.join(repo, "a.txt"), "w").write("x")
        git(repo, "add", "a.txt")
        r = git(repo, "commit", "-m", "t")
        self.assertEqual(r.returncode, 0, r.stderr)
        mark = os.path.join(repo, ".git", "flight-info-dirty")
        self.assertTrue(os.path.isfile(mark))
        self.assertTrue(open(mark, encoding="utf-8").read().strip())

    def test_no_dirty_skips_without_touching_board(self):
        repo, cfg = make_repo()
        rc, out = run("refresh_if_dirty.py", "--repo-root", repo, "--config", cfg)
        self.assertEqual(rc, 0)
        self.assertIn("无脏", out)
        self.assertFalse(os.path.isdir(os.path.join(repo, "boards", "flight")))

    def test_max_age_forces_refresh_when_board_is_old(self):
        """GitHub 侧更新不产生本地提交：板龄超限必须刷，不能等钩子。"""
        repo, cfg = make_repo()
        rc, out = run("refresh.py", "--repo-root", repo, "--config", cfg, "--quiet")
        self.assertEqual(rc, 0, out)
        bj = os.path.join(repo, "boards", "flight", "board.json")
        data = json.load(open(bj, encoding="utf-8"))
        data["generated_at"] = "2020-01-01T00:00:00+00:00"
        json.dump(data, open(bj, "w", encoding="utf-8"))
        rc, out = run("refresh_if_dirty.py", "--repo-root", repo, "--config", cfg,
                      "--max-age", "30")
        self.assertEqual(rc, 0, out)
        fresh = json.load(open(bj, encoding="utf-8"))
        self.assertNotEqual(fresh["generated_at"], "2020-01-01T00:00:00+00:00")


class TestNoBlackWindow(unittest.TestCase):
    def test_task_entry_uses_wscript_only(self):
        repo, cfg = make_repo()
        rc, out = run("install_auto.py", "--repo-root", repo, "--config", cfg, "--apply")
        self.assertEqual(rc, 0, out)
        bat = os.path.join(repo, "boards", "flight", "refresh_task.bat")
        body = open(bat, encoding="utf-8").read()
        self.assertIn("wscript", body)
        self.assertNotIn("start \"\" /min python", body)
        tick = os.path.join(repo, "boards", "flight", "refresh_tick.vbs")
        self.assertTrue(os.path.isfile(tick))
        tick_body = open(tick, encoding="utf-8").read()
        self.assertIn("sh.Run cmd, 0, True", tick_body)     # 0 = 隐藏窗口
        self.assertIn("--max-age", tick_body)

    def test_default_interval_is_30(self):
        repo, cfg = make_repo()
        rc, out = run("install_auto.py", "--repo-root", repo, "--config", cfg)
        self.assertIn("30", out)


class TestRuntimeRetention(unittest.TestCase):
    def test_runtime_keeps_only_recent_runs(self):
        d = tempfile.mkdtemp(prefix="fi-ret-")
        conn = db.connect(db.db_path(d))
        db.migrate(conn, os.path.join(SKILL_ROOT, "schema"))
        for i in range(db.RUNTIME_KEEP + 5):
            db.replace_runtime(conn, f"r{i:04d}", {"queue": {"pending": i}})
        db.commit(conn)
        n = conn.execute("SELECT COUNT(*) AS n FROM runtime_state").fetchone()["n"]
        self.assertEqual(n, db.RUNTIME_KEEP)
        latest = db.fetch_runtime(conn)
        self.assertEqual(latest["queue"]["pending"], db.RUNTIME_KEEP + 4)
        conn.close()


class TestRuntimeSources(unittest.TestCase):
    def test_queue_and_token_sources(self):
        from flightinfo.sources import tower_state
        repo, _ = make_repo()
        state = os.path.join(repo, ".git", "kai-mode")
        os.makedirs(state, exist_ok=True)
        json.dump({"cursor_updated_at": "2026-10-27T08:00:00Z",
                   "pending": {"1877": {"sha": "abc1234", "ac": "5/5",
                                        "branch": "feat/x", "urgent": True}}},
                  open(os.path.join(state, "ship-queue.json"), "w"))
        ctx = {"repo_root": repo, "paths": {"state_dir": ".git/kai-mode"}}
        res = tower_state.collect({}, ctx)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["queue"]["pending"], 1)
        self.assertTrue(res["queue"]["rows"][0]["urgent"])

        tok = tower_state.collect_token({}, ctx)
        self.assertEqual(tok["tower"]["state"], "free")

    def test_missing_state_dir_is_skipped_not_faked(self):
        from flightinfo.sources import tower_state
        res = tower_state.collect({}, {"repo_root": "/nope", "paths": {}})
        self.assertEqual(res["status"], "skipped")
        self.assertIn("state_dir", res["detail"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
