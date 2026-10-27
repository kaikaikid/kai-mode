# -*- coding: utf-8 -*-
"""doctor 第 14 项 decoupling-gate（解耦门）：残留必红、白名单不报、模板 slug 必红、干净仓绿。"""

import json

from test_doctor import detail_of, make_repo, run_doctor, status_of

GATE = "decoupling-gate"


def test_residue_file_turns_gate_red_and_lists_position(tmp_path):
    """①假文件带硬路径残留 ⇒ 门红，且按「文件:行号:模式」点名、给修法。"""
    root = make_repo(tmp_path)
    (root / "core" / "skills" / "alpha").mkdir(parents=True)
    (root / "core" / "skills" / "alpha" / "notes.md").write_text(
        "第一行干净。\n读取 .ai/router.md 的登记面，主树在 kai-vass。\n", encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, GATE) == "fail"
    detail = detail_of(data, GATE)
    assert "core/skills/alpha/notes.md:2:.ai/router" in detail
    assert "core/skills/alpha/notes.md:2:kai-vass" in detail
    assert "修法" in detail and "kai-mode.project.json" in detail  # 指到配置实例


def test_whitelist_dirs_do_not_report(tmp_path):
    """②白名单目录里的残留不报：插件技能内层的 _superseded/ 归档不算正本。"""
    root = make_repo(tmp_path)
    sup = root / "core" / "skills" / "alpha" / "_superseded"
    sup.mkdir(parents=True)
    (sup / "old.md").write_text("旧稿残留 kai-vass 主树。\n", encoding="utf-8")
    rc, data = run_doctor(root)
    assert status_of(data, GATE) == "ok"
    assert rc == 0


def test_schema3_template_reviving_tiers_is_red(tmp_path):
    """③a schema 4 模板把六档字段写回来 ⇒ 红，文案点名已退役（ADR-0008 D3）。"""
    root = make_repo(tmp_path)
    tpl = {
        "schema": 4,
        "models": {
            "agents": {"worker": {"model": None}},
            "tiers": ["R", "C", "P", "V", "G", "W"],
            "default": "C",
            "roles": {"code": {"tier": "C"}},
        },
    }
    (root / "templates").mkdir()
    (root / "templates" / "kai-mode.project.json").write_text(
        json.dumps(tpl, ensure_ascii=False), encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, GATE) == "fail"
    detail = detail_of(data, GATE)
    assert "models.tiers 已退役" in detail and "ADR-0008" in detail
    assert "models.default 已退役" in detail and "models.roles 已退役" in detail


def test_schema3_template_with_model_name_is_red(tmp_path):
    """③b 模板把模型写死（非 null）⇒ 红：框架不写死模型，值归用户实例。"""
    root = make_repo(tmp_path)
    tpl = {"schema": 4, "models": {"agents": {"worker": {"model": "group/tier-code-xhigh"}}}}
    (root / "templates").mkdir()
    (root / "templates" / "kai-mode.project.json").write_text(
        json.dumps(tpl, ensure_ascii=False), encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, GATE) == "fail"
    detail = detail_of(data, GATE)
    assert "只许 null" in detail and "group/" in detail


def test_schema3_template_metadata_junk_key_is_red(tmp_path):
    """③c agents.<人格> 里塞回 tier/spawn 之类 ⇒ 红（只许 model）。"""
    root = make_repo(tmp_path)
    tpl = {"schema": 4, "models": {"agents": {"worker": {"model": None, "tier": "C"}}}}
    (root / "templates").mkdir()
    (root / "templates" / "kai-mode.project.json").write_text(
        json.dumps(tpl, ensure_ascii=False), encoding="utf-8")
    rc, data = run_doctor(root)
    assert rc == 1
    assert status_of(data, GATE) == "fail"
    assert "多余键 tier" in detail_of(data, GATE)


def test_clean_repo_gate_is_green(tmp_path):
    """④干净仓 ⇒ 门绿，整仓也绿。"""
    root = make_repo(tmp_path)
    (root / "core").mkdir()
    rc, data = run_doctor(root)
    assert data["ok"] is True
    assert rc == 0
    assert status_of(data, GATE) == "ok"
    assert "0 命中" in detail_of(data, GATE)


def test_template_config_path_values_are_not_flagged(tmp_path):
    """配置模板本体是项目差异层载体：audit_dir 的 .ai/scope 采样值是硬路径的合法新家（ADR-0004 D2），不报。"""
    root = make_repo(tmp_path)
    (root / "templates").mkdir()
    (root / "templates" / "kai-mode.project.json").write_text(json.dumps({
        "schema": 4,
        "paths": {"audit_dir": ".ai/scope/audit"},
        "models": {"agents": {"worker": {"model": None}}},
    }, ensure_ascii=False), encoding="utf-8")
    rc, data = run_doctor(root)
    assert status_of(data, GATE) == "ok"
    assert rc == 0


def test_template_schema2_skips_models_subcheck(tmp_path):
    """schema 2 兼容期模板：models 子检查不适用（不红），其余五种模式照扫。"""
    root = make_repo(tmp_path)
    (root / "templates").mkdir()
    (root / "templates" / "kai-mode.project.json").write_text(
        json.dumps({"schema": 2, "day_tables": ".ai/day-tables"}, ensure_ascii=False), encoding="utf-8")
    rc, data = run_doctor(root)
    assert status_of(data, GATE) == "ok"
    assert "schema=2" in detail_of(data, GATE)
