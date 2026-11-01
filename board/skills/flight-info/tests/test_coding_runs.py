# -*- coding: utf-8 -*-
"""coding-runs 源的回归测试（标准库 unittest，pytest 也能收集）。"""
import json
import os
import sys
import tempfile
import unittest

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SKILL_ROOT not in sys.path:
    sys.path.insert(0, SKILL_ROOT)

from flightinfo import stage  # noqa: E402
from flightinfo.sources import coding_runs  # noqa: E402

V2_RULES = [
    {"when": "state_closed", "stage": "closed"},
    {"when": "label_equals", "value": "v2:closed", "stage": "closed"},
    {"when": "label_equals", "value": "v2:hold", "stage": "hold"},
    {"when": "label_equals", "value": "v2:to_ship", "stage": "to_ship"},
    {"when": "label_equals", "value": "v2:review", "stage": "review"},
    {"when": "label_equals", "value": "v2:flying", "stage": "flying"},
    {"when": "label_equals", "value": "v2:queued", "stage": "queued"},
    {"when": "no_issue", "stage": "unresolved"},
    {"when": "branch_exists", "stage": "flying"},
    {"when": "else", "stage": "queued"},
]


def write_run(root, run_id, phase, **fields):
    d = os.path.join(root, ".coding", "runs", run_id)
    os.makedirs(d, exist_ok=True)
    state = {"run_id": run_id, "phase": phase, "updated_at": "2026-11-01T10:00:00"}
    state.update(fields)
    with open(os.path.join(d, "state.json"), "w", encoding="utf-8") as f:
        json.dump(state, f)


