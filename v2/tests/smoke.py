#!/usr/bin/env python
"""V2 闭环冒烟测试：用 mock 适配器跑完正常路径与几条关键分支。

    python v2/tests/smoke.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODING = ROOT / "v2" / "coding_main.py"
PY = sys.executable


def run(cwd: Path, *args: str, expect: int = 0) -> str:
    r = subprocess.run([PY, str(CODING), *args], cwd=str(cwd), capture_output=True, text=True)
    if r.returncode != expect:
        raise AssertionError(f"{args} -> rc={r.returncode}\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def make_repo() -> Path:
    d = Path(tempfile.mkdtemp(prefix="coding-smoke-"))
    git(d, "init", "-q")
    git(d, "config", "user.email", "t@t")
    git(d, "config", "user.name", "t")
    (d / "a.txt").write_text("hello\n", encoding="utf-8")
    git(d, "add", ".")
    git(d, "commit", "-qm", "init")
    git(d, "branch", "-M", "main")
    return d


def plan(repo: Path, run_id: str, tasks: list[dict]) -> None:
    p = repo / "tasks.json"
    p.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
    run(repo, "plan", run_id, "--file", str(p))


def main() -> None:
    checks: list[str] = []
    repo = make_repo()
    try:
        # 1. 正常路径
        rid = run(repo, "run", "smoke", "--base", "main")
        plan(repo, rid, [
            {"id": "t1", "title": "a", "brief": "x", "tier": "light", "touchset": ["a.txt"], "ac": ["ok"]},
            {"id": "t2", "title": "b", "brief": "y", "tier": "light", "deps": ["t1"], "touchset": ["b.txt"], "ac": ["ok"]},
        ])
        run(repo, "gate", rid, "g0", "approve")
        assert '"t1"' in run(repo, "next", rid), "t1 should be ready"
        assert '"t2"' not in run(repo, "next", rid), "t2 must wait for t1"
        run(repo, "spawn", rid, "t1", "--adapter", "mock")
        time.sleep(0.2)
        run(repo, "report", rid, "t1")
        run(repo, "accept", rid, "t1")
        run(repo, "spawn", rid, "t2", "--adapter", "mock")
        time.sleep(0.2)
        run(repo, "report", rid, "t2")
        run(repo, "accept", rid, "t2")
        status = run(repo, "status")
        assert "closing" in status or "done" in status, status
        run(repo, "gate", rid, "g2", "approve")
        assert "done" in run(repo, "status")
        checks.append("normal path")

        # 2. 门被否决回流
        rid2 = run(repo, "run", "reject-test", "--base", "main")
        plan(repo, rid2, [{"id": "t1", "title": "a", "brief": "x", "tier": "light",
                           "touchset": ["c.txt"], "ac": ["ok"]}])
        run(repo, "gate", rid2, "g0", "approve")
        out = run(repo, "gate", rid2, "g2", "reject")
        assert "reviewing" in out or "delegating" in out, out
        checks.append("gate reject")

        # 3. touchset 冲突：同文件两个 run
        run(repo, "spawn", rid2, "t1", "--adapter", "mock")
        time.sleep(0.2)
        rid3 = run(repo, "run", "conflict", "--base", "main")
        plan(repo, rid3, [{"id": "t1", "title": "a", "brief": "x", "tier": "light",
                           "touchset": ["c.txt"], "ac": ["ok"]}])
        run(repo, "gate", rid3, "g0", "approve")
        assert run(repo, "next", rid3) == "[]", "overlapping touchset must wait"
        checks.append("touchset conflict")

        # 4. 加急预留槽
        urgent = run(repo, "run", "urgent", "--base", "main", "--urgent")
        assert urgent.startswith("r-")
        checks.append("urgent slot")

        # 5. adopt 晚激活
        (repo / "a.txt").write_text("dirty\n", encoding="utf-8")
        ra = run(repo, "adopt", "late")
        state = json.loads((repo / ".coding" / "runs" / ra / "state.json").read_text(encoding="utf-8"))
        assert state["gates"]["g0"] == "skipped" and state["baseline"]["dirty"], state
        checks.append("adopt")

        # 5b. 脏件分类 + 收起 + 放回（不删未提交内容）
        (repo / "a.txt").write_text("dirty2\n", encoding="utf-8")
        (repo / "untracked.txt").write_text("u\n", encoding="utf-8")
        info = json.loads(run(repo, "dirty", "--json"))
        assert info["blocks_ship"] and any(e["path"] == "a.txt" for e in info["product"]), info
        parked = json.loads(run(repo, "park", "-m", "smoke"))
        assert parked["ok"] and parked["stash_ref"], parked
        assert (repo / "a.txt").read_text(encoding="utf-8") == "hello\n"
        assert (repo / "untracked.txt").exists(), "untracked files must not be parked"
        back = json.loads(run(repo, "unpark", parked["stash_ref"]))
        assert back["ok"] and (repo / "a.txt").read_text(encoding="utf-8") == "dirty2\n", back
        checks.append("dirty+park+unpark")

        # 6. doctor / gc
        run(repo, "doctor")
        run(repo, "gc", "--all")
        checks.append("doctor+gc")

        # 7. 看板 HTML
        out = run(repo, "status", "--html")
        assert Path(out).exists(), out
        checks.append("board html")

        # 8. 跃迁模式：自动批门 + 门卫审查 + 自动发货
        for r in (rid, rid2, rid3, urgent, ra):
            if (repo / ".coding" / "runs" / r / "state.json").exists():
                run(repo, "stop", r)
        git(repo, "checkout", "--", "a.txt")
        rid4 = run(repo, "warp", "warp path", "--base", "main").splitlines()[0]
        plan(repo, rid4, [{"id": "t1", "title": "a", "brief": "x", "tier": "light",
                           "touchset": ["j.txt"], "ac": ["ok"]}])
        run(repo, "spawn", rid4, "t1", "--adapter", "mock")
        time.sleep(0.2)
        run(repo, "report", rid4, "t1")
        run(repo, "review", rid4, "t1", "--adapter", "mock", "--apply")
        state = json.loads((repo / ".coding" / "runs" / rid4 / "state.json").read_text(encoding="utf-8"))
        assert state["phase"] == "closing" and state["gates"]["g2"] == "pending", state
        assert not state.get("can_ship"), state
        checks.append("jump stops before ship")
        run(repo, "gate", rid4, "g2", "approve")
        state = json.loads((repo / ".coding" / "runs" / rid4 / "state.json").read_text(encoding="utf-8"))
        assert state["phase"] == "done" and state["gates"]["g2"] == "approved", state
        checks.append("jump autopilot")

        # 9. drive：脚本无人值守跑完整条流水线（PRI-jump 有发货权，能一路到 done）
        rid5 = run(repo, "jump", "drive path", "--base", "main").splitlines()[0]
        plan(repo, rid5, [
            {"id": "t1", "title": "a", "brief": "x", "tier": "light", "touchset": ["d1.txt"], "ac": ["ok"]},
            {"id": "t2", "title": "b", "brief": "y", "tier": "light", "deps": ["t1"], "touchset": ["d2.txt"], "ac": ["ok"]},
        ])
        run(repo, "drive", "--run", rid5, "--adapter", "mock")
        state = json.loads((repo / ".coding" / "runs" / rid5 / "state.json").read_text(encoding="utf-8"))
        assert state["phase"] == "done", state
        checks.append("drive")

        # 10. P0-1 报告解析：claude -p JSON 信封（type=result + 内层 JSON 字符串）与裸报告
        sys.path.insert(0, str(ROOT / "v2"))
        from coding import adapters as _ad, state as _st
        envelope = json.dumps({
            "type": "result", "subtype": "success", "total_cost_usd": 0.01,
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "result": json.dumps({"result": "done", "verdict": "return", "defects": ["x"],
                                  "files_changed": [], "verification": [], "open_questions": []}),
        })
        rep = _ad.parse_report(envelope)
        assert rep.get("verdict") == "return" and rep.get("result") == "done", rep
        assert rep.get("usage", {}).get("input_tokens") == 10, rep
        bare = json.dumps({"result": "done", "files_changed": [], "verification": [], "open_questions": []})
        assert _ad.parse_report(bare).get("result") == "done"
        checks.append("parse envelope")

        # 11. P0-5 工人工具面收窄：Bash 白名单（裸 Bash 消失）+ deny .coding/**；只读连 Edit/Write 都没有
        wcmd = _ad.worker_cmd(read_only=False)
        aw = wcmd[wcmd.index("--allowedTools") + 1]
        dw = wcmd[wcmd.index("--disallowedTools") + 1]
        assert "Bash(git add:*)" in aw and "Bash(git commit:*)" in aw, aw
        assert "Bash," not in aw and not aw.startswith("Bash,"), aw
        assert "Edit(.coding/**)" in dw and "Write(.coding/**)" in dw, dw
        assert "Bash(python -c:*)" in dw, dw
        rcmd = _ad.worker_cmd(read_only=True)
        assert "Edit" not in rcmd[rcmd.index("--allowedTools") + 1], rcmd
        checks.append("worker tool surface")

        # 12. P0-2 G2 阶段守卫：delegating + running 任务时 gate g2 approve 必须失败
        rg = run(repo, "run", "g2-guard", "--base", "main")
        plan(repo, rg, [{"id": "t1", "title": "a", "brief": "x", "tier": "light",
                         "touchset": ["g1.txt"], "ac": ["ok"]}])
        run(repo, "gate", rg, "g0", "approve")
        run(repo, "spawn", rg, "t1", "--adapter", "mock")
        run(repo, "gate", rg, "g2", "approve", expect=1)
        assert (repo / ".coding" / "worktrees" / rg).exists(), "worktree must survive a rejected g2"
        checks.append("g2 guard")

        # 13. P0-3 未提交成果不可丢：worktree 有未提交改动 → 发货失败并转 blocked，树与成果保留
        run(repo, "report", rg, "t1")
        run(repo, "review", rg, "t1", "--adapter", "mock", "--apply")
        wt = repo / ".coding" / "worktrees" / rg
        (wt / "a.txt").write_text("uncommitted\n", encoding="utf-8")
        run(repo, "gate", rg, "g2", "approve", expect=1)
        st_rg = json.loads((repo / ".coding" / "runs" / rg / "state.json").read_text(encoding="utf-8"))
        assert st_rg["phase"] == "blocked", st_rg["phase"]
        assert (repo / ".coding" / "worktrees" / rg).exists(), "uncommitted work must not be destroyed"
        assert (wt / "a.txt").read_text(encoding="utf-8") == "uncommitted\n", "uncommitted content must survive"
        checks.append("uncommitted guard")

        # 13b. 提交后发货放行（新 run：blocked 没有 P0 出口，恢复语义归 P1-9）
        rg2 = run(repo, "run", "commit-ok", "--base", "main")
        plan(repo, rg2, [{"id": "t1", "title": "a", "brief": "x", "tier": "light",
                          "touchset": ["g2.txt"], "ac": ["ok"]}])
        run(repo, "gate", rg2, "g0", "approve")
        run(repo, "spawn", rg2, "t1", "--adapter", "mock")
        run(repo, "report", rg2, "t1")
        run(repo, "review", rg2, "t1", "--adapter", "mock", "--apply")
        wt2 = repo / ".coding" / "worktrees" / rg2
        (wt2 / "b.txt").write_text("worker output\n", encoding="utf-8")
        git(wt2, "add", "-A")
        git(wt2, "commit", "-qm", "wip: worker output")
        run(repo, "gate", rg2, "g2", "approve")
        st2 = json.loads((repo / ".coding" / "runs" / rg2 / "state.json").read_text(encoding="utf-8"))
        assert st2["phase"] == "done", st2
        checks.append("commit then ship")

        # 14. P0-4 stop 真正停机：generic 长跑 worker 被杀树，终态后 report/spawn 被拒
        os.environ["CODING_GENERIC_CMD"] = f'"{sys.executable}" -c "import time; time.sleep(120)"'
        rs = run(repo, "run", "stoppable", "--base", "main")
        plan(repo, rs, [{"id": "t1", "title": "a", "brief": "x", "tier": "light",
                         "touchset": ["s1.txt"], "ac": ["ok"]}])
        run(repo, "gate", rs, "g0", "approve")
        pid = json.loads(run(repo, "spawn", rs, "t1", "--adapter", "generic"))["pid"]
        assert _st._pid_alive(pid), "sleeper should be running"
        run(repo, "stop", rs)
        for _ in range(20):
            if not _st._pid_alive(pid):
                break
            time.sleep(0.25)
        assert not _st._pid_alive(pid), "stop must kill the worker process tree"
        run(repo, "report", rs, "t1", expect=1)
        run(repo, "spawn", rs, "t1", "--adapter", "mock", expect=1)
        checks.append("stop kills tree")

        # 15. P0-5 残余兜底（方案 A）：state.json 被直写 → 决策命令验签拒载；stop/status 仍可用
        sp = repo / ".coding" / "runs" / rs / "state.json"
        sp.write_text(sp.read_text(encoding="utf-8").replace('"cancelled"', '"done"'), encoding="utf-8")
        run(repo, "resume", rs, expect=1)
        run(repo, "gate", rs, "g2", "approve", expect=1)
        assert "stopped" in run(repo, "stop", rs)
        assert rs in run(repo, "status")
        checks.append("state integrity")
    finally:
        import shutil
        shutil.rmtree(repo, ignore_errors=True)

    print("PASS: " + ", ".join(checks))


if __name__ == "__main__":
    main()
