"""coding 命令行：控制平面入口。

用法见 `coding --help`。所有状态变更都经过这里，AI 不直接改 state.json。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from . import adapters, scheduler, state as st, worktree


# ---------------------------------------------------------------------------
# helpers


def _err(msg: str) -> "NoReturn":
    print(f"coding: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _root() -> Path:
    return st.repo_root()


def _save(s: dict[str, Any]) -> None:
    st.save(s, _root())


def _session_dir(run_id: str, sid: str) -> Path:
    return st.run_dir(run_id, _root()) / "sessions" / sid


def _new_sid() -> str:
    return f"s-{int(time.time() * 1000) % 10**10}"


def _has_ui(s: dict[str, Any]) -> bool:
    return any(t.get("ui") for t in s.get("tasks", []))


def _gate_ok(s: dict[str, Any], g: str) -> bool:
    return s.get("gates", {}).get(g) in {"approved", "skipped"}


def advance(s: dict[str, Any]) -> None:
    """按设计里的 phase 推进条件推进；只做确定性判断。循环到稳定。"""
    # 没有 UI 任务时 G1 自动跳过（G1 只在碰可见 UI 时才有意义）
    if s.get("tasks") and not _has_ui(s) and s.get("gates", {}).get("g1") == "pending":
        s["gates"]["g1"] = "skipped"

    for _ in range(6):
        phase = s.get("phase")
        tasks = s.get("tasks", [])
        before = phase

        if phase == "planning":
            if _gate_ok(s, "g0"):
                if _has_ui(s) and not _gate_ok(s, "g1"):
                    s["phase"] = "design"
                else:
                    s["phase"] = "delegating"
        elif phase == "design":
            if _gate_ok(s, "g1"):
                s["phase"] = "delegating"
        elif phase == "delegating":
            if tasks and not any(t.get("status") in {"pending", "ready", "running", "review", "returned"} for t in tasks):
                s["phase"] = "reviewing"
        elif phase == "reviewing":
            if tasks and all(t.get("status") in {"accepted", "abandoned"} for t in tasks):
                s["phase"] = "closing"

        if s.get("phase") == before:
            break


def _task(s: dict[str, Any], tid: str) -> dict[str, Any]:
    for t in s.get("tasks", []):
        if t.get("id") == tid:
            return t
    _err(f"task not found: {tid}")


def _report_path(run_id: str, tid: str) -> Path:
    return st.run_dir(run_id, _root()) / "sessions" / f"{tid}.report.json"


# ---------------------------------------------------------------------------
# commands


def cmd_run(args: argparse.Namespace) -> None:
    root = _root()
    with st.lock(root):
        rid = st.new_run_id()
        s = {
            "schema_version": st.SCHEMA_VERSION,
            "run_id": rid,
            "issue": args.issue,
            "phase": "queued",
            "priority": "urgent" if args.urgent else "normal",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "base_branch": args.base or worktree.base_branch(root),
            "branch": worktree.branch_name(rid),
            "worktree": str(worktree.worktree_path(rid, root)),
            "depends_on_runs": args.depends or [],
            "budget": {"max_tokens": args.max_tokens, "used_tokens": 0},
            "gates": {"g0": "pending", "g1": "pending", "g2": "pending"},
            "tasks": [],
            "touchset": [],
            "resources": [],
            "resume": {"last_accepted": None, "next_action": "plan"},
        }
        ok, why = scheduler.can_start(s, root)
        if ok:
            worktree.create(rid, s["base_branch"], root)
            s["phase"] = "planning"
            s["resume"]["next_action"] = "plan"
        else:
            s["resume"]["next_action"] = f"waiting: {why}"
        _save(s)
        print(rid)


def cmd_adopt(args: argparse.Namespace) -> None:
    """晚激活：把当前工作区的未提交改动接管为一个 run 的 baseline。"""
    root = _root()
    with st.lock(root):
        rid = st.new_run_id()
        head = worktree._git("rev-parse", "HEAD", cwd=root).stdout.strip()
        dirty = worktree._git("status", "--porcelain", cwd=root).stdout.strip()
        s = {
            "schema_version": st.SCHEMA_VERSION,
            "run_id": rid,
            "issue": args.issue,
            "phase": "planning",
            "priority": "normal",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "base_branch": worktree.base_branch(root),
            "branch": worktree.branch_name(rid),
            "worktree": str(root),  # 接管当前工作区，不建树
            "depends_on_runs": [],
            "budget": {"max_tokens": args.max_tokens, "used_tokens": 0},
            "gates": {"g0": "skipped", "g1": "pending", "g2": "pending"},
            "tasks": [],
            "touchset": [],
            "resources": [],
            "baseline": {"head": head, "dirty": dirty},
            "resume": {"last_accepted": None, "next_action": "plan"},
        }
        _save(s)
        print(rid)


def cmd_plan(args: argparse.Namespace) -> None:
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        if s["phase"] not in {"planning", "design"}:
            _err(f"cannot plan in phase {s['phase']}")
        raw = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
        data = json.loads(raw)
        tasks = data.get("tasks", data if isinstance(data, list) else [])
        norm = []
        for i, t in enumerate(tasks, 1):
            norm.append({
                "id": t.get("id") or f"t{i}",
                "title": t.get("title") or f"task {i}",
                "brief": t.get("brief", ""),
                "tier": t.get("tier", "medium"),
                "deps": t.get("deps", []),
                "touchset": t.get("touchset", []),
                "ac": t.get("ac", []),
                "ui": bool(t.get("ui", False)),
                "status": "pending",
                "attempts": 0,
                "session_id": None,
            })
        s["tasks"] = norm
        s["touchset"] = sorted({p for t in norm for p in t.get("touchset", [])})
        s["resume"]["next_action"] = "gate g0"
        advance(s)
        _save(s)
        print(f"planned {len(norm)} task(s)")


def cmd_gate(args: argparse.Namespace) -> None:
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        g = args.gate
        if g not in {"g0", "g1", "g2"}:
            _err("gate must be g0, g1 or g2")
        if args.decision == "approve":
            s["gates"][g] = "approved"
        elif args.decision == "reject":
            s["gates"][g] = "rejected"
            s["phase"] = {"g0": "planning", "g1": "design", "g2": "reviewing"}[g]
        else:
            s["gates"][g] = "skipped"

        if g == "g2" and args.decision == "approve":
            ok, msg = worktree.merge(s["run_id"], s["base_branch"], root)
            if not ok:
                s["phase"] = "blocked"
                s["resume"]["next_action"] = f"resolve merge conflict: {msg}"
                _save(s)
                _err(f"merge failed, run blocked: {msg}")
            s["phase"] = "done"
            s["resume"]["next_action"] = "done"
            _save(s)
            worktree.remove(s["run_id"], root)
            print("merged and closed")
            return

        advance(s)
        _save(s)
        print(f"{g}={s['gates'][g]} phase={s['phase']}")


def cmd_next(args: argparse.Namespace) -> None:
    root = _root()
    runs = [st.load(args.run_id, root)] if args.run_id else st.list_runs(root)
    out = []
    for s in runs:
        if s.get("phase") in st.TERMINAL_PHASES:
            continue
        for t in scheduler.ready_tasks(s, root):
            out.append({"run_id": s["run_id"], "task_id": t["id"], "title": t["title"], "tier": t["tier"]})
    print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_spawn(args: argparse.Namespace) -> None:
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        t = _task(s, args.task_id)
        ok, why = scheduler.can_spawn(s, t, root)
        if not ok:
            _err(f"cannot spawn: {why}")
        if t.get("status") not in {"pending", "returned", "ready"}:
            _err(f"task {t['id']} is {t.get('status')}")
        if t.get("status") != "returned" and not scheduler.deps_done(t, {x["id"]: x for x in s["tasks"]}):
            _err("deps not done")

        adapter = adapters.pick(args.adapter)
        sid = _new_sid()
        sdir = _session_dir(s["run_id"], sid)
        brief = _build_brief(s, t)
        cwd = Path(s["worktree"]) if s.get("worktree") else root
        handle = adapter.spawn(brief, cwd, sdir, tier=t.get("tier", "medium"), timeout=args.timeout)
        t["status"] = "running"
        t["session_id"] = sid
        t["attempts"] = int(t.get("attempts", 0)) + (1 if args.retry else 0)
        s.setdefault("sessions", []).append({
            "id": sid, "task_id": t["id"], "adapter": adapter.name,
            "pid": handle.get("pid"), "started_at": time.time(), "status": "running",
        })
        s["phase"] = "delegating" if s["phase"] in {"planning", "design"} else s["phase"]
        _save(s)
        print(json.dumps({"session": sid, "adapter": adapter.name, "pid": handle.get("pid")}))


def _build_brief(s: dict[str, Any], t: dict[str, Any]) -> str:
    return (
        f"You are a worker in a V2 run. The orchestrator owns the plan, design and final judgment; "
        f"you own exactly this task.\n\n"
        f"TASK: {t['title']}\n\n{t.get('brief','')}\n\n"
        f"ACCEPTANCE CRITERIA:\n" + "\n".join(f"- {a}" for a in t.get("ac", [])) + "\n\n"
        f"RULES:\n"
        f"- Do only this task. Do not widen scope, refactor neighbours, or invent UI.\n"
        f"- Never run destructive commands (rm -rf, drop, force push). They are denied.\n"
        f"- Verify before reporting: build, test, or exercise the path; report the command and outcome.\n"
        f"- End your reply with ONE JSON object and nothing after it:\n"
        f'{{"result":"done|partial|blocked","files_changed":["path — what"],'
        f'"verification":["cmd -> outcome"],"open_questions":["..."],"notes":"<=100 chars"}}\n'
    )


def cmd_report(args: argparse.Namespace) -> None:
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        t = _task(s, args.task_id)
        sid = t.get("session_id")
        if not sid:
            _err("task has no session")
        sess = next((x for x in s.get("sessions", []) if x["id"] == sid), None)
        if not sess:
            _err("session record missing")
        sdir = _session_dir(s["run_id"], sid)
        adapter = adapters.get(sess["adapter"])
        # 进程可能已经结束，报告落盘即可
        text = adapter.read({"dir": str(sdir)})
        report = adapters.parse_report(text)
        report_path = _report_path(s["run_id"], t["id"])
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        # 报告与 diff 对账
        changed = worktree.changed_files(s["run_id"], s["base_branch"], root)
        claimed = report.get("files_changed") or []
        claimed_paths = [c.split(" — ")[0].strip() for c in claimed if isinstance(c, str)]
        missing = [c for c in claimed_paths if c and c not in changed]
        if missing:
            report["result"] = "partial"
            report["notes"] = (report.get("notes", "") + f" [mismatch: {', '.join(missing[:5])}]").strip()

        sess["status"] = "finished"
        t["status"] = "review"
        s["resume"]["next_action"] = f"review {t['id']}"
        _save(s)
        print(json.dumps(report, ensure_ascii=False, indent=2))


def cmd_accept(args: argparse.Namespace) -> None:
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        t = _task(s, args.task_id)
        if t.get("status") != "review":
            _err(f"task {t['id']} is {t.get('status')}, not review")
        t["status"] = "accepted"
        s["resume"]["last_accepted"] = t["id"]
        s["resume"]["next_action"] = "next"
        advance(s)
        _save(s)
        print(f"accepted {t['id']} phase={s['phase']}")


def cmd_return(args: argparse.Namespace) -> None:
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        t = _task(s, args.task_id)
        if t.get("status") != "review":
            _err(f"task {t['id']} is {t.get('status')}, not review")
        t["status"] = "returned"
        t["attempts"] = int(t.get("attempts", 0)) + 1
        t["defects"] = args.defects or ""
        if t["attempts"] >= 3:
            t["status"] = "blocked"
        s["resume"]["next_action"] = f"rework {t['id']}"
        _save(s)
        print(f"returned {t['id']} attempts={t['attempts']} status={t['status']}")


def cmd_reopen(args: argparse.Namespace) -> None:
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        t = _task(s, args.task_id)
        t["status"] = "pending"
        s["resume"]["last_accepted"] = None
        if s["phase"] in {"reviewing", "closing"}:
            s["phase"] = "delegating"
        _save(s)
        print(f"reopened {t['id']}")


def cmd_stop(args: argparse.Namespace) -> None:
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        s["phase"] = "cancelled"
        s["resume"]["next_action"] = "stopped"
        _save(s)
        print(f"stopped {s['run_id']}")


def cmd_resume(args: argparse.Namespace) -> None:
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        if s["phase"] == "queued":
            ok, why = scheduler.can_start(s, root)
            if not ok:
                print(f"still queued: {why}")
                return
            worktree.create(s["run_id"], s["base_branch"], root)
            s["phase"] = "planning"
        advance(s)
        _save(s)
        print(json.dumps({"run_id": s["run_id"], "phase": s["phase"],
                          "resume": s["resume"], "gates": s["gates"]}, ensure_ascii=False, indent=2))


def cmd_status(args: argparse.Namespace) -> None:
    root = _root()
    runs = st.list_runs(root)
    if args.html:
        _write_board(runs, root)
        print(str(st.coding_dir(root) / "board.html"))
        return
    if not runs:
        print("no runs")
        return
    print(f"{'RUN':10} {'PHASE':11} {'TASKS':7} {'GATE':6} {'PRI':7} ISSUE")
    for s in runs:
        tasks = s.get("tasks", [])
        done = sum(1 for t in tasks if t.get("status") in {"accepted", "abandoned"})
        total = len(tasks)
        gate = next((g for g in ("g0", "g1", "g2") if s.get("gates", {}).get(g) == "pending"), "-")
        print(f"{s['run_id']:10} {s.get('phase',''):11} {f'{done}/{total}' if total else '-':7} "
              f"{gate:6} {s.get('priority','normal'):7} {s.get('issue','')[:40]}")


def _write_board(runs: list[dict[str, Any]], root: Path) -> None:
    cols = {"doing": [], "waiting": [], "done": []}
    for s in runs:
        p = s.get("phase")
        if p in {"planning", "design", "delegating", "reviewing", "closing"}:
            cols["doing"].append(s)
        elif p in {"queued", "paused", "blocked"}:
            cols["waiting"].append(s)
        else:
            cols["done"].append(s)

    def card(s: dict[str, Any]) -> str:
        tasks = s.get("tasks", [])
        done = sum(1 for t in tasks if t.get("status") in {"accepted", "abandoned"})
        return (f"<div class=card><b>{s['run_id']}</b><div>{s.get('issue','')}</div>"
                f"<small>{s.get('phase')} · {done}/{len(tasks)} · {s.get('priority')}</small></div>")

    html = f"""<!doctype html><meta charset=utf-8><title>coding board</title>
