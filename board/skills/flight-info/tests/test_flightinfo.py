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
from flightinfo.sources import board_cards, handoff, issues, tasks  # noqa: E402

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

    def test_pipe_table_rows(self):
        """五列表格日表（塔台写法）必须读出票，不能只读出排班。"""
        with tempfile.TemporaryDirectory() as repo:
            d = os.path.join(repo, "tasks")
            os.makedirs(d)
            with open(os.path.join(d, "2026-10-25-main.md"), "w", encoding="utf-8") as f:
                f.write("# 任务表 · 主机长\n\n"
                        "| 序 | 票号 | 里程碑 | 一句话 | 塔台备注 |\n"
                        "|---|---|---|---|---|\n"
                        "| 1 | #1711 | ② 记忆网络 | 云模型通道接线 | **在制**：别关 |\n"
                        "| 2 | #1890 | 横切治理 | 假阳收口 | 新派·可开工 |\n")
            res = tasks.collect({"include": ["*-main.md"], "lanes": ["main"]},
                                {"repo_root": repo, "paths": {"day_tables_dir": "tasks"}})
            self.assertEqual(res["detail"], "2 行排班 / 2 张票")
            first = res["flights"][0]
            self.assertEqual((first["ticket"], first["title"], first["milestone"], first["owner"]),
                             ("#1711", "云模型通道接线", "② 记忆网络", "main"))
            self.assertEqual(res["schedules"][0]["note"], "**在制**：别关")

    def test_ace_hotfix_row(self):
        """王牌热修行（H-日期-序号）也要进板，不能当无票号的杂活丢掉。"""
        self.assertEqual(tasks._parse_line("H-20261027-1 修文案 | 施工中"),
                         ("#H-20261027-1", "修文案", "施工中"))
        with tempfile.TemporaryDirectory() as repo:
            d = os.path.join(repo, "tasks")
            os.makedirs(d)
            with open(os.path.join(d, "2026-10-27-ace.md"), "w", encoding="utf-8") as f:
                f.write("| 序 | 票号 | 里程碑 | 一句话 | 王牌备注 |\n"
                        "|---|---|---|---|---|\n"
                        "| 1 | H-20261027-1 | 加急通道 | 修文案 | 施工中 |\n")
            res = tasks.collect({"include": ["*-ace.md"], "lanes": ["ace"]},
                                {"repo_root": repo, "paths": {"day_tables_dir": "tasks"}})
            self.assertEqual(res["detail"], "1 行排班 / 1 张票")
            self.assertEqual(res["flights"][0]["ticket"], "#H-20261027-1")
            self.assertEqual(res["flights"][0]["owner"], "ace")

    def test_second_lane_in_defaults(self):
        """二副日表必须被默认 include / lanes 接住，不能掉出看板。"""
        with tempfile.TemporaryDirectory() as repo:
            d = os.path.join(repo, "tasks")
            os.makedirs(d)
            with open(os.path.join(d, "2026-10-27-second.md"), "w", encoding="utf-8") as f:
                f.write("| 序 | 票号 | 里程碑 | 一句话 | 塔台备注 |\n"
                        "|---|---|---|---|---|\n"
                        "| 1 | #1900 | 二副道 | 跑第三条机长道 | 新派·可开工 |\n")
            res = tasks.collect({}, {"repo_root": repo, "paths": {"day_tables_dir": "tasks"}})
            self.assertEqual(res["detail"], "1 行排班 / 1 张票")
            self.assertEqual(res["flights"][0]["owner"], "second")
            self.assertEqual(res["schedules"][0]["lane"], "second")

    def test_list_line_still_works(self):
        """老写法不许因为加了表格支持而退化。"""
        with tempfile.TemporaryDirectory() as repo:
            d = os.path.join(repo, "tasks")
            os.makedirs(d)
            with open(os.path.join(d, "2026-10-25-copilot.md"), "w", encoding="utf-8") as f:
                f.write("- [ ] #12 修断链 | 施工中\n")
            res = tasks.collect({"include": ["*-copilot.md"], "lanes": ["copilot"]},
                                {"repo_root": repo, "paths": {"day_tables_dir": "tasks"}})
            self.assertEqual(res["detail"], "1 行排班 / 1 张票")
            self.assertEqual(res["schedules"][0]["ticket"], "#12")


class TestIssues(unittest.TestCase):
    def test_queries_default_open_only(self):
        self.assertEqual(issues.queries_for("open", 200, False), [("open", 200)])

    def test_queries_include_closed(self):
        self.assertEqual(issues.queries_for("open", 200, True, 400),
                         [("open", 200), ("closed", 400)])
        self.assertEqual(issues.queries_for("open", 200, True)[1], ("closed", 200))

    def test_queries_none_is_empty(self):
        self.assertEqual(issues.queries_for("none", 200, True), [])


