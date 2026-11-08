"""角色实例入口归属的测例（Issue #7 AC-05）。

判据实现住 engine/coding/hostguard.py，接线点是 engine/coding/auto.py 的 _host_run。
宿主→程序名的映射是**数据**（adapters/role-hosts.json → 项目侧 .coding/host-programs.json），
内核不写宿主名（engine/tests/test_purity.py 守着）。

断的是「拦住了没」，不是「有没有调用 guard」：合法路径要真的能派出去，
非法路径要在**起进程之前**就炸。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
for p in (str(REPO), str(REPO / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import engine.coding.auto as auto  # noqa: E402
import engine.coding.hostguard as hg  # noqa: E402
import rolelib  # noqa: E402

TABLE = {h: frozenset(v) for h, v in rolelib.host_programs(REPO).items()}


# ── 映射表来自数据，不是写死的 ──────────────────────────────────────────────
def test_table_comes_from_projection_and_covers_six_hosts():
    assert set(TABLE) == set(rolelib.HOSTS)
    assert "codex" in TABLE["codex"]
    assert "agent" in TABLE["cursor"]


def test_table_written_by_emit_table_round_trips(tmp_path):
    table = rolelib.host_programs(REPO)
    d = tmp_path / ".coding"
    d.mkdir()
    (d / "host-programs.json").write_text(json.dumps(table), encoding="utf-8")
    assert hg.load_table(tmp_path) == {h: frozenset(v) for h, v in table.items()}


def test_missing_table_means_unverified_not_silent_ok(tmp_path):
    assert hg.load_table(tmp_path) == {}
    verdict, why = hg.check("codex exec", "qoder", {})
    assert verdict == hg.UNVERIFIED
    assert "host-unverified" in why


# ── 程序名归属 ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("cmd,expect", [
    ("codex exec -s read-only --json", "codex"),
    ("C:\\tools\\codex.exe exec", "codex"),
    ("/usr/local/bin/opencode run", "opencode"),
    ("claude -p 'x'", "claude"),
    ("./qoder.cmd --agent kanna", "qoder"),
    ("copilot -p 'x' --agent reviewer", "copilot"),
    ("agent -p 'x' --mode=ask", "agent"),
    ("", ""),
])
def test_program_of(cmd, expect):
    assert hg.program_of(cmd) == expect


def test_owner_of_known_and_unknown():
    assert hg.owner_of("codex", TABLE) == "codex"
    assert hg.owner_of("agent", TABLE) == "cursor"
    assert hg.owner_of("python", TABLE) is None
    assert hg.owner_of("", TABLE) is None


# ── 裁决矩阵 ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("host,cmd,verdict", [
    ("qoder", "qoder --agent kanna", hg.OK),
    ("qoder", "codex exec -s read-only", hg.BLOCK),
    ("qoder", "opencode run", hg.BLOCK),
    ("codex", "codex exec -s workspace-write", hg.OK),
    ("codex", "claude -p x", hg.BLOCK),
    ("opencode", "opencode run", hg.OK),
    ("claude", "claude --agent reviewer", hg.OK),
    ("cursor", "agent -p x", hg.OK),
    ("qoder", "python scripts/x.py", hg.OK),
    ("", "codex exec", hg.UNVERIFIED),
    ("qoder", "", hg.OK),
])
def test_check_matrix(host, cmd, verdict):
    got, why = hg.check(cmd, host, TABLE)
    assert got == verdict, why
    assert why


def test_block_message_names_both_hosts():
    verdict, why = hg.check("codex exec", "qoder", TABLE)
    assert verdict == hg.BLOCK
    assert "qoder" in why and "codex" in why


def test_assert_raises_on_block_only():
    with pytest.raises(hg.CrossHostError):
        hg.assert_own_host("codex exec", "qoder", TABLE)
    hg.assert_own_host("qoder --agent kanna", "qoder", TABLE)
    hg.assert_own_host("python x.py", "qoder", TABLE)
    hg.assert_own_host("codex exec", "", TABLE)


def test_receipt_shape():
    r = hg.receipt("codex exec", "qoder", TABLE)
    assert r["host"] == "qoder" and r["program"] == "codex"
    assert r["owner"] == "codex" and r["verdict"] == hg.BLOCK
    assert r["reason"]


# ── 当前宿主怎么读 ──────────────────────────────────────────────────────────
def test_current_host_reads_config_then_env(tmp_path, monkeypatch):
    monkeypatch.delenv("KAI_HOST", raising=False)
    assert hg.current_host(tmp_path) == ""
    (tmp_path / ".coding").mkdir()
    (tmp_path / ".coding" / "config.json").write_text(
        json.dumps({"host": "Qoder"}), encoding="utf-8")
    assert hg.current_host(tmp_path) == "qoder"
    monkeypatch.setenv("KAI_HOST", "codex")
    assert hg.current_host(tmp_path) == "qoder", "配置实例优先于环境变量"
    (tmp_path / ".coding" / "config.json").write_text("{}", encoding="utf-8")
    assert hg.current_host(tmp_path) == "codex"


# ── 接线：非法路径必须在起进程之前炸 ────────────────────────────────────────
@pytest.fixture()
def framed(tmp_path, monkeypatch):
    """把 _root() 指到假仓，配宿主＋映射表，并记录有没有真的起进程。"""
    (tmp_path / ".coding").mkdir()
    (tmp_path / ".coding" / "host-programs.json").write_text(
        json.dumps(rolelib.host_programs(REPO)), encoding="utf-8")

    def set_host(h):
        (tmp_path / ".coding" / "config.json").write_text(
            json.dumps({"host": h}), encoding="utf-8")

    calls = []

    def fake_run(argv, **kw):
        calls.append(argv)

        class R:
            returncode = 0
            stdout = ""
            stderr = ""
        return R()

    monkeypatch.setattr(auto, "_root", lambda: tmp_path)
    monkeypatch.setattr(auto.subprocess, "run", fake_run)
    return set_host, calls


def test_wiring_blocks_cross_host_before_spawn(framed):
    set_host, calls = framed
    set_host("qoder")
    with pytest.raises(hg.CrossHostError):
        auto._host_run("codex exec -s read-only", "任务卡", ".")
    assert calls == [], "被拦的命令不许起进程"


def test_wiring_allows_own_host_and_spawns(framed):
    set_host, calls = framed
    set_host("codex")
    auto._host_run("codex exec -s workspace-write {brief}", "任务卡", ".")
    assert len(calls) == 1
    assert calls[0][0] == "codex"
    assert calls[0][-1] == "任务卡", "占位符要换成提示词"


def test_wiring_with_unknown_host_proceeds(framed):
    set_host, calls = framed
    set_host("")
    auto._host_run("codex exec", "任务卡", ".")
    assert len(calls) == 1
    assert hg.receipt("codex exec", "", TABLE)["verdict"] == hg.UNVERIFIED


def test_wiring_allows_non_host_programs(framed):
    set_host, calls = framed
    set_host("qoder")
    auto._host_run("python -m my_worker {brief}", "任务卡", ".")
    assert len(calls) == 1


def test_reverse_matrix_is_not_all_green():
    """自证尺子不是恒绿：同一命令换宿主，裁决必须翻。"""
    assert hg.check("codex exec", "codex", TABLE)[0] == hg.OK
    assert hg.check("codex exec", "qoder", TABLE)[0] == hg.BLOCK


def test_kernel_source_has_no_vendor_names():
    """同一条纯净化判据在这里再守一遍：拦截逻辑不许把宿主名写进内核代码。"""
    src = (REPO / "engine" / "coding" / "hostguard.py").read_text(encoding="utf-8").lower()
    for vendor in ("claude", "codex", "opencode", "qoder", "cursor", "copilot", "gemini"):
        assert vendor not in src, f"hostguard.py 出现宿主名 {vendor}"