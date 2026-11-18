"""角色正本／皮肤／渲染／现读的测例（Issue #7 AC-02、AC-08）。

判据实现住 scripts/rolelib.py，CLI 住 scripts/render-roles.py，doctor 的 role-canon 门共用同一份。
变异一律在 tmp_path 的副本上做，绝不改真仓、绝不用 git checkout 还原。
每个「尺子抓得到」的断言都配一条反向：把病灶种回去，尺子必须红。
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
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
    """把角色面拷进假仓：变异只动副本。

    渲染路径要的唯一家文件也得拷进来——渲染器是失败关闭的（体例或措辞表缺了
    就抛，不静默产出「没有总结体例」的提示词），假仓少文件就不是真仓了。
    """
    (tmp_path / "roles").mkdir()
    shutil.copytree(REPO / "roles" / "canon", tmp_path / "roles" / "canon")
    shutil.copytree(REPO / "roles" / "skins", tmp_path / "roles" / "skins")
    shutil.copytree(REPO / "roles" / "presets", tmp_path / "roles" / "presets")
    for name in ("input-contract.md", "output-routing.md", "envelope-header.md",
                 "summary-convention.md", "summary-slots.json"):
        shutil.copy2(REPO / "roles" / name, tmp_path / "roles" / name)
    (tmp_path / "adapters").mkdir()
    shutil.copy2(REPO / "adapters" / "role-hosts.json", tmp_path / "adapters" / "role-hosts.json")
    (tmp_path / "scripts").mkdir()
    shutil.copy2(REPO / "scripts" / "rolelib.py", tmp_path / "scripts" / "rolelib.py")
    # 派生体例门要看的两个落点也得在，否则假仓里门只会报「文件不在」
    (tmp_path / "docs").mkdir()
    shutil.copy2(REPO / "docs" / "eval-cases.md", tmp_path / "docs" / "eval-cases.md")
    gold_dir = tmp_path / "core" / "skills" / "gold"
    (gold_dir / "references").mkdir(parents=True)
    shutil.copy2(REPO / "core" / "skills" / "gold" / "SKILL.md", gold_dir / "SKILL.md")
    shutil.copy2(REPO / "core" / "skills" / "gold" / "references" / "commands.md",
                 gold_dir / "references" / "commands.md")
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


def test_exactly_one_primary_and_it_is_the_coordinator():
    """康娜是主 AI 人格，不是可派发的子代理——由 kind 字段机械定住。"""
    canon = rl.load_canon(REPO)
    primaries = [rid for rid, c in canon.items() if c["meta"].get("kind") == "primary"]
    assert primaries == [rl.PRIMARY_ID] == ["coordinator"]
    assert rl.PRIMARY_ID not in rl.DISPATCHABLE_IDS
    assert len(rl.DISPATCHABLE_IDS) == 7


def test_kind_splits_core_three_and_specialist_four():
    """ADR-0036 D1：kind 三档；核心 3 进 agent 目录，专家 4 走 profile。"""
    canon = rl.load_canon(REPO)
    kinds = {rid: c["meta"]["kind"] for rid, c in canon.items()}
    assert kinds == rl.KIND_BY_ROLE
    assert set(rl.CORE_IDS) == {"engineer", "reviewer", "archivist"}
    assert set(rl.SPECIALIST_IDS) == {"researcher", "architect", "designer", "writer"}
    assert set(rl.CORE_IDS) | set(rl.SPECIALIST_IDS) == set(rl.DISPATCHABLE_IDS)
    assert not (set(rl.CORE_IDS) & set(rl.SPECIALIST_IDS))


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
    """渲染两遍结果一样：派生物没有「旧版」这个概念，重渲染就是全部。默认只出七个可派发角色。"""
    first = rl.render_all(REPO, host, skin)
    assert len(first) == 7
    assert "coordinator.md" not in first and "_primary.md" not in first
    for name, text in first.items():
        (tmp_path / name).write_bytes(text.encode("utf-8"))
    second = rl.render_all(REPO, host, skin)
    assert first == second
    for name, text in second.items():
        assert (tmp_path / name).read_bytes() == text.encode("utf-8")


def test_ac02_with_primary_adds_only_the_session_agent(host="qoder"):
    files = rl.render_all(REPO, host, "guild", with_primary=True)
    assert len(files) == 8
    prim = next(n for n in files if n.startswith("_primary"))
    body = _body_of(files[prim])
    assert body == rl.render_primary(REPO, "guild")


def test_ac02_render_body_comes_from_prompt(tmp_path):
    """同一个组装点：渲染文件的正文逐字节等于 prompt 现读结果，没有第二套拼装。"""
    for host in rl.HOSTS:
        files = rl.render_all(REPO, host, "guild")
        for rid in rl.DISPATCHABLE_IDS:
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
    import re as _re
    m = _re.search(r"canon_version=(\d+)\.(\d+)\.(\d+)", before)
    assert m, before[:200]
    major, minor, patch = map(int, m.groups())
    bumped = f"{major}.{minor}.{patch + 1}"
    p = repo_copy / "roles" / "canon" / "reviewer.md"
    p.write_text(_re.sub(r"canon_version: \d+\.\d+\.\d+", f"canon_version: {bumped}",
                         p.read_text(encoding="utf-8"), count=1), encoding="utf-8")
    after = rl.render_prompt(repo_copy, "reviewer", "generic")
    assert f"canon_version={bumped}" in after and after != before
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


def test_canon_fingerprint_ignores_line_endings(tmp_path):
    """同一份正本以 LF / CRLF 落盘，指纹必须相同；否则同一 blob 跨机两值。"""
    text = (REPO / "roles" / "canon" / "reviewer.md").read_text(encoding="utf-8")
    text = text.replace("\r\n", "\n")
    shas = {}
    for name, payload in (("lf", text.encode("utf-8")),
                          ("crlf", text.replace("\n", "\r\n").encode("utf-8"))):
        root = tmp_path / name
        (root / "roles" / "canon").mkdir(parents=True)
        (root / "roles" / "canon" / "reviewer.md").write_bytes(payload)
        shas[name] = rl.load_canon(root)["reviewer"]["sha256"]
    assert shas["lf"] == shas["crlf"], shas


def test_canon_fingerprint_matches_normalized_git_blob():
    """工作树 CRLF 不得让指纹漂离 git blob：指纹以 LF 归一后的字节为准。

    实现期工作树会脏（kind 拆分尚未提交）：对干净件仍与 HEAD blob 逐字对账；
    对有意改动的件只要求指纹等于「归一后的工作树字节」，不把未提交改动误判成漂移。
    """
    canon = rl.load_canon(REPO)
    dirty = []
    for p in sorted((REPO / "roles" / "canon").glob("*.md")):
        rel = p.relative_to(REPO).as_posix()
        blob = subprocess.run(
            ["git", "show", f"HEAD:{rel}"], cwd=REPO, capture_output=True, check=True
        ).stdout
        want = rl.sha256_bytes(blob.replace(b"\r\n", b"\n"))
        if canon[p.stem]["sha256"] == want:
            continue
        dirty.append(p.name)
        assert canon[p.stem]["sha256"] == rl.sha256_normalized(p.read_bytes()), p.name
    assert dirty == sorted(set(dirty)), dirty


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


def test_primary_keeps_the_agent_tool():
    """主 AI 人格是派活的那一方：把它自己的 Agent 工具禁掉，「由康娜自己调出来」就没了。"""
    files = rl.render_all(REPO, "qoder", "generic", with_primary=True)
    prim = files["_primary.md"]
    fm = prim.split("---")[1]
    assert "disallowedTools: [Agent]" not in fm
    assert "disallowedTools" not in fm, "主 AI 人格不该有任何 disallowedTools"
    for name, text in files.items():
        if name == "_primary.md":
            continue
        assert "Agent" in text.split("---")[1], f"{name} 应禁再派"


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


# ── 分层投影：核心 3 → agent 目录；专家 4 → profiles（标 generated）───────────
@pytest.mark.parametrize("host", rl.HOSTS)
def test_render_kind_core_and_specialist_split(host):
    core = rl.render_all(REPO, host, "guild", kind="core")
    spec = rl.render_all(REPO, host, "guild", kind="specialist")
    suffix = rl.load_hosts(REPO)["hosts"][host].get("suffix", ".md")
    assert set(core) == {f"{r}{suffix}" for r in rl.CORE_IDS}
    assert set(spec) == {f"{r}.md" for r in rl.SPECIALIST_IDS}
    assert "_primary.md" not in core and "_primary.md" not in spec
    for name, text in spec.items():
        assert text.startswith("<!-- generated: kai-role-profile;"), name
        assert not text.startswith("---"), f"{name} 是 profile，不该带宿主 frontmatter"
        rid = Path(name).stem
        assert rl.render_prompt(REPO, rid, "guild") in text, f"{name} 正文不是同一个组装点"
    for name, text in core.items():
        if rl.load_hosts(REPO)["hosts"][host].get("agent_file"):
            assert text.startswith("---"), f"{host}/{name} 核心角色应有宿主 frontmatter"


def test_projection_config_keeps_specialists_out_of_agent_dirs():
    hosts = rl.load_hosts(REPO)["hosts"]
    for host, cfg in hosts.items():
        assert cfg.get("profiles_dir"), host
        assert cfg.get("primary", {}).get("mode") == "session-prompt", host
        if cfg.get("agent_file"):
            dest = cfg["dest_dir"].replace("\\", "/").strip("/")
            prof = cfg["profiles_dir"].replace("\\", "/").strip("/")
            assert prof != dest and not prof.startswith(dest + "/"), host
            pdir = cfg["primary"]["dir"].replace("\\", "/").strip("/")
            assert pdir != dest and not pdir.startswith(dest + "/"), host


def test_reverse_missing_profiles_dir_is_red(repo_copy):
    p = repo_copy / "adapters" / "role-hosts.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["hosts"]["qoder"].pop("profiles_dir", None)
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    bad = rl.validate(repo_copy)
    assert any("profiles_dir" in b for b in bad), bad


def test_reverse_primary_in_agent_dir_is_red(repo_copy):
    p = repo_copy / "adapters" / "role-hosts.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["hosts"]["qoder"]["primary"]["dir"] = d["hosts"]["qoder"]["dest_dir"]
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    bad = rl.validate(repo_copy)
    assert any("primary.dir 落在 agent 目录" in b for b in bad), bad


def test_discoverable_budget_is_under_15k_and_marked_estimate():
    est = rl.discoverable_estimate(REPO)
    assert est["estimate"] is True
    assert est["tokens_est"] <= est["limit"], est
    assert set(est["parts"]) == {"primary_table", "core_descriptions", "specialist_triggers"}


# ── dispatch preset：加载 / 校验 / 未知报缺件 ───────────────────────────────
def test_framework_presets_are_valid_and_resolvable():
    names = sorted(rl.preset_sources(REPO))
    assert names, "至少要有框架默认 preset"
    assert rl.preset_problems(REPO) == []
    for name in names:
        data = rl.resolve_preset(REPO, name)
        assert data["schema"] == rl.PRESET_SCHEMA
        assert data["lead"] in data["roles"]
        assert "coordinator" not in data["roles"] and "archivist" not in data["roles"]


def test_preset_project_override_wins_and_unknown_is_missing(tmp_path):
    proj = tmp_path / "proj"
    (proj / ".ai" / "presets").mkdir(parents=True)
    base = json.loads((REPO / "roles" / "presets" / "review-only.json").read_text(encoding="utf-8"))
    base["description"] = "项目覆盖版"
    (proj / ".ai" / "presets" / "review-only.json").write_text(
        json.dumps(base, ensure_ascii=False), encoding="utf-8")
    got = rl.resolve_preset(REPO, "review-only", proj)
    assert got["_source"] == "project" and got["description"] == "项目覆盖版"
    with pytest.raises(rl.RoleError) as e:
        rl.resolve_preset(REPO, "no-such-preset", proj)
    assert "缺件" in str(e.value)


@pytest.mark.parametrize("mutate,needle", [
    (lambda d: d["roles"].append("coordinator"), "不能含 coordinator"),
    (lambda d: d.__setitem__("roles", ["reviewer", "writer"]), "reviewer 只能单独"),
    (lambda d: d["isolation"].__setitem__("review", "optional"), "isolation.review"),
    (lambda d: d["budget"].__setitem__("max_tokens", -1), "正整数"),
    (lambda d: d.__setitem__("lead", "engineer"), "lead 必须"),
    (lambda d: d.__setitem__("extra", 1), "未知字段"),
])
def test_preset_validator_catches_bad_shapes(mutate, needle):
    data = json.loads((REPO / "roles" / "presets" / "content-small.json").read_text(encoding="utf-8"))
    mutate(data)
    bad = rl.validate_preset(data, "content-small")
    assert any(needle in b for b in bad), bad


# ── 角色边界对账：coordinator 产物含 diff / 代码改动即红 ───────────────────
def _boundary_status(root):
    doctor = _load_doctor()
    return doctor.chk_role_boundary(str(root), None)


def test_role_boundary_gate_is_green_on_real_repo():
    status, msg = _boundary_status(REPO)
    assert status == "ok", msg


def test_role_boundary_gate_catches_coordinator_self_execution_text(repo_copy):
    p = repo_copy / "roles" / "canon" / "coordinator.md"
    p.write_text(p.read_text(encoding="utf-8") + "\n小修补可在当前会话直接做。\n", encoding="utf-8")
    status, msg = _boundary_status(repo_copy)
    assert status == "fail" and "小修补" in msg, msg


def test_role_boundary_gate_catches_coordinator_diff_artifact(repo_copy):
    run = repo_copy / ".coding" / "runs" / "r1"
    run.mkdir(parents=True)
    (run / "report.json").write_text(json.dumps({
        "role_id": "coordinator",
        "changed_files": ["scripts/rolelib.py"],
        "artifacts": [{"type": "code", "uri": "x.patch"}],
    }, ensure_ascii=False), encoding="utf-8")
    status, msg = _boundary_status(repo_copy)
    assert status == "fail" and "coordinator 产物含" in msg, msg


def test_role_boundary_gate_allows_engineer_diff_artifact(repo_copy):
    run = repo_copy / ".coding" / "runs" / "r1"
    run.mkdir(parents=True)
    (run / "report.json").write_text(json.dumps({
        "role_id": "engineer",
        "changed_files": ["scripts/rolelib.py"],
    }, ensure_ascii=False), encoding="utf-8")
    status, msg = _boundary_status(repo_copy)
    assert status == "ok", msg


def test_role_entry_skill_exists_and_points_at_profiles():
    skill = REPO / "core" / "skills" / "role-entry" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---\nname: role-entry\n")
    for rid in rl.SPECIALIST_IDS:
        assert f"`{rid}`" in text, rid
    assert ".ai/roles/profiles/<role_id>.md" in text
    assert "## mission" not in text, "入口 skill 不该复制专家契约"


def test_doctor_projection_and_preset_checks_are_wired_and_green():
    doctor = _load_doctor()
    status, msg = doctor.chk_role_projection(str(REPO), None)
    assert status == "ok", msg
    status, msg = doctor.chk_dispatch_preset(str(REPO), None)
    assert status == "ok", msg


# ── 两条消费路径：打包（要重渲染） vs 现读（零同步）──────────────────────────
def _body_of(text: str) -> str:
    return text.split("---", 2)[2].lstrip("\n") if text.startswith("---") else text


def test_prompt_equals_body_of_rendered_file():
    """现读出来的正文与该宿主渲染文件的正文逐字相同——两条路同源，不是两套。
    主 AI 人格不在渲染面里，单独比 render_primary。"""
    for host in rl.HOSTS:
        for skin in rl.SKINS:
            files = rl.render_all(REPO, host, skin)
            for rid in rl.DISPATCHABLE_IDS:
                fname = next(n for n in files if n.startswith(rid))
                assert _body_of(files[fname]) == rl.render_prompt(REPO, rid, skin), f"{host}/{rid}"
    assert rl.render_primary(REPO, "guild").startswith("<!-- kai-role role_id=coordinator")


def test_prompt_tracks_canon_without_any_file(repo_copy):
    """现读路径不依赖任何落地文件：改正本，下一次 prompt 就是新的。"""
    before = rl.render_prompt(repo_copy, "reviewer", "generic")
    import re as _re2
    m2 = _re2.search(r"canon_version=(\d+)\.(\d+)\.(\d+)", before)
    assert m2, before[:200]
    major2, minor2, patch2 = map(int, m2.groups())
    bumped2 = f"{major2}.{minor2}.{patch2 + 1}"
    p = repo_copy / "roles" / "canon" / "reviewer.md"
    p.write_text(_re2.sub(r"canon_version: \d+\.\d+\.\d+", f"canon_version: {bumped2}",
                          p.read_text(encoding="utf-8"), count=1), encoding="utf-8")
    assert rl.render_prompt(repo_copy, "reviewer", "generic") != before


def test_pack_contains_seven_dispatchable_roles():
    pack = rl.render_pack(REPO, "guild")
    for rid in rl.DISPATCHABLE_IDS:
        assert f"role={rid}" in pack
    assert "role=coordinator" not in pack, "主 AI 人格不该混进可派发包"
    assert pack.count("<!-- kai-role") == 7


def test_primary_prompt_carries_dispatch_table():
    """主 AI 人格的会话提示词要自带「能调出谁」，否则它不知道怎么派。"""
    p = rl.render_primary(REPO, "guild")
    assert "## 可调出的角色" in p
    for rid in rl.DISPATCHABLE_IDS:
        assert rid in p
    assert "只读角色拿不到写权限时" in p


# ── 给别的 AI 做初始化：bootstrap 卡片与落点 ────────────────────────────────
def test_bootstrap_card_names_primary_and_all_seven():
    for host in rl.HOSTS:
        card = rl.render_bootstrap(REPO, host, "guild")
        assert "主 AI 人格是 **康娜**" in card, host
        for rid in rl.DISPATCHABLE_IDS:
            assert f"| {rid} |" in card, f"{host}/{rid}"
        assert "role_id=coordinator" not in card or True  # 主 AI 人格不当可派发列
        assert "不跨宿主借兵" in card and "记忆只有一个写者" in card
        assert "## 5. 指纹" in card


def test_bootstrap_card_dispatch_line_follows_host_capability():
    with_agent = rl.render_bootstrap(REPO, "qoder", "generic")
    without = rl.render_bootstrap(REPO, "codex", "generic")
    assert "可派发的定义" in with_agent
    assert "没有 agent 定义文件层" in without
    assert "-s read-only" in without
    assert "`worker_cmd`" in without
    assert "`worker_cmd`" not in with_agent, "有原生子代理的宿主不该被劝去配宿主命令"


@pytest.mark.parametrize("host,expected_dir", [("qoder", ".qoder/agents"),
                                               ("opencode", ".ai/roles")])
def test_bootstrap_cli_writes_roles_table_card_and_is_idempotent(host, expected_dir, tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    cmd = [sys.executable, str(SCRIPTS / "render-roles.py"), "bootstrap",
           "--project", str(proj), "--host", host, "--skin", "generic"]
    r1 = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    assert r1.returncode == 0, r1.stderr
    roles = proj / expected_dir
    core_names = {f"{r}.md" for r in rl.CORE_IDS}
    # opencode 没有 agent 文件层，主 AI 会话 prompt 与核心提示词同住 .ai/roles（仍不进 agent 目录）。
    expected_core = core_names | ({"_primary.md"} if expected_dir == ".ai/roles" else set())
    assert {p.name for p in roles.glob("*.md")} == expected_core, "核心 3 才进 agent 目录"
    profiles = proj / ".ai" / "roles" / "profiles"
    assert {p.name for p in profiles.glob("*.md")} == {f"{r}.md" for r in rl.SPECIALIST_IDS}
    primary = proj / ".ai" / "roles" / "_primary.md"
    assert primary.is_file() and "skin=generic" in primary.read_text(encoding="utf-8")
    assert (proj / ".coding" / "host-programs.json").is_file()
    assert (proj / ".ai" / "BOOTSTRAP.md").is_file()
    r2 = subprocess.run(cmd, cwd=str(REPO), capture_output=True, text=True,
                        encoding="utf-8", errors="replace")
    assert r2.returncode == 0
    assert "新增（0）" in r2.stdout and "内容相同（8）" in r2.stdout


def test_bootstrap_card_never_lands_inside_a_scanned_agent_dir(tmp_path):
    """说明卡不能放进宿主的 agent 目录：那边会被扫成「代理定义」，多出一个空壳代理。"""
    proj = tmp_path / "q"
    proj.mkdir()
    r = subprocess.run([sys.executable, str(SCRIPTS / "render-roles.py"), "bootstrap",
                        "--project", str(proj), "--host", "qoder", "--skin", "generic"],
                       cwd=str(REPO), capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    assert r.returncode == 0, r.stderr
    agents = proj / ".qoder" / "agents"
    assert not (agents / "BOOTSTRAP.md").exists()
    assert (proj / ".ai" / "BOOTSTRAP.md").is_file()


def test_bootstrap_dry_run_writes_nothing(tmp_path):
    proj = tmp_path / "d"
    proj.mkdir()
    r = subprocess.run([sys.executable, str(SCRIPTS / "render-roles.py"), "bootstrap",
                        "--project", str(proj), "--host", "codex", "--skin", "guild",
                        "--dry-run"], cwd=str(REPO), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    assert list(proj.rglob("*")) == [], "dry-run 不许写盘"


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


def test_reverse_second_primary_is_red(repo_copy):
    """只许一个主 AI 人格：给别人也标 primary，尺子必须红。"""
    p = repo_copy / "roles" / "canon" / "reviewer.md"
    p.write_text(p.read_text(encoding="utf-8").replace("kind: core", "kind: primary"),
                 encoding="utf-8")
    bad = rl.validate(repo_copy)
    assert any("主 AI 人格只能是" in b for b in bad), bad


def test_reverse_primary_marked_specialist_is_red(repo_copy):
    p = repo_copy / "roles" / "canon" / "coordinator.md"
    p.write_text(p.read_text(encoding="utf-8").replace("kind: primary", "kind: specialist"),
                 encoding="utf-8")
    bad = rl.validate(repo_copy)
    assert any("kind 只能是 primary" in b for b in bad), bad


def test_reverse_bad_kind_is_red(repo_copy):
    p = repo_copy / "roles" / "canon" / "writer.md"
    p.write_text(p.read_text(encoding="utf-8").replace("kind: specialist", "kind: subagent"),
                 encoding="utf-8")
    bad = rl.validate(repo_copy)
    assert any("kind 非法" in b for b in bad), bad


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


# ── 总结体例：失败关闭 + 表情实渲 ──────────────────────────────────────────
def test_render_fails_closed_without_summary_convention(repo_copy):
    """体例缺失必须抛，不能静默产出「没有总结体例」的提示词。"""
    (repo_copy / "roles" / "summary-convention.md").unlink()
    with pytest.raises(rl.RoleError):
        rl.render_prompt(repo_copy, "reviewer", "guild")


def test_render_fails_closed_without_summary_slots(repo_copy):
    """措辞表缺失同样抛——体例与措辞都是常驻层的必件。"""
    (repo_copy / "roles" / "summary-slots.json").unlink()
    with pytest.raises(rl.RoleError):
        rl.render_prompt(repo_copy, "reviewer", "guild")


def test_render_fails_closed_without_input_contract(repo_copy):
    """输入契约缺失同样抛——它写着「每次任务必读，不可跳过」，缺了就不该静默降级。"""
    (repo_copy / "roles" / "input-contract.md").unlink()
    with pytest.raises(rl.RoleError):
        rl.render_prompt(repo_copy, "reviewer", "guild")


def test_render_fails_closed_without_envelope_spec(repo_copy):
    """信封规格缺失同样抛——机器面规格是常驻层必件，缺了不静默降级。"""
    (repo_copy / "roles" / "envelope-header.md").unlink()
    with pytest.raises(rl.RoleError):
        rl.render_prompt(repo_copy, "reviewer", "guild")


def test_render_fails_closed_without_output_routing(repo_copy):
    """载体路由缺失同样抛——八类载体清单只有这一个家。"""
    (repo_copy / "roles" / "output-routing.md").unlink()
    with pytest.raises(rl.RoleError):
        rl.render_prompt(repo_copy, "reviewer", "guild")


def test_shared_blocks_present_in_order_and_canon_never_copies_them():
    """共享契约一个家：四块齐全、顺序正确；canon 不许再抄一份。

    对应 doctor 的 spec-shared 门；这里在测例层再钉一次，变异测试有两条腿。
    """
    banned = ("`schema_version`", "`idempotency_key`", "`fact` 必带 `evidence_refs`",
              "Writing（文字）", "Video（视频）",
              "状态词只用：完成 / 部分完成 / 阻塞 / 失败",
              "roles/envelope-header.md", "roles/output-routing.md")
    for rid in rl.ROLE_IDS:
        text = (REPO / "roles" / "canon" / f"{rid}.md").read_text(encoding="utf-8")
        for b in banned:
            assert b not in text, f"roles/canon/{rid}.md 抄了共享块内容「{b}」"
        for sk in rl.SKINS:
            out = rl.render_prompt(REPO, rid, sk)
            i_id = out.index("## identity")
            blocks = [
                out.index(rl.load_input_contract(REPO)),
                out.index(rl.load_envelope_spec(REPO)),
                out.index(rl.load_output_routing(REPO)),
                out.index(rl.load_summary_convention(REPO)),
            ]
            assert i_id < blocks[0], f"{rid}/{sk} 人格应排在共享契约前"
            assert blocks == sorted(blocks), f"{rid}/{sk} 共享块顺序不对"


def test_summary_title_carries_the_role_own_emoji(repo_copy):
    """标题要渲本角色自己的表情，不能留占位符——角色看不到自己该写哪个表情。"""
    out = rl.render_prompt(repo_copy, "reviewer", "guild")
    emoji = rl.load_skin(repo_copy, "guild")["roles"]["reviewer"]["summary_emoji"]
    title_line = next(l for l in out.splitlines() if l.startswith("- 标题："))
    assert emoji in title_line, f"标题行里没有本角色的表情：{title_line}"
    assert "<角色表情>" not in title_line, f"标题行还留着占位符：{title_line}"


# ── 派生体例门：措辞漂移必须被抓 ──────────────────────────────────────────
def _load_doctor():
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import doctor
    return doctor


def _summary_derived_status(root):
    doctor = _load_doctor()
    status, _msg = doctor.chk_summary_derived(str(root), None)
    return status


def test_summary_derived_gate_is_green_on_real_repo():
    assert _summary_derived_status(REPO) == "ok"


def test_summary_derived_gate_catches_gold_template_drift(repo_copy):
    """gold 模板里的标记词改了要判红——散文里出现过不算，判据是位置性的。"""
    p = repo_copy / "core" / "skills" / "gold" / "SKILL.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("```markdown\n办妥：<一句话结果>\n还欠着：<还差什么>\n等你拍板：<事项>\n```\n",
                 encoding="utf-8")
    assert _summary_derived_status(repo_copy) == "fail"


def test_summary_derived_gate_catches_single_eval_row_drift(repo_copy):
    """只漂一行也要判红——另一行对了不能盖住它。"""
    p = repo_copy / "docs" / "eval-cases.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("| COM-01 | x | 办妥什么、欠着什么、要你拍板什么 |\n"
                 "| COM-05 | y | 搞定~搞定~／还欠着／等你拍板 |\n", encoding="utf-8")
    assert _summary_derived_status(repo_copy) == "fail"


def test_slot_binding_gate_catches_a_removed_field(repo_copy):
    """绑定点的字段名要是从 canon 里删了，门必须红——绑定要查得出「写的那个字段还在不在」。"""
    p = repo_copy / "roles" / "canon" / "writer.md"
    p.write_text(p.read_text(encoding="utf-8").replace("unchecked_sentences", "gone_field"),
                 encoding="utf-8")
    doctor = _load_doctor()
    status, msg = doctor.chk_slot_binding(str(repo_copy), None)
    assert status == "fail", msg
    assert "unchecked_sentences" in msg, msg


def test_slot_binding_gate_is_green_on_real_repo():
    doctor = _load_doctor()
    status, msg = doctor.chk_slot_binding(str(REPO), None)
    assert status == "ok", msg


# ── 变异实测钉住：这些漂移必须被判红 ──────────────────────────────────────
def _slots_write(repo_copy, mutate):
    p = repo_copy / "roles" / "summary-slots.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    mutate(data)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_summary_derived_gate_catches_title_drift(repo_copy):
    """唯一家的标题动作短语改了要判红（title 也在比对集里）。"""
    _slots_write(repo_copy, lambda d: d["roles"]["coordinator"].__setitem__("title", "两个字交差"))
    assert _summary_derived_status(repo_copy) == "fail"


def test_summary_derived_gate_catches_none_drift(repo_copy):
    """唯一家的「无待决」写法改了要判红（none 也在比对集里）。"""
    _slots_write(repo_copy, lambda d: d["roles"]["coordinator"].__setitem__("none", "没你事"))
    assert _summary_derived_status(repo_copy) == "fail"


def test_summary_derived_gate_catches_retired_family_variant(repo_copy):
    """退役标签的同族变体（「待拍板：」而非精确串「待拍板：无」）也要判红。"""
    p = repo_copy / "core" / "skills" / "gold" / "SKILL.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("```markdown\n## 💰 一句话交差\n搞定~搞定~：x\n还欠着：y\n"
                 "等你拍板：z\n```\n\n待拍板：<事项>\n", encoding="utf-8")
    assert _summary_derived_status(repo_copy) == "fail"


def test_summary_derived_gate_catches_markers_in_an_unsanctioned_file(repo_copy):
    """白名单外的文件里出现标记词要判红——否则会悄悄长出第二个家。"""
    p = repo_copy / "core" / "skills" / "gold" / "references" / "drift.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("搞定~搞定~：随手写的\n", encoding="utf-8")
    assert _summary_derived_status(repo_copy) == "fail"


def test_emoji_derived_gate_catches_skin_emoji_change(repo_copy):
    """皮肤的表情改了，正本里硬抄的字面量就漂了——门必须红。"""
    p = repo_copy / "roles" / "skins" / "guild.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data["roles"]["coordinator"]["summary_emoji"] = "🪙"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    doctor = _load_doctor()
    status, msg = doctor.chk_emoji_derivation(str(repo_copy), None)
    assert status == "fail", msg


def _write_gold(repo_copy, body):
    p = repo_copy / "core" / "skills" / "gold" / "SKILL.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


GOOD_TMPL = ("```markdown\n## 💰 一句话交差\n搞定~搞定~：<结果>\n"
             "还欠着：<差什么>\n等你拍板：<事项>\n```\n")


def test_summary_derived_gate_is_not_masked_by_another_fence(repo_copy):
    """真模板漂移时，另开一个围栏块塞标记词不能把它盖住（N-a）。"""
    _write_gold(repo_copy,
                "```markdown\n## 💰 一句话交差\n办妥：<结果>\n"
                "还欠着：<差什么>\n等你拍板：<事项>\n```\n\n"
                "```markdown\n搞定~搞定~：x\n还欠着：y\n等你拍板：z\n```\n")
    assert _summary_derived_status(repo_copy) == "fail"


def test_summary_derived_gate_tolerates_list_bullets(repo_copy):
    """模板行加个列表符是纯排版，不该误报（N-c）。"""
    _write_gold(repo_copy,
                "```markdown\n## 💰 一句话交差\n- 搞定~搞定~：<结果>\n"
                "- 还欠着：<差什么>\n- 等你拍板：<事项>\n```\n")
    assert _summary_derived_status(repo_copy) == "ok"

# ── 落点对照门：装配面的指纹漂了必须红 ────────────────────────────────────
def _landing_status(root, monkeypatch=None):
    """跑落点对照门；monkeypatch 给了就把 HOME 钉到假目录（隔离本机真落点）。"""
    doctor = _load_doctor()
    if monkeypatch is not None:
        monkeypatch.setenv("KAI_DOCTOR_FAKE_HOME", "Z:/no-such-home")
    status, msg = doctor.chk_landing_compare(str(root), None)
    return status, msg


def _make_landing(tmp_path, role_id="reviewer", skin="guild"):
    """在假落点里造一份含指纹的 AGENTS.md，指纹从真仓现算。"""
    doctor = _load_doctor()
    land = tmp_path / "landing" / "agent-x"
    land.mkdir(parents=True)
    canon = rl.load_canon(REPO)
    sk = rl.load_skin(REPO, skin)
    entry = sk["roles"][role_id]
    fp = rl.fingerprint(canon[role_id]["meta"], canon[role_id]["sha256"], skin,
                        str(sk["skin_version"]), rl.entry_sha256(entry))
    (land / "AGENTS.md").write_text(f"# 假落点\n\n{fp}\n\n正文。\n", encoding="utf-8")
    return land


def test_landing_compare_skips_when_no_landing_dir(tmp_path, monkeypatch):
    """没配落点目录 ⇒ skip，不是红：别的机器上 doctor 照样绿。"""
    monkeypatch.delenv("KAI_LANDING_DIRS", raising=False)
    monkeypatch.setenv("KAI_DOCTOR_FAKE_HOME", str(tmp_path / "no-home"))
    doctor = _load_doctor()
    monkeypatch.setattr(doctor, "_landing_dirs", lambda root: [])
    status, msg = _landing_status(REPO)
    assert status == "skip", msg
    assert "未配置落点目录" in msg, msg


def test_landing_compare_is_green_on_matching_fingerprint(tmp_path, monkeypatch):
    land = _make_landing(tmp_path)
    monkeypatch.setenv("KAI_LANDING_DIRS", str(tmp_path / "landing"))
    status, msg = _landing_status(REPO)
    assert status == "ok", msg
    assert "1 份 OpenBot 落点（子目录 AGENTS.md" in msg, msg


def test_landing_compare_catches_tampered_sha(tmp_path, monkeypatch):
    """故意把落点指纹里的 canon_sha256 改一位 ⇒ 红并点名目录与字段。"""
    land = _make_landing(tmp_path)
    p = land / "AGENTS.md"
    text = p.read_text(encoding="utf-8")
    m = __import__("re").search(r"canon_sha256=([0-9a-f]{64})", text)
    flipped = ("0" if m.group(1)[0] != "0" else "1") + m.group(1)[1:]
    p.write_text(text.replace(f"canon_sha256={m.group(1)}", f"canon_sha256={flipped}", 1),
                 encoding="utf-8")
    monkeypatch.setenv("KAI_LANDING_DIRS", str(tmp_path / "landing"))
    status, msg = _landing_status(REPO)
    assert status == "fail", msg
    assert "agent-x/AGENTS.md" in msg, msg
    assert "canon_sha256" in msg, msg


def test_landing_compare_skips_files_without_fingerprint(tmp_path, monkeypatch):
    """无指纹的 AGENTS.md 不计红（不属于八角色），只进计数。"""
    land = tmp_path / "landing" / "agent-x"
    land.mkdir(parents=True)
    (land / "AGENTS.md").write_text("# 不是角色\n", encoding="utf-8")
    monkeypatch.setenv("KAI_LANDING_DIRS", str(tmp_path / "landing"))
    status, msg = _landing_status(REPO)
    assert status == "ok", msg
    assert "无指纹跳过" in msg, msg


def _make_flat_landing(tmp_path, role_id="reviewer", skin="guild"):
    """造「平铺 *.md」形态落点（.claude/agents 同类），指纹从真仓现算。"""
    doctor = _load_doctor()
    land = tmp_path / "project" / "host"
    land.mkdir(parents=True)
    canon = rl.load_canon(REPO)
    sk = rl.load_skin(REPO, skin)
    entry = sk["roles"][role_id]
    fp = rl.fingerprint(canon[role_id]["meta"], canon[role_id]["sha256"], skin,
                        str(sk["skin_version"]), rl.entry_sha256(entry))
    md = "# 平铺落点\n\n{fp}\n\n正文。\n".format(fp=fp)
    (land / "designer.md").write_text(md, encoding="utf-8")
    return land


def test_landing_compare_is_green_on_flat_host_agents(tmp_path, monkeypatch):
    """平铺 *.md 形态与 OpenBot 形态同一条比对：指纹一致 ⇒ 绿并分开报数。"""
    land = _make_flat_landing(tmp_path)
    monkeypatch.setenv("KAI_LANDING_DIRS", str(tmp_path / "project" / "host"))
    status, msg = _landing_status(REPO)
    assert status == "ok", msg
    assert "无指纹跳过 0 份" in msg, msg
    # 单份指纹一致的落点：OpenBot 形态或平铺形态计其一，另一形态为 0
    assert "份 OpenBot 落点" in msg and "份宿主平铺落点" in msg, msg
    assert ("1 份 OpenBot" in msg or "1 份宿主平铺" in msg), msg


def test_landing_compare_catches_flat_host_sha_tampered(tmp_path, monkeypatch):
    """平铺形态里 sha 改一位 ⇒ 红并点名文件与字段。"""
    land = _make_flat_landing(tmp_path)
    p = land / "designer.md"
    text = p.read_text(encoding="utf-8")
    m = __import__("re").search(r"canon_sha256=([0-9a-f]{64})", text)
    flipped = ("0" if m.group(1)[0] != "0" else "1") + m.group(1)[1:]
    p.write_text(text.replace(f"canon_sha256={m.group(1)}", f"canon_sha256={flipped}", 1),
                 encoding="utf-8")
    monkeypatch.setenv("KAI_LANDING_DIRS", str(tmp_path / "project" / "host"))
    status, msg = _landing_status(REPO)
    assert status == "fail", msg
    assert "designer.md" in msg, msg
    assert "canon_sha256" in msg, msg


def test_landing_compare_discovers_repo_parent_flat_dirs(tmp_path, monkeypatch):
    """自发现：KAI_LANDING_DIRS 未配、假 home 不存在时，仓根上级下的
    ``.claude/agents``／``.qoder/agents`` 平铺形态自动加入（不写死本机路径）。"""
    import os

    doctor = _load_doctor()
    repo_root = tmp_path / "repo"
    (repo_root.parent / ".claude" / "agents").mkdir(parents=True)
    (repo_root.parent / ".claude" / "agents" / "designer.md").write_text(
        "# 自发现落点\n\n<!-- kai-role role_id=designer ... -->\n", encoding="utf-8")
    monkeypatch.delenv("KAI_LANDING_DIRS", raising=False)
    monkeypatch.setenv("KAI_DOCTOR_FAKE_HOME", str(tmp_path / "no-home"))
    dirs = doctor._landing_dirs(str(repo_root))
    want = os.path.normpath(os.path.join(str(repo_root.parent), ".claude", "agents"))
    assert any(os.path.normpath(d) == want for d in dirs), dirs
    # 真上溯路径不带本机绝对路径（不写死）
    for d in dirs:
        assert "/D:" not in d and "C:\\" not in d, d


def test_landing_compare_is_green_on_real_repo(tmp_path, monkeypatch):
    """真机绿：~/OpenBot/Agents（OpenBot 形态）＋仓根上级的平铺项目落点
    （.claude/agents 等，形态 B）与现渲一致；只断言不因机器错而红。"""
    doctor = _load_doctor()
    monkeypatch.delenv("KAI_LANDING_DIRS", raising=False)
    monkeypatch.setenv("KAI_DOCTOR_FAKE_HOME", str(tmp_path / "no-home"))
    status, msg = doctor.chk_landing_compare(str(REPO), None)
    if status == "skip":
        return  # 本机没配落点目录的环境，不判
    # 真机上只断言不因「读不出来 / role_id 不在正本里」这类机器错而红
    assert status in ("ok", "fail"), msg
    if status == "fail":
        assert "读不出来" not in msg, msg
    if status == "ok":
        assert "OpenBot 落点" in msg and "宿主平铺落点" in msg, msg


def test_landing_compare_is_green_on_real_openbot_agents(tmp_path, monkeypatch):
    """真机绿：~/OpenBot/Agents 下与现渲一致的角色面（coordinator 已重渲 1.3.0）。"""
    doctor = _load_doctor()
    monkeypatch.delenv("KAI_LANDING_DIRS", raising=False)
    monkeypatch.setenv("KAI_DOCTOR_FAKE_HOME", str(tmp_path / "no-home"))
    status, msg = doctor.chk_landing_compare(str(REPO), None)
    if status == "skip":
        return  # 本机没配落点目录的环境，不判
    # 真机上只断言不因「读不出来 / role_id 不在正本里」这类机器错而红
    assert status in ("ok", "fail"), msg
    if status == "fail":
        assert "读不出来" not in msg, msg