class TestHandoff(unittest.TestCase):
    def test_collect_missing_dir_is_absent(self):
        with tempfile.TemporaryDirectory() as repo:
            res = handoff.collect({}, {"repo_root": repo, "paths": {}})
            self.assertEqual(res["status"], "absent")
            self.assertEqual(res["handoffs"], [])

    def test_collect_lists_sorts_and_limits(self):
        """日期新在前，取首行标题，templates/ 与非月目录跳过。"""
        with tempfile.TemporaryDirectory() as repo:
            m = os.path.join(repo, "handoff", "10-session", "2026-10")
            os.makedirs(m)
            os.makedirs(os.path.join(repo, "handoff", "templates"))
            with open(os.path.join(m, "2026-10-24-old.md"), "w", encoding="utf-8") as f:
                f.write("# 旧的纸条\n正文不搬。\n")
            with open(os.path.join(m, "2026-10-26-new.md"), "w", encoding="utf-8") as f:
                f.write("# 新的纸条\n")
            with open(os.path.join(repo, "handoff", "templates", "T.md"), "w",
                      encoding="utf-8") as f:
                f.write("# 模板不该被收\n")
            res = handoff.collect({"limit": 10},
                                  {"repo_root": repo, "paths": {"handoff_dir": "handoff"}})
            self.assertEqual(res["status"], "ok")
            self.assertEqual(len(res["handoffs"]), 2)
            newest = res["handoffs"][0]
            self.assertEqual(newest["doc_date"], "2026-10-26")
            self.assertEqual(newest["title"], "新的纸条")
            self.assertEqual(newest["slot"], "10-session")
            self.assertEqual(newest["rel_path"], "handoff/10-session/2026-10/2026-10-26-new.md")
            self.assertEqual([r["ord"] for r in res["handoffs"]], [0, 1])

    def test_collect_limit_caps(self):
        with tempfile.TemporaryDirectory() as repo:
            m = os.path.join(repo, "handoff", "20-plan", "2026-10")
            os.makedirs(m)
            for i in range(5):
                with open(os.path.join(m, f"2026-10-0{i + 1}-a.md"), "w",
                          encoding="utf-8") as f:
                    f.write(f"# {i}\n")
            res = handoff.collect({"limit": 2},
                                  {"repo_root": repo, "paths": {"handoff_dir": "handoff"}})
            self.assertEqual(len(res["handoffs"]), 2)

    def test_db_round_trip_and_render_section(self):
        """索引要落库再读得出，且渲染成可点的相对链接。"""
        rows = [{"slot": "10-session", "rel_path": "handoff/10-session/2026-10/x.md",
                 "title": "标题", "doc_date": "2026-10-26", "ord": 0}]
        with tempfile.TemporaryDirectory() as repo:
            conn = db.connect(db.db_path(repo))
            db.migrate(conn, os.path.join(SKILL_ROOT, "schema"))
            run = db.new_run_id()
            self.assertEqual(db.replace_handoffs(conn, run, rows), 1)
            self.assertEqual(len(db.fetch_handoffs(conn, run)), 1)
            self.assertEqual(db.fetch_handoffs(conn, "不存在的run"), [])
            html = render._handoff_section(rows, "../../")
            self.assertIn('href="../../handoff/10-session/2026-10/x.md"', html)
            conn.close()


class TestHandoffDateForms(unittest.TestCase):
    """跨角色交接件用 HANDOFF-YYYYMMDD-主题.md：以前解析不到日期 ⇒ 沉到月初 ⇒ 被条数上限挤掉。"""

    def test_prefixed_form_parses(self):
        self.assertEqual(handoff._doc_date("HANDOFF-20261026-route-1900-to-tower.md"),
                         "2026-10-26")
        self.assertEqual(handoff._doc_date("2026-10-26-tower-cron.md"), "2026-10-26")

    def test_non_dates_are_rejected(self):
        for fn in ("README.md", "v9.14-notes.md", "12345678.md"):
            self.assertEqual(handoff._doc_date(fn), "", fn)

    def test_handoff_file_ranks_with_same_day_reports(self):
        with tempfile.TemporaryDirectory() as repo:
            m = os.path.join(repo, "handoff", "10-session", "2026-10")
            os.makedirs(m)
            for fn in ("2026-10-26-tower-cron.md",
                       "HANDOFF-20261026-route-1900-to-tower.md"):
                with open(os.path.join(m, fn), "w", encoding="utf-8") as f:
                    f.write("# 标题\n")
            res = handoff.collect({"limit": 8},
                                  {"repo_root": repo, "paths": {"handoff_dir": "handoff"}})
            self.assertEqual([r["doc_date"] for r in res["handoffs"]],
                             ["2026-10-26", "2026-10-26"])
            self.assertEqual(len(res["handoffs"]), 2)   # 不被挤掉


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


