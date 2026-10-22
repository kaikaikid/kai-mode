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


def run_doctor(root, *extra):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
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
