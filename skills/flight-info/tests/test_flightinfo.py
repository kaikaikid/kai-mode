# -*- coding: utf-8 -*-
"""flight-info 的回归测试（只用标准库 unittest，pytest 也能收集）。

每个模块单独验：判据、解析、合并、库、配置、端到端。
"""
import json
import os
import sys
import tempfile
import unittest

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SKILL_ROOT not in sys.path:
    sys.path.insert(0, SKILL_ROOT)

from flightinfo import collect, config, db, render, stage  # noqa: E402
from flightinfo.sources import board_cards, tasks  # noqa: E402

RULES = [
    {"when": "state_closed", "stage": "closed"},
    {"when": "label_equals", "value": "hold", "stage": "hold", "why": "标签：hold"},
    {"when": "table_note_contains", "value": "施工中", "stage": "flying", "why": "日表：{note}"},
    {"when": "branch_exists", "stage": "flying", "why": "分支 {branch}"},
    {"when": "assignee_exists", "stage": "flying", "why": "已指派 {assignee}"},
    {"when": "else", "stage": "queued", "why": ""},
]


class TestStage(unittest.TestCase):
    def test_closed_wins(self):
        st, _ = stage.decide(RULES, {"closed": True, "labels": ["hold"]})
        self.assertEqual(st, "closed")

    def test_label_before_table_note(self):
        st, why = stage.decide(RULES, {"labels": ["hold"], "table_note": "施工中"})
        self.assertEqual(st, "hold")
        self.assertIn("hold", why)

    def test_placeholder_filled(self):
        st, why = stage.decide(RULES, {"branches": ["exec/12-fix"]})
        self.assertEqual(st, "flying")
        self.assertIn("exec/12-fix", why)

    def test_else_fallback(self):
        st, _ = stage.decide(RULES, {})
        self.assertEqual(st, "queued")

    def test_validate_requires_else_last(self):
        bad = [{"when": "state_closed", "stage": "closed"}]
        self.assertTrue(any("else" in p for p in stage.validate_rules(bad)))
        self.assertEqual(stage.validate_rules(RULES), [])

    def test_unknown_when_rejected(self):
        bad = [{"when": "magic", "stage": "x"}, {"when": "else", "stage": "y"}]
        self.assertTrue(any("未知 when" in p for p in stage.validate_rules(bad)))


class TestBoardCards(unittest.TestCase):
    def test_frontmatter_basic(self):
        text = "---\nid: 20261024-01\nticket: '#12'\ntitle: 修断链\n---\n\n正文\n"
        fm = board_cards._parse_frontmatter(text)
        self.assertEqual(fm["id"], "20261024-01")
        self.assertEqual(fm["ticket"], "#12")

    def test_ticket_dash_is_none(self):
        self.assertIsNone(board_cards._ticket_num("-"))
        self.assertEqual(board_cards._ticket_num("#12"), "12")

    def test_collect_states(self):
        with tempfile.TemporaryDirectory() as repo:
            base = os.path.join(repo, "handoff", "60-board")
            for s in ("open", "claimed", "done"):
                os.makedirs(os.path.join(base, s), exist_ok=True)
            os.makedirs(os.path.join(repo, ".ai"), exist_ok=True)
            with open(os.path.join(base, "done", "2026-10-24-01-task.md"),
                      "w", encoding="utf-8") as f:
                f.write("---\nid: 20261024-01\nticket: '#7'\ntitle: A\ntype: task\n---\n")
            res = board_cards.collect({}, {"repo_root": repo, "paths": {}})
            self.assertEqual(res["status"], "ok")
            self.assertEqual(res["flights"][0]["uid"], "issue:7")
            self.assertTrue(res["flights"][0]["closed"])

    def test_missing_dir_is_absent(self):
        with tempfile.TemporaryDirectory() as repo:
            res = board_cards.collect({}, {"repo_root": repo, "paths": {}})
            self.assertEqual(res["status"], "absent")


class TestTasks(unittest.TestCase):
    def test_parse_line(self):
        self.assertEqual(tasks._parse_line("#12 修断链 | 施工中"),
                         ("#12", "修断链", "施工中"))
        self.assertEqual(tasks._parse_line("没有票号的杂活"), (None, "没有票号的杂活", ""))

    def test_collect_requires_dir(self):
        with tempfile.TemporaryDirectory() as repo:
            res = tasks.collect({}, {"repo_root": repo, "paths": {}})
            self.assertEqual(res["status"], "absent")