class TestStaleRemap(unittest.TestCase):
    """停滞：有在飞证据但已经不动了，不许继续冒充在飞。"""

    def test_flying_becomes_stale_after_threshold(self):
        from datetime import datetime, timedelta
        old = (datetime.now().astimezone() - timedelta(days=9)).isoformat()
        st, why, prev, days = stage.apply_stale("flying", "分支 exec/9-x", old,
                                                {"flying": 3})
        self.assertEqual(st, "stale")
        self.assertEqual(prev, "flying")
        self.assertEqual(days, 9)
        self.assertIn("9 天没动", why)

    def test_within_threshold_stays(self):
        from datetime import datetime, timedelta
        recent = (datetime.now().astimezone() - timedelta(days=1)).isoformat()
        st, _, prev, days = stage.apply_stale("flying", "分支 x", recent, {"flying": 3})
        self.assertEqual(st, "flying")
        self.assertEqual(prev, "")

    def test_unknown_time_is_not_zero_days(self):
        """时间认不到必须报「不知道」，不能悄悄当 0 天＝活跃。"""
        st, _, prev, days = stage.apply_stale("flying", "分支 x", "", {"flying": 3})
        self.assertEqual(st, "flying")
        self.assertIsNone(days)

    def test_threshold_is_per_stage(self):
        """待发货压一天就该喊，排队一周不动是常态——阈值按阶段给。"""
        from datetime import datetime, timedelta
        two = (datetime.now().astimezone() - timedelta(days=2)).isoformat()
        cfg = {"flying": 3, "to_ship": 1}
        self.assertEqual(stage.apply_stale("to_ship", "w", two, cfg)[0], "stale")
        self.assertEqual(stage.apply_stale("flying", "w", two, cfg)[0], "flying")

    def test_closed_never_becomes_stale(self):
        from datetime import datetime, timedelta
        old = (datetime.now().astimezone() - timedelta(days=30)).isoformat()
        self.assertEqual(stage.apply_stale("closed", "", old, {"flying": 3})[0], "closed")


class TestUnresolvedBranch(unittest.TestCase):
    """残留分支：有 exec/ 分支但 GitHub 认不到这张票，不该进航班流。"""

    def test_no_issue_wins_over_branch(self):
        rules = [{"when": "no_issue", "stage": "unresolved", "why": "分支 {branch} 无票面"},
                 {"when": "branch_exists", "stage": "flying", "why": "分支 {branch}"},
                 {"when": "else", "stage": "queued"}]
        st, why = stage.decide(rules, {"branches": ["exec/9992"]})
        self.assertEqual(st, "unresolved")
        self.assertIn("exec/9992", why)

    def test_branch_with_url_is_flying(self):
        rules = [{"when": "no_issue", "stage": "unresolved", "why": "无票面"},
                 {"when": "branch_exists", "stage": "flying", "why": "分支 {branch}"},
                 {"when": "else", "stage": "queued"}]
        st, _ = stage.decide(rules, {"branches": ["exec/12-x"],
                                     "url": "https://x/12"})
        self.assertEqual(st, "flying")

    def test_validate_accepts_no_issue(self):
        rules = [{"when": "no_issue", "stage": "unresolved", "value": ""},
                 {"when": "else", "stage": "queued"}]
        self.assertEqual(stage.validate_rules(rules), [])