class TestCodingRuns(unittest.TestCase):
    def test_absent_when_no_coding_dir(self):
        with tempfile.TemporaryDirectory() as repo:
            res = coding_runs.collect({}, {"repo_root": repo})
            self.assertEqual(res["status"], "absent")
            self.assertEqual(res["flights"], [])

    def test_maps_every_phase(self):
        with tempfile.TemporaryDirectory() as repo:
            for i, phase in enumerate(("queued", "planning", "design", "delegating",
                                       "reviewing", "closing", "done", "blocked",
                                       "cancelled", "failed"), 1):
                write_run(repo, f"r-{i}", phase, issue=f"#10{i}")
            res = coding_runs.collect({}, {"repo_root": repo})
            self.assertEqual(res["status"], "ok")
            got = {f["phase"]: f for f in res["flights"]}
            self.assertEqual(got["queued"]["labels"][0], "v2:queued")
            self.assertEqual(got["planning"]["labels"][0], "v2:flying")
            self.assertEqual(got["design"]["labels"][0], "v2:flying")
            self.assertEqual(got["delegating"]["labels"][0], "v2:flying")
            self.assertEqual(got["reviewing"]["labels"][0], "v2:review")
            self.assertEqual(got["closing"]["labels"][0], "v2:to_ship")
            self.assertEqual(got["blocked"]["labels"][0], "v2:hold")
            self.assertEqual(got["done"]["labels"][0], "v2:closed")
            self.assertTrue(got["done"]["closed"])
            self.assertTrue(got["cancelled"]["closed"])
            self.assertTrue(got["failed"]["closed"])

    def test_stage_rules_precede_heuristics(self):
        """V2 行带分支/无 url 时也不能被 no_issue 判成残留分支。"""
        for phase, expected in (("delegating", "flying"), ("blocked", "hold"),
                                ("closing", "to_ship"), ("reviewing", "review")):
            rec = {"uid": "run:x", "labels": [f"v2:{coding_runs._phase_stage(phase)}"],
                   "branches": ["travel/r-x"], "url": "", "closed": False}
            st, _ = stage.decide(V2_RULES, rec)
            self.assertEqual(st, expected, phase)

    def test_issue_number_and_url(self):
        with tempfile.TemporaryDirectory() as repo:
            write_run(repo, "r-a", "planning",
                      issue="https://github.com/acme/widgets/issues/42 加导出")
            res = coding_runs.collect({}, {"repo_root": repo})
            f = res["flights"][0]
            self.assertEqual(f["ticket"], "#42")
            self.assertEqual(f["url"], "https://github.com/acme/widgets/issues/42")
            self.assertIn("加导出", f["title"])

    def test_no_branches_or_assignee(self):
        with tempfile.TemporaryDirectory() as repo:
            write_run(repo, "r-a", "delegating", branch="travel/r-a", fleet_id="host-1")
            f = coding_runs.collect({}, {"repo_root": repo})["flights"][0]
            self.assertEqual(f["branches"], [])
            self.assertEqual(f["assignee"], "")
            self.assertEqual(f["owner"], "host-1")

    def test_task_counts_and_next_action(self):
        with tempfile.TemporaryDirectory() as repo:
            write_run(repo, "r-a", "delegating",
                      tasks=[{"id": "t1", "status": "accepted"},
                             {"id": "t2", "status": "running"},
                             {"id": "t3", "status": "blocked"}],
                      resume={"next_action": "review t2"},
                      gates={"g0": "approved", "g1": "skipped", "g2": "pending"})
            f = coding_runs.collect({}, {"repo_root": repo})["flights"][0]
            self.assertEqual((f["tasks_total"], f["tasks_done"],
                              f["tasks_running"], f["tasks_blocked"]), (3, 1, 1, 1))
            self.assertEqual(f["next_action"], "review t2")
            self.assertEqual(f["gates"]["g2"], "pending")

    def test_bad_state_degrades_not_crashes(self):
        with tempfile.TemporaryDirectory() as repo:
            write_run(repo, "r-good", "planning")
            bad = os.path.join(repo, ".coding", "runs", "r-bad")
            os.makedirs(bad)
            with open(os.path.join(bad, "state.json"), "w", encoding="utf-8") as f:
                f.write("{not json")
            res = coding_runs.collect({}, {"repo_root": repo})
            self.assertEqual(res["status"], "ok")
            self.assertEqual(len(res["flights"]), 1)
            self.assertIn("1 个读不了", res["detail"])

    def test_all_bad_is_fail(self):
        with tempfile.TemporaryDirectory() as repo:
            bad = os.path.join(repo, ".coding", "runs", "r-bad")
            os.makedirs(bad)
            with open(os.path.join(bad, "state.json"), "w", encoding="utf-8") as f:
                f.write("{not json")
            res = coding_runs.collect({}, {"repo_root": repo})
            self.assertEqual(res["status"], "fail")
            self.assertEqual(res["flights"], [])

    def test_missing_phase_is_skipped(self):
        with tempfile.TemporaryDirectory() as repo:
            d = os.path.join(repo, ".coding", "runs", "r-x")
            os.makedirs(d)
            with open(os.path.join(d, "state.json"), "w", encoding="utf-8") as f:
                json.dump({"run_id": "r-x"}, f)
            res = coding_runs.collect({}, {"repo_root": repo})
            self.assertEqual(res["status"], "fail")
            self.assertEqual(res["flights"], [])

    def test_unknown_phase_is_hold_not_queued(self):
        with tempfile.TemporaryDirectory() as repo:
            write_run(repo, "r-x", "some-new-phase")
            f = coding_runs.collect({}, {"repo_root": repo})["flights"][0]
            self.assertEqual(f["labels"][0], "v2:hold")

    def test_uid_is_run_not_issue(self):
        with tempfile.TemporaryDirectory() as repo:
            write_run(repo, "r-a", "planning", issue="#7")
            write_run(repo, "r-b", "planning", issue="#7")
            res = coding_runs.collect({}, {"repo_root": repo})
            self.assertEqual({f["uid"] for f in res["flights"]}, {"run:r-a", "run:r-b"})


if __name__ == "__main__":
    unittest.main()
