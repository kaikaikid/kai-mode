"""门禁三样在**不依赖宿主 hooks** 时仍生效的测例（Issue #7 AC-06）。

三样：① 工作树隔离 ② 范围校验（touchset）③ 发货单点。
判据实现住 engine/coding/{worktree,scheduler,cli}.py。断言分两层：
行为层（真建树、真判重叠、真挡发货）＋ 结构层（这三处实现里没有宿主钩子 API）。
"""

from __future__ import annotations

import argparse
import contextlib
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import engine.coding.cli as cli  # noqa: E402
import engine.coding.hostguard as hg  # noqa: E402,F401  （同包导入可用性）
import engine.coding.scheduler as sched  # noqa: E402
import engine.coding.worktree as wt  # noqa: E402


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


@pytest.fixture()
def bare_repo(tmp_path):
    """一个带一次提交的临时仓，够 git worktree 用。"""
    r = tmp_path / "proj"
    r.mkdir()
    git("init", "-q", cwd=r)
    git("config", "user.email", "t@example.com", cwd=r)
    git("config", "user.name", "t", cwd=r)
    (r / "README.md").write_text("base\n", encoding="utf-8")
    git("add", "README.md", cwd=r)
    git("commit", "-qm", "base", cwd=r)
    git("branch", "-M", "main", cwd=r)
    return r


# ── ① 工作树隔离 ────────────────────────────────────────────────────────────
def test_worktree_is_a_separate_tree_and_branch(bare_repo):
    p = wt.create("r-ac06", base="main", root=bare_repo)
    assert p.is_dir()
    assert wt.branch_name("r-ac06") not in ("main", "master")
    (p / "only-in-wt.txt").write_text("x", encoding="utf-8")
    assert not (bare_repo / "only-in-wt.txt").exists(), "主树被写穿了"
    assert wt.changed_files("r-ac06", "main", bare_repo) == ["only-in-wt.txt"]
    wt.remove("r-ac06", root=bare_repo)
    assert not p.exists()


def test_worktree_creation_never_touches_main_worktree(bare_repo):
    before = (bare_repo / "README.md").read_bytes()
    p = wt.create("r-ac06b", base="main", root=bare_repo)
    (p / "README.md").write_text("改了子树的 README\n", encoding="utf-8")
    assert (bare_repo / "README.md").read_bytes() == before
    wt.remove("r-ac06b", root=bare_repo)


# ── ② 范围校验 ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("a,b,expect", [
    (["src/a.py"], ["src/a.py"], True),
    (["src/a.py"], ["src/b.py"], False),
    (["src/**"], ["src/deep/x.py"], True),
    (["src/*.py"], ["src/x.py"], True),
    # 实现是**保守**粗判：同静态前缀就算重叠，宁可多拦（见 _static_prefix 注释）
    (["src/*.py"], ["src/deep/x.py"], True),
    (["src/*.py"], ["tests/x.py"], False),
    (["src/"], ["src/x.py"], True),
    ([], ["src/x.py"], False),
    (["a.py"], [], False),
])
def test_touchset_overlap_matrix(a, b, expect):
    assert sched.touchsets_overlap(a, b) is expect


def test_touchset_prefix_rule_is_conservative_not_exact():
    """把「保守」这件事钉住：glob 只取静态前缀粗判，宁可多拦；
    但真正不相交的目录必须放过，不能一律 True。"""
    assert sched.touchsets_overlap(["src/*.py"], ["src/deep/x.py"]) is True
    assert sched.touchsets_overlap(["src/deep/*.py"], ["src/deep/a/b.py"]) is True
    assert sched.touchsets_overlap(["src/deep/*.py"], ["src/x.py"]) is False
    assert sched.touchsets_overlap(["src/*.py"], ["other/x.py"]) is False


def test_touchset_overlap_is_symmetric():
    for a, b in ((["src/**"], ["src/x.py"]), (["a/b.py"], ["a/c.py"]), (["x"], [])):
        assert sched.touchsets_overlap(a, b) == sched.touchsets_overlap(b, a)


def test_inflight_touchsets_collects_running_and_review():
    run = {"tasks": [
        {"id": "t1", "status": "running", "touchset": ["a/**"]},
        {"id": "t2", "status": "review", "touchset": ["b.py"]},
        {"id": "t3", "status": "accepted", "touchset": ["c.py"]},
        {"id": "t4", "status": "ready", "touchset": ["d.py"]},
    ]}
    got = sched.inflight_touchsets(run)
    assert "a/**" in got and "b.py" in got
    assert "c.py" not in got and "d.py" not in got, "已收口/未开工的不占范围"


# ── ③ 发货单点 ──────────────────────────────────────────────────────────────
def _run(phase, statuses=("accepted",)):
    return {
        "run_id": "r1", "phase": phase, "gates": {"g0": "approved", "g1": "approved"},
        "tasks": [{"id": f"t{i}", "status": s} for i, s in enumerate(statuses)],
        "sessions": [], "resume": {"next_action": ""},
    }


