"""fleet 命令行：控制平面入口。

用法见 `fleet --help`（`travel`/`coding` 兼容别名）。所有状态变更都经过这里，AI 不直接改 state.json。
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

from . import TASK_SCHEMA_VERSION, auto, dirty, scheduler, state as st, worktree


# ---------------------------------------------------------------------------
# helpers


def _err(msg: str) -> "NoReturn":
    print(f"fleet: {msg}", file=sys.stderr)
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
                     f"Shipped by fleet run {s.get('run_id')} (autopilot)."],
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
    # 速推模式（autopilot）：G0/G1 由门卫自批，不等人
    if s.get("autopilot"):
        if s.get("gates", {}).get("g0") == "pending":
            s["gates"]["g0"] = "approved"
        if s.get("gates", {}).get("g1") == "pending":
            s["gates"]["g1"] = "approved" if _has_ui(s) else "skipped"
        # G2 发货门：门卫代理自动批（默认开，速推模式专属）— 在 phase 推进循环之后执行

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
            # return_locked 的任务不算「可继续的活」：第三次 return 锁死的只留人工路。
            if any(t.get("status") in {"pending", "ready", "running", "review"} or
                    (t.get("status") == "returned" and not t.get("return_locked"))
                    for t in tasks):
                s["phase"] = "delegating"
            elif tasks and all(t.get("status") in {"accepted", "abandoned"} for t in tasks):
                # 全验收后才被卡 blocked 的 run（验收发生在 blocked 期间）：回 reviewing
                # 走常规 reviewing→closing 推进，ship 才有触发点。
                s["phase"] = "reviewing"
        elif phase == "cancelled":
            # CANCELLED→CLOSED：取消后的确认落档。live session 已被 cmd_stop 清掉；
            # 这里只在「无在途任务、无运行中会话」时落档 closed_at，不复活、不逆转。
            live = [x["id"] for x in s.get("sessions", []) if x.get("status") == "running"]
            busy = any(t.get("status") in {"pending", "ready", "running", "review", "returned"}
                       for t in tasks)
            if not live and not busy and not s.get("closed_at"):
                import time as _t
                s["closed_at"] = _t.strftime("%Y-%m-%dT%H:%M:%S")

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

    # 速推模式：phase 推进到 closing 后，门卫代理自动批 G2 → 发货（merge → 收尾门 → push → 关票）。
    # 发货权只归加急速推（can_ship）：普通开团停在验收门，等康娜或人工 gate g2 发货。
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
                st.set_blocked_reason(s, "ship_failed")
                st.record_event(s, "ship_failed", message=msg[:200])
        else:
            s["resume"]["next_action"] = "construction done; no ship right — ship via gold or `fleet gate <run> g2 approve`"


def _task(s: dict[str, Any], tid: str) -> dict[str, Any]:
    for t in s.get("tasks", []):
        if t.get("id") == tid:
            return t
    _err(f"task not found: {tid}")


def _report_path(run_id: str, tid: str) -> Path:
    return st.run_dir(run_id, _root()) / "sessions" / f"{tid}.report.json"


def _card_report_path(run_id: str, sid: str) -> str:
    """任务卡上的报告路径：绝对路径。

    子代理在 worktree 里工作，而 `.coding/` 住渲染根——相对路径会被解析到 worktree，
    报告写到内核读不到的地方（smoke 实测踩到）。给绝对路径，双方没有歧义。
    """
    return str(st.run_dir(run_id, _root()) / "sessions" / sid / "report.json")


def _diff_base(s: dict[str, Any]) -> str:
    """native 任务的 diff 基线：分支与 base 的 merge-base，取不到退回 base 分支名。"""
    try:
        mb = worktree._git("merge-base", s.get("base_branch") or "main",
                           s.get("branch") or worktree.branch_name(s["run_id"]),
                           cwd=_root(), check=False).stdout.strip()
    except Exception:
        mb = ""
    return mb or s.get("base_branch") or "HEAD"


def _claim_card(s: dict[str, Any], t: dict[str, Any], sess: dict[str, Any]) -> dict[str, Any]:
    """宿主原生子代理的任务卡：状态里能确定的都放进来，不依赖进程句柄。"""
    return {
        "task_id": t["id"],
        "brief": t.get("brief", ""),
        "worktree": s.get("worktree") or str(_root()),
        "touchset": list(t.get("touchset", [])),
        "ac": list(t.get("ac", [])),
        "report_path": _card_report_path(s["run_id"], sess["id"]),
        "diff_base": sess.get("diff_base") or _diff_base(s),
    }


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
    """开团：无人值守自动挡（不发货）。autopilot=True，施工+门由门卫代理自批，只在红线/异常时停。
    发货权只归速推（jump / --urgent）：普通开团停在验收门，由康娜或人工 gate g2 发货。"""
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
        args.ships = 1
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
    if not getattr(args, "no_auto", False):
        for rid in ids:
            print(f"auto-driving {rid}")
            auto.drive(rid)


def cmd_jump(args: argparse.Namespace) -> None:
    """速推：加急无人值守，有发货权。默认无人值守跑到底；--no-auto 才退回手动逐条推。"""
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
            "ship_limit": 1,
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
                # Task 显式版本：创建时锁定 TASK_SCHEMA_VERSION，运行中不静默升级
                # （旧任务按锁定版本执行；升版只追加——见 docs/schema.md）。
                "schema_version": TASK_SCHEMA_VERSION,
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
                "blocked_reason": None,
                "blocked_at": None,
                "return_locked": False,
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
                st.set_blocked_reason(s, "ship_failed")
                st.record_event(s, "ship_failed", message=msg[:200])
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


def cmd_claim(args: argparse.Namespace) -> None:
    """宿主原生子代理占位：校验后写 session（mode=native）并输出任务卡，不起进程。

    幂等：同一 task 已经是 running 且有 native session 时，原样返回同一张卡，
    不重复占槽、不新增 session。
    """
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        if s.get("phase") in st.TERMINAL_PHASES:
            _err(f"run is terminal ({s['phase']}); claim rejected")
        if s.get("phase") == "queued":
            _err("run is queued; wait for a free slot")
        t = _task(s, args.task_id)

        sid = t.get("session_id")
        if t.get("status") == "running" and sid:
            sess = next((x for x in s.get("sessions", []) if x.get("id") == sid), None)
            if sess is None:
                _err(f"task {t['id']} is running but session {sid} is missing from state")
            mode = st.session_mode(sess)
            if mode != "native":
                _err(f"task {t['id']} is already running under a {mode} session ({sid}); "
                     f"use `fleet report {s['run_id']} {t['id']}`")
            print(json.dumps(_claim_card(s, t, sess), ensure_ascii=False, indent=2))
            return

        if t.get("status") not in {"pending", "ready", "returned"}:
            _err(f"task {t['id']} is {t.get('status')}")
        if t.get("status") != "returned" and not scheduler.deps_done(
                t, {x["id"]: x for x in s["tasks"]}):
            _err("deps not done")
        touchset = t.get("touchset", [])
        if scheduler.touchsets_overlap(touchset, scheduler.inflight_touchsets(s)):
            _err("touchset overlaps an in-flight task in this run")
        for other, others in scheduler.other_runs_touchsets(s, root):
            if scheduler.touchsets_overlap(touchset, others):
                _err(f"touchset overlaps an in-flight task in run {other}")
        ok, why = scheduler.can_spawn(s, t, root)
        if not ok:
            _err(f"cannot claim: {why}")

        sid = _new_sid()
        sess = {
            "id": sid,
            "task_id": t["id"],
            "adapter": "native",
            "pid": None,
            "started_at": time.time(),
            "status": "running",
            # 幂等重放时复用同一基线，任务卡才能一模一样。
            "diff_base": _diff_base(s),
        }
        st.set_session_mode(sess, "native")
        s.setdefault("sessions", []).append(sess)
        t["status"] = "running"
        t["session_id"] = sid
        s["phase"] = "delegating" if s["phase"] in {"planning", "design"} else s["phase"]
        _session_dir(s["run_id"], sid).mkdir(parents=True, exist_ok=True)
        _save(s)
        print(json.dumps(_claim_card(s, t, sess), ensure_ascii=False, indent=2))


def cmd_release(args: argparse.Namespace) -> None:
    """释放 native 占位：task 回 pending，session 标 released，随后可再次 claim。

    只收 native session；CLI 子进程的生命周期归 `fleet report` / `fleet stop`。
    """
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        t = _task(s, args.task_id)
        sid = t.get("session_id")
        if not sid:
            _err(f"task {t['id']} has no session")
        sess = next((x for x in s.get("sessions", []) if x.get("id") == sid), None)
        if sess is None:
            _err(f"session {sid} is missing from state")
        mode = st.session_mode(sess)
        if mode != "native":
            _err(f"release only supports native sessions; {sid} is {mode}")
        if t.get("status") != "running":
            _err(f"task {t['id']} is {t.get('status')}, not running")
        sess["status"] = "released"
        t["status"] = "pending"
        t["session_id"] = None
        _save(s)
        print(json.dumps({"task_id": t["id"], "session": sid, "mode": mode,
                          "task_status": t["status"], "session_status": sess["status"]},
                         ensure_ascii=False, indent=2))


def cmd_block(args: argparse.Namespace) -> None:
    """人工/主会话把任务标 blocked：原因码必须在 docs/schema.md 码表里（set_blocked_reason 守门）。
    超时、缺件这类内核判不了的原因走这里——只记录，不自动重开。"""
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        t = _task(s, args.task_id)
        if t.get("status") in {"accepted", "abandoned"}:
            _err(f"task {t['id']} is terminal ({t.get('status')}); states kept, record an event instead")
        try:
            st.set_blocked_reason(t, args.reason)
        except ValueError as e:
            _err(str(e))
        t["status"] = "blocked"
        t["session_id"] = None
        st.record_event(s, "task_blocked", task_id=t["id"], reason=args.reason)
        advance(s, root)
        _save(s)
        print(json.dumps({"task_id": t["id"], "status": "blocked",
                          "blocked_reason": t["blocked_reason"]}, ensure_ascii=False))


def cmd_report(args: argparse.Namespace) -> None:
    """收宿主原生子代理写的报告（<session>/report.json），与 diff 对账后转 review。"""
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
    # report_path 由 claim 卡给出（绝对路径），优先用它；state 里 sessions 也可能有 session_dir
    rp = Path(sdir) / "report.json"
    if not rp.is_file():
        # 兜底：claim 卡的 report_path
        t_rp = t.get("report_path")
        if t_rp:
            rp = Path(t_rp)
    if not rp.is_file():
        report = {"result": "partial", "files_changed": [], "verification": [],
                  "open_questions": [], "notes": "native report missing: " + str(rp)}
    else:
        try:
            report = json.loads(rp.read_text(encoding="utf-8"))
        except Exception as e:
            report = {"result": "partial", "files_changed": [], "verification": [],
                      "open_questions": [], "notes": "native report not parseable: " + str(e)}
    if not isinstance(report, dict) or "result" not in report:
        report = {"result": "partial", "files_changed": [], "verification": [],
                  "open_questions": [], "notes": "native report missing 'result' field"}
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
        # 只读角色不许改动：这条门不依赖宿主工具白名单（ADR-0033 D7 / 实测发现）。
        # 声明 read_only 的会话只要在树上改了东西，一律不收，直接退回。
        if sess and sess.get("read_only") and changed:
            report["result"] = "returned"
            report["notes"] = (report.get("notes", "")
                              + f" [read_only violation: {len(changed)} 个文件被改动，"
                                f"{', '.join(changed[:5])}]").strip()
            t["status"] = "returned"
            s["resume"]["next_action"] = f"returned {t['id']} (read_only violation)"
            sess["status"] = "finished"
            _save(s)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return
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


def cmd_review(args: argparse.Namespace) -> None:
    """门卫审查：只输出审查卡，由宿主只读子代理执行；裁决用 fleet verdict 写回。"""
    cmd_review_native(args)


def cmd_review_native(args: argparse.Namespace) -> dict:
    """只输出 native 审查卡，不 spawn。返回 card dict。"""
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        if s.get("phase") in st.TERMINAL_PHASES:
            _err(f"run is terminal ({s['phase']}); review rejected")
        t = _task(s, args.task_id)
        if t.get("status") != "review":
            _err(f"task {t['id']} is {t.get('status')}, not review")
        mb = worktree._git("merge-base", s.get("base_branch") or "main",
                           s.get("branch") or worktree.branch_name(s["run_id"]),
                           cwd=_root(), check=False).stdout.strip()
        diff_base = mb or s.get("base_branch") or "HEAD"
        changed = worktree.changed_files(s["run_id"], s["base_branch"], root)
        sid = _new_sid()
        sdir = _session_dir(s["run_id"], sid)
        sdir.mkdir(parents=True, exist_ok=True)
        report_path = _card_report_path(s["run_id"], sid)
        card = {
            "task_id": t["id"],
            "worktree": s.get("worktree") or str(root),
            "diff_base": diff_base,
            "changed_files": changed,
            "ac": list(t.get("ac", [])),
            "touchset": list(t.get("touchset", [])),
            "review_report_path": report_path,
            "read_only": True,
            "instructions": "Use a read-only subagent of this host. Do not modify files. "
                            "End with one JSON object: {verdict:accept|return|defer, defects:[], deferred_items:[], reason:""}",
        }
        print(json.dumps(card, ensure_ascii=False, indent=2))
        return card


def cmd_verdict(args: argparse.Namespace) -> None:
    """把 native 审查裁决写回：accept -> accepted；return -> returned（3 次转 blocked）；defer -> 记入团长队列。
    验收放给AI：accept即过；defer只把"要团长拍板的事"挂起、不阻塞施工。
    """
    root = _root()
    rp = Path(args.file)
    if not rp.is_file():
        _err(f"verdict file not found: {rp}")
    try:
        rep = json.loads(rp.read_text(encoding="utf-8"))
    except Exception as e:
        _err(f"verdict file not parseable: {e}")
    if not isinstance(rep, dict):
        _err("verdict file must be a JSON object")
    # interop：审计算子可按 Receipt/Envelope 信封投递（role_id 必为 reviewer）——
    # 信封严格模式：未声明字段、fact 缺 evidence_refs、非 reviewer verdict 一律拒收。
    # 信封路径缺 verdict 一律拒收：不默认 accept，也不让非 reviewer 信封经此落账
    # （validate_receipt 已拒非 reviewer 带 verdict；缺 verdict 在这里直接拦）。
    if "role_id" in rep or "schema_version" in rep or "idempotency_key" in rep:
        problems = st.validate_receipt(rep)
        v = rep.get("verdict")
        if not isinstance(v, dict):
            problems.append("envelope must carry a verdict object "
                            "{value: accept|return|defer, ...}")
        if problems:
            _err("receipt rejected: " + "; ".join(problems[:5]))
        rep = {"verdict": v.get("value"),
               "defects": v.get("defects", []),
               "reason": v.get("reason", ""),
               "deferred_items": v.get("deferred_items", [])}
    verdict = rep.get("verdict")
    if verdict not in {"accept", "return", "defer"}:
        _err(f"invalid verdict: {verdict!r} (expected accept/return/defer)")
    defects = rep.get("defects", [])
    reason = rep.get("reason", "") or rep.get("notes", "")
    # defer 专用：要团长拍板的事项列表
    deferred_items = rep.get("deferred_items", [])  # [{id, question, reason, role, priority}]
    if verdict == "defer" and not deferred_items:
        _err("verdict=defer 必须带 deferred_items（要团长拍板的具体事项）")

    with st.lock(root):
        s = st.load(args.run_id, root)
        if s.get("phase") in st.TERMINAL_PHASES:
            _err(f"run is terminal ({s['phase']}); verdict rejected")
        t = _task(s, args.task_id)
        if t.get("status") != "review":
            _err(f"task {t['id']} is {t.get('status')}, not review")
        sid = _new_sid()
        t["review"] = {
            "verdict": verdict,
            "defects": defects,
            "reason": reason,
            "session": sid,
        }
        t["session_id"] = sid
        s.setdefault("sessions", []).append({
            "id": sid, "task_id": t["id"], "adapter": "native-review",
            "pid": None, "started_at": time.time(), "status": "finished",
            "role": "reviewer", "mode": "native",
            # 只读声明：报告入口据此拒收任何改动（ADR-0033 D7）。不靠宿主工具白名单。
            "read_only": True,
        })
        if verdict == "accept":
            t["status"] = "accepted"
            s["resume"]["last_accepted"] = t["id"]
            s["resume"]["next_action"] = "next"
        elif verdict == "defer":
            # 验收放给AI：技术验收已过，只把"要团长拍板的事"挂起；task 标 accepted，事项进团长队列
            t["status"] = "accepted"
            s["resume"]["last_accepted"] = t["id"]
            s["resume"]["next_action"] = "next"
            q = s.setdefault("owner_deferred", [])
            for item in deferred_items:
                q.append({
                    "id": item.get("id") or f"DEFER-{t['id']}-{len(q)+1}",
                    "task_id": t["id"],
                    "question": item.get("question", ""),
                    "reason": item.get("reason", ""),
                    "role": item.get("role", "reviewer"),
                    "priority": item.get("priority", "normal"),
                    "recorded_at": time.time(),
                    "status": "pending",
                })
        else:
            t["status"] = "returned"
            t["attempts"] = int(t.get("attempts", 0) or 0) + 1
            t["defects"] = "; ".join(defects) if defects else reason
            if t["attempts"] >= 3:
                t["status"] = "blocked"
                # 第三次 return：锁死，不再自动重开；只留人工 reopen / 拆分重派的路。
                t["return_locked"] = True
                st.set_blocked_reason(t, "return_limit")
                st.record_event(s, "return_limit_blocked", task_id=t["id"],
                                attempts=t["attempts"])
            s["resume"]["next_action"] = f"rework {t['id']}"
        advance(s, root)
        _save(s)
    print(json.dumps({"task_id": t["id"], "verdict": verdict, "task_status": t["status"],
                      "attempts": t.get("attempts", 0), "phase": s["phase"]},
                     ensure_ascii=False, indent=2))


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
            t["return_locked"] = True
            st.set_blocked_reason(t, "return_limit")
            st.record_event(s, "return_limit_blocked", task_id=t["id"],
                            attempts=t["attempts"])
        s["resume"]["next_action"] = f"rework {t['id']}"
        _save(s)
        print(f"returned {t['id']} attempts={t['attempts']} status={t['status']}")


def cmd_reopen(args: argparse.Namespace) -> None:
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        t = _task(s, args.task_id)
        # 第三次 return 锁死的任务不自动重开；显式人工解锁走 --unlock：
        # 清 return_locked 与 blocked 原因码、回 pending，记事件留痕。
        if t.get("return_locked"):
            if not getattr(args, "unlock", False):
                print(json.dumps({"task_id": t["id"], "return_locked": True,
                                  "hint": "blocked by 3rd return; unlock explicitly "
                                          "with `fleet reopen <run> <task> --unlock` "
                                          "(human decision), or re-plan the task"},
                                 ensure_ascii=False))
                return
            t["return_locked"] = False
            t["blocked_reason"] = None
            t["blocked_at"] = None
            st.record_event(s, "return_lock_unlocked", task_id=t["id"],
                            unlocked_at=time.time())
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
        # 迟到取消：已经在终态的任务不受影响，只记事件，不逆转。
        late = [t["id"] for t in s.get("tasks", [])
                if t.get("status") in {"accepted", "abandoned"}]
        if late:
            st.record_event(s, "cancel_late", task_ids=late,
                            note="stop arrived after terminal; states kept")
        s["phase"] = "cancelled"
        s["resume"]["next_action"] = "stopped" + (f" (killed pids: {','.join(killed)})" if killed else "")
        _save(s)
        print(f"stopped {s['run_id']}" + (f"; killed pids {','.join(killed)}" if killed else ""))


def cmd_confirm(args: argparse.Namespace) -> None:
    """交接确认：handoff 状态 accepted|rejected|needs_clarification，责任转移记事件。
    重复确认同一 handoff 幂等：状态不变，只回显。"""
    root = _root()
    with st.lock(root):
        s = st.load(args.run_id, root)
        hs = s.setdefault("handoffs", [])
        h = next((x for x in hs if x.get("id") == args.handoff_id), None)
        if h is None:
            h = {"id": args.handoff_id, "status": "pending",
                 "from": None, "to": None, "at": None}
            hs.append(h)
        if h.get("status") == args.decision:
            print(json.dumps({"handoff_id": h["id"], "status": h["status"],
                              "idempotent": True}, ensure_ascii=False))
            return
        h["status"] = args.decision
        h["at"] = time.time()
        st.record_event(s, "handoff_confirmed", handoff_id=h["id"],
                        status=args.decision)
        _save(s)
        print(json.dumps({"handoff_id": h["id"], "status": h["status"]},
                         ensure_ascii=False))


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
        # 每个 session 的执行模式单独一行：旧 state 无 mode 时按 native 显示（只剩这一种模式）。
        for sess in s.get("sessions", []):
            role = f" role={sess['role']}" if sess.get("role") else ""
            print(f"  session {sess.get('id','')} task={sess.get('task_id') or '-'} "
                  f"mode={st.session_mode(sess)} status={sess.get('status','')}{role}")


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
    sessions: list[dict[str, Any]] = []
    for s in st.list_runs(root):
        rid = s["run_id"]
        # 诊断面列出全部 session 的执行模式（旧 state 无 mode 时按 native，只剩这一种模式）。
        for sess in s.get("sessions", []):
            sessions.append({
                "run_id": rid, "session": sess.get("id"), "task": sess.get("task_id"),
                "mode": st.session_mode(sess), "status": sess.get("status"),
            })
        if s.get("phase") in st.TERMINAL_PHASES:
            continue
        wt = Path(s.get("worktree", ""))
        if s.get("phase") != "queued" and not wt.exists():
            problems.append(f"{rid}: worktree missing ({wt})")
        if s.get("phase") in {"closing", "reviewing"} and wt.exists():
            r = worktree._git("status", "--porcelain", cwd=wt, check=False)
            if r.stdout.strip() and s.get("phase") == "closing":
                problems.append(f"{rid}: uncommitted changes before closing")
    print(json.dumps({"problems": problems, "sessions": sessions}, ensure_ascii=False, indent=2))
    if problems:
        raise SystemExit(2)


# ---------------------------------------------------------------------------
# argparse


def promote_queued(root: "Path") -> list[str]:
    """惰性调度：把 queued 的 run 按创建时间依次塞进空槽并推进。"""
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


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fleet", description="fleet execution kernel control plane")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="create a run")
    r.add_argument("--fleet", default=None, help="fleet id; slots are per-fleet")
    r.add_argument("--ships", type=int, default=None, help="run count 1-3 (default 1)")
    r.add_argument("--crew", type=int, default=None, help="concurrent subagents 1-5 (default 5)")
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

    cl = sub.add_parser("claim", help="claim a task for a host-native subagent (no CLI spawn)")
    cl.add_argument("run_id")
    cl.add_argument("task_id")
    cl.set_defaults(func=cmd_claim)

    rl = sub.add_parser("release", help="release a native claim; task returns to pending")
    rl.add_argument("run_id")
    rl.add_argument("task_id")
    rl.set_defaults(func=cmd_release)

    bl = sub.add_parser("block", help="mark a task blocked with a reason code (see docs/schema.md)")
    bl.add_argument("run_id")
    bl.add_argument("task_id")
    bl.add_argument("--reason", required=True,
                    help="one of return_limit|auto_fail_limit|read_only_violation|"
                         "merge_conflict|ship_failed|timeout|cancel_late|"
                         "worker_clamped|missing_capability")
    bl.set_defaults(func=cmd_block)

    rp = sub.add_parser("report", help="collect a host-native subagent report")
    rp.add_argument("run_id")
    rp.add_argument("task_id")
    rp.set_defaults(func=cmd_report)

    rv = sub.add_parser("review", help="print a review card for a host-native read-only subagent")
    rv.add_argument("run_id")
    rv.add_argument("task_id")
    rv.set_defaults(func=cmd_review)

    vd = sub.add_parser("verdict", help="write a native review verdict (accept/return/defer)")
    vd.add_argument("run_id")
    vd.add_argument("task_id")
    vd.add_argument("--file", required=True, help="path to review report JSON")
    vd.set_defaults(func=cmd_verdict)

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
    ro.add_argument("--unlock", action="store_true",
                    help="explicitly clear the 3rd-return lock (human decision); records an event")
    ro.set_defaults(func=cmd_reopen)

    stp = sub.add_parser("stop", help="stop a run, keep its state")
    stp.add_argument("run_id")
    stp.set_defaults(func=cmd_stop)

    cf = sub.add_parser("confirm", help="confirm a handoff (accepted/rejected/needs_clarification)")
    cf.add_argument("run_id")
    cf.add_argument("handoff_id")
    cf.add_argument("decision", choices=["accepted", "rejected", "needs_clarification"])
    cf.set_defaults(func=cmd_confirm)

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

    wp = sub.add_parser("warp", help="autopilot run: warp mode (no ship)")
    wp.add_argument("--fleet", default=None, help="fleet id; slots are per-fleet")
    wp.add_argument("--ships", type=int, default=None, help="run count 1-3 (default 1)")
    wp.add_argument("--crew", type=int, default=None, help="concurrent subagents 1-5 (default 5)")
    wp.add_argument("issue")
    wp.add_argument("--urgent", action="store_true")
    wp.add_argument("--base")
    wp.add_argument("--depends", nargs="*", default=[])
    wp.add_argument("--tasks", help="task graph JSON file; plan immediately")
    wp.add_argument("--no-auto", action="store_true",
                    help="manual: print the plan and stop; drive claim/report/review yourself")
    wp.set_defaults(func=cmd_warp)

    jp = sub.add_parser("jump", help="urgent autopilot run (ships)")
    jp.add_argument("--fleet", default=None, help="fleet id; slots are per-fleet")
    jp.add_argument("--ships", type=int, default=None, help="run count 1-3 (default 1)")
    jp.add_argument("--crew", type=int, default=None, help="concurrent subagents 1-5 (default 5)")
    jp.add_argument("issue")
    jp.add_argument("--base")
    jp.add_argument("--depends", nargs="*", default=[])
    jp.add_argument("--tasks", help="task graph JSON file; plan immediately")
    jp.add_argument("--no-auto", action="store_true",
                    help="manual: print the plan and stop; drive claim/report/review yourself")
    jp.set_defaults(func=cmd_jump)

    ap = sub.add_parser("auto", help="unattended drive: claim→subagent→report→review→verdict loop")
    ap.add_argument("run_id")
    ap.add_argument("--worker-cmd", default=auto.DEFAULT_WORKER,
                    help="host command for worker subagent ({brief} placeholder)")
    ap.add_argument("--reviewer-cmd", default=auto.DEFAULT_REVIEWER,
                    help="host command for reviewer subagent ({brief} placeholder)")
    ap.set_defaults(func=auto.cmd_auto)

    asp = sub.add_parser("assimilate", help="merge an external branch (needs user approval)")
    asp.add_argument("branch")
    asp.add_argument("--run", default=None, help="run id")
    asp.add_argument("--approve", action="store_true", help="user approved assimilation")
    asp.set_defaults(func=cmd_assimilate)

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