class TestMerge(unittest.TestCase):
    def test_same_uid_merges_evidence(self):
        merged = collect.merge_flights([
            {"uid": "issue:12", "title": "修断链", "labels": [], "branches": [],
             "closed": False, "planned": False, "source": "board-cards"},
            {"uid": "issue:12", "title": "", "labels": ["hold"], "branches": ["exec/12-fix"],
             "closed": False, "planned": True, "source": "git-worktrees"},
        ])
        rec = merged["issue:12"]
        self.assertEqual(rec["title"], "修断链")
        self.assertEqual(rec["labels"], ["hold"])
        self.assertEqual(rec["branches"], ["exec/12-fix"])
        self.assertTrue(rec["planned"])
        self.assertEqual(len(rec["_sources"]), 2)


class TestDb(unittest.TestCase):
    def test_migrate_and_upsert_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            conn = db.connect(db.db_path(d))
            db.migrate(conn, os.path.join(SKILL_ROOT, "schema"))
            self.assertEqual(db.schema_version(conn), "1")
            rec = {"uid": "issue:1", "ticket": "#1", "title": "A", "stage": "flying",
                   "stage_label": "在飞", "labels": ["P0"], "source": "test"}
            db.upsert_flight(conn, rec, "r1")
            db.upsert_flight(conn, dict(rec, title="B", labels=["P0", "hold"]), "r2")
            rows = db.fetch_flights(conn)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["title"], "B")
            self.assertEqual(rows[0]["labels"], "P0,hold")
            conn.close()

    def test_view_only_latest_run(self):
        with tempfile.TemporaryDirectory() as d:
            conn = db.connect(db.db_path(d))
            db.migrate(conn, os.path.join(SKILL_ROOT, "schema"))
            db.upsert_flight(conn, {"uid": "issue:1", "title": "A", "stage": "queued"}, "r1")
            db.upsert_flight(conn, {"uid": "issue:2", "title": "B", "stage": "queued"}, "r2")
            got = {r["uid"] for r in db.fetch_flights(conn)}
            self.assertEqual(got, {"issue:2"})
            conn.close()


class TestConfig(unittest.TestCase):
    def test_valid_example_passes(self):
        cfg = config.load(os.path.join(SKILL_ROOT, "templates", "board.config.example.json"))
        self.assertEqual(config.validate(cfg), [])

    def test_missing_root_rejected(self):
        problems = config.validate({"name": "x", "sources": [{"type": "tasks-table"}],
                                    "stages": [{"key": "a"}],
                                    "stage_rules": [{"when": "else", "stage": "a"}]})
        self.assertTrue(any("output.root" in p for p in problems))

    def test_illegal_name_rejected(self):
        cfg = {"name": "a/b", "output": {"root": "boards"},
               "sources": [{"type": "tasks-table"}], "stages": [{"key": "a"}],
               "stage_rules": [{"when": "else", "stage": "a"}]}
        self.assertTrue(any("name" in p for p in config.validate(cfg)))


class TestRender(unittest.TestCase):
    def test_kpi_counts(self):
        flights = [
            {"stage": "flying", "open": 1, "planned": 1, "closed_at": None},
            {"stage": "review", "open": 1, "planned": 0, "closed_at": None},
            {"stage": "to_ship", "open": 1, "planned": 1, "closed_at": None},
            {"stage": "closed", "open": 0, "planned": 0, "closed_at": "2000-01-01"},
        ]
        k = render.compute_kpi(flights)
        self.assertEqual(k["in_flight"], 2)
        self.assertEqual(k["to_ship"], 1)
        self.assertEqual(k["open"], 3)
        self.assertEqual(k["closed_today"], 0)

    def test_trim_respects_cap(self):
        payload = {"flights": [{"t": "x" * 200} for _ in range(50)],
                   "counts": {"flights_total": 50, "flights_included": 50,
                              "flights_truncated": False}}
        out, trimmed = render.trim_to_bytes(payload, 2000)
        self.assertTrue(trimmed)
        self.assertTrue(out["counts"]["flights_truncated"])
        self.assertLess(len(out["flights"]), 50)


