# -*- coding: utf-8 -*-
"""doctor 在假仓（tmp_path）上的行为：每种违规都得红，一切正常才绿。"""

import json
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DOCTOR = os.path.join(REPO, "scripts", "doctor.py")

SKILL_MD = """---
name: {name}
status: active
approved_by: human:kaikaikid
approved: 2026-10-22
sources:
  - resource: "x"
    note: "y"
description: >
  {name} 的说明。
version: 1.0.0
updated: 2026-10-22
---

# {name}

正文。
"""


def make_repo(tmp_path, skills=("alpha",)):
    """造一个处处合规的假仓：注册表、SKILL.md、VERSION、README、.gitattributes 都齐。"""
    root = tmp_path / "repo"
    (root / "skills").mkdir(parents=True)
    entries = []
    for name in skills:
        d = root / "skills" / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(SKILL_MD.format(name=name), encoding="utf-8")
        entries.append({"name": name, "path": f"skills/{name}", "kind": "framework",
                        "scope": "global", "install": "auto", "summary": "一句话"})
    (root / "registry.json").write_text(
        json.dumps({"schema": "kai-mode-registry/1", "version": 1, "skills": entries}, ensure_ascii=False),
        encoding="utf-8")
    (root / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    (root / "README.md").write_text("# 假仓\n\n状态：9.9.9\n", encoding="utf-8")
    (root / ".gitattributes").write_text("* text=auto\n*.bat text eol=crlf\n", encoding="utf-8")
    # 15 handoff-slots / 18 canon-dup 的必需件：假仓也要齐，否则 clean_repo 不是绿的
    for slot in ("00-inbox", "10-session", "20-plan", "30-research",
                 "40-review", "50-comms", "60-board", "90-archive"):
        (root / "handoff" / slot).mkdir(parents=True, exist_ok=True)
    (root / "handoff" / "README.md").write_text("# handoff\n\n假仓规范。\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "canon.json").write_text(json.dumps({
        "retired_terms": [], "scan_roots": ["skills"], "exempt": [], "canon_keys": [],
    }, ensure_ascii=False), encoding="utf-8")
    return root


def make_library(tmp_path, root, skills=("alpha",), marker_root=None):
    """造假中央库：`<tmp>/lib/skills/<名>/…` ＋ 可选 `<tmp>/lib/.kai-mode-source.json`。"""
    lib_root = tmp_path / "lib"
    lib = lib_root / "skills"
    lib.mkdir(parents=True)
    for name in skills:
        d = lib / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text((root / "skills" / name / "SKILL.md").read_text(encoding="utf-8"),
                                    encoding="utf-8")
    if marker_root is not None:
        (lib_root / ".kai-mode-source.json").write_text(
            json.dumps({"schema": "kai-mode-source/1", "root": str(marker_root),
                        "applied_at": "2026-10-22T00:00:00+00:00", "skills": len(skills)},
                       ensure_ascii=False), encoding="utf-8")
    return lib


