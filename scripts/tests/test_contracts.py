"""无人格契约投影的测例：六个可派发角色，只给契约、不给人物。

投影对象是「只做契约内的事、不面向用户」的执行子代理，所以正文必须：
有指纹、有一句身份、有输入契约与信封规格、有正本四块逐字；
没有 `## personality`、没有总结体例/措辞、没有载体路由。

判据实现住 scripts/rolelib.py，CLI 住 scripts/render-roles.py。
变异一律在 tmp_path 的副本上做，绝不改真仓。
"""

from __future__ import annotations

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
    """只拷契约投影要用的面：canon、skins、两份唯一家契约、投影表。"""
    (tmp_path / "roles").mkdir()
    shutil.copytree(REPO / "roles" / "canon", tmp_path / "roles" / "canon")
    shutil.copytree(REPO / "roles" / "skins", tmp_path / "roles" / "skins")
    for name in ("input-contract.md", "envelope-header.md"):
        shutil.copy2(REPO / "roles" / name, tmp_path / "roles" / name)
    (tmp_path / "adapters").mkdir()
    shutil.copy2(REPO / "adapters" / "role-hosts.json", tmp_path / "adapters" / "role-hosts.json")
    return tmp_path


# ── 契约包：七份、无主 AI 人格 ─────────────────────────────────────────────
def test_contract_pack_has_six_dispatchable_roles():
    pack = rl.render_contracts_pack(REPO, "guild")
    assert pack.count("<!-- kai-role") == 6, "契约包必须恰好六份（六个可派发角色）"
    for rid in rl.DISPATCHABLE_IDS:
        assert f"role={rid}" in pack, rid
        assert f"role_id={rid}" in pack, rid
    assert "role=coordinator" not in pack and "role_id=coordinator" not in pack, \
        "主 AI 人格不是子代理，不该进契约包"


def test_contract_prompt_rejects_the_primary_persona():
    """主 AI 人格面向用户、要调度；把它投成无人格契约等于把主会话变成执行腿。"""
    with pytest.raises(rl.RoleError):
        rl.render_contract_prompt(REPO, rl.PRIMARY_ID, "guild")


# ── 该有的都有：指纹、身份句、输入契约、信封规格、canon 四块逐字 ────────────
def test_contract_prompt_carries_fingerprint_identity_and_contracts():
    for skin in rl.SKINS:
        for rid in rl.DISPATCHABLE_IDS:
            out = rl.render_contract_prompt(REPO, rid, skin)
            assert out.startswith("<!-- kai-role"), f"{skin}/{rid} 缺指纹"
            assert f"role_id={rid}" in out and f"skin={skin}" in out
            name = rl.load_skin(REPO, skin)["roles"][rid]["name"]
            assert f"你是{name}执行子代理，只做契约内的事，不面向用户。" in out, f"{skin}/{rid} 身份句不对"
            assert rl.load_input_contract(REPO) in out, f"{skin}/{rid} 缺输入契约"
            assert rl.load_envelope_spec(REPO) in out, f"{skin}/{rid} 缺信封规格"


def test_contract_prompt_keeps_all_four_canon_blocks_verbatim():
    canon = rl.load_canon(REPO)
    for rid in rl.DISPATCHABLE_IDS:
        out = rl.render_contract_prompt(REPO, rid, "guild")
        body = canon[rid]["body"].lstrip("\n").rstrip("\n")
        assert body in out, f"{rid} 的四块没有逐字进契约投影"
        for block in rl.CANON_BLOCKS:
            assert f"## {block}" in out, f"{rid} 缺块 {block}"
        assert "## mission" in out


def test_contract_fingerprint_is_recomputable():
    canon = rl.load_canon(REPO)
    sk = rl.load_skin(REPO, "guild")
    out = rl.render_contract_prompt(REPO, "reviewer", "guild")
    head = next(line for line in out.splitlines() if line.startswith("<!-- kai-role"))
    assert f"canon_sha256={canon['reviewer']['sha256']}" in head
    assert f"skin_sha256={rl.entry_sha256(sk['roles']['reviewer'])}" in head
    assert f"canon_version={canon['reviewer']['meta']['canon_version']}" in head