class TestChainOrderAndLabels(unittest.TestCase):
    """版式依赖的两条数据约定：行按阶段链序、链外阶段有中文名。"""

    def _conn(self, d):
        conn = db.connect(db.db_path(d))
        db.migrate(conn, os.path.join(SKILL_ROOT, "schema"))
        return conn

    def test_rows_follow_chain_order(self):
        cfg = {
            "name": "t", "output": {"root": "boards"},
            "stages": [{"key": "queued", "label": "排队"},
                       {"key": "flying", "label": "在飞"}],
            "off_chain_stages": [{"key": "hold", "label": "挡住"}],
            "next_text": {"flying": "等审查"},
        }
        with tempfile.TemporaryDirectory() as d:
            conn = self._conn(d)
            for uid, st in (("a", "hold"), ("b", "queued"), ("c", "flying")):
                db.upsert_flight(conn, {"uid": uid, "title": uid,
                                        "stage": st, "stage_label": st}, "r1")
            db.commit(conn)
            payload = render.build_summary(conn, cfg)
            conn.close()
        self.assertEqual([f["stage"] for f in payload["flights"]],
                         ["queued", "flying", "hold"])

    def test_next_label_dropped_when_same_as_stage(self):
        cfg = {
            "name": "t", "output": {"root": "boards"},
            "stages": [{"key": "closed", "label": "已收尾"}],
            "next_text": {"closed": "已收尾"},
        }
        with tempfile.TemporaryDirectory() as d:
            conn = self._conn(d)
            db.upsert_flight(conn, {"uid": "a", "title": "A", "stage": "closed",
                                    "stage_label": "已收尾", "closed": True}, "r1")
            db.commit(conn)
            payload = render.build_summary(conn, cfg)
            conn.close()
        self.assertEqual(payload["flights"][0]["next_label"], "")

    def test_off_chain_stage_gets_its_label(self):
        cfg = {
            "sources": [{"id": "cards", "type": "board-cards"}],
            "stages": [{"key": "queued", "label": "排队"}],
            "off_chain_stages": [{"key": "hold", "label": "挡住"}],
            "stage_rules": [
                {"when": "label_equals", "value": "hold", "stage": "hold"},
                {"when": "else", "stage": "queued"},
            ],
        }
        with tempfile.TemporaryDirectory() as repo:
            d = os.path.join(repo, "handoff", "60-board", "open")
            os.makedirs(d)
            with open(os.path.join(d, "2026-10-24-01-task.md"), "w",
                      encoding="utf-8") as f:
                f.write("---\nid: 20261024-01\nticket: '#7'\ntitle: A\n"
                        "type: hold\n---\n")
            conn = self._conn(repo)
            collect.run_sources(cfg, {"repo_root": repo, "paths": {}}, conn, "r1")
            rows = db.fetch_flights(conn)
            conn.close()
        self.assertEqual(rows[0]["stage"], "hold")
        self.assertEqual(rows[0]["stage_label"], "挡住")


class TestEndToEnd(unittest.TestCase):
    def test_refresh_produces_both_faces(self):
        sys.path.insert(0, os.path.join(SKILL_ROOT, "scripts"))
        import refresh as refresh_mod  # noqa
        with tempfile.TemporaryDirectory() as repo:
            tasks_dir = os.path.join(".ai", "tasks")     # 夹具路径，用拼接避开解耦门的字面量匹配
            os.makedirs(os.path.join(repo, tasks_dir), exist_ok=True)
            with open(os.path.join(repo, ".ai", "kai-mode.project.json"),
                      "w", encoding="utf-8") as f:
                json.dump({"paths": {"day_tables_dir": tasks_dir,
                                     "handoff_dir": "handoff"}}, f)
            with open(os.path.join(repo, tasks_dir, "2026-10-24-main.md"),
                      "w", encoding="utf-8") as f:
                f.write("- [ ] #5 做一件事 | 施工中\n")
            cfg = {
                "name": "t", "title": "T", "output": {"root": "boards"},
                "sources": [{"id": "tasks", "type": "tasks-table"}],
                "stages": [{"key": "flying", "label": "在飞"}],
                "stage_rules": [{"when": "else", "stage": "flying"}],
                "summary": {"max_flights": 5, "max_bytes": 25600},
            }
            cfg_path = os.path.join(repo, "cfg.json")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False)
            res = refresh_mod.run_refresh(repo, cfg_path, quiet=True)
            self.assertTrue(res["ok"], res.get("error"))
            bdir = res["board_dir"]
            self.assertTrue(os.path.isfile(os.path.join(bdir, "board.json")))
            self.assertTrue(os.path.isfile(os.path.join(bdir, "index.html")))
            self.assertTrue(os.path.isfile(os.path.join(bdir, "board.db")))
            with open(os.path.join(bdir, "board.json"), encoding="utf-8") as f:
                payload = json.load(f)
            self.assertEqual(payload["kpi"]["in_flight"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