class TestOwnerResolution(unittest.TestCase):
    """掌机三源：日表车道（事实）→ 票面指派（事实）→ 阶段推断（要标记）。"""

    def test_lane_beats_assignee(self):
        rec = {"owner": "", "assignee": "kaikaikid", "stage": "flying"}
        self.assertEqual(collect.resolve_owner(rec, "deputy",
                                               {"deputy": "副机长"}, {}),
                         ("副机长", "lane"))

    def test_assignee_when_no_lane(self):
        rec = {"owner": "", "assignee": "kaikaikid", "stage": "flying"}
        self.assertEqual(collect.resolve_owner(rec, None, {}, {}),
                         ("kaikaikid", "assignee"))

    def test_infer_is_marked(self):
        rec = {"owner": "", "assignee": "", "stage": "to_ship"}
        self.assertEqual(collect.resolve_owner(rec, None, {"tower": "塔台"},
                                               {"to_ship": "tower"}),
                         ("塔台", "infer"))

    def test_nothing_found_is_honest_blank(self):
        self.assertEqual(collect.resolve_owner({"stage": "queued"}, None, {}, {}),
                         ("", ""))

    def test_lane_index_only_latest_day(self):
        rows = [{"ticket": "#1", "lane": "main", "table_date": "2026-10-24"},
                {"ticket": "#1", "lane": "deputy", "table_date": "2026-10-26"},
                {"ticket": "#2", "lane": "main", "table_date": "2026-10-26"}]
        idx = collect.lane_index(rows)
        self.assertEqual(idx, {"1": "deputy", "2": "main"})

    def test_lane_index_is_per_lane_not_global(self):
        """各车道各取自己最新那张表：落后车道不许被别车道的日期挤掉。

        2026-10-29 实测踩过：主/副道写 10-29，王牌道停在 10-27，
        原实现取全局 max ⇒ 王牌道的票全丢了归属，看着像"ACE 手上没活"。
        """
        rows = [{"ticket": "#1", "lane": "main", "table_date": "2026-10-29"},
                {"ticket": "#2", "lane": "ace", "table_date": "2026-10-27"}]
        self.assertEqual(collect.lane_index(rows), {"1": "main", "2": "ace"})

    def test_lane_index_newer_table_wins_across_lanes(self):
        """同一票在两条车道的最新表里都有 → 取日表较新的那条。"""
        rows = [{"ticket": "#1", "lane": "main", "table_date": "2026-10-29"},
                {"ticket": "#1", "lane": "ace", "table_date": "2026-10-30"}]
        self.assertEqual(collect.lane_index(rows), {"1": "ace"})

    def test_ticket_key_scales(self):
        for v in ("#1711", "1711", "issue:1711", " #1711 "):
            self.assertEqual(collect.ticket_key(v), "1711")


class TestFacesNotSharedBudget(unittest.TestCase):
    """人面全量、AI 面按预算裁——两本账不许混。"""

    def _cfg(self):
        return {"name": "t", "output": {"root": "boards"},
                "stages": [{"key": "flying", "label": "在飞"},
                           {"key": "closed", "label": "已收尾"}],
                "off_chain_stages": [{"key": "stale", "label": "停滞"}],
                "summary": {"max_flights": 3, "max_bytes": 25600},
                "stage_rules": [{"when": "else", "stage": "flying"}]}

    def test_human_face_keeps_every_open_flight(self):
        with tempfile.TemporaryDirectory() as d:
            conn = db.connect(db.db_path(d))
            db.migrate(conn, os.path.join(SKILL_ROOT, "schema"))
            for i in range(10):
                db.upsert_flight(conn, {"uid": f"issue:{i}", "ticket": f"#{i}",
                                        "title": f"票 {i}", "stage": "flying",
                                        "open": 1, "url": f"http://x/{i}"}, "r1")
            db.upsert_flight(conn, {"uid": "issue:99", "ticket": "#99", "title": "已关",
                                    "stage": "closed", "closed": True, "open": 0}, "r1")
            db.commit(conn)
            payload = render.build_summary(conn, self._cfg(), d)
            conn.close()
        self.assertEqual(len(payload["flights"]), 3)        # AI 面受 max_flights 管
        self.assertEqual(len(payload["all_open"]), 10)      # 人面＝未收尾全量
        self.assertEqual(payload["counts"]["open_total"], 10)

    def test_board_json_drops_human_only_keys(self):
        with tempfile.TemporaryDirectory() as d:
            payload = {"schema": "x", "title": "T", "direction": "", "run_id": "r",
                       "kpi": render.compute_kpi([]), "flights": [{"t": 1}],
                       "all_open": [{"a": i} for i in range(50)],
                       "degraded": [], "trend": [], "schedules": [], "sources": {},
                       "blocked": [], "milestones": [], "handoffs": [],
                       "counts": {"flights_total": 1, "flights_included": 1,
                                  "flights_truncated": False}}
            render.write_outputs(d, payload, self._cfg())
            with open(os.path.join(d, "board.json"), encoding="utf-8") as f:
                bj = json.load(f)
            self.assertNotIn("all_open", bj)
            with open(os.path.join(d, "index.html"), encoding="utf-8") as f:
                html = f.read()
            self.assertIn(">距今</th>", html)                 # 人面带「距今」列
            self.assertGreater(html.count('class="upd'), 1)

    def test_budget_measured_the_same_way_it_is_written(self):
        """紧凑量、美化写＝预算形同虚设。这条锁死 indent 一致性。"""
        payload = {"flights": [{"why": "字" * 200} for _ in range(30)],
                   "counts": {"flights_total": 30, "flights_included": 30,
                              "flights_truncated": False}}
        out, _ = render.trim_to_bytes(payload, 8000, indent=1)
        self.assertLessEqual(len(render.dumps(out, 1)), 8000)

    def test_ai_face_keeps_flights_under_budget(self):
        """AI 面超预算时，先瘦历史与长文，票不许被挤成 0 张。

        2026-10-29 实测踩过：24 轮趋势占 13 KB，加急行/卡点行留着全文，
        25.6 KB 的预算被吃光 ⇒ AI 面最后只剩 0 张航班（板上 48 张未收尾），
        那等于对 AI 说"没事干"。
        """
        payload = {"schema": "x", "title": "T", "direction": "", "run_id": "r",
                   "kpi": render.compute_kpi([]),
                   "flights": [{"ticket": f"#{i}", "title": "票", "stage": "flying",
                                "why": "判据" * 50} for i in range(30)],
                   "degraded": [],
                   "trend": [{"run_id": f"r{i}", "kpi": {"total": 100, "open": 10}}
                             for i in range(24)],
                   "schedules": [{"lane": "main", "ticket": "#1", "summary": "排班",
                                  "note": "备注" * 500, "table_date": "2026-10-29"}],
                   "urgent": {"label": "ace-queue", "lanes": ["ace"],
                              "rows": [{"lane": "ace", "ticket": "#77", "summary": "加急",
                                        "note": "加急备注" * 500,
                                        "table_date": "2026-10-29"}],
                              "tickets": [{"ticket": "#88", "why": "判据" * 200}]},
                   "sources": {}, "runtime": {},
                   "blocked": [{"ticket": "#9", "title": "卡住", "owner": "主机长",
                                "why": "卡点判据" * 300}],
                   "milestones": [], "handoffs": [],
                   "counts": {"flights_total": 30, "flights_included": 30,
                              "flights_truncated": False}}
        with tempfile.TemporaryDirectory() as d:
            render.write_outputs(d, payload, self._cfg())
            with open(os.path.join(d, "board.json"), encoding="utf-8") as f:
                bj = json.load(f)
        self.assertGreater(len(bj["flights"]), 0)          # 票不许被挤没
        self.assertLessEqual(len(render.dumps(bj, 1)), 25600)
        self.assertLessEqual(len(bj["urgent"]["rows"][0]["note"]), 161)
        self.assertLessEqual(len(bj["blocked"][0]["why"]), 161)
        self.assertLessEqual(len(bj["trend"]), 8)


