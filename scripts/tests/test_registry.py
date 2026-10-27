# -*- coding: utf-8 -*-
"""注册表口径的测试：能解析、字段校验会拒非法取值、装机集只取 install:auto、没有注册表就回落。"""

import importlib.util
import json
import os
import sys

import pytest

sys.dont_write_bytecode = True  # 别在技能目录里落 __pycache__（会被装机尺当成正本差异）

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
MAGPIE = os.path.join(REPO, "core", "skills", "set-kai-mode", "scripts", "magpie-sync.py")


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


def _repo_inventory():
    """本仓的装机清单：优先 registry.json（老仓），否则由 marketplace 合成。"""
    data, err = ms.read_skill_registry(REPO)
    assert err is None, err
    assert data is not None, "本仓既没有 registry.json 也没有 .claude-plugin/marketplace.json"
    return data


def _plugin_skill_dirs():
    """盘上每个插件下的技能目录（marketplace 布局），repo 相对路径（正斜杠）。"""
    mp_path = os.path.join(REPO, ".claude-plugin", "marketplace.json")
    if not os.path.isfile(mp_path):
        return None
    with open(mp_path, encoding="utf-8") as f:
        mp = json.load(f)
    found = []
    for plugin in mp.get("plugins") or []:
        src = plugin.get("source")
        if not isinstance(src, str) or not os.path.isdir(os.path.join(REPO, *os.path.normpath(src).split(os.sep))):
            continue
        skills_dir = os.path.join(REPO, *os.path.normpath(src).split(os.sep), "skills")
        if not os.path.isdir(skills_dir):
            continue
        for name in os.listdir(skills_dir):
            if os.path.isfile(os.path.join(skills_dir, name, "SKILL.md")):
                found.append(name)
    return sorted(found)


def test_inventory_parses_and_is_valid():
    data = _repo_inventory()
    assert data["schema"] == ms.REGISTRY_SCHEMA
    assert isinstance(data["version"], int) and not isinstance(data["version"], bool)
    assert ms.registry_entry_problems(data) == []
    names = [e["name"] for e in data["skills"]]
    assert len(names) == len(set(names))


def test_inventory_covers_every_skill_dir_on_disk():
    """盘上每个技能目录都在清单里（清单不靠手工枚举：对着盘面数）。"""
    data = _repo_inventory()
    registered = sorted(e["name"] for e in data["skills"])
    on_disk = _plugin_skill_dirs()
    if on_disk is None:
        # 老仓：skills/ 平铺
        skills_dir = os.path.join(REPO, "skills")
        on_disk = sorted(n for n in os.listdir(skills_dir)
                         if os.path.isfile(os.path.join(skills_dir, n, "SKILL.md")))
    assert on_disk == registered


def test_inventory_paths_match_disk():
    data = _repo_inventory()
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


