"""角色正本／皮肤／渲染／现读的测例（Issue #7 AC-02、AC-08）。

判据实现住 scripts/rolelib.py，CLI 住 scripts/render-roles.py，doctor 的 role-canon 门共用同一份。
变异一律在 tmp_path 的副本上做，绝不改真仓、绝不用 git checkout 还原。
每个「尺子抓得到」的断言都配一条反向：把病灶种回去，尺子必须红。
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"


def _load_rolelib():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import rolelib
    return rolelib


rl = _load_rolelib()


@pytest.fixture()
def repo_copy(tmp_path):
    """把角色面拷进假仓：变异只动副本。"""
    (tmp_path / "roles").mkdir()
    shutil.copytree(REPO / "roles" / "canon", tmp_path / "roles" / "canon")
    shutil.copytree(REPO / "roles" / "skins", tmp_path / "roles" / "skins")
    (tmp_path / "adapters").mkdir()
    shutil.copy2(REPO / "adapters" / "role-hosts.json", tmp_path / "adapters" / "role-hosts.json")
    return tmp_path


# ── 真仓契约 ────────────────────────────────────────────────────────────────
def test_real_repo_canon_validates():
    assert rl.validate(REPO) == []


def test_eight_roles_two_skins_six_hosts():
    canon = rl.load_canon(REPO)
    assert set(canon) == set(rl.ROLE_IDS)
    assert len(canon) == 8
    for skin in rl.SKINS:
        assert set(rl.load_skin(REPO, skin)["roles"]) == set(rl.ROLE_IDS)
    assert set(rl.load_hosts(REPO)["hosts"]) == set(rl.HOSTS)


def test_canon_has_exactly_four_blocks_in_order():
    for rid, c in rl.load_canon(REPO).items():
        assert tuple(c["blocks"]) == rl.CANON_BLOCKS, rid
        assert tuple(c["order"]) == rl.META_KEYS, rid


def test_canon_body_is_host_neutral():
    """角色正本里不许出现宿主专有词——那些住 adapters/。"""
    for rid, c in rl.load_canon(REPO).items():
        for tok in rl.HOST_TOKENS:
            assert tok not in c["body"], f"{rid} 正文含宿主词 {tok}"


def test_skin_identity_states_the_name():
    """子代理看不到自己的类型名，identity 必须逐字写出名字（实测坑 1）。"""
    for skin in rl.SKINS:
        for rid, e in rl.load_skin(REPO, skin)["roles"].items():
            assert e["name"] in e["identity"], f"{skin}/{rid}"


# ── AC-08：换皮肤只换前两块 ──────────────────────────────────────────────────
def _canon_tail(text: str) -> str:
    return text.split("## mission", 1)[1]


def test_ac08_canon_byte_identical_across_skins_all_hosts():
    for host in rl.HOSTS:
        a = rl.render_all(REPO, host, "generic")
        b = rl.render_all(REPO, host, "guild")
        assert set(a) == set(b)
        for name in a:
            assert _canon_tail(a[name]) == _canon_tail(b[name]), f"{host}/{name} 职责四块漂了"
            assert a[name] != b[name], f"{host}/{name} 皮肤没生效"


def test_ac08_filenames_stable_across_skins():
    """文件名用 role_id，换皮肤不改名，重渲染才对得上同一份。"""
    for host in rl.HOSTS:
        assert set(rl.render_all(REPO, host, "generic")) == set(rl.render_all(REPO, host, "guild"))


# ── AC-02（口径 2026-11-08 修订）：同一组装点，重渲染即自愈 ──────────────────
@pytest.mark.parametrize("host", rl.HOSTS)
@pytest.mark.parametrize("skin", rl.SKINS)
def test_ac02_render_is_idempotent(host, skin, tmp_path):
    """渲染两遍结果一样：派生物没有「旧版」这个概念，重渲染就是全部。"""
    first = rl.render_all(REPO, host, skin)
    assert len(first) == 8
    for name, text in first.items():
        (tmp_path / name).write_bytes(text.encode("utf-8"))
    second = rl.render_all(REPO, host, skin)
    assert first == second
    for name, text in second.items():
        assert (tmp_path / name).read_bytes() == text.encode("utf-8")


def test_ac02_render_body_comes_from_prompt(tmp_path):
    """同一个组装点：渲染文件的正文逐字节等于 prompt 现读结果，没有第二套拼装。"""
    for host in rl.HOSTS:
        files = rl.render_all(REPO, host, "guild")
        for rid in rl.ROLE_IDS:
            fname = next(n for n in files if n.startswith(rid))
            assert _body_of(files[fname]) == rl.render_prompt(REPO, rid, "guild"), f"{host}/{rid}"


def test_ac02_hand_edit_is_healed_by_rerender(tmp_path):
    """去掉 stale 巡检后，保护靠「一律重渲染」：手改一笔，下次 render 覆盖回正本结果。"""
    host, skin = "qoder", "guild"
    files = rl.render_all(REPO, host, skin)
    for name, text in files.items():
        (tmp_path / name).write_bytes(text.encode("utf-8"))
    p = tmp_path / "reviewer.md"
    p.write_text(p.read_text(encoding="utf-8") + "\n手改一笔。\n", encoding="utf-8")
    assert p.read_text(encoding="utf-8").endswith("手改一笔。\n")
    for name, text in rl.render_all(REPO, host, skin).items():
        (tmp_path / name).write_bytes(text.encode("utf-8"))
    assert p.read_bytes() == files["reviewer.md"].encode("utf-8"), "重渲染没把手改覆盖掉"


def test_ac02_canon_bump_changes_fingerprint_immediately(repo_copy):
    """正本升版：现读与渲染结果同时变，指纹跟着变——不需要任何巡检来告知。"""
    before = rl.render_prompt(repo_copy, "reviewer", "generic")
    assert "canon_version=1.0.0" in before
    p = repo_copy / "roles" / "canon" / "reviewer.md"
    p.write_text(p.read_text(encoding="utf-8").replace(
        "canon_version: 1.0.0", "canon_version: 1.1.0"), encoding="utf-8")
    after = rl.render_prompt(repo_copy, "reviewer", "generic")
    assert "canon_version=1.1.0" in after and after != before
    rendered = rl.render_all(repo_copy, "qoder", "generic")["reviewer.md"]
    assert _body_of(rendered) == after, "渲染路径没跟着正本走"


def test_fingerprint_is_recomputable():
    canon = rl.load_canon(REPO)
    sk = rl.load_skin(REPO, "guild")
    text = rl.render_all(REPO, "qoder", "guild")["archivist.md"]
    head = next(l for l in text.splitlines() if l.startswith("<!-- kai-role"))
    assert f"canon_sha256={canon['archivist']['sha256']}" in head
    assert f"skin_sha256={rl.entry_sha256(sk['roles']['archivist'])}" in head
    assert "role_id=archivist" in head and "skin=guild" in head


def test_entry_fingerprint_ignores_json_whitespace_and_key_order():
    e = {"name": "n", "identity": "i", "personality": "p"}
    reordered = {"personality": "p", "name": "n", "identity": "i", "_extra": "ignored"}
    assert rl.entry_sha256(e) == rl.entry_sha256(reordered)


# ── 宿主投影：只读与禁嵌套真的落到字段上 ──────────────────────────────────────
def test_readonly_roles_get_no_write_tools_on_qoder():
    files = rl.render_all(REPO, "qoder", "generic")
    canon = rl.load_canon(REPO)
    for name, text in files.items():
        rid = Path(name).stem
        fm = text.split("---")[1]
        tools_line = next(l for l in fm.splitlines() if l.startswith("tools:"))
        if canon[rid]["meta"]["access_need"] == "read_only":
            for forbidden in ("Write", "Edit", "Bash"):
                assert forbidden not in tools_line, f"{rid} 只读却给了 {forbidden}"
            assert "disallowedTools:" in fm, rid
        else:
            assert "Write" in tools_line, rid
        assert "Agent" in fm, f"{rid} 没禁再派子代理"


def test_cursor_readonly_uses_flag_not_tools():
    files = rl.render_all(REPO, "cursor", "generic")
    assert "readonly: true" in files["reviewer.md"]
    assert "readonly: false" in files["engineer.md"]
    assert "tools:" not in files["reviewer.md"]


def test_copilot_effort_downmaps_and_omits_unverified_model():
    files = rl.render_all(REPO, "copilot", "generic")
    reviewer = files["reviewer.agent.md"]
    # reviewer 的 effort=max，Copilot 只有 low/medium/high ⇒ 降到 high
    assert "reasoningEffort: high" in reviewer
    # model 档位全是 inherit 且该宿主未确证认 inherit ⇒ 不写该字段，不发明值
    assert "model:" not in reviewer
    tools_line = next(l for l in reviewer.split("---")[1].splitlines() if l.startswith("tools:"))
    assert "edit" not in tools_line and "execute" not in tools_line
    assert "agent" not in tools_line, "Copilot 靠不给 agent 别名禁再派"


def test_hosts_without_agent_file_render_prompt_only():
    for host in ("codex", "opencode"):
        for name, text in rl.render_all(REPO, host, "generic").items():
            assert not text.startswith("---"), f"{host}/{name} 不该有 frontmatter"
            assert "<!-- kai-role" in text
            assert "## mission" in text


def test_every_host_declares_whether_readonly_is_hard():
    """只读到底硬不硬必须如实标，默认当硬就是自欺（实测见 ADR-0033「实测发现」）。"""
    hosts = rl.load_hosts(REPO)["hosts"]
    for name, cfg in hosts.items():
        assert cfg.get("readonly_hard") in ("yes", "no", "unverified"), name


def test_qoder_readonly_is_pinned_as_not_hard():
    """钉住实测结论：Desktop 这条派发面上工具白名单没被执行，只读不是硬机制。
    哪天宿主修好了，这条会红——那就该把它改成 yes，并同步 ADR-0033。"""
    assert rl.load_hosts(REPO)["hosts"]["qoder"]["readonly_hard"] == "no"


# ── 两条消费路径：打包（要重渲染） vs 现读（零同步）──────────────────────────
def _body_of(text: str) -> str:
    return text.split("---", 2)[2].lstrip("\n") if text.startswith("---") else text


def test_prompt_equals_body_of_rendered_file():
    """现读出来的正文与该宿主渲染文件的正文逐字相同——两条路同源，不是两套。"""
    for host in rl.HOSTS:
        for skin in rl.SKINS:
            files = rl.render_all(REPO, host, skin)
            for rid in rl.ROLE_IDS:
                fname = next(n for n in files if n.startswith(rid))
                assert _body_of(files[fname]) == rl.render_prompt(REPO, rid, skin), f"{host}/{rid}"


def test_prompt_tracks_canon_without_any_file(repo_copy):
    """现读路径不依赖任何落地文件：改正本，下一次 prompt 就是新的。"""
    before = rl.render_prompt(repo_copy, "reviewer", "generic")
    p = repo_copy / "roles" / "canon" / "reviewer.md"
    p.write_text(p.read_text(encoding="utf-8").replace(
        "canon_version: 1.0.0", "canon_version: 1.1.0"), encoding="utf-8")
    assert rl.render_prompt(repo_copy, "reviewer", "generic") != before


def test_pack_contains_all_eight_roles():
    pack = rl.render_pack(REPO, "guild")
    for rid in rl.ROLE_IDS:
        assert f"role={rid}" in pack
    assert pack.count("<!-- kai-role") == 8


# ── 反向：把病灶种回副本，尺子必须红 ──────────────────────────────────────────
def test_reverse_host_token_in_canon_is_red(repo_copy):
    p = repo_copy / "roles" / "canon" / "engineer.md"
    p.write_text(p.read_text(encoding="utf-8") + "\n用 disallowedTools 禁掉写工具。\n", encoding="utf-8")
    bad = rl.validate(repo_copy)
    assert any("宿主专有词" in b for b in bad), bad


def test_reverse_block_order_is_red(repo_copy):
    p = repo_copy / "roles" / "canon" / "writer.md"
    t = p.read_text(encoding="utf-8").replace("## mission", "## TEMP").replace("## boundaries", "## mission")
    p.write_text(t.replace("## TEMP", "## boundaries"), encoding="utf-8")
    bad = rl.validate(repo_copy)
    assert any("正文块不符" in b for b in bad), bad


def test_reverse_missing_skin_role_is_red(repo_copy):
    p = repo_copy / "roles" / "skins" / "generic.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    del d["roles"]["archivist"]
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    bad = rl.validate(repo_copy)
    assert any("角色集不符" in b for b in bad), bad


def test_reverse_identity_without_name_is_red(repo_copy):
    p = repo_copy / "roles" / "skins" / "guild.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["roles"]["kanna" if "kanna" in d["roles"] else "coordinator"]["identity"] = "你是酒馆的守护者。"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    bad = rl.validate(repo_copy)
    assert any("identity 里没写出名字" in b for b in bad), bad


def test_reverse_frontmatter_key_order_is_red(repo_copy):
    p = repo_copy / "roles" / "canon" / "designer.md"
    t = p.read_text(encoding="utf-8")
    t = t.replace("access_need: writable\nmodel_tier: standard", "model_tier: standard\naccess_need: writable")
    p.write_text(t, encoding="utf-8")
    bad = rl.validate(repo_copy)
    assert any("键序不符" in b for b in bad), bad


def test_reverse_host_without_own_cli_is_red(repo_copy):
    p = repo_copy / "adapters" / "role-hosts.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["hosts"]["codex"]["own_cli"] = ""
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    bad = rl.validate(repo_copy)
    assert any("本宿主自己的 CLI" in b for b in bad), bad


def test_reverse_unverified_host_without_evidence_is_red(repo_copy):
    p = repo_copy / "adapters" / "role-hosts.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["hosts"]["cursor"]["verified"] = ""
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    bad = rl.validate(repo_copy)
    assert any("缺 verified" in b for b in bad), bad


def test_reverse_missing_readonly_hard_is_red(repo_copy):
    p = repo_copy / "adapters" / "role-hosts.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["hosts"]["qoder"].pop("readonly_hard", None)
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    bad = rl.validate(repo_copy)
    assert any("readonly_hard" in b for b in bad), bad


def test_mutation_fixture_is_not_a_noop(repo_copy):
    """自证变异夹具真的能改到东西：改一份正本，指纹必须变。"""
    before = rl.load_canon(repo_copy)["engineer"]["sha256"]
    p = repo_copy / "roles" / "canon" / "engineer.md"
    p.write_text(p.read_text(encoding="utf-8") + "\n多一行。\n", encoding="utf-8")
    after = rl.load_canon(repo_copy)["engineer"]["sha256"]
    assert before != after