# ── 该没有的都没有：人格、总结体例/措辞、载体路由 ──────────────────────────
def test_contract_prompt_has_no_personality():
    sk = rl.load_skin(REPO, "guild")
    for rid in rl.DISPATCHABLE_IDS:
        out = rl.render_contract_prompt(REPO, rid, "guild")
        assert "## personality" not in out, f"{rid} 混进了人格块"
        assert "## identity" not in out, f"{rid} 混进了人格块"
        assert sk["roles"][rid]["personality"].strip() not in out, f"{rid} 混进了人格正文"


def test_contract_prompt_has_no_summary_or_routing():
    conv = rl.load_summary_convention(REPO)
    routing = rl.load_output_routing(REPO)
    for rid in rl.DISPATCHABLE_IDS:
        out = rl.render_contract_prompt(REPO, rid, "guild")
        assert conv not in out, f"{rid} 混进了总结体例"
        assert routing not in out, f"{rid} 混进了载体路由"
        assert "## 我的总结措辞" not in out, f"{rid} 混进了总结措辞"
        assert "roles/output-routing.md" not in out


# ── 稳定与同源 ─────────────────────────────────────────────────────────────
def test_contract_render_is_stable():
    a = rl.render_contract_prompt(REPO, "engineer", "guild")
    b = rl.render_contract_prompt(REPO, "engineer", "guild")
    assert a == b, "同一正本两次现读必须逐字节相同"
    assert rl.render_contracts_pack(REPO, "guild") == rl.render_contracts_pack(REPO, "guild")


def test_contract_prompt_tracks_canon(repo_copy):
    """现读：改正本，下一次投影立刻跟着变，不需要重渲染任何文件。"""
    before = rl.render_contract_prompt(repo_copy, "engineer", "guild")
    p = repo_copy / "roles" / "canon" / "engineer.md"
    p.write_text(p.read_text(encoding="utf-8") + "\n多一行契约。\n", encoding="utf-8")
    after = rl.render_contract_prompt(repo_copy, "engineer", "guild")
    assert after != before and "多一行契约。" in after


def test_contract_fails_closed_without_contract_files(repo_copy):
    (repo_copy / "roles" / "input-contract.md").unlink()
    with pytest.raises(rl.RoleError):
        rl.render_contract_prompt(repo_copy, "engineer", "guild")


def test_contract_pack_is_the_six_prompts_in_order():
    pack = rl.render_contracts_pack(REPO, "guild")
    for rid in rl.DISPATCHABLE_IDS:
        assert rl.render_contract_prompt(REPO, rid, "guild") in pack, rid


# ── CLI：contracts --role / --pack / --json / 默认皮肤 guild ───────────────
def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPTS / "render-roles.py"), *args],
                          cwd=str(REPO), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def test_cli_contracts_pack_prints_content():
    r = _run("contracts", "--pack", "--skin", "guild")
    assert r.returncode == 0, r.stderr
    assert r.stdout.count("<!-- kai-role") == 6
    assert "## mission" in r.stdout and "## personality" not in r.stdout


def test_cli_contracts_role_defaults_to_guild_skin():
    r = _run("contracts", "--role", "reviewer")
    assert r.returncode == 0, r.stderr
    assert "skin=guild" in r.stdout
    assert "## mission" in r.stdout


def test_cli_contracts_json_is_machine_readable():
    r = _run("contracts", "--role", "reviewer", "--json")
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["skin"] == "guild" and data["role"] == "reviewer"
    assert data["chars"] == len(data["prompt"])
    assert "## personality" not in data["prompt"]


def test_cli_contracts_requires_role_or_pack():
    r = _run("contracts")
    assert r.returncode == 2
    assert "--role" in r.stderr and "--pack" in r.stderr
