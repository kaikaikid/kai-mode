# -*- coding: utf-8 -*-
"""eval-check 确定性检查器自身的测试（W4.1）：判词枚举、证据、密钥、COM 归属。"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SPEC = Path(__file__).resolve().parents[1] / "eval-check.py"


def _mod():
    spec = importlib.util.spec_from_file_location("eval_check", SPEC)
    m = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(m)
    return m


def base(**over):
    env = {
        "schema_version": 1,
        "task_id": "t1",
        "role_id": "engineer",
        "idempotency_key": "k1",
        "claims": [{"kind": "fact", "text": "x", "evidence_refs": ["a.py:1"]}],
        "artifacts": [{"artifact_id": "a1", "type": "code", "format": "py",
                       "uri": "a.py", "version": "1", "created_by": "engineer"}],
    }
    env.update(over)
    return env


def test_valid_envelope_passes():
    assert _mod().check(base(), "E-engineer-01", "engineer") == []


def test_fact_without_evidence_fails():
    p = _mod().check(base(claims=[{"kind": "fact", "text": "x"}]), "E", "engineer")
    assert any("evidence_refs" in x for x in p)


def test_legacy_verdict_rejected():
    p = _mod().check(base(verdict={"value": "PASS"}), "E", "reviewer")
    assert any("forbidden legacy verdict" in x for x in p)


def test_non_reviewer_verdict_rejected():
    p = _mod().check(base(verdict={"value": "accept"}), "E", "engineer")
    assert any("only role_id=reviewer" in x for x in p)


def test_defer_needs_items():
    p = _mod().check(base(role_id="reviewer", verdict={"value": "defer"}), "E", "reviewer")
    assert any("deferred_items" in x for x in p)


def test_secret_only_names_pattern():
    p = _mod().check(base(notes="tok=ghp_" + "a" * 30), "E", "engineer")
    hits = [x for x in p if "secret-like" in x]
    assert hits and "github_token" in hits[0]
    assert "a" * 30 not in json.dumps(p)  # 不回显内容


def test_com_only_for_coordinator():
    p = _mod().check(base(), "COM-01", "engineer")
    assert any("coordinator only" in x for x in p)
    assert _mod().check(base(role_id="coordinator"), "COM-01", "coordinator") == []