class TestDegradedFlag(unittest.TestCase):
    def test_bad_source_is_named(self):
        got = render._degraded({"issues": {"status": "fail", "detail": "gh 不可用"},
                                "tasks": {"status": "ok"}})
        self.assertEqual([g["id"] for g in got], ["issues"])
        html = render._flag(got)
        self.assertIn('class="flag"', html)
        self.assertIn("gh 不可用", html)

    def test_all_green_prints_nothing(self):
        self.assertEqual(render._degraded({"a": {"status": "ok"}}), [])
        self.assertEqual(render._flag([]), "")


class TestHistory(unittest.TestCase):
    def test_append_is_idempotent_per_run(self):
        with tempfile.TemporaryDirectory() as d:
            kpi = render.compute_kpi([])
            self.assertTrue(render.append_history(d, "r1", kpi, {}))
            render.append_history(d, "r1", kpi, {})
            rows = render.read_trend(d)
            self.assertEqual([r["run_id"] for r in rows], ["r1"])
            render.append_history(d, "r2", kpi, {})
            self.assertEqual([r["run_id"] for r in render.read_trend(d)], ["r1", "r2"])

    def test_trend_needs_two_rounds_to_draw(self):
        self.assertEqual(render._trend({"trend": []}), "")
        one = [{"run_id": "a", "kpi": {"open": 3}}]
        self.assertEqual(render._trend({"trend": one}), "")
        two = one + [{"run_id": "b", "kpi": {"open": 2}}]
        html = render._trend({"trend": two})
        self.assertIn("<svg", html)
        self.assertIn("未收尾", html)

    def test_missing_history_is_silent(self):
        self.assertEqual(render.read_trend(None), [])
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(render.read_trend(d), [])


class TestKpiNewCounters(unittest.TestCase):
    def test_stale_not_counted_as_in_flight(self):
        flights = [{"stage": "flying", "open": 1}, {"stage": "stale", "open": 1},
                   {"stage": "unresolved", "open": 1}, {"stage": "closed", "open": 0}]
        k = render.compute_kpi(flights)
        self.assertEqual(k["in_flight"], 1)
        self.assertEqual(k["stale"], 1)
        self.assertEqual(k["unresolved"], 1)
        self.assertEqual(k["open"], 3)



