"""双仓库开发规范：QA 归一化、渲染、缺件处置。

规范正本住 `templates/dual-repo.md`；实现住 `scripts/init-project.py`。
测例只断三件事：① 认不出的答案一律「待定」，绝不替用户选默认；② 模板里的占位被填干净；
③ 已有结论不被重跑覆盖。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TBD = "待定"


def _load_init():
    p = REPO / "scripts" / "init-project.py"
    spec = importlib.util.spec_from_file_location("_kai_init_project", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ip = _load_init()


# ── 归一化：认得出就归一，认不出就是待定 ────────────────────────────────────
@pytest.mark.parametrize("raw,expect", [
    ("双仓", "dual"), ("dual", "dual"), ("DUAL", "dual"), ("单仓", "single"), ("single", "single"),
    ("", TBD), (TBD, TBD), ("随便写的", TBD), (None, TBD),
])
def test_topology_normalization(raw, expect):
    assert ip._pick_enum("topology", raw) == expect


def test_all_answers_empty_stay_pending():
    """一个都没答 ⇒ 五项全待定。规范明写不许替用户选默认值。"""
    got = ip.release_values({})
    assert {k: got[k] for k in ip.RELEASE_KEYS} == {k: TBD for k in ip.RELEASE_KEYS}
    assert got["repo"] == TBD


def test_answers_are_normalized_not_echoed():
    got = ip.release_values({
        "q1_topology": "双仓", "q2_visibility": "私有",
        "q3_dev_push": "只有用户推", "q4_release_issues": "关闭",
        "q5_release_history": "不可变", "release_repo": "owner/release",
    })
    assert got == {"topology": "dual", "visibility": "private", "dev_push": "user-only",
                   "issues": "closed", "history": "immutable-tags", "repo": "owner/release"}


def test_garbage_answer_does_not_become_a_choice():
    got = ip.release_values({"q3_dev_push": "AI 随便推吧"})
    assert got["dev_push"] == TBD


# ── 渲染：模板占位填干净 ────────────────────────────────────────────────────
@pytest.fixture()
def proj(tmp_path):
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "dual-repo.md").write_text(
        (REPO / "templates" / "dual-repo.md").read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


LAYOUT = {"project_scaffold": {"dual_repo": {"from": "templates/dual-repo.md",
                                             "to": ".ai/dual-repo.md"}}}


def _render(proj, ans):
    mp = pytest.MonkeyPatch()
    mp.setattr(ip, "ROOT", str(proj))
    try:
        out = ip.gen_dual_repo(str(proj), ans, LAYOUT)
        p = proj / ".ai" / "dual-repo.md"
        return out, (p.read_text(encoding="utf-8") if p.is_file() else "")
    finally:
        mp.undo()


def test_render_fills_every_placeholder(proj):
    out, text = _render(proj, {"q1_topology": "dual", "q2_visibility": "private",
                               "q3_dev_push": "user-only", "q4_release_issues": "closed",
                               "q5_release_history": "immutable-tags",
                               "release_repo": "owner/release", "repo_slug": "owner/dev"})
    assert out == [".ai/dual-repo.md"]
    assert "{{" not in text and "}}" not in text, "有没填的占位"
    assert "双仓（dual）" in text and "私有（private）" in text
    assert "只有用户推（user-only）" in text
    assert "owner/dev" in text and "owner/release" in text


def test_render_keeps_pending_visible(proj):
    """没答的项必须肉眼可见「待定」，不能悄悄变成默认值。"""
    _, text = _render(proj, {})
    assert text.count(TBD) >= 5
    assert "双仓（dual）" not in text
    assert "单仓（single）" not in text


def test_render_single_repo_keeps_collapse_rule(proj):
    _, text = _render(proj, {"q1_topology": "单仓"})
    assert "单仓（single）" in text
    assert "票＝代码＝发布同一仓" in text or "票=代码=发布同一仓" in text


def test_existing_file_is_not_overwritten(proj):
    """用户改过的结论不许被重跑抹掉。"""
    d = proj / ".ai"
    d.mkdir()
    (d / "dual-repo.md").write_text("我自己改过的结论\n", encoding="utf-8")
    out, text = _render(proj, {"q1_topology": "dual"})
    assert out == []
    assert text == "我自己改过的结论\n"


# ── 配置实例：五题答案落进 release 段 ───────────────────────────────────────
def test_apply_writes_release_section():
    tpl = json.loads((REPO / "templates" / "kai-mode.project.json").read_text(encoding="utf-8"))
    assert set(ip.RELEASE_KEYS) | {"repo"} <= set(tpl["release"])
    cfg = ip.apply(json.loads(json.dumps(tpl)), {
        "project": "p", "q1_topology": "dual", "q2_visibility": "public",
        "q3_dev_push": "user-only", "q4_release_issues": "redirect",
        "q5_release_history": "immutable-tags", "release_repo": "o/r",
    })
    assert cfg["release"]["topology"] == "dual"
    assert cfg["release"]["issues"] == "redirect"
    assert cfg["release"]["repo"] == "o/r"


def test_apply_with_no_answers_keeps_everything_pending():
    tpl = json.loads((REPO / "templates" / "kai-mode.project.json").read_text(encoding="utf-8"))
    cfg = ip.apply(json.loads(json.dumps(tpl)), {"project": "p"})
    for k in ip.RELEASE_KEYS:
        assert cfg["release"][k] == TBD, k


# ── 反向：模板与清单必须成对 ────────────────────────────────────────────────
def test_template_has_all_tokens_and_layout_points_at_it():
    text = (REPO / "templates" / "dual-repo.md").read_text(encoding="utf-8")
    for token in ("{{Q1}}", "{{Q2}}", "{{Q3}}", "{{Q4}}", "{{Q5}}",
                  "{{DEV_REPO}}", "{{RELEASE_REPO}}"):
        assert token in text, token
    layout = json.loads((REPO / "manifests" / "package-layout.json").read_text(encoding="utf-8"))
    spec = layout["project_scaffold"]["dual_repo"]
    assert spec["from"] == "templates/dual-repo.md"
    assert spec["to"] == ".ai/dual-repo.md"
    assert (REPO / spec["from"]).is_file()


def test_config_template_release_has_a_live_consumer():
    """ADR-0015：键必须有活消费方。release 段的消费方就是 init-project 的渲染与 apply；
    且 apply 以模板为准，模板没这一段就不凭空造（ADR-0014）。"""
    src = (REPO / "scripts" / "init-project.py").read_text(encoding="utf-8")
    assert 'cfg.get("release")' in src
    assert "def gen_dual_repo(" in src
    assert "def release_values(" in src