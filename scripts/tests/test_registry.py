# -*- coding: utf-8 -*-
"""注册表口径的测试：能解析、字段校验会拒非法取值、装机集只取 install:auto、没有注册表就回落。"""

import importlib.util
import json
import os
import sys

import pytest

sys.dont_write_bytecode = True  # 别在技能目录里落 __pycache__（会被装机尺当成正本差异）

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
MAGPIE = os.path.join(REPO, "skills", "set-kai-mode", "scripts", "magpie-sync.py")


def _load():
    spec = importlib.util.spec_from_file_location("kai_mode_magpie_sync", MAGPIE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ms = _load()


def _entry(name="x", **kw):
    e = {"name": name, "path": f"skills/{name}", "kind": "framework", "scope": "global",
         "install": "auto", "summary": "一句话"}
    e.update(kw)
    return e


def _write(root, entries, schema=None):
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "registry.json"), "w", encoding="utf-8") as f:
        json.dump({"schema": schema or ms.REGISTRY_SCHEMA, "version": 1, "skills": entries},
                  f, ensure_ascii=False)
    return root


def test_registry_json_parses_and_is_valid():
    with open(os.path.join(REPO, "registry.json"), encoding="utf-8") as f:
        data = json.load(f)
    assert data["schema"] == ms.REGISTRY_SCHEMA
    assert isinstance(data["version"], int) and not isinstance(data["version"], bool)
    assert ms.registry_entry_problems(data) == []
    names = [e["name"] for e in data["skills"]]
    assert len(names) == len(set(names))


def test_registry_covers_every_skill_dir_on_disk():
    """盘上每个技能目录都在注册表里（清单不靠手工枚举：对着盘面数）。"""
    with open(os.path.join(REPO, "registry.json"), encoding="utf-8") as f:
        data = json.load(f)
    skills_dir = os.path.join(REPO, "skills")
    on_disk = sorted(n for n in os.listdir(skills_dir)
                     if os.path.isfile(os.path.join(skills_dir, n, "SKILL.md")))
    registered = sorted(e["name"] for e in data["skills"])
    assert on_disk == registered


def test_registry_paths_match_disk():
    with open(os.path.join(REPO, "registry.json"), encoding="utf-8") as f:
        data = json.load(f)
    for e in data["skills"]:
        assert os.path.isdir(os.path.join(REPO, *e["path"].split("/"))), e["name"]
        assert e["path"].split("/")[-1] == e["name"], e["name"]


@pytest.mark.parametrize("bad_field,bad_value", [
    ("kind", "weird"),
    ("scope", "planet"),
    ("install", "sometimes"),
])
def test_validation_rejects_illegal_enum(bad_field, bad_value):
    data = {"schema": ms.REGISTRY_SCHEMA, "version": 1, "skills": [_entry(**{bad_field: bad_value})]}
    problems = ms.registry_entry_problems(data)
    assert problems, f"{bad_field}={bad_value} 应当被拒"
    assert any(bad_field in p for p in problems)


def test_validation_requires_fields_and_summary():
    data = {"schema": ms.REGISTRY_SCHEMA, "version": 1, "skills": [
        {"name": "x", "path": "skills/x", "kind": "framework", "scope": "global", "install": "auto"},
    ]}
    problems = ms.registry_entry_problems(data)
    assert any("summary" in p for p in problems)

    data["skills"][0]["summary"] = "   "
    problems = ms.registry_entry_problems(data)
    assert any("summary" in p for p in problems)


def test_install_plan_takes_only_auto(tmp_path):
    root = str(tmp_path / "repo")
    _write(root, [_entry("auto-x"), _entry("manual-x", install="manual"), _entry("none-x", install="none")])
    plan = ms.install_plan(root)
    assert set(plan) == {"auto-x"}
    assert plan["auto-x"]["source"] == os.path.join(".ai", "skills", "project-skills", "auto-x")
    assert plan["auto-x"]["path"] == "skills/auto-x"  # 注册表原样（仓内相对路径，正斜杠可移植）


def test_install_plan_honours_registry_source(tmp_path):
    root = str(tmp_path / "repo")
    _write(root, [_entry("loop", source=".ai/skills/loop")])
    plan = ms.install_plan(root)
    assert plan["loop"]["source"] == ".ai/skills/loop"


def test_install_plan_falls_back_to_builtin_without_registry(tmp_path):
    root = str(tmp_path / "repo")
    os.makedirs(root, exist_ok=True)
    plan = ms.install_plan(root)
    assert set(plan) == set(ms.FAMILIES)
    assert len(plan) == 8
    assert plan["loop"]["source"] == os.path.join(".ai", "skills", "loop")


def test_unknown_schema_is_reported_not_guessed(tmp_path):
    root = str(tmp_path / "repo")
    _write(root, [_entry("x")], schema="some-other-schema/9")
    data, err = ms.read_skill_registry(root)
    assert data is None
    assert err and "schema" in err
    with pytest.raises(SystemExit):
        ms.install_plan(root)


def test_family_candidates_order_is_source_then_path_then_skills(tmp_path):
    root = str(tmp_path / "repo")
    _write(root, [_entry("x", source=".ai/skills/loop", path="skills/x")])
    plan = ms.install_plan(root)
    cands = ms.family_candidates("x", plan)
    # ① source ② 注册表 path ③ skills/<名>（②③ 归一化后同一个目录 ⇒ 去重）
    assert cands == [".ai/skills/loop", "skills/x"]
    assert len(cands) == len(set(os.path.normpath(c) for c in cands))