def run_doctor(root, *extra, library=None, isolate_home=True):
    """跑 doctor（子进程）。默认把中央库从环境里摘掉（HOME 指到空目录）⇒ 第 13 项跳过，
    免得测到本机真库；要用假库就传 `library=`。"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    env.pop("KAI_MAGPIE_LIBRARY", None)
    if library:
        env["KAI_MAGPIE_LIBRARY"] = str(library)
    if isolate_home:
        fake_home = str(root.parent / "fakehome")
        os.makedirs(fake_home, exist_ok=True)
        env["HOME"] = fake_home
        env["USERPROFILE"] = fake_home
    p = subprocess.run([sys.executable, DOCTOR, "--root", str(root), "--json", *extra],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    return p.returncode, json.loads(p.stdout)


def status_of(data, cid):
    return next(c["status"] for c in data["checks"] if c["id"] == cid)


def detail_of(data, cid):
    return next(c["detail"] for c in data["checks"] if c["id"] == cid)


def test_clean_repo_is_green(tmp_path):
    root = make_repo(tmp_path)
    rc, data = run_doctor(root)
    assert data["ok"] is True
    assert rc == 0
    assert not [c for c in data["checks"] if c["status"] == "fail"]


def test_unregistered_skill_dir_is_red(tmp_path):
    root = make_repo(tmp_path)
    ghost = root / "skills" / "ghost"
    ghost.mkdir()
    (ghost / "SKILL.md").write_text(SKILL_MD.format(name="ghost"), encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "unregistered-skill") == "fail"
    assert "ghost" in detail_of(data, "unregistered-skill")


def test_missing_frontmatter_field_is_red(tmp_path):
    root = make_repo(tmp_path)
    md = root / "skills" / "alpha" / "SKILL.md"
    md.write_text(SKILL_MD.format(name="alpha").replace("approved_by: human:kaikaikid\n", ""),
                  encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "skill-frontmatter") == "fail"


def test_frontmatter_name_mismatch_is_red(tmp_path):
    root = make_repo(tmp_path)
    md = root / "skills" / "alpha" / "SKILL.md"
    md.write_text(SKILL_MD.format(name="alpha").replace("name: alpha", "name: beta"),
                  encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "skill-frontmatter") == "fail"
    assert "三处不一致" in detail_of(data, "skill-frontmatter")


def test_unquoted_colon_in_frontmatter_is_red(tmp_path):
    root = make_repo(tmp_path)
    md = root / "skills" / "alpha" / "SKILL.md"
    md.write_text(SKILL_MD.format(name="alpha").replace(
        "description: >\n  alpha 的说明。", "description: alpha: 冒号"), encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "frontmatter-yaml") == "fail"
    assert ": " in detail_of(data, "frontmatter-yaml")


def test_quoted_colon_in_frontmatter_is_green(tmp_path):
    root = make_repo(tmp_path)
    md = root / "skills" / "alpha" / "SKILL.md"
    md.write_text(SKILL_MD.format(name="alpha").replace(
        "description: >\n  alpha 的说明。", 'description: "alpha: 冒号"'), encoding="utf-8")
    rc, data = run_doctor(root)
    assert status_of(data, "frontmatter-yaml") == "ok"
    assert rc == 0


def test_reserved_char_frontmatter_is_red(tmp_path):
    root = make_repo(tmp_path)
    md = root / "skills" / "alpha" / "SKILL.md"
    md.write_text(SKILL_MD.format(name="alpha").replace(
        "description: >\n  alpha 的说明。", "description: @reserved"), encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "frontmatter-yaml") == "fail"
    assert "保留字符" in detail_of(data, "frontmatter-yaml")


def test_host_token_in_skill_is_red(tmp_path):
    root = make_repo(tmp_path)
    (root / "skills" / "alpha" / "notes.md").write_text(
        "起会话用 create_chat_session。\n", encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "host-neutral") == "fail"
    assert "create_chat_session" in detail_of(data, "host-neutral")


def test_host_token_in_adapters_is_allowed(tmp_path):
    root = make_repo(tmp_path)
    (root / "adapters").mkdir()
    (root / "adapters" / "qoder.md").write_text("qoder_cron list\n", encoding="utf-8")
    rc, data = run_doctor(root)
    assert status_of(data, "host-neutral") == "ok"
    assert rc == 0


def test_broken_relative_link_is_red(tmp_path):
    root = make_repo(tmp_path)
    md = root / "skills" / "alpha" / "SKILL.md"
    md.write_text(SKILL_MD.format(name="alpha") + "\n见 [别的](../missing/SKILL.md)\n", encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "broken-link") == "fail"


def test_machine_absolute_path_is_red(tmp_path):
    root = make_repo(tmp_path)
    (root / "skills" / "alpha" / "notes.md").write_text("板写到 D:\\boards\\airport\n", encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "machine-path") == "fail"
    assert "D:" in detail_of(data, "machine-path")


def test_machine_path_allow_marker_is_exempt(tmp_path):
    root = make_repo(tmp_path)
    (root / "skills" / "alpha" / "notes.md").write_text(
        "板写到 D:\\boards\\airport  # doctor:allow-machine-path\n", encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 0
    assert status_of(data, "machine-path") == "ok"


def test_version_mismatch_is_red(tmp_path):
    root = make_repo(tmp_path)
    (root / "README.md").write_text("# 假仓\n\n状态：0.0.1\n", encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "version-in-readme") == "fail"


def test_missing_registry_is_red(tmp_path):
    root = make_repo(tmp_path)
    (root / "registry.json").unlink()
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "registry-file") == "fail"


def test_registered_path_missing_is_red(tmp_path):
    root = make_repo(tmp_path)
    (root / "skills" / "alpha" / "SKILL.md").unlink()
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "missing-skill-path") == "fail"


def test_bad_install_enum_is_red(tmp_path):
    root = make_repo(tmp_path)
    data = json.loads((root / "registry.json").read_text(encoding="utf-8"))
    data["skills"][0]["install"] = "sometimes"
    (root / "registry.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    rc, out = run_doctor(root)
    assert rc == 1
    assert status_of(out, "registry-fields") == "fail"


def test_canon_wake_fence_phrase_is_red(tmp_path):
    root = make_repo(tmp_path)
    (root / "docs" / "canon.json").write_text(json.dumps({
        "retired_terms": [], "scan_roots": ["skills"], "exempt": [],
        "canon_keys": [{
            "key": "wake-fence",
            "home": "docs/adr/0010-role-wake-fence.md",
            "pattern": "拉起继任机长",
            "forbidden": ["skills"],
        }],
    }, ensure_ascii=False), encoding="utf-8")
    (root / "skills" / "alpha" / "notes.md").write_text(
        "发现停摆就拉起继任机长。\n", encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "canon-dup") == "fail"
    assert "wake-fence" in detail_of(data, "canon-dup")


def test_canon_value_restatement_is_red(tmp_path):
    """可调数值（在飞名额）只许住 home：技能里出现同义复述即红。"""
    root = make_repo(tmp_path)
    (root / "loops").mkdir()
    (root / "loops" / "loop-protocol.md").write_text("名额：各同时最多 2 张 issue。\n", encoding="utf-8")
    (root / "docs" / "canon.json").write_text(json.dumps({
        "retired_terms": [], "scan_roots": ["skills"], "exempt": [],
        "canon_keys": [{
            "key": "pilot-wip",
            "home": "loops/loop-protocol.md",
            "pattern": "(最多|各|只能)\\s*2\\s*张|2\\s*张在飞",
            "forbidden": ["skills"],
        }],
    }, ensure_ascii=False), encoding="utf-8")
    (root / "skills" / "alpha" / "notes.md").write_text("机长最多 2 张在飞。\n", encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "canon-dup") == "fail"
    assert "pilot-wip" in detail_of(data, "canon-dup")


def test_sources_dead_path_is_red(tmp_path):
    """sources 里的路径必须指向随装件；自然语言条目（含空白）不判路径。"""
    root = make_repo(tmp_path)
    md = root / "skills" / "alpha" / "SKILL.md"
    text = md.read_text(encoding="utf-8").replace(
                'sources:\n  - resource: "x"\n    note: "y"\n',
        'sources:\n'
        '  - resource: "references/nope.md"\n'
        '    note: "死指针"\n'
        '  - resource: "上游 mattpocock/skills 的某件（未入库）"\n'
        '    note: "自然语言出处，不该被判路径"\n')
    md.write_text(text, encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    detail = detail_of(data, "broken-link")
    assert "references/nope.md" in detail
    assert "mattpocock" not in detail


def test_sources_shipped_path_is_green(tmp_path):
    """sources 指向本技能内真实文件（含花括号展开）时不许假红。"""
    root = make_repo(tmp_path, skills=("alpha", "beta"))
    (root / "skills" / "alpha" / "references").mkdir()
    (root / "skills" / "alpha" / "references" / "source.md").write_text("x\n", encoding="utf-8")
    md = root / "skills" / "alpha" / "SKILL.md"
    md.write_text(md.read_text(encoding="utf-8").replace(
                'sources:\n  - resource: "x"\n    note: "y"\n',
        'sources:\n'
        '  - resource: "references/source.md"\n'
        '    note: "本技能文件"\n'
        '  - resource: "skills/{alpha,beta}/SKILL.md"\n'
        '    note: "花括号展开两条都真"\n'), encoding="utf-8")
    rc, data = run_doctor(root)
    assert status_of(data, "broken-link") == "ok", detail_of(data, "broken-link")


def test_install_profiles_bad_reference_is_red(tmp_path):
    root = make_repo(tmp_path)
    (root / "manifests").mkdir()
    (root / "manifests" / "install-profiles.json").write_text(json.dumps({
        "schema": "kai-mode-install-profiles/1", "version": 1,
        "profiles": {
            "core": {"skills": ["alpha"]},
            "full": {"skills": ["alpha", "ghost"]},
        },
    }, ensure_ascii=False), encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "install-profiles") == "fail"
    assert "ghost" in detail_of(data, "install-profiles")


def test_install_set_must_match_registry(tmp_path):
    """注册表说这条要装（install:auto），magpie-sync 却装不了（没 name）⇒ 两边对不上 ⇒ 红。"""
    root = make_repo(tmp_path)
    data = json.loads((root / "registry.json").read_text(encoding="utf-8"))
    data["skills"].append({"path": "skills/ghost2", "kind": "personal",
                            "scope": "owner", "install": "auto", "summary": "x"})
    (root / "registry.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    rc, out = run_doctor(root)
    assert rc == 1
    assert status_of(out, "install-set-match") == "fail"


# ── 13 install-sync：装机同步（库副本 vs 本仓 ＋ 装机来源标记）────────────────────


def test_install_sync_green_when_library_matches(tmp_path):
    root = make_repo(tmp_path)
    lib = make_library(tmp_path, root, marker_root=root)
    rc, data = run_doctor(root, library=lib)
    assert status_of(data, "install-sync") == "ok"
    assert "逐字相同" in detail_of(data, "install-sync")
    assert rc == 0


def test_install_sync_red_when_library_content_differs(tmp_path):
    root = make_repo(tmp_path)
    lib = make_library(tmp_path, root, marker_root=root)
    bad = lib / "alpha" / "SKILL.md"
    bad.write_text(bad.read_text(encoding="utf-8") + " ", encoding="utf-8")
    rc, data = run_doctor(root, library=lib)
    assert rc == 1
    assert status_of(data, "install-sync") == "fail"
    detail = detail_of(data, "install-sync")
    assert "alpha/SKILL.md" in detail and "内容不符" in detail
    assert "apply --root" in detail  # 给出修法


def test_install_sync_red_when_library_missing_a_file(tmp_path):
    root = make_repo(tmp_path)
    lib = make_library(tmp_path, root, marker_root=root)
    (lib / "alpha" / "SKILL.md").unlink()
    rc, data = run_doctor(root, library=lib)
    assert rc == 1
    assert status_of(data, "install-sync") == "fail"
    assert "缺件" in detail_of(data, "install-sync")


def test_install_sync_red_when_marker_missing(tmp_path):
    root = make_repo(tmp_path)
    lib = make_library(tmp_path, root, marker_root=None)  # 不写标记
    rc, data = run_doctor(root, library=lib)
    assert rc == 1
    assert status_of(data, "install-sync") == "fail"
    detail = detail_of(data, "install-sync")
    assert "没钉死" in detail
    assert "apply --root" in detail


def test_install_sync_red_when_marker_points_elsewhere(tmp_path):
    root = make_repo(tmp_path)
    other = tmp_path / "otherrepo"
    other.mkdir()
    lib = make_library(tmp_path, root, marker_root=other)
    rc, data = run_doctor(root, library=lib)
    assert rc == 1
    assert status_of(data, "install-sync") == "fail"
    detail = detail_of(data, "install-sync")
    assert str(other) in detail  # 点名那个别的仓


def test_install_sync_skipped_when_no_library(tmp_path):
    root = make_repo(tmp_path)
    rc, data = run_doctor(root)  # 不给 library，且 HOME 指向空目录 ⇒ 库定位不到
    assert status_of(data, "install-sync") == "skip"
    assert rc == 0  # 跳过不是红


def test_install_sync_present_in_json_output(tmp_path):
    root = make_repo(tmp_path)
    rc, data = run_doctor(root)
    ids = [c["id"] for c in data["checks"]]
    assert "install-sync" in ids
    assert len(ids) >= 19  # 项数随门增长；这里只锁 install-sync 在列，不锁死总数


# ── 24 package-layout：三层打包边界 ───────────────────────────────────────────
def add_layout(root, *, handoff_files=None, exclude_dirs=None, config_from=None):
    """给假仓加一份最小清单：安装面 + 骨架。"""
    (root / "manifests").mkdir(exist_ok=True)
    (root / "templates").mkdir(exist_ok=True)
    (root / "templates" / "kai-mode.project.json").write_text("{}\n", encoding="utf-8")
    (root / "templates" / "GLOSSARY.md").write_text("# GLOSSARY\n", encoding="utf-8")
    files = handoff_files if handoff_files is not None else {"handoff/README.md": "handoff/README.md"}
    layout = {
        "schema": "kai-mode-package-layout/1",
        "repo_only": ["docs/"],
        "host_payload": {
            "source": "registry.json#install:auto",
            "exclude_dirs": exclude_dirs or ["tests", "__pycache__", ".pytest_cache"],
            "exclude_suffixes": [".pyc"],
        },
        "project_scaffold": {
            "config": {
                "from": config_from or "templates/kai-mode.project.json",
                "to": ".ai/kai-mode.project.json",
            },
            "glossary": {"from": "templates/GLOSSARY.md", "to": "GLOSSARY.md"},
            "handoff": {
                "slots": ["00-inbox", "60-board"],
                "monthly_slots": ["00-inbox"],
                "board_slot": "60-board",
                "board_children": ["open"],
                "files": files,
            },
            "adr_dir": "docs/adr",
            "placeholder": ".gitkeep",
        },
    }
    (root / "manifests" / "package-layout.json").write_text(
        json.dumps(layout, ensure_ascii=False), encoding="utf-8")


def test_package_layout_absent_is_skip(tmp_path):
    root = make_repo(tmp_path)
    rc, data = run_doctor(root)
    assert status_of(data, "package-layout") == "skip"
    assert rc == 0


def test_package_layout_source_tests_are_allowed(tmp_path):
    """源仓里的 tests/ 是本仓开发件：只要安装面排除它，就不该判红。"""
    root = make_repo(tmp_path)
    add_layout(root)
    (root / "skills" / "alpha" / "tests").mkdir()
    (root / "skills" / "alpha" / "tests" / "test_a.py").write_text("def test_a():\n    pass\n",
                                                                  encoding="utf-8")
    rc, data = run_doctor(root)
    assert status_of(data, "package-layout") == "ok"
    assert rc == 0


def test_package_layout_exclude_missing_is_red(tmp_path):
    root = make_repo(tmp_path)
    add_layout(root, exclude_dirs=["__pycache__", ".pytest_cache"])
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "package-layout") == "fail"
    assert "tests" in detail_of(data, "package-layout")


def test_package_layout_history_source_is_red(tmp_path):
    root = make_repo(tmp_path)
    hist = root / "handoff" / "40-review" / "2026-10"
    hist.mkdir(parents=True)
    (hist / "dev-record.md").write_text("# 本仓开发记录\n", encoding="utf-8")
    add_layout(root, handoff_files={"handoff/40-review/2026-10/dev-record.md": "handoff/x.md"})
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "package-layout") == "fail"
    assert "越界" in detail_of(data, "package-layout")


def test_package_layout_missing_source_is_red(tmp_path):
    root = make_repo(tmp_path)
    add_layout(root, config_from="templates/nope.json")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "package-layout") == "fail"
    assert "源件不存在" in detail_of(data, "package-layout")


# ── 26 config-instance：实跑 init-project，实例里不许有虚构值 ────────────────
def add_init(root, gates_extra=None):
    """把真 init-project 装进假仓，并写一份最小 schema 模板；gates_extra 用来塞「没被问答的门」。"""
    import shutil
    (root / "scripts").mkdir(exist_ok=True)
    shutil.copyfile(os.path.join(REPO, "scripts", "init-project.py"),
                    str(root / "scripts" / "init-project.py"))
    tpl = {
        "schema": 4, "_note_0": "t", "project": "<project-name>", "repo_root": ".",
        "models": {"_note": "n", "agents": {}},
        "ship_mode": "tower",
        "host": {"_note": "n", "adapter": "<qoder|codex>"},
        "registry": {"_note": "n", "adrs": {"dir": "<adr-dir>"},
                     "skills": {"project_skills_dir": ".ai/skills/project-skills",
                                "loop_dir": ".ai/skills/loop"}},
        "paths": {"_note": "n", "day_tables_dir": "<day-tables-dir>",
                  "day_table_pattern": "YYYY-MM-DD-{lane}.md", "lanes": ["main", "deputy"],
                  "handoff_dir": "handoff", "ideas_dir": "ideas"},
        "gates": dict({"_note": "n", "captain_preflight": ""}, **(gates_extra or {})),
        "issue": {"_note": "n", "platform": "github", "repo": "<owner>/<repo>",
                  "boom_summary_ticket": None},
    }
    (root / "templates" / "kai-mode.project.json").write_text(
        json.dumps(tpl, ensure_ascii=False, indent=2), encoding="utf-8")


def test_config_instance_preset_gate_is_red(tmp_path):
    root = make_repo(tmp_path)
    add_layout(root)
    add_init(root, {"ready": "scripts/ready.py", "env_doctor": "scripts/env-doctor.py"})
    rc, data = run_doctor(root)
    assert rc == 1
    detail = detail_of(data, "config-instance")
    assert status_of(data, "config-instance") == "fail"
    assert "没被问答的门" in detail
    assert "ready" in detail and "env_doctor" in detail


def test_config_instance_machine_path_is_red(tmp_path):
    root = make_repo(tmp_path)
    add_layout(root)
    add_init(root)
    p = root / "templates" / "kai-mode.project.json"
    tpl = json.loads(p.read_text(encoding="utf-8"))
    tpl["paths"]["audit_dir"] = "C:" + chr(92) + "Users" + chr(92) + "kaikaikid" + chr(92) + "audit"
    p.write_text(json.dumps(tpl, ensure_ascii=False, indent=2), encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert "机器绝对路径进了实例" in detail_of(data, "config-instance")


def test_config_instance_clean_is_green(tmp_path):
    root = make_repo(tmp_path)
    add_layout(root)
    add_init(root)
    rc, data = run_doctor(root)
    assert status_of(data, "config-instance") == "ok", detail_of(data, "config-instance")


# ── 25 payload-refs：安装面零开发史引用（ADR-0013） ──────────────────────────
def test_payload_refs_external_link_is_red(tmp_path):
    root = make_repo(tmp_path)
    (root / "skills" / "alpha" / "notes.md").write_text(
        "[协议](../../loops/loop-protocol.md)\n", encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "payload-refs") == "fail"
    assert "不随技能安装" in detail_of(data, "payload-refs")


def test_payload_refs_framework_url_is_red(tmp_path):
    root = make_repo(tmp_path)
    (root / "skills" / "alpha" / "notes.md").write_text(
        "详见 [README](https://github.com/kaikaikid/kai-mode/blob/main/README.md)\n",
        encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    detail = detail_of(data, "payload-refs")
    assert status_of(data, "payload-refs") == "fail"
    assert "框架仓 URL" in detail


def test_payload_refs_adr_citation_is_red(tmp_path):
    root = make_repo(tmp_path)
    (root / "skills" / "alpha" / "notes.md").write_text(
        "唤醒围栏的判据正本：ADR-0010。\n", encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert "框架 ADR 编号" in detail_of(data, "payload-refs")


def test_payload_refs_maintainer_gate_is_red(tmp_path):
    root = make_repo(tmp_path)
    (root / "skills" / "alpha" / "notes.md").write_text(
        "- `python scripts/doctor.py --with-tests` 全绿。\n"
        "- 项目仓 `python scripts/env-doctor.py --hooks` 全绿（这条合法）。\n",
        encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    detail = detail_of(data, "payload-refs")
    assert "维护者门禁命令" in detail
    assert "env-doctor" not in detail


def test_payload_refs_sibling_skill_is_green(tmp_path):
    root = make_repo(tmp_path, skills=("alpha", "beta"))
    (root / "skills" / "alpha" / "notes.md").write_text(
        "[beta](../beta/SKILL.md)\n\n判据正本：框架仓 `loops/loop-protocol.md`（不随技能安装）。\n",
        encoding="utf-8")
    rc, data = run_doctor(root)
    assert status_of(data, "payload-refs") == "ok"
    assert rc == 0


# ── 08 tracked-cache：缓存、运行数据与本仓开发流水都不许被跟踪 ────────────────
def _git_init_add(root, force_paths=()):
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    for rel in force_paths:
        subprocess.run(["git", "-C", str(root), "add", "-f", rel], check=True,
                       capture_output=True)


def test_tracked_runtime_data_is_red(tmp_path):
    root = make_repo(tmp_path)
    (root / "session.db").write_text("x", encoding="utf-8")
    (root / "agent-data").mkdir()
    (root / "agent-data" / "run.txt").write_text("x", encoding="utf-8")
    _git_init_add(root, ("session.db", "agent-data/run.txt"))
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, "tracked-cache") == "fail"
    detail = detail_of(data, "tracked-cache")
    assert "session.db" in detail
    assert "agent-data" in detail


def test_tracked_clean_repo_is_green(tmp_path):
    root = make_repo(tmp_path)
    _git_init_add(root)
    rc, data = run_doctor(root)
    assert status_of(data, "tracked-cache") == "ok"
    assert rc == 0


def test_tracked_handoff_flow_is_red(tmp_path):
    """本仓开发流水（日期目录里的评审件、看板工单）被跟踪 ⇒ 红。"""
    root = make_repo(tmp_path)
    add_layout(root)
    d = root / "handoff" / "40-review" / "2026-10"
    d.mkdir(parents=True)
    (d / "2026-10-24-x-review.md").write_text("# 评审\n", encoding="utf-8")
    b = root / "handoff" / "60-board" / "open"
    b.mkdir(parents=True)
    (b / "2026-10-24-x-task.md").write_text("# 工单\n", encoding="utf-8")
    _git_init_add(root)
    rc, data = run_doctor(root)
    assert rc == 1
    detail = detail_of(data, "tracked-cache")
    assert "2026-10-24-x-review.md" in detail
    assert "2026-10-24-x-task.md" in detail
    assert "handoff/README.md" not in detail


def test_tracked_handoff_spec_files_are_green(tmp_path):
    """规范件、模板与槽位/看板状态占位 .gitkeep 是骨架源 ⇒ 绿。"""
    root = make_repo(tmp_path)
    add_layout(root, handoff_files={
        "handoff/README.md": "handoff/README.md",
        "handoff/60-board/README.md": "handoff/60-board/README.md",
        "handoff/templates/HANDOFF-template.md": "handoff/templates/HANDOFF-template.md",
    })
    (root / "handoff" / "60-board" / "README.md").write_text("# 看板\n", encoding="utf-8")
    (root / "handoff" / "templates").mkdir()
    (root / "handoff" / "templates" / "HANDOFF-template.md").write_text("# 模板\n", encoding="utf-8")
    (root / "handoff" / "40-review" / ".gitkeep").write_text("", encoding="utf-8")
    (root / "handoff" / "60-board" / "open").mkdir()
    (root / "handoff" / "60-board" / "open" / ".gitkeep").write_text("", encoding="utf-8")
    _git_init_add(root)
    rc, data = run_doctor(root)
    assert status_of(data, "tracked-cache") == "ok"