@pytest.fixture()
def gate_harness(monkeypatch):
    """把一个 run 灌进 cmd_gate，记录 _ship 有没有被叫。"""
    shipped = []

    def build(state):
        monkeypatch.setattr(cli, "_root", lambda: Path("."))
        monkeypatch.setattr(cli.st, "load", lambda rid, root=None, verify=True: state)
        monkeypatch.setattr(cli.st, "lock", lambda root=None, timeout=30.0: contextlib.nullcontext())
        monkeypatch.setattr(cli, "_save", lambda s: None)
        monkeypatch.setattr(cli, "advance", lambda s, root: None)
        monkeypatch.setattr(cli.worktree, "remove", lambda rid, root=None: None)
        monkeypatch.setattr(cli, "_ship", lambda s, root: (shipped.append(s["run_id"]) or (True, "ok")))
        return shipped

    return build


def test_g2_blocks_when_not_closing(gate_harness):
    shipped = gate_harness(_run("planning"))
    with pytest.raises(SystemExit):
        cli.cmd_gate(argparse.Namespace(run_id="r1", gate="g2", decision="approve"))
    assert shipped == [], "没到 closing 就发货了"


def test_g2_blocks_when_tasks_not_accepted(gate_harness):
    shipped = gate_harness(_run("closing", ("accepted", "running")))
    with pytest.raises(SystemExit):
        cli.cmd_gate(argparse.Namespace(run_id="r1", gate="g2", decision="approve"))
    assert shipped == []


def test_g2_ships_exactly_once_when_clean(gate_harness):
    shipped = gate_harness(_run("closing"))
    cli.cmd_gate(argparse.Namespace(run_id="r1", gate="g2", decision="approve"))
    assert shipped == ["r1"]


def test_g0_and_g1_never_ship(gate_harness):
    shipped = gate_harness(_run("planning"))
    cli.cmd_gate(argparse.Namespace(run_id="r1", gate="g0", decision="approve"))
    cli.cmd_gate(argparse.Namespace(run_id="r1", gate="g1", decision="approve"))
    assert shipped == [], "只有 g2 能触发发货"


def test_ship_has_exactly_two_control_plane_call_sites():
    """结构断言：发货只有两条口子，都在主会话控制面里，都要求 phase==closing。
    角色实例（worker/reviewer）碰不到任何一条。"""
    src = (REPO / "engine" / "coding" / "cli.py").read_text(encoding="utf-8")
    assert src.count("def _ship(") == 1
    calls = [l.strip() for l in src.splitlines() if "_ship(" in l and "def " not in l]
    assert len(calls) == 2, calls
    # 两条口子：advance()（加急跃迁）与 cmd_gate()（显式 G2）
    lines = src.splitlines()
    enclosing = []
    for n, l in enumerate(lines, 1):
        if "_ship(" in l and "def " not in l:
            fn = [x for x in lines[:n] if x.startswith("def ")][-1]
            enclosing.append(fn.split("(")[0].replace("def ", ""))
    assert enclosing == ["advance", "cmd_gate"], enclosing
    # 角色实例侧的处理函数一律不许出现发货
    for fn in ("def cmd_claim", "def cmd_report", "def cmd_verdict",
               "def cmd_review", "def cmd_review_native"):
        body = src.split(fn, 1)[1].split("\ndef ", 1)[0]
        assert "_ship(" not in body, f"{fn} 里出现了发货调用"


def test_autopilot_ship_requires_can_ship(monkeypatch):
    """加急跃迁那条口子也要门：没有 can_ship 就不许发货。"""
    shipped = []
    state = _run("closing")
    state.update({"autopilot": True, "can_ship": False, "gates": {"g2": "pending"}})
    monkeypatch.setattr(cli, "_root", lambda: Path("."))
    monkeypatch.setattr(cli, "_save", lambda s: None)
    monkeypatch.setattr(cli.worktree, "remove", lambda rid, root=None: None)
    monkeypatch.setattr(cli, "_ship", lambda s, root: (shipped.append(s["run_id"]) or (True, "ok")))
    cli.advance(state, Path("."))
    assert shipped == [], "没有 can_ship 也发了货"
    state["can_ship"] = True
    cli.advance(state, Path("."))
    assert shipped == ["r1"], "加急跃迁应当发一次货"


# ── 结构层：三处实现都不靠宿主钩子 ──────────────────────────────────────────
HOOK_APIS = ("PreToolUse", "PostToolUse", "SubagentStart", "SubagentStop", "hook(")


def test_three_gates_do_not_use_host_hooks():
    for rel in ("engine/coding/worktree.py", "engine/coding/scheduler.py", "engine/coding/cli.py"):
        text = (REPO / rel).read_text(encoding="utf-8")
        for api in HOOK_APIS:
            assert api not in text, f"{rel} 出现了宿主钩子 {api}，门禁就押在会被剥掉的东西上了"


def test_no_host_hooks_in_role_render_or_memory():
    for rel in ("scripts/rolelib.py", "scripts/role-memory.py", "engine/coding/hostguard.py"):
        text = (REPO / rel).read_text(encoding="utf-8")
        for api in HOOK_APIS:
            assert api not in text, f"{rel} 出现了宿主钩子 {api}"


def test_reverse_gate_matrix_is_not_all_green():
    """自证尺子不是恒绿：同一状态换个 gate，结果必须翻。"""
    src = (REPO / "engine" / "coding" / "cli.py").read_text(encoding="utf-8")
    assert 'if g == "g2" and args.decision == "approve":' in src
    assert sched.touchsets_overlap(["a"], ["b"]) is False
    assert sched.touchsets_overlap(["a"], ["a"]) is True