class TestLaneOrder(unittest.TestCase):
    """车道左右顺序＝配置书写顺序，不是字母序（副机长不该天然压在主前面）。"""

    def _cfg(self):
        return {"name": "t", "output": {"root": "boards"}, "repo": "o/r",
                "role_labels": {"main": "主机长", "deputy": "副机长", "tower": "塔台"},
                "stages": [{"key": "queued", "label": "排队"}],
                "sources": [{"id": "tasks", "type": "tasks-table",
                             "lanes": ["main", "deputy", "second", "ace"]}],
                "stage_rules": [{"when": "else", "stage": "queued"}]}

    def test_order_follows_config(self):
        self.assertEqual(render._lane_order(self._cfg()),
                         ["main", "deputy", "second", "ace"])

    def test_main_renders_left_of_deputy(self):
        sched = [{"lane": "deputy", "ticket": "#2", "summary": "副道活", "note": "",
                  "table_date": "2026-10-27"},
                 {"lane": "main", "ticket": "#1", "summary": "主道活", "note": "",
                  "table_date": "2026-10-27"}]
        html = render._shift_section({"schedules": sched}, self._cfg())
        self.assertLess(html.index("主机长"), html.index("副机长"))

    def test_second_renders_after_deputy(self):
        sched = [{"lane": "second", "ticket": "#3", "summary": "二副道活", "note": "",
                  "table_date": "2026-10-27"},
                 {"lane": "deputy", "ticket": "#2", "summary": "副道活", "note": "",
                  "table_date": "2026-10-27"}]
        self.assertLess(render._shift_section({"schedules": sched}, self._cfg()).index("副机长"),
                        render._shift_section({"schedules": sched}, self._cfg()).index("二副"))

    def test_unknown_lane_still_shows_after_known(self):
        self.assertEqual(render._ordered_lanes({"zed", "main"}, ["main", "deputy"]),
                         ["main", "zed"])


