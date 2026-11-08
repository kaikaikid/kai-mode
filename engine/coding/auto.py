"""自动接上：把 claim→派活→report→审查→verdict 的循环在控制面里自己走完。

设计裁决（2026-11-05）：舰桥说一次 `/jump` 之后不再逐条敲命令。循环必须住在
能跨会话的东西里——内核，不是舰桥的技能文本。执行仍走宿主原生子代理；
内核不 import 任何 CLI SDK，只通过「宿主命令」拉起一次性会话（命令从 TRAVEL_WORKER_CMD 环境变量读）。
状态推进仍只由现有命令写 state.json，本模块不自己改状态。
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import hostguard

# 宿主命令从环境变量或 `.coding/config.json` 的 worker_cmd / reviewer_cmd 读。
# 占位符 {brief} 换成提示词；两处都没配时 drive() 报缺件，不碰状态。
DEFAULT_WORKER = os.environ.get("TRAVEL_WORKER_CMD", "")
DEFAULT_REVIEWER = os.environ.get("TRAVEL_REVIEWER_CMD", "")


def _config_cmd(key: str) -> str:
    """从 `.coding/config.json` 读宿主命令；只读这一处，不猜。"""
    from . import state as st
    p = st.coding_dir(_root()) / "config.json"
    if not p.is_file():
        return ""
    try:
        cfg = json.loads(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return ""
    return str(cfg.get(key) or "").strip()


def _run_cmd(args: list[str], cwd: str | None = None) -> dict | list:
    """调 `travel` 自己：一律走 coding_main.py（包入口），不直接跑 cli.py（相对导入会炸）。"""
    r = subprocess.run([sys.executable, str(Path(__file__).parent.parent / "coding_main.py")] + args,
                       cwd=cwd or str(_root()), capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"_raw": r.stdout, "_err": r.stderr, "_rc": r.returncode}


def _root() -> Path:
    from . import state as st
    return st.repo_root()


def _host_run(host_cmd: str, prompt: str, cwd: str) -> subprocess.CompletedProcess:
    """按 argv 列表跑宿主命令，绝不拼 shell 字符串。

    Windows 下用 shell=True 拼长提示词会被引号转义拆碎（smoke 实测），
    所以宿主命令一律 shlex 拆成 argv，提示词作为独立 argv 元素整段传入。
    """
    argv = shlex.split(host_cmd, posix=(os.name != "nt"))
    if not argv:
        raise ValueError("empty host command")
    # 角色实例的入口必须属于当前宿主（ADR-0033 D3）。跨宿主借兵在这里就炸，
    # 不给「先跑起来再说」的缝。宿主→程序名映射从 .coding/host-programs.json 读（数据，不写死）。
    hostguard.assert_own_host(host_cmd, hostguard.current_host(_root()),
                              hostguard.load_table(_root()))
    if any(a == "{brief}" for a in argv):
        argv = [prompt if a == "{brief}" else a for a in argv]
    else:  # 没写占位符：追加到末尾
        argv.append(prompt)
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _spawn_worker(card: dict, host_cmd: str) -> dict:
    """拉起一次性子会话执行任务卡，读它写的 report.json。宿主命令不支持就报缺件。"""
    program = host_cmd.split()[0] if host_cmd.strip() else ""
    if not program:
        return {"_needs_subagent": True, "card": card}
    if not shutil.which(program):
        return {"_error": f"host command not found: {program}; fix TRAVEL_WORKER_CMD or remove it"}
    prompt = (
        "你是舰队施工子代理。只改 touchset 范围内的文件，完成后把报告写到 report_path。\n"
        "报告契约：{\"result\":\"done|partial|blocked\",\"files_changed\":[\"path — 改了什么\"],"
        "\"commit\":\"<HEAD sha，无改动留空>\",\"verification\":[\"命令 -> 结果\"],"
        "\"open_questions\":[],\"notes\":\"<=100字\"}\n\n"
        "任务卡：\n" + json.dumps(card, ensure_ascii=False, indent=2)
    )
    r = _host_run(host_cmd, prompt, card.get("worktree") or str(_root()))
    if r.returncode != 0:
        return {"_error": f"worker command failed (rc={r.returncode})",
                "_stderr": (r.stderr or "")[-600:], "_stdout": (r.stdout or "")[-300:]}
    rp = Path(card["report_path"])
    if not rp.is_absolute():
        rp = _root() / rp
    if rp.is_file():
        try:
            return json.loads(rp.read_text(encoding="utf-8"))
        except Exception as e:
            return {"_error": f"report not parseable: {e}", "_stdout": r.stdout[-500:]}
    return {"_error": f"worker did not write report (rc={r.returncode})",
            "_stdout": r.stdout[-500:], "_stderr": r.stderr[-300:]}


def _spawn_reviewer(card: dict, host_cmd: str) -> dict:
    program = host_cmd.split()[0] if host_cmd.strip() else ""
    if not program:
        return {"_needs_subagent": True, "card": card}
    if not shutil.which(program):
        return {"_error": f"host command not found: {program}; fix TRAVEL_REVIEWER_CMD or remove it"}
    prompt = (
        "你是舰队门卫审查子代理，只读。读 worktree 里 diff_base..HEAD 的实际 diff，"
        "逐条对 AC，不改任何文件。把裁决写到 review_report_path："
        "{\"verdict\":\"accept|return\",\"defects\":[],\"reason\":\"\"}\n\n"
        "审查卡：\n" + json.dumps(card, ensure_ascii=False, indent=2)
    )
    r = _host_run(host_cmd, prompt, card.get("worktree") or str(_root()))
    if r.returncode != 0:
        return {"_error": f"reviewer command failed (rc={r.returncode})",
                "_stderr": (r.stderr or "")[-600:]}
    rp = Path(card["review_report_path"])
    if not rp.is_absolute():
        rp = _root() / rp
    if rp.is_file():
        try:
            return json.loads(rp.read_text(encoding="utf-8"))
        except Exception as e:
            return {"_error": f"review report not parseable: {e}"}
    return {"_error": f"reviewer did not write report (rc={r.returncode})",
            "_stdout": r.stdout[-500:]}


def _phase_of(run_id: str) -> str:
    from . import state as st
    try:
        with st.lock(_root()):
            return st.load(run_id, _root()).get("phase", "")
    except Exception:
        return ""


def drive(run_id: str, worker_cmd: str = DEFAULT_WORKER, reviewer_cmd: str = DEFAULT_REVIEWER,
          max_rounds: int = 50) -> dict:
    """无人值守循环：取下一个任务 → claim → 派子会话 → report → 审查 → verdict，直到终态。"""
    from . import state as st

    worker_cmd = (worker_cmd or "").strip() or _config_cmd("worker_cmd")
    reviewer_cmd = (reviewer_cmd or "").strip() or _config_cmd("reviewer_cmd")

    log = []
    checked = False
    for _ in range(max_rounds):
        with st.lock(_root()):
            s = st.load(run_id, _root())
        phase = s.get("phase")
        if phase in st.TERMINAL_PHASES:
            log.append(f"run {run_id} reached terminal phase: {phase}")
            break
        if phase == "blocked":
            log.append(f"run {run_id} blocked: {s.get('resume', {}).get('next_action', '')}")
            break
        if phase == "queued":
            log.append(f"run {run_id} queued; waiting for a free slot")
            break

        # 命令存在性预检（只在真要 claim 前做一次）：命令写错就不 claim，
        # 否则会连失败两次、把任务打成 blocked。
        if not checked:
            checked = True
            # 未配命令时跳过可执行性检查：此时走 AI 原生子代理，不 spawn。

        # 取 ready 任务
        tasks = _run_cmd(["next", run_id])
        if isinstance(tasks, dict):
            ready = [tasks] if tasks.get("task_id") else []
        else:
            ready = [t for t in tasks if isinstance(t, dict) and t.get("task_id")]
        if not ready:
            # 没有 ready 任务但也没到终态：可能在等审查/验收，推进一下
            _run_cmd(["resume", run_id])
            with st.lock(_root()):
                s2 = st.load(run_id, _root())
            if s2.get("phase") in st.TERMINAL_PHASES or s2.get("phase") == "blocked":
                log.append(f"run {run_id} phase after resume: {s2.get('phase')}")
                break
            if not any(t.get("status") in {"running", "review"} for t in s2.get("tasks", [])):
                log.append(f"run {run_id}: no ready tasks, nothing in flight; stopping")
                break
            continue

        for t in ready[:3]:  # 每轮最多推 3 个任务，避免一次吃太多
            tid = t["task_id"]
            # 该任务连续失败 2 次先停：不像舰桥那样死循环烧 token。
            with st.lock(_root()):
                _s = st.load(run_id, _root())
            _t = next((x for x in _s.get("tasks", []) if x["id"] == tid), None)
            if _t and _t.get("auto_fails", 0) >= 2:
                _t["status"] = "blocked"
                _s["resume"]["next_action"] = f"auto: task {tid} failed twice; needs a human"
                st.save(_s, _root())
                log.append(f"blocked {tid}: failed twice")
                continue
            log.append(f"claim {run_id}/{tid}")

            def _fail(note: str) -> None:
                with st.lock(_root()):
                    _s2 = st.load(run_id, _root())
                    _t2 = next((x for x in _s2.get("tasks", []) if x["id"] == tid), None)
                    if _t2 is not None:
                        _t2["auto_fails"] = int(_t2.get("auto_fails", 0)) + 1
                        st.save(_s2, _root())
                log.append(note)
            card = _run_cmd(["claim", run_id, tid])
            if "_raw" in card or "task_id" not in card:
                _fail(f"claim failed for {tid}: {card.get('_err', card)}")
                continue

            log.append(f"worker on {tid}")
            rep = _spawn_worker(card, worker_cmd)
            if rep.get("_needs_subagent"):
                log.append(f"subagent needed on {tid}: run a writable host-native subagent on the card above, "
                           f"then fleet report {run_id} {tid}")
                result = {"run_id": run_id, "phase": "delegating", "next_action": f"subagent {tid}",
                          "pending_card": card, "log": log}
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return result
            if "_error" in rep:
                _fail(f"worker error on {tid}: {rep['_error']}")
                _run_cmd(["release", run_id, tid])
                continue

            log.append(f"report {tid}")
            _run_cmd(["report", run_id, tid])

            log.append(f"review {tid}")
            rcard = _run_cmd(["review", run_id, tid])
            if "review_report_path" not in rcard:
                log.append(f"review card failed for {tid}: {rcard}")
                continue
            verdict = _spawn_reviewer(rcard, reviewer_cmd)
            if verdict.get("_needs_subagent"):
                log.append(f"subagent needed on {tid}: run a read-only host-native subagent on the review card above, "
                           f"then fleet verdict {run_id} {tid} --file <path>")
                result = {"run_id": run_id, "phase": "review", "next_action": f"reviewer {tid}",
                          "pending_card": rcard, "log": log}
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return result
            if "_error" in verdict:
                _fail(f"reviewer error on {tid}: {verdict['_error']}")
                continue

            vp = Path(rcard["review_report_path"])
            if not vp.is_absolute():
                vp = _root() / vp
            log.append(f"verdict {tid}: {verdict.get('verdict')}")
            _run_cmd(["verdict", run_id, tid, "--file", str(vp)])

    with st.lock(_root()):
        final = st.load(run_id, _root())
    result = {"run_id": run_id, "phase": final.get("phase"),
              "next_action": final.get("resume", {}).get("next_action"),
              "log": log}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def cmd_auto(args: argparse.Namespace) -> None:
    drive(args.run_id, worker_cmd=args.worker_cmd, reviewer_cmd=args.reviewer_cmd)
