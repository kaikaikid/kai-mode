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
    assert len(ids) == 13