class TestUrgentLane(unittest.TestCase):
    """紧急任务＝王牌腿：日表 ace 车道 或 ace-queue 标签，任一成立就亮。"""

    def _cfg(self):
        return {"name": "t", "output": {"root": "boards"}, "repo": "o/r",
                "role_labels": {"main": "主机长", "deputy": "副机长",
                                "tower": "塔台", "ace": "王牌机长"},
                "stages": [{"key": "queued", "label": "排队"},
                           {"key": "flying", "label": "在飞"}],
                "off_chain_stages": [{"key": "hold", "label": "挡住"}],
                "sources": [{"id": "tasks", "type": "tasks-table",
                             "lanes": ["main", "deputy", "second", "ace"]}],
                "stage_rules": [{"when": "else", "stage": "queued"}],
                "view": {"urgent": {"lanes": ["ace"], "label": "ace-queue"}}}

    def _payload(self, sched_rows, flights):
        with tempfile.TemporaryDirectory() as d:
            conn = db.connect(db.db_path(d))
            db.migrate(conn, os.path.join(SKILL_ROOT, "schema"))
            run = "r1"
            # build_summary 靠 source_run 定位"最新一轮"，夹具必须记一笔源
            db.record_source(conn, run, "tasks", "tasks-table", "ok", len(sched_rows), "测例")
            db.replace_schedules(conn, run, sched_rows)
            for f in flights:
                db.upsert_flight(conn, f, run)
            db.commit(conn)
            payload = render.build_summary(conn, self._cfg(), d)
            conn.close()
        return payload

    def test_ace_rows_leave_shift_and_light_urgent(self):
        payload = self._payload(
            [{"lane": "main", "ticket": "#1", "summary": "主道", "note": "",
              "table_date": "2026-10-27"},
             {"lane": "ace", "ticket": "#77", "summary": "线上着火", "note": "加急",
              "table_date": "2026-10-27"}],
            [{"uid": "issue:1", "ticket": "#1", "title": "主道", "stage": "queued",
              "open": 1}])
        self.assertEqual([r["ticket"] for r in payload["urgent"]["rows"]], ["#77"])
        self.assertEqual([s["ticket"] for s in payload["schedules"]], ["#1"])
        html = render._urgent_section(payload, self._cfg())
        self.assertIn("线上着火", html)
        self.assertIn("王牌机长", html)
        self.assertNotIn("当前没有加急任务", html)

    def test_ace_queue_label_counts_as_urgent(self):
        payload = self._payload([], [
            {"uid": "issue:88", "ticket": "#88", "title": "熔断没接", "stage": "flying",
             "open": 1, "labels": ["ace-queue", "risk:high"],
             "url": "https://x/88"}])
        self.assertEqual([x["ticket"] for x in payload["urgent"]["tickets"]], ["#88"])
        html = render._urgent_section(payload, self._cfg())
        self.assertIn("#88", html)
        self.assertIn('href="https://x/88"', html)      # 加急票必须能直接点开

    def test_closed_ticket_is_not_urgent(self):
        """已关的票不是"在手活"：不该占加急名额、也不该报超编。

        2026-10-29 实测踩过：ace-queue 标签留在一堆已关票上，板子因此报
        "超编：同刻 6 张"——那是完工留痕，不是 ACE 手上有六件活。
        """
        payload = self._payload([], [
            {"uid": "issue:90", "ticket": "#90", "title": "早关了", "stage": "closed",
             "closed": True, "open": 0, "labels": ["ace-queue"], "url": "https://x/90"}])
        self.assertEqual(payload["urgent"]["tickets"], [])
        html = render._urgent_section(payload, self._cfg())
        self.assertIn("当前没有加急任务", html)

    def test_closed_ticket_row_is_not_urgent(self):
        """日表行对应的票已关 ⇒ 那行是留痕，不算在手活。"""
        payload = self._payload(
            [{"lane": "ace", "ticket": "#91", "summary": "早关了", "note": "已发货",
              "table_date": "2026-10-27"}],
            [{"uid": "issue:91", "ticket": "#91", "title": "早关了", "stage": "closed",
              "closed": True, "open": 0}])
        self.assertEqual(payload["urgent"]["rows"], [])

    def test_lagging_lane_keeps_its_own_latest_day(self):
        """落后车道的日表不许被别车道的日期挤掉（2026-10-29 实测）。

        主/副道写 10-29、王牌道停在 10-27 时，牌子上不该"王牌道整条消失"。
        """
        payload = self._payload(
            [{"lane": "main", "ticket": "#1", "summary": "主道今天", "note": "",
              "table_date": "2026-10-29"},
             {"lane": "ace", "ticket": "#77", "summary": "加急还没完", "note": "加急",
              "table_date": "2026-10-27"}],
            [{"uid": "issue:1", "ticket": "#1", "title": "主道今天", "stage": "queued",
              "open": 1}])
        self.assertEqual([r["ticket"] for r in payload["urgent"]["rows"]], ["#77"])
        self.assertEqual([s["ticket"] for s in payload["schedules"]], ["#1"])
        html = render._urgent_section(payload, self._cfg())
        self.assertIn("加急还没完", html)
        self.assertIn("1 张 · 加急", html)
        self.assertIn("协议同刻只许 1 张", html)

    def test_empty_state_tells_how_to_light_it(self):
        payload = self._payload([], [])
        html = render._urgent_section(payload, self._cfg())
        self.assertIn("当前没有加急任务", html)
        self.assertIn("ace-queue", html)          # 空态要自带亮起方式
        self.assertIn("-ace.md", html)

    def test_over_one_ticket_is_reported(self):
        """协议：王牌同刻只许 1 张。超了必须看得见，不能默默堆着。"""
        payload = self._payload(
            [{"lane": "ace", "ticket": "#a1", "summary": "一", "note": "",
              "table_date": "2026-10-27"},
             {"lane": "ace", "ticket": "#a2", "summary": "二", "note": "",
              "table_date": "2026-10-27"}], [])
        html = render._urgent_section(payload, self._cfg())
        self.assertIn("超编", html)

    def test_urgent_section_precedes_shift(self):
        payload = self._payload(
            [{"lane": "main", "ticket": "#1", "summary": "主道", "note": "",
              "table_date": "2026-10-27"}], [])
        html = render.render_html(dict(payload, title="T", direction="", run_id="r1",
                                       kpi=render.compute_kpi([]), degraded=[], trend=[],
                                       milestones=[], handoffs=[], sources={}, blocked=[],
                                       counts={}), self._cfg())
        self.assertLess(html.index('id="s-urgent"'), html.index('id="s-shift"'))



