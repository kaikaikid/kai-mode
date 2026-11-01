"""travel 命令行：控制平面入口。

用法见 `travel --help`。所有状态变更都经过这里，AI 不直接改 state.json。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from . import adapters, dirty, scheduler, service, state as st, worktree
from .feishu import cards as fcards, config as fcfg, lark as flark, notify as fnotify
from .feishu import runner as frunner, triage as ftriage


# ---------------------------------------------------------------------------
# helpers


def _err(msg: str) -> "NoReturn":
    print(f"travel: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _warn_weak_adapter(adapter: "adapters.Adapter") -> None:
    """工具面没有硬拦的适配器只适合只读/建议，别拿它跑发货链路（契约 §3）。"""
    cap = adapters.capabilities(adapter)
    if cap.get("ok") and not cap.get("supportsTools"):
        print(f"[travel:warn] adapter '{adapter.name}' declares supportsTools=false: "
              f"worker tool surface is prompt-only, do not use it for shipping", file=sys.stderr)


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


def _coding_config(root: "Path") -> dict[str, Any]:
    p = st.coding_dir(root) / "config.json"
    cfg: dict[str, Any] = {}
    if p.exists():
        try:
            cfg = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
    # 项目配置实例可以登记收尾门；.coding/config.json 显式值优先。
    if not cfg.get("finish_cmd"):
        inst = root / ".ai" / "kai-mode.project.json"
        if inst.exists():
            try:
                gates = (json.loads(inst.read_text(encoding="utf-8")) or {}).get("gates") or {}
                if gates.get("finish_cmd"):
                    cfg["finish_cmd"] = gates["finish_cmd"]
            except Exception:
                pass
    return cfg


ISSUE_RE = re.compile(r"https?://github\.com/[\w.-]+/[\w.-]+/issues/(\d+)|(?<![\w#])#(\d+)")


def _issue_number(text: str) -> str | None:
    m = ISSUE_RE.search(text or "")
    if not m:
        return None
    return m.group(1) or m.group(2)


def _close_issue(s: dict[str, Any], root: "Path") -> tuple[bool, str]:
    """从 issue 文本自动识别票号并关票；识别不到就跳过，不阻塞发货。"""
    num = _issue_number(s.get("issue", ""))
    if not num:
        return False, "no issue reference"
    try:
        import subprocess as _sp
        r = _sp.run(["gh", "issue", "close", num, "--comment",
                     f"Shipped by V2 run {s.get('run_id')} (autopilot)."],
                    cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=30, creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0:
            return False, (r.stderr or r.stdout).strip()[:300]
        return True, f"closed #{num}"
    except Exception as e:
        return False, str(e)


def _kill_tree(pid: int) -> None:
    """杀进程树。Windows 上 .cmd 包装进程不带走子进程，必须 /T；POSIX 直接 SIGKILL。"""
    if os.name == "nt":
        import subprocess as _sp
        _sp.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0))
    else:
        import signal as _signal
        try:
            os.kill(pid, _signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def _ship(s: dict[str, Any], root: "Path") -> tuple[bool, str]:
    """发货：merge → 收尾门 → push → 关票。失败返回 (False, 原因)。"""
    cfg = _coding_config(root)
    # 未提交成果不可丢：merge 拿的是分支，worktree.remove 会删树——
    # worktree 里有任何未提交改动（含 untracked）都必须先拦下。
    wt = s.get("worktree") or ""
    if wt and Path(wt) != Path(root) and Path(wt).exists():
        porc = worktree._git("status", "--porcelain", cwd=wt, check=False).stdout
        dirty = [ln for ln in porc.splitlines() if ln.strip()]
        if dirty:
            return False, ("worktree has uncommitted changes (shipping would destroy them); "
                           "commit first: " + " | ".join(dirty[:5]))
    ok, msg = worktree.ship(s["run_id"], s["base_branch"], root, finish_cmd=cfg.get("finish_cmd"))
    ship = {"ok": ok, "message": msg}
    if ok:
        closed, cm = _close_issue(s, root)
        ship["issue_closed"] = closed
        ship["issue_message"] = cm
    s["ship"] = ship
    return ok, msg


def advance(s: dict[str, Any], root: "Path | None" = None) -> None:
    """按设计里的 phase 推进条件推进；只做确定性判断。循环到稳定。"""
    # 没有 UI 任务时 G1 自动跳过（G1 只在碰可见 UI 时才有意义）
    if s.get("tasks") and not _has_ui(s) and s.get("gates", {}).get("g1") == "pending":
        s["gates"]["g1"] = "skipped"
    # 跃迁模式（autopilot）：G0/G1 由门卫自批，不等人
    if s.get("autopilot"):
        if s.get("gates", {}).get("g0") == "pending":
            s["gates"]["g0"] = "approved"
        if s.get("gates", {}).get("g1") == "pending":
            s["gates"]["g1"] = "approved" if _has_ui(s) else "skipped"
        # G2 发货门：门卫代理自动批（默认开，跃迁模式专属）— 在 phase 推进循环之后执行

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
        elif phase == "blocked":
            # 救场出口：review inconclusive / rework 后任务仍有可继续的活 → 回 delegating
            # 让 drive 接手；任务全终态（真 blocked）或 ship 失败的 run 不在此复活。
            if any(t.get("status") in {"pending", "ready", "running", "review", "returned"} for t in tasks):
                s["phase"] = "delegating"
            elif tasks and all(t.get("status") in {"accepted", "abandoned"} for t in tasks):
                # 全验收后才被卡 blocked 的 run（验收发生在 blocked 期间）：回 reviewing
                # 走常规 reviewing→closing 推进，ship 才有触发点。
                s["phase"] = "reviewing"

        if s.get("phase") == before:
            break

    # 任务图里已有 blocked/failed，且没有可继续的活 → 整 run 转 blocked，别停在 reviewing/delegating 假象
    tasks = s.get("tasks", [])
    if (tasks and s.get("phase") not in {"blocked"} | st.TERMINAL_PHASES
            and any(t.get("status") in {"blocked", "failed"} for t in tasks)
            and all(t.get("status") in {"accepted", "abandoned", "blocked", "failed"} for t in tasks)):
        blocked_ids = [t["id"] for t in tasks if t.get("status") in {"blocked", "failed"}]
        s["phase"] = "blocked"
        s["resume"]["next_action"] = "task(s) blocked: " + ", ".join(blocked_ids)

    # 跃迁模式：phase 推进到 closing 后，门卫代理自动批 G2 → 发货（merge → 收尾门 → push → 关票）。
    # 发货权只归加急跃迁（can_ship）：普通 jump 停在 closing，等舰桥或人工 gate g2 发货。
    if s.get("autopilot") and s.get("phase") == "closing" and s.get("gates", {}).get("g2") == "pending":
        if root is None:
            pass
        elif s.get("can_ship"):
            ok, msg = _ship(s, root)
            if ok:
                s["gates"]["g2"] = "approved"
                s["phase"] = "done"
                s["resume"]["next_action"] = "done"
                worktree.remove(s["run_id"], root)
            else:
                s["phase"] = "blocked"
                s["resume"]["next_action"] = f"ship failed: {msg}"
        else:
            s["resume"]["next_action"] = "construction done; no ship right — ship via bridge or `coding gate <run> g2 approve`"


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
    ships = max(1, min(3, getattr(args, "ships", None) or 1))
    fleet = getattr(args, "fleet", None) or st.new_fleet_id()
    crew = max(1, min(5, getattr(args, "crew", None) or 5))
    ids: list[str] = []
    for _ in range(ships):
        with st.lock(root):
            rid = st.new_run_id()
            s = {
                "schema_version": st.SCHEMA_VERSION,
                "run_id": rid,
                "issue": args.issue,
                "phase": "queued",
                "priority": "urgent" if args.urgent else "normal",
                "fleet_id": fleet,
                "ship_limit": ships,
                "crew_limit": crew,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "base_branch": args.base or worktree.base_branch(root),
                "branch": worktree.branch_name(rid),
                "worktree": str(worktree.worktree_path(rid, root)),
                "depends_on_runs": args.depends or [],
                "autopilot": bool(getattr(args, "autopilot", False)),
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
            ids.append(rid)
    for rid in ids:
        print(rid)
    return ids[0]


def cmd_warp(args: argparse.Namespace) -> None:
    """曲速：全自动挡（不发货）。autopilot=True，施工+门由门卫代理自批，只在红线/异常时停。
    发货权只归跃迁（jump / --urgent）：普通 warp 停在 closing，由舰桥或人工 gate g2 发货。"""
    # 复用 cmd_run 的建 run 逻辑，但强制 autopilot
    args.autopilot = True
    args.urgent = getattr(args, "urgent", False)
    if getattr(args, "base", None) is None:
        # base 优先级：显式 --base > 仓里还有 dev 就用 dev（老仓的约定）> 当前分支。
        # 本仓已把 dev 并进 main 并删掉，所以这里会落到 main。
        _r = worktree._git("rev-parse", "--verify", "dev", cwd=_root(), check=False)
        args.base = "dev" if _r.returncode == 0 else worktree.base_branch(_root())
    args.max_tokens = getattr(args, "max_tokens", 200000)
    args.depends = getattr(args, "depends", [])
    if getattr(args, "ships", None) is None:
        args.ships = 2
    before = {r["run_id"] for r in st.list_runs(_root())}
    rid = cmd_run(args)
    ids = [r["run_id"] for r in st.list_runs(_root()) if r["run_id"] not in before]
    for one in ids:
        with st.lock(_root()):
            s = st.load(one, _root())
            s["autopilot"] = True
            s["can_ship"] = bool(getattr(args, "urgent", False))
            st.save(s, _root())
    if getattr(args, "tasks", None):
        cmd_plan(argparse.Namespace(run_id=rid, file=args.tasks))
    print(f"warp run {' '.join(ids)} autopilot=True")


def cmd_jump(args: argparse.Namespace) -> None:
    """跃迁：加急全自动，有发货权。"""
    args.urgent = True
    args.autopilot = True
    cmd_warp(args)


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
            "fleet_id": st.new_fleet_id(),
            "ship_limit": 2,
            "crew_limit": 5,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "base_branch": worktree.base_branch(root),
            "branch": worktree.branch_name(rid),
            "worktree": str(root),  # 接管当前工作区，不建树
            "depends_on_runs": [],
            "autopilot": False,
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


def cmd_dirty(args: argparse.Namespace) -> None:
    """打印主树脏件分类；product 类才阻塞发货。"""
    info = dirty.inspect(_root())
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        print(dirty.format_human(info))


def cmd_park(args: argparse.Namespace) -> None:
    """把主树里的无关产品改动收进命名 stash，留回执；不删、不改写。"""
    res = dirty.park(_root(), message=args.message or "", include_records=args.all)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if not res.get("ok"):
        raise SystemExit(1)


def cmd_unpark(args: argparse.Namespace) -> None:
    """把收起的改动放回工作区（apply，不 drop）。"""
    if args.list:
        print(json.dumps(dirty.list_parked(_root()), ensure_ascii=False, indent=2))
        return
    res = dirty.unpark(_root(), args.ref)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if not res.get("ok"):
        raise SystemExit(1)


def cmd_plan(args: argparse.Namespace) -> None:
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        if s["phase"] not in {"planning", "design", "queued"}:
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
        advance(s, root)
        _save(s)
        print(f"planned {len(norm)} task(s)")


def cmd_gate(args: argparse.Namespace) -> None:
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        g = args.gate
        if g not in {"g0", "g1", "g2"}:
            _err("gate must be g0, g1 or g2")
        if g == "g2" and args.decision == "approve":
            # G2 阶段守卫：发货只能发生在「全部验收、无人还在干活」的 closing 上
            bad = []
            if s.get("phase") != "closing":
                bad.append(f"phase is {s.get('phase')}, not closing")
            not_done = [t["id"] for t in s.get("tasks", [])
                        if t.get("status") not in {"accepted", "abandoned"}]
            if not_done:
                bad.append("tasks not accepted/abandoned: " + ", ".join(not_done[:5]))
            live = [x["id"] for x in s.get("sessions", [])
                    if x.get("status") == "running" and x.get("pid")
                    and st._pid_alive(int(x["pid"]))]
            if live:
                bad.append("live sessions: " + ", ".join(live))
            if bad:
                _err("g2 blocked: " + "; ".join(bad))
        if args.decision == "approve":
            s["gates"][g] = "approved"
        elif args.decision == "reject":
            s["gates"][g] = "rejected"
            s["phase"] = {"g0": "planning", "g1": "design", "g2": "reviewing"}[g]
        else:
            s["gates"][g] = "skipped"

        if g == "g2" and args.decision == "approve":
            ok, msg = _ship(s, root)
            if not ok:
                s["phase"] = "blocked"
                s["resume"]["next_action"] = f"ship failed: {msg}"
                _save(s)
                _err(f"ship failed, run blocked: {msg}")
            s["gates"]["g2"] = "approved"
            s["phase"] = "done"
            s["resume"]["next_action"] = "done"
            _save(s)
            worktree.remove(s["run_id"], root)
            print(f"shipped: {msg}")
            return

        advance(s, root)
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
        if s.get("phase") in st.TERMINAL_PHASES:
            _err(f"run is terminal ({s['phase']}); spawn rejected")
        if s.get("phase") == "queued":
            _err("run is queued; wait for a free slot")
        t = _task(s, args.task_id)
        ok, why = scheduler.can_spawn(s, t, root)
        if not ok:
            _err(f"cannot spawn: {why}")
        if t.get("status") not in {"pending", "returned", "ready"}:
            _err(f"task {t['id']} is {t.get('status')}")
        if t.get("status") != "returned" and not scheduler.deps_done(t, {x["id"]: x for x in s["tasks"]}):
            _err("deps not done")

        adapter = adapters.pick(args.adapter)
        _warn_weak_adapter(adapter)
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
        f"- Work only inside your own worktree. Never run control-plane commands (`coding ...`); "
        f"only the orchestrator owns the run.\n"
        f"- Never run destructive commands (rm -rf, drop, force push). They are denied.\n"
        f"- Verify before reporting: build, test, or exercise the path; report the command and outcome.\n"
        f"- Commit before reporting: `git add -- <files you changed> && git commit -m \"<task>: <title>\"`. "
        f"Uncommitted work is blocked at shipping and will be treated as not delivered.\n"
        f"- End your reply with ONE JSON object and nothing after it:\n"
        f'{{"result":"done|partial|blocked","files_changed":["path — what"],'
        f'"commit":"<HEAD sha after your commit; empty if nothing changed>",'
        f'"verification":["cmd -> outcome"],"open_questions":["..."],"notes":"<=100 chars"}}\n'
    )


def cmd_report(args: argparse.Namespace) -> None:
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        if s.get("phase") in st.TERMINAL_PHASES:
            _err(f"run is terminal ({s['phase']}); report rejected")
        t = _task(s, args.task_id)
        sid = t.get("session_id")
        if not sid:
            _err("task has no session")
        sess = next((x for x in s.get("sessions", []) if x["id"] == sid), None)
        if not sess:
            _err("session record missing")
        sdir = _session_dir(s["run_id"], sid)
        try:
            adapter = adapters.get(sess["adapter"])
        except Exception as e:
            _err(f"cannot reopen adapter '{sess.get('adapter')}' recorded in state: {e}")
        pid = 0
        pidf = sdir / "pid"
        if pidf.exists():
            try:
                pid = int(pidf.read_text().strip())
            except Exception:
                pid = 0
    # 等待子会话进程结束放在锁外：长任务不能占住整个仓库的写锁
    if pid > 0:
        deadline = time.time() + args.timeout
        while time.time() < deadline and st._pid_alive(pid):
            time.sleep(0.5)
        if st._pid_alive(pid):
            # 超时：先杀进程树再按失败处理（重试/计次语义见 P1-8）
            _kill_tree(pid)
            with st.lock(root):
                s = st.load(args.run_id, root)
                t = _task(s, args.task_id)
                t["status"] = "failed"
                sess = next((x for x in s.get("sessions", []) if x["id"] == t.get("session_id")), None)
                if sess:
                    sess["status"] = "failed"
                s["resume"]["next_action"] = f"worker {t['id']} timed out and was killed"
                _save(s)
            _err(f"worker timed out after {args.timeout}s; process tree killed")
    # 进程可能已经结束，报告落盘即可
    text = adapter.read({"dir": str(sdir)})
    report = adapters.parse_report(text)
    report_path = _report_path(args.run_id, args.task_id)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    with st.lock(root):
        s = st.load(args.run_id, root)
        t = _task(s, args.task_id)
        # 提交对账：报了 commit 就必须是 worktree HEAD 的祖先（存在且已落在分支上）
        commit = str(report.get("commit") or "").strip()
        if commit:
            wt = s.get("worktree") or str(root)
            r = worktree._git("merge-base", "--is-ancestor", commit, "HEAD", cwd=wt, check=False)
            if r.returncode != 0:
                report["result"] = "partial"
                report["notes"] = (report.get("notes", "") + " [commit not on worktree HEAD]").strip()
        # 报告与 diff 对账
        changed = worktree.changed_files(s["run_id"], s["base_branch"], root)
        claimed = report.get("files_changed") or []
        claimed_paths = [c.split(" — ")[0].strip() for c in claimed if isinstance(c, str)]
        missing = [c for c in claimed_paths if c and c not in changed]
        if missing:
            report["result"] = "partial"
            report["notes"] = (report.get("notes", "") + f" [mismatch: {', '.join(missing[:5])}]").strip()
        sess = next((x for x in s.get("sessions", []) if x["id"] == t.get("session_id")), None)
        if sess:
            sess["status"] = "finished"
        t["status"] = "review"
        s["resume"]["next_action"] = f"review {t['id']}"
        _save(s)
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _build_review_brief(s: dict[str, Any], t: dict[str, Any]) -> str:
    root = _root()
    wt = s.get("worktree") or str(root)
    mb = worktree._git("merge-base", s["base_branch"], worktree.branch_name(s["run_id"]),
                       cwd=root, check=False).stdout.strip()
    diff_cmd = f"git diff {mb}..HEAD" if mb else "git diff"
    lines = [
        "REVIEWER: you are an independent gatekeeper. You did not write this code.",
        "Read the actual diff, do not trust any report. You must not modify files.",
        "",
        f"TASK: {t['title']}",
        "",
        t.get("brief", ""),
        "",
        "ACCEPTANCE CRITERIA:",
        *[f"- {a}" for a in t.get("ac", [])],
        "",
        "DIFF COMMAND:",
        f"  {diff_cmd}",
        "",
        "CHECK:",
        "- every AC is actually met by the diff;",
        "- no files changed outside the declared touchset;",
        "- no destructive or unrelated changes.",
        "",
        "End your reply with ONE JSON object and nothing after it:",
        '{"verdict":"accept|return","defects":["..."],"reason":"<=100 chars",'
        '"result":"done","files_changed":[],"verification":[],"open_questions":[]}',
    ]
    return chr(10).join(lines) + chr(10)


def cmd_review(args: argparse.Namespace) -> None:
    """门卫子代理：独立上下文只读审查，产出 accept/return 裁决。"""
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        if s.get("phase") in st.TERMINAL_PHASES:
            _err(f"run is terminal ({s['phase']}); review rejected")
        t = _task(s, args.task_id)
        if t.get("status") != "review":
            _err(f"task {t['id']} is {t.get('status')}, not review")
        adapter = adapters.pick(args.adapter)
        _warn_weak_adapter(adapter)
        sid = _new_sid()
        sdir = _session_dir(s["run_id"], sid)
        brief = _build_review_brief(s, t)
        cwd = Path(s["worktree"]) if s.get("worktree") else root
    # 评审子代理在锁外跑，避免一次审查占住整个仓库的写锁
    handle = adapter.spawn(brief, cwd, sdir, tier="careful", timeout=args.timeout, read_only=True)
    adapter.wait(handle, args.timeout)
    text = adapter.read(handle)
    rep = adapters.parse_report(text)
    verdict = rep.get("verdict") or ("accept" if rep.get("result") == "done" else None)
    if verdict not in {"accept", "return"}:
        # 评审员结论不明确（报告解析失败/无 verdict）：这不是 worker 的错，
        # 不烧重做轮次；转 blocked 叫醒人——门卫失灵按异常处理，不静默放行。
        with st.lock(root):
            s = st.load(args.run_id, root)
            t = _task(s, args.task_id)
            t["review"] = {
                "verdict": "inconclusive",
                "defects": [],
                "reason": rep.get("reason", "") or rep.get("notes", "") or "reviewer report unparseable",
                "session": sid,
            }
            t["session_id"] = sid
            s.setdefault("sessions", []).append({
                "id": sid, "task_id": t["id"], "adapter": adapter.name,
                "pid": handle.get("pid"), "started_at": time.time(), "status": "finished",
                "role": "reviewer",
            })
            if args.apply:
                s["phase"] = "blocked"
                s["resume"]["next_action"] = f"review inconclusive on {t['id']}: {t['review']['reason']}"
            _save(s)
        print(json.dumps(t["review"], ensure_ascii=False, indent=2))
        return
    with st.lock(root):
        s = st.load(args.run_id, root)
        t = _task(s, args.task_id)
        t["review"] = {
            "verdict": verdict,
            "defects": rep.get("defects", []),
            "reason": rep.get("reason", "") or rep.get("notes", ""),
            "session": sid,
        }
        t["session_id"] = sid
        s.setdefault("sessions", []).append({
            "id": sid, "task_id": t["id"], "adapter": adapter.name,
            "pid": handle.get("pid"), "started_at": time.time(), "status": "finished",
            "role": "reviewer",
        })
        if args.apply:
            if verdict == "accept":
                t["status"] = "accepted"
                s["resume"]["last_accepted"] = t["id"]
                s["resume"]["next_action"] = "next"
            else:
                t["status"] = "returned"
                t["attempts"] = int(t.get("attempts", 0)) + 1
                t["defects"] = "; ".join(rep.get("defects", [])) or rep.get("reason", "")
                if t["attempts"] >= 3:
                    t["status"] = "blocked"
                s["resume"]["next_action"] = f"rework {t['id']}"
            advance(s, root)
        _save(s)
    print(json.dumps(t["review"], ensure_ascii=False, indent=2))


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
        advance(s, root)
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
        # verify=False：被篡改的 run 也必须能停机杀进程，诊断面不因验签失灵
        s = st.load(args.run_id, root, verify=False)
        # 停机先杀人再改状态：只杀 sessions 里登记的 running pid，绝不按镜像名扫杀
        killed = []
        for sess in s.get("sessions", []):
            if sess.get("status") != "running":
                continue
            pid = int(sess.get("pid") or 0)
            if pid > 0 and st._pid_alive(pid):
                _kill_tree(pid)
                killed.append(str(pid))
            sess["status"] = "stopped"
        s["phase"] = "cancelled"
        s["resume"]["next_action"] = "stopped" + (f" (killed pids: {','.join(killed)})" if killed else "")
        _save(s)
        print(f"stopped {s['run_id']}" + (f"; killed pids {','.join(killed)}" if killed else ""))


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
        advance(s, root)
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


def cmd_feishu(args: argparse.Namespace) -> None:
    """飞书桥：状态 / 自检 / 分诊预览 / 起桥。运行时实现见 v2/coding/feishu/。"""
    root = _root()
    action = getattr(args, "action", None) or "status"
    cfg = fcfg.load(root)

    if action == "status":
        problems = fcfg.problems(cfg)
        rows = fnotify.run_rows(root)
        print(json.dumps({
            "enabled": bool(cfg.get("enabled")),
            "bots": [{"name": b.get("name"), "profile": b.get("profile"),
                      "chat_id": b.get("chat_id")} for b in cfg.get("bots") or []],
            "chat": cfg.get("chat"),
            "problems": problems,
            "runs": rows,
            "config": str(fcfg.machine_path()),
        }, ensure_ascii=False, indent=2))
        return

    if action == "doctor":
        v = flark.version()
        chats = flark.chats("")
        print(json.dumps({
            "lark_cli": (v.stdout or v.stderr or "").strip(),
            "cli_ok": v.returncode == 0,
            "chats_rc": chats.returncode,
            "problems": fcfg.problems(cfg),
            "config": str(fcfg.machine_path()),
        }, ensure_ascii=False, indent=2))
        return

    if action == "triage":
        text = " ".join(getattr(args, "text", []) or [])
        print(json.dumps(ftriage.decide(text), ensure_ascii=False, indent=2))
        return

    if action == "board":
        print(json.dumps(fcards.board(fnotify.run_rows(root)), ensure_ascii=False, indent=2))
        return

    if action == "send-test":
        bot = fcfg.bot_for(cfg)
        chat = str(bot.get("chat_id") or "")
        if not chat:
            _err("no chat_id configured; set bots[0].chat_id in the feishu config")
        r = flark.send_text(str(bot.get("profile") or ""), chat,
                                  " ".join(getattr(args, "text", []) or []) or "kai-mode 自检")
        print(json.dumps({"rc": r.returncode, "stderr": (r.stderr or "").strip()[:300]},
                         ensure_ascii=False, indent=2))
        if r.returncode != 0:
            raise SystemExit(1)
        return

    if action == "run":
        raise SystemExit(frunner.run(root, once=bool(getattr(args, "once", False))))

    _err(f"unknown feishu action: {action}")


def cmd_harness(args: argparse.Namespace) -> None:
    """宿主适配器自举：check 看现状，verify 真跑用例，trust 登记放行。

    契约见 v2/skills/travel/host-adapter.md。
    """
    root = _root()
    action = getattr(args, "action", None) or "check"
    if action in {"check", "list"}:
        print(json.dumps(adapters.inventory(root), ensure_ascii=False, indent=2))
        return
    name = getattr(args, "name", None)
    if not name:
        _err(f"harness {action} needs an adapter name")
    if action == "verify":
        res = adapters.verify(name, root, timeout=getattr(args, "timeout", None))
        print(json.dumps(res, ensure_ascii=False, indent=2))
        if not res.get("ok"):
            raise SystemExit(1)
        print(f"travel: verified. Next: travel harness trust {name}", file=sys.stderr)
        return
    if action == "trust":
        rec = adapters.trust(name, root)
        print(json.dumps(rec, ensure_ascii=False, indent=2))
        receipt = Path(rec["path"]).with_suffix(".verify.json")
        ok = False
        if receipt.is_file():
            try:
                v = json.loads(receipt.read_text(encoding="utf-8"))
                ok = bool(v.get("ok")) and v.get("sha256") == rec["sha256"] and v.get("adapter") == name
            except Exception:
                ok = False
        if not ok:
            print(f"[travel:warn] {name} has no passing verify receipt for THIS file "
                  f"(verified or unread receipt only); you are trusting an unverified adapter. "
                  f"Read it first.", file=sys.stderr)
        return
    _err(f"unknown harness action: {action}")


# ---------------------------------------------------------------------------
# argparse


def promote_queued(root: "Path") -> list[str]:
    """惰性排班：把 queued 的 run 按创建时间依次塞进空槽并推进。"""
    promoted: list[str] = []
    with st.lock(root):
        queued = sorted(
            (r for r in st.list_runs(root) if r.get("phase") == "queued"),
            key=lambda r: r.get("created_at", ""),
        )
        for s in queued:
            ok, _why = scheduler.can_start(s, root)
            if not ok:
                continue
            worktree.create(s["run_id"], s["base_branch"], root)
            s["phase"] = "planning"
            s["resume"]["next_action"] = "plan"
            advance(s, root)
            st.save(s, root)
            promoted.append(s["run_id"])
    return promoted


def cmd_assimilate(args: argparse.Namespace) -> None:
    """吞并外部分支：需要用户明确同意。"""
    root = _root()
    branch = args.branch
    # 用户确认门：必须显式 --approve
    if not getattr(args, "approve", False):
        print(json.dumps({"ok": False, "reason": "user approval required: re-run with --approve"}, ensure_ascii=False))
        return
    # merge
    r = worktree._git("merge", "--no-ff", "-m", f"assimilate {branch}", branch, cwd=root, check=False)
    if r.returncode != 0:
        worktree._git("merge", "--abort", cwd=root, check=False)
        print(json.dumps({"ok": False, "reason": (r.stderr or r.stdout).strip()[:300]}, ensure_ascii=False))
        return
    print(json.dumps({"ok": True, "message": "assimilated " + branch}, ensure_ascii=False))


def cmd_drive(args: argparse.Namespace) -> None:
    """全自动驱动：脚本循环 spawn → report → review → accept，直到所有 run 到终态或 blocked。"""
    root = _root()
    for _step in range(args.max_steps):
        promote_queued(root)
        ids = [args.run] if args.run else [r["run_id"] for r in st.list_runs(root)]
        runs = []
        for rid in ids:
            try:
                r = st.load(rid, root)
            except FileNotFoundError:
                continue
            if r.get("phase") not in st.TERMINAL_PHASES:
                runs.append(r)
        if not runs:
            break
        acted = False
        for s in runs:
            rid = s["run_id"]
            if s.get("phase") in {"blocked", "queued"}:
                continue
            if s.get("autopilot") and not s.get("tasks"):
                with st.lock(root):
                    s2 = st.load(rid, root)
                    s2["phase"] = "blocked"
                    s2["resume"]["next_action"] = "no task graph; plan required"
                    st.save(s2, root)
                acted = True
                continue
            # 1) 收已经跑完的 worker 报告
            for t in list(s.get("tasks", [])):
                if t.get("status") == "running":
                    cmd_report(argparse.Namespace(run_id=rid, task_id=t["id"], timeout=args.timeout))
                    acted = True
                    s = st.load(rid, root)
            # 2) 门卫子代理审查
            for t in list(s.get("tasks", [])):
                if t.get("status") == "review":
                    cmd_review(argparse.Namespace(run_id=rid, task_id=t["id"],
                                                   adapter=args.review_adapter or args.adapter,
                                                   timeout=args.review_timeout, apply=True))
                    acted = True
                    s = st.load(rid, root)
            # 3) 派 ready 任务
            for t in scheduler.ready_tasks(s, root):
                ok, _why = scheduler.can_spawn(s, t, root)
                if not ok:
                    break
                cmd_spawn(argparse.Namespace(run_id=rid, task_id=t["id"], adapter=args.adapter,
                                             timeout=args.timeout, retry=False))
                acted = True
                s = st.load(rid, root)
        if not acted:
            break
    summary = []
    for r in st.list_runs(root):
        summary.append({"run": r["run_id"], "phase": r.get("phase"),
                        "issue": r.get("issue"), "ship": r.get("ship")})
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def cmd_serve(args: argparse.Namespace) -> None:
    """本地监工服务：只读 API + 受控 gate/stop/drive；默认只绑 127.0.0.1。"""
    service.serve(args, _root())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="travel", description="V2 execution kernel control plane")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="create a run")
    r.add_argument("--fleet", default=None, help="fleet id; slots are per-fleet")
    r.add_argument("--ships", type=int, default=None, help="ship count 1-3 (default 2)")
    r.add_argument("--crew", type=int, default=None, help="crew cap 1-5 (default 5)")
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

    di = sub.add_parser("dirty", help="classify dirty files in the main tree")
    di.add_argument("--json", action="store_true")
    di.set_defaults(func=cmd_dirty)

    pk = sub.add_parser("park", help="stash product changes in the main tree (reversible)")
    pk.add_argument("-m", "--message", default="")
    pk.add_argument("--all", action="store_true", help="park record files too")
    pk.set_defaults(func=cmd_park)

    up = sub.add_parser("unpark", help="apply a parked stash back")
    up.add_argument("ref", nargs="?")
    up.add_argument("--list", action="store_true")
    up.set_defaults(func=cmd_unpark)

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
    rp.add_argument("--timeout", type=int, default=1800)
    rp.set_defaults(func=cmd_report)

    rv = sub.add_parser("review", help="independent gatekeeper review (read-only subagent)")
    rv.add_argument("run_id")
    rv.add_argument("task_id")
    rv.add_argument("--adapter")
    rv.add_argument("--timeout", type=int, default=900)
    rv.add_argument("--apply", action="store_true", help="apply verdict to task status")
    rv.set_defaults(func=cmd_review)

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

    hz = sub.add_parser("harness", help="host adapters: check / list / verify / trust")
    hz.add_argument("action", nargs="?", default="check", choices=["check", "list", "verify", "trust"])
    hz.add_argument("name", nargs="?", default=None, help="adapter name (for verify / trust)")
    hz.add_argument("--timeout", type=int, default=None, help="per-probe timeout seconds (default 180)")
    hz.set_defaults(func=cmd_harness)

    fs = sub.add_parser("feishu", help="feishu bridge: status / doctor / triage / board / send-test / run")
    fs.add_argument("action", nargs="?", default="status",
                    choices=["status", "doctor", "triage", "board", "send-test", "run"])
    fs.add_argument("text", nargs="*", default=[], help="text for triage / send-test")
    fs.add_argument("--once", action="store_true", help="run: do one notify tick and exit")
    fs.set_defaults(func=cmd_feishu)

    wp = sub.add_parser("warp", help="autopilot run: warp mode (no ship)")
    wp.add_argument("--fleet", default=None, help="fleet id; slots are per-fleet")
    wp.add_argument("--ships", type=int, default=None, help="ship count 1-3 (default 2)")
    wp.add_argument("--crew", type=int, default=None, help="crew cap 1-5 (default 5)")
    wp.add_argument("issue")
    wp.add_argument("--urgent", action="store_true")
    wp.add_argument("--base")
    wp.add_argument("--depends", nargs="*", default=[])
    wp.add_argument("--tasks", help="task graph JSON file; plan immediately")
    wp.set_defaults(func=cmd_warp)

    jp = sub.add_parser("jump", help="urgent autopilot run (ships)")
    jp.add_argument("--fleet", default=None, help="fleet id; slots are per-fleet")
    jp.add_argument("--ships", type=int, default=None, help="ship count 1-3 (default 2)")
    jp.add_argument("--crew", type=int, default=None, help="crew cap 1-5 (default 5)")
    jp.add_argument("issue")
    jp.add_argument("--base")
    jp.add_argument("--depends", nargs="*", default=[])
    jp.add_argument("--tasks", help="task graph JSON file; plan immediately")
    jp.set_defaults(func=cmd_jump)

    asp = sub.add_parser("assimilate", help="merge an external branch (needs user approval)")
    asp.add_argument("branch")
    asp.add_argument("--run", default=None, help="run id")
    asp.add_argument("--approve", action="store_true", help="user approved assimilation")
    asp.set_defaults(func=cmd_assimilate)

    dr = sub.add_parser("drive", help="run the whole loop unattended")
    dr.add_argument("--run")
    dr.add_argument("--adapter")
    dr.add_argument("--review-adapter")
    dr.add_argument("--max-steps", type=int, default=500)
    dr.add_argument("--timeout", type=int, default=1800)
    dr.add_argument("--review-timeout", type=int, default=900)
    dr.set_defaults(func=cmd_drive)

    sv = sub.add_parser("serve", help="local supervisor service (read API + controlled actions)")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8765)
    sv.add_argument("--token", default=None, help="require X-Travel-Token on POST")
    sv.add_argument("--board-dir", default=None, help="serve index.html/board.json from here")
    sv.add_argument("--drive", action="store_true", help="run `travel drive` periodically")
    sv.add_argument("--drive-interval", type=int, default=60)
    sv.add_argument("--refresh-cmd", default=None, help="command to refresh the board")
    sv.add_argument("--max-age", type=int, default=30, help="board age before refresh (minutes)")
    sv.add_argument("--allow-remote", action="store_true")
    sv.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        st.sweep(_root())
        args.func(args)
        promote_queued(_root())
    except (RuntimeError, FileNotFoundError, TimeoutError) as e:
        _err(str(e))


if __name__ == "__main__":
    main()
