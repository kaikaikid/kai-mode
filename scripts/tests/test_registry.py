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
    # 与 doctor 的 LEGACY_LOCKED 同口径：两个被环境锁死、已判退役的目录不参与“盘面==注册表”。
    legacy_locked = {"航班信息", "set-航班信息"}
    on_disk = sorted(n for n in os.listdir(skills_dir)
                     if os.path.isfile(os.path.join(skills_dir, n, "SKILL.md"))
                     and n not in legacy_locked)
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


def test_source_marker_receipt_fields(tmp_path):
    lib = str(tmp_path / "data" / "library" / "skills")
    os.makedirs(lib)
    root = str(tmp_path / "repo")
    os.makedirs(root)
    ms.write_source_marker(lib, root, 2, profile="core", skill_names=["a", "b"],
                           hashes={"a": "h1", "b": "h2"}, source_commit="deadbeef")
    data = ms.read_source_marker(lib)
    assert data["profile"] == "core"
    assert data["skill_names"] == ["a", "b"]
    assert data["hashes"] == {"a": "h1", "b": "h2"}
    assert data["source_commit"] == "deadbeef"
    assert ms.marked_profile(lib) == "core"


def test_backup_and_restore_roundtrip(tmp_path):
    lib = str(tmp_path / "data" / "library" / "skills")
    os.makedirs(os.path.join(lib, "alpha"))
    with open(os.path.join(lib, "alpha", "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("# before\n")
    reg = ms.registry_path(lib)
    with open(reg, "w", encoding="utf-8") as f:
        json.dump({"skills": []}, f)
    backup = ms.backup_library(lib)
    assert backup and os.path.isdir(backup)
    with open(os.path.join(lib, "alpha", "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("# after\n")
    os.remove(reg)
    assert ms.restore_library(lib, backup) is True
    assert open(os.path.join(lib, "alpha", "SKILL.md"), encoding="utf-8").read() == "# before\n"
    assert os.path.isfile(reg)


def test_retire_registry_entries_only_removes_named(tmp_path):
    lib = str(tmp_path / "data" / "library" / "skills")
    os.makedirs(lib)
    reg = ms.registry_path(lib)
    before = {
        "skills": [{"name": "塔台", "agents": ["qoder"]}, {"name": "tower"}],
        "applied": {"qoder": {"skills": ["塔台", "tower"], "mcp": ["keep"]}},
        "icons": {"x": 1},
    }
    with open(reg, "w", encoding="utf-8") as f:
        json.dump(before, f, ensure_ascii=False)
    removed = ms.retire_registry_entries(lib, {"塔台"})
    assert removed == ["塔台"]
    after = json.loads(open(reg, encoding="utf-8").read())
    assert [s["name"] for s in after["skills"]] == ["tower"]
    assert after["applied"]["qoder"]["skills"] == ["tower"]
    assert after["applied"]["qoder"]["mcp"] == ["keep"]
    assert after["icons"] == {"x": 1}


def test_retire_legacy_moves_dir_and_unlinks(tmp_path):
    lib = str(tmp_path / "data" / "library" / "skills")
    for name in ("kai-mode", "塔台", "tower"):
        os.makedirs(os.path.join(lib, name))
        with open(os.path.join(lib, name, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write(f"# {name}\n")
    home = str(tmp_path / "home")
    face = os.path.join(home, ".fake", "skills")
    os.makedirs(face)
    os.symlink(os.path.join(lib, "kai-mode"), os.path.join(face, "kai-mode"),
               target_is_directory=True)
    os.symlink(os.path.join(lib, "塔台"), os.path.join(face, "塔台"), target_is_directory=True)
    moved, unlinked, skipped = ms.retire_legacy(lib, home=home)
    assert moved and unlinked and not skipped
    assert not os.path.exists(os.path.join(lib, "塔台"))
    assert not os.path.lexists(os.path.join(face, "塔台"))
    assert os.path.isdir(os.path.join(lib, "tower"))


def test_retire_legacy_dry_run_does_not_move(tmp_path):
    lib = str(tmp_path / "data" / "library" / "skills")
    os.makedirs(os.path.join(lib, "塔台"))
    home = str(tmp_path / "home")
    moved, unlinked, skipped = ms.retire_legacy(lib, home=home, dry=True)
    assert moved
    assert os.path.isdir(os.path.join(lib, "塔台"))


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


def _write_profiles(root, profiles):
    d = os.path.join(root, "manifests")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "install-profiles.json"), "w", encoding="utf-8") as f:
        json.dump({"schema": ms.PROFILES_SCHEMA, "version": 1, "profiles": profiles},
                  f, ensure_ascii=False)


def test_install_plan_profile_filters(tmp_path):
    root = str(tmp_path / "repo")
    _write(root, [_entry("a"), _entry("b"), _entry("c", install="manual")])
    _write_profiles(root, {
        "core": {"skills": ["a"]},
        "full": {"skills": ["a", "b"]},
    })
    assert set(ms.install_plan(root, "core")) == {"a"}
    assert set(ms.install_plan(root, "full")) == {"a", "b"}
    assert set(ms.install_plan(root)) == {"a", "b"}


def test_install_plan_rejects_unknown_or_non_auto_profile(tmp_path):
    root = str(tmp_path / "repo")
    _write(root, [_entry("a"), _entry("b", install="manual")])
    _write_profiles(root, {
        "core": {"skills": ["a"]},
        "full": {"skills": ["a", "b"]},
    })
    with pytest.raises(SystemExit):
        ms.install_plan(root, "nope")
    with pytest.raises(SystemExit):
        ms.install_plan(root, "full")


def test_repo_install_profiles_are_valid():
    with open(os.path.join(REPO, "manifests", "install-profiles.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    assert cfg["schema"] == ms.PROFILES_SCHEMA
    with open(os.path.join(REPO, "registry.json"), encoding="utf-8") as f:
        reg = json.load(f)
    auto = {e["name"] for e in reg["skills"] if e.get("install") == "auto"}
    for name in ("core", "full"):
        assert name in cfg["profiles"]
        assert set(cfg["profiles"][name]["skills"]) <= auto
    assert set(cfg["profiles"]["core"]["skills"]) <= set(cfg["profiles"]["full"]["skills"])


def test_install_plan_without_profiles_rejects_profile(tmp_path):
    root = str(tmp_path / "repo")
    _write(root, [_entry("a"), _entry("b")])
    with pytest.raises(SystemExit):
        ms.install_plan(root, "core")  # 无 profiles 文件 ⇒ 指定档位应报错，不静默全装

