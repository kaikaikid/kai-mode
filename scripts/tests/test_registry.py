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


def test_source_marker_roundtrip(tmp_path):
    """装机来源标记：写在库根，记住「这个库是从哪个仓装来的」。"""
    library = str(tmp_path / "data" / "library" / "skills")
    os.makedirs(library)
    src_root = str(tmp_path / "repo")
    os.makedirs(src_root)
    path = ms.write_source_marker(library, src_root, 8)
    assert path == os.path.join(str(tmp_path / "data" / "library"), ".kai-mode-source.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["schema"] == "kai-mode-source/1"
    assert os.path.normcase(data["root"]) == os.path.normcase(os.path.abspath(src_root))
    assert data["skills"] == 8
    assert data["applied_at"]
    # 标记解回正本根
    assert os.path.normcase(ms.marked_root(ms.library_root(library))) == os.path.normcase(os.path.abspath(src_root))


def test_marked_root_refuses_broken_markers(tmp_path):
    """标记缺失／损坏／schema 不认识／目录没了 ⇒ None（不硬失败，走老路）。"""
    lib_root = str(tmp_path / "data" / "library")
    os.makedirs(lib_root)
    assert ms.marked_root(lib_root) is None
    marker = os.path.join(lib_root, ".kai-mode-source.json")
    with open(marker, "w", encoding="utf-8") as f:
        f.write("{ 这不是 json")
    assert ms.marked_root(lib_root) is None
    with open(marker, "w", encoding="utf-8") as f:
        json.dump({"schema": "别的/1", "root": lib_root}, f)
    assert ms.marked_root(lib_root) is None
    with open(marker, "w", encoding="utf-8") as f:
        json.dump({"schema": "kai-mode-source/1", "root": os.path.join(lib_root, "没了")}, f)
    assert ms.marked_root(lib_root) is None


def test_marker_does_not_change_install_plan(tmp_path):
    """标记只管「正本根从哪来」，不改变装机清单。"""
    root = str(tmp_path / "repo")
    _write(root, [_entry("auto-x"), _entry("manual-x", install="manual")])
    before = ms.install_plan(root)
    os.makedirs(os.path.join(root, "skills", "auto-x"), exist_ok=True)
    lib = str(tmp_path / "lib" / "skills")
    os.makedirs(lib)
    ms.write_source_marker(lib, root, 1)
    assert ms.install_plan(root) == before
