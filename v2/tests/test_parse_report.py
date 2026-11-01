# -*- coding: utf-8 -*-
"""报告解析回归测试（标准库 unittest，pytest 也能收集）。

#1939 现场：worker/reviewer 两轮报告都被判 partial——报告正文前面有 Findings 段落，
段落里带花括号（`{a:1}`），旧的贪婪正则 `{.*}` 从那个花括号一路吃到末尾，
末尾真正的报告反而解析不出来。这里逐条钉死。
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "v2"))

from coding import adapters  # noqa: E402


def envelope(inner: str, **extra) -> str:
    return json.dumps({"type": "result", "result": inner, **extra}, ensure_ascii=False)


class TestParseReport(unittest.TestCase):
    def test_envelope_with_plain_inner_json(self):
        r = adapters.parse_report(envelope(json.dumps({"result": "done", "files_changed": []})))
        self.assertEqual(r["result"], "done")

    def test_envelope_inner_with_prefix_text(self):
        inner = ('SUMMARY done\n{"result":"done","verdict":"accept","defects":[],'
                 '"reason":"ok","files_changed":[],"verification":[],"open_questions":[]}')
        r = adapters.parse_report(envelope(inner))
        self.assertEqual(r["result"], "done")
        self.assertEqual(r["verdict"], "accept")

    def test_envelope_prefix_text_with_braces(self):
        """关键回归：Findings 段落里带 `{a:1}`，贪婪正则会把末尾报告吞掉。"""
        inner = ('Findings:\n- src/a.py:12 - {a:1} 这个映射写错了\n'
                 '{"result":"done","verdict":"accept","defects":[],"reason":"ok",'
                 '"files_changed":[],"verification":[],"open_questions":[]}')
        r = adapters.parse_report(envelope(inner))
        self.assertEqual(r["result"], "done")
        self.assertEqual(r["verdict"], "accept")

    def test_envelope_nested_braces_and_multiple_objects(self):
        inner = 'see {x: {y: 1}} then final\n{"result":"done","files_changed":[]}'
        r = adapters.parse_report(envelope(inner))
        self.assertEqual(r["result"], "done")

    def test_last_report_wins(self):
        """正文里先出现一个带 result 的对象、末尾又有一份：取末尾那份。"""
        inner = ('{"result":"partial","files_changed":[]}\n...more...\n'
                 '{"result":"done","files_changed":["a.py"]}')
        r = adapters.parse_report(envelope(inner))
        self.assertEqual(r["result"], "done")
        self.assertEqual(r["files_changed"], ["a.py"])

    def test_bare_json_passthrough(self):
        r = adapters.parse_report(json.dumps({"result": "done", "files_changed": []}))
        self.assertEqual(r["result"], "done")

    def test_bare_text_with_trailing_json(self):
        r = adapters.parse_report('some log lines\n{"result":"partial","files_changed":["a.py"]}')
        self.assertEqual(r["result"], "partial")
        self.assertEqual(r["files_changed"], ["a.py"])

    def test_unparseable_is_partial(self):
        r = adapters.parse_report("garbage without json")
        self.assertEqual(r["result"], "partial")
        self.assertIn("read diff", r["notes"])

    def test_usage_is_carried_over(self):
        inner = json.dumps({"result": "done", "files_changed": []})
        r = adapters.parse_report(envelope(inner, usage={"total_tokens": 10},
                                           total_cost_usd=0.01))
        self.assertEqual(r["usage"], {"total_tokens": 10})
        self.assertAlmostEqual(r["total_cost_usd"], 0.01)


if __name__ == "__main__":
    unittest.main()