<style>
body{{font:14px system-ui;background:#111;color:#eee;margin:0;padding:16px}}
h2{{font-size:14px;color:#aaa;margin:0 0 8px}}
.cols{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
.col{{background:#1b1b1b;border-radius:8px;padding:10px;min-height:60vh}}
.card{{background:#262626;border-radius:6px;padding:8px;margin:6px 0;border-left:3px solid #8f8cf4}}
.card small{{color:#999}}
</style>
<div class=cols>
<div class=col><h2>在做</h2>{''.join(card(s) for s in cols['doing'])}</div>
<div class=col><h2>在等</h2>{''.join(card(s) for s in cols['waiting'])}</div>
<div class=col><h2>已完成</h2>{''.join(card(s) for s in cols['done'])}</div>
</div>"""
    p = st.coding_dir(root) / "board.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")


def cmd_gc(args: argparse.Namespace) -> None:
    root = _root()
    removed = []
    for s in st.list_runs(root):
        if s.get("phase") not in st.TERMINAL_PHASES:
            continue
        age = time.time() - Path(st.state_path(s["run_id"], root)).stat().st_mtime
        if not args.all and age < 24 * 3600:
            continue
        worktree.remove(s["run_id"], root)
        removed.append(s["run_id"])
        if args.all:
            import shutil
            shutil.rmtree(st.run_dir(s["run_id"], root), ignore_errors=True)
    print(json.dumps({"removed": removed}, ensure_ascii=False))


def cmd_doctor(args: argparse.Namespace) -> None:
    root = _root()
    problems = []
    for s in st.list_runs(root):
        rid = s["run_id"]
        if s.get("phase") in st.TERMINAL_PHASES:
            continue
        wt = Path(s.get("worktree", ""))
        if s.get("phase") != "queued" and not wt.exists():
            problems.append(f"{rid}: worktree missing ({wt})")
        if s.get("phase") in {"closing", "reviewing"} and wt.exists():
            r = worktree._git("status", "--porcelain", cwd=wt, check=False)
            if r.stdout.strip() and s.get("phase") == "closing":
                problems.append(f"{rid}: uncommitted changes before closing")
    print(json.dumps({"problems": problems}, ensure_ascii=False, indent=2))
    if problems:
        raise SystemExit(2)


# ---------------------------------------------------------------------------
# argparse


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="coding", description="V2 execution kernel control plane")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="create a run")
    r.add_argument("issue")
    r.add_argument("--urgent", action="store_true")
    r.add_argument("--base")
    r.add_argument("--max-tokens", type=int, default=200000)
    r.add_argument("--depends", nargs="*", default=[])
    r.set_defaults(func=cmd_run)

    a = sub.add_parser("adopt", help="adopt current dirty tree as a run baseline")
    a.add_argument("issue")
    a.add_argument("--max-tokens", type=int, default=200000)
    a.set_defaults(func=cmd_adopt)

    pl = sub.add_parser("plan", help="set the task graph")
    pl.add_argument("run_id")
    pl.add_argument("--file")
    pl.set_defaults(func=cmd_plan)

    g = sub.add_parser("gate", help="approve/reject/skip a gate")
    g.add_argument("run_id")
    g.add_argument("gate", choices=["g0", "g1", "g2"])
    g.add_argument("decision", choices=["approve", "reject", "skip"])
    g.set_defaults(func=cmd_gate)

    n = sub.add_parser("next", help="show ready tasks")
    n.add_argument("run_id", nargs="?")
    n.set_defaults(func=cmd_next)

    sp = sub.add_parser("spawn", help="start a worker for a task")
    sp.add_argument("run_id")
    sp.add_argument("task_id")
    sp.add_argument("--adapter")
    sp.add_argument("--timeout", type=int, default=1800)
    sp.add_argument("--retry", action="store_true")
    sp.set_defaults(func=cmd_spawn)

    rp = sub.add_parser("report", help="collect a worker report")
    rp.add_argument("run_id")
    rp.add_argument("task_id")
    rp.set_defaults(func=cmd_report)

    ac = sub.add_parser("accept", help="accept a task")
    ac.add_argument("run_id")
    ac.add_argument("task_id")
    ac.set_defaults(func=cmd_accept)

    rt = sub.add_parser("return", help="return a task with defects")
    rt.add_argument("run_id")
    rt.add_argument("task_id")
    rt.add_argument("--defects", default="")
    rt.set_defaults(func=cmd_return)

    ro = sub.add_parser("reopen", help="reopen an accepted task")
    ro.add_argument("run_id")
    ro.add_argument("task_id")
    ro.set_defaults(func=cmd_reopen)

    stp = sub.add_parser("stop", help="stop a run, keep its state")
    stp.add_argument("run_id")
    stp.set_defaults(func=cmd_stop)

    rs = sub.add_parser("resume", help="resume a run from state.json")
    rs.add_argument("run_id")
    rs.set_defaults(func=cmd_resume)

    s = sub.add_parser("status", help="show runs")
    s.add_argument("--html", action="store_true")
    s.set_defaults(func=cmd_status)

    gc = sub.add_parser("gc", help="clean finished resources")
    gc.add_argument("--all", action="store_true")
    gc.set_defaults(func=cmd_gc)

    d = sub.add_parser("doctor", help="reconcile state with git")
    d.set_defaults(func=cmd_doctor)

    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        st.sweep(_root())
        args.func(args)
    except (RuntimeError, FileNotFoundError, TimeoutError) as e:
        _err(str(e))


if __name__ == "__main__":
    main()
