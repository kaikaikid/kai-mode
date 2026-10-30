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

        # 6. doctor / gc
        run(repo, "doctor")
        run(repo, "gc", "--all")
        checks.append("doctor+gc")

        # 7. 看板 HTML
        out = run(repo, "status", "--html")
        assert Path(out).exists(), out
        checks.append("board html")
    finally:
        import shutil
        shutil.rmtree(repo, ignore_errors=True)

    print("PASS: " + ", ".join(checks))


if __name__ == "__main__":
    main()