def test_marketplace_synthesis(tmp_path):
    """测试从 marketplace.json 合成注册表"""
    root = str(tmp_path / "repo")
    os.makedirs(root, exist_ok=True)

    # Create marketplace.json
    marketplace = {
        "name": "kai-mode",
        "plugins": [
            {
                "name": "airport",
                "source": "./airport",
                "description": "五岗位机场剧本"
            },
            {
                "name": "core",
                "source": "./core",
                "description": "统一入口、装机"
            }
        ]
    }
    os.makedirs(os.path.join(root, ".claude-plugin"), exist_ok=True)
    with open(os.path.join(root, ".claude-plugin", "marketplace.json"), "w", encoding="utf-8") as f:
        json.dump(marketplace, f, ensure_ascii=False)

    # Create plugin manifests
    for plugin in ["airport", "core"]:
        plugin_dir = os.path.join(root, plugin)
        os.makedirs(plugin_dir, exist_ok=True)
        os.makedirs(os.path.join(plugin_dir, ".claude-plugin"), exist_ok=True)

        manifest = {
            "name": plugin,
            "version": "1.0.0",
            "description": f"{plugin} 描述"
        }
        with open(os.path.join(plugin_dir, ".claude-plugin", "plugin.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False)

        # Create some skills
        skills_dir = os.path.join(plugin_dir, "skills")
        os.makedirs(skills_dir, exist_ok=True)

        for skill in ["test-skill-1", "test-skill-2"]:
            skill_dir = os.path.join(skills_dir, skill)
            os.makedirs(skill_dir, exist_ok=True)

            # Create SKILL.md with frontmatter
            skill_md = f"""---
name: {skill}
status: active
approved_by: human:test
approved: 2026-10-27
sources:
  - resource: "test"
    note: "test"
description: >
  {skill} 的说明。
version: 1.0.0
updated: 2026-10-27
---

# {skill}

正文。
"""
            with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write(skill_md)

    # Test synthesis
    data, err = ms.read_skill_registry(root)
    assert data is not None
    assert err is None
    assert data["schema"] == "kai-mode-registry/1"
    assert data["version"] == 1

    # Check skills
    skills = data["skills"]
    assert len(skills) == 4  # 2 plugins × 2 skills each

    # Verify skill structure
    skill_names = [s["name"] for s in skills]
    assert "test-skill-1" in skill_names
    assert "test-skill-2" in skill_names

    # Check specific skill
    skill = next(s for s in skills if s["name"] == "test-skill-1")
    assert skill["path"] in ["./airport/skills/test-skill-1", "./core/skills/test-skill-1", "airport/skills/test-skill-1", "core/skills/test-skill-1"]
    assert skill["kind"] == "framework"
    assert skill["scope"] == "global"
    assert skill["install"] == "auto"
    assert skill["plugin"] in ["airport", "core"]
    assert skill["version"] == "1.0.0"
    assert skill["since"] == "1.0.0"


def test_marketplace_synthesis_fallback_to_legacy(tmp_path):
    """测试当 registry.json 存在时优先使用它"""
    root = str(tmp_path / "repo")
    os.makedirs(root, exist_ok=True)

    # Create registry.json
    _write(root, [_entry("legacy-skill")])

    # Also create marketplace.json
    marketplace = {
        "name": "kai-mode",
        "plugins": [
            {
                "name": "core",
                "source": "./core",
                "description": "统一入口、装机"
            }
        ]
    }
    os.makedirs(os.path.join(root, ".claude-plugin"), exist_ok=True)
    with open(os.path.join(root, ".claude-plugin", "marketplace.json"), "w", encoding="utf-8") as f:
        json.dump(marketplace, f, ensure_ascii=False)

    # Test that registry.json takes precedence
    data, err = ms.read_skill_registry(root)
    assert data is not None
    assert err is None
    assert len(data["skills"]) == 1
    assert data["skills"][0]["name"] == "legacy-skill"


def test_marketplace_invalid_format_errors(tmp_path):
    """测试无效的 marketplace.json 格式会报错"""
    root = str(tmp_path / "repo")
    os.makedirs(root, exist_ok=True)

    # Invalid marketplace - missing plugins
    os.makedirs(os.path.join(root, ".claude-plugin"), exist_ok=True)
    with open(os.path.join(root, ".claude-plugin", "marketplace.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "test"}, f, ensure_ascii=False)

    data, err = ms.read_skill_registry(root)
    assert data is None
    assert "plugins" in err


def test_marketplace_remote_source_skipped(tmp_path):
    """测试远程 source 的插件会被跳过"""
    root = str(tmp_path / "repo")
    os.makedirs(root, exist_ok=True)

    # Marketplace with remote source
    marketplace = {
        "name": "kai-mode",
        "plugins": [
            {
                "name": "remote-plugin",
                "source": "https://github.com/example/plugin",
                "description": "远程插件"
            },
            {
                "name": "local-plugin",
                "source": "./local-plugin",
                "description": "本地插件"
            }
        ]
    }
    os.makedirs(os.path.join(root, ".claude-plugin"), exist_ok=True)
    with open(os.path.join(root, ".claude-plugin", "marketplace.json"), "w", encoding="utf-8") as f:
        json.dump(marketplace, f, ensure_ascii=False)

    # Create local plugin
    plugin_dir = os.path.join(root, "local-plugin")
    os.makedirs(plugin_dir, exist_ok=True)
    os.makedirs(os.path.join(plugin_dir, ".claude-plugin"), exist_ok=True)

    manifest = {
        "name": "local-plugin",
        "version": "1.0.0",
        "description": "本地插件描述"
    }
    with open(os.path.join(plugin_dir, ".claude-plugin", "plugin.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False)

    # Add one skill inside the local plugin
    skill_dir = os.path.join(plugin_dir, "skills", "local-skill")
    os.makedirs(skill_dir)
    with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("---\nname: local-skill\ndescription: >\n  本地技能。\n---\n\n# local-skill\n")

    # Test synthesis
    data, err = ms.read_skill_registry(root)
    assert data is not None
    assert err is None

    # Only local plugin skills should be included
    skills = data["skills"]
    skill_names = [s["name"] for s in skills]
    assert "local-plugin" not in skill_names  # The plugin itself is not a skill
    assert "local-skill" in skill_names
    assert any("local-plugin/skills/" in s["path"] for s in skills)


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
    reg = _repo_inventory()
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