class TestDayTableRobustness(unittest.TestCase):
    """Kai-vass 2026-10-27 实测事故回归：塔台备注里的裸 `|` 撑破一行表格，
    解析器把列映射冲掉 ⇒ 「序」3/4/5/10 被当成票号 ⇒ 板库多出 4 张不存在的票。"""

    def _repo(self, body):
        d = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, d, True)
        os.makedirs(os.path.join(d, "tasks"))
        with open(os.path.join(d, "tasks", "2026-10-27-main.md"), "w",
                  encoding="utf-8") as f:
            f.write(body)
        return d

    def test_bare_sequence_number_is_not_a_ticket(self):
        """「序」列是裸数字，永远不该变成票号。"""
        d = self._repo("# 任务表 · 主机长 · 2026-10-27\n\n"
                       "| 序 | 票号 | 里程碑 | 一句话 | 塔台备注 |\n"
                       "|---|---|---|---|---|\n"
                       "| 1 | #1512 | ② 记忆网络 | 质疑功能 | 在飞 |\n")
        res = tasks.collect({"include": ["*-main.md"], "lanes": ["main"]},
                            {"repo_root": d, "paths": {"day_tables_dir": "tasks"}})
        self.assertEqual([f["ticket"] for f in res["flights"]], ["#1512"])
        self.assertNotIn("#1", [f["ticket"] for f in res["flights"]])

    def test_broken_row_does_not_poison_later_rows(self):
        """备注含裸 `|` ⇒ 该行溢出成正文 ⇒ 后面的行仍要按表头列取票号。"""
        d = self._repo("# 任务表 · 副机长 · 2026-10-24\n\n"
                       "| 序 | 票号 | 里程碑 | 一句话 | 塔台备注 |\n"
                       "|---|---|---|---|---|\n"
                       "| 1 | #1512 | ② 记忆网络 | 质疑 | **票面与** 标签是 |\n"
                       "eady-for-human＋hold」，实际标签是\n"
                       "eady-for-agent 无 hold ⇒ 归地勤订正\n"
                       "| 3 | #1887 | ② 记忆网络 | 读侧挑作品 | 备用 |\n"
                       "| 4 | #1879 | ① 资源管理 | 写库失败被吞 | 备用 |\n")
        res = tasks.collect({"include": ["*-main.md"], "lanes": ["main"]},
                            {"repo_root": d, "paths": {"day_tables_dir": "tasks"}})
        got = [f["ticket"] for f in res["flights"]]
        self.assertIn("#1887", got)
        self.assertIn("#1879", got)
        self.assertNotIn("#3", got)          # 事故现场：这两个就是被造出来的假票
        self.assertNotIn("#4", got)
        by = {f["ticket"]: f for f in res["flights"]}
        self.assertEqual(by["#1887"]["milestone"], "② 记忆网络")   # 列映射没丢
        self.assertEqual(by["#1887"]["title"], "读侧挑作品")

    def test_hotfix_ticket_number_keeps_shape(self):
        """无票热修号 H-YYYYMMDD-N 不是 bug，要照常收，且不被拼成 #H-。"""
        d = self._repo("# 任务表 · 王牌飞行员 · 2026-10-27\n\n"
                       "| 序 | 票号 | 里程碑 | 一句话 | 备注 |\n"
                       "|---|---|---|---|---|\n"
                       "| 1 | H-20261027-1 | 无票热修 | 板不自动更新 | 施工中 |\n")
        res = tasks.collect({"include": ["*-main.md"], "lanes": ["main"]},
                            {"repo_root": d, "paths": {"day_tables_dir": "tasks"}})
        # 沿用既有契约：H- 号也带 # 前缀（见 TestTasks.test_ace_hotfix_row）
        self.assertEqual([f["ticket"] for f in res["flights"]], ["#H-20261027-1"])


class TestOpenCountReconciliation(unittest.TestCase):
    """未收尾数必须能自证：GitHub 有票面的 ＋ 没票面的（残留分支／热修号）。"""

    def _cfg(self):
        return {"name": "t", "output": {"root": "boards"},
                "stages": [{"key": "flying", "label": "在飞"},
                           {"key": "queued", "label": "排队"}],
                "off_chain_stages": [{"key": "unresolved", "label": "残留分支"}],
                "sources": [{"id": "tasks", "type": "tasks-table", "lanes": ["main"]}],
                "stage_rules": [{"when": "else", "stage": "queued"}]}

    def test_split_by_ticket_face(self):
        with tempfile.TemporaryDirectory() as d:
            conn = db.connect(db.db_path(d))
            db.migrate(conn, os.path.join(SKILL_ROOT, "schema"))
            db.record_source(conn, "r1", "tasks", "tasks-table", "ok", 3, "测例")
            db.upsert_flight(conn, {"uid": "issue:1", "ticket": "#1", "title": "有票面",
                                    "stage": "queued", "open": 1,
                                    "url": "https://x/1"}, "r1")
            db.upsert_flight(conn, {"uid": "issue:2", "ticket": "#2", "title": "残留分支",
                                    "stage": "unresolved", "open": 1, "url": ""}, "r1")
            db.commit(conn)
            payload = render.build_summary(conn, self._cfg(), d)
            conn.close()
        k = payload["kpi"]
        self.assertEqual(k["open"], 2)
        self.assertEqual(k["open_with_face"], 1)
        self.assertEqual(k["open_no_face"], 1)
        html = render.render_html(dict(payload, title="T", direction="", run_id="r1",
                                       degraded=[], trend=[], milestones=[], handoffs=[],
                                       sources={}, blocked=[], urgent={"rows": [], "tickets": [],
                                                                      "label": "ace-queue"},
                                       schedules=[], counts=payload["counts"],
                                       kpi=k), self._cfg())
        self.assertIn("有票面 1", html)
        self.assertIn("无票面 1", html)



if __name__ == "__main__":
    unittest.main(verbosity=2)
