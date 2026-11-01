# -*- coding: utf-8 -*-
"""源：V2 执行内核的 run（`.coding/runs/*/state.json`）。

只读，不 import `v2`：看板是独立安装件，项目里可能没有 v2 包。
一个 run 出一条 flight 记录，uid 用 `run:<run_id>`（同一 issue 可能开多个 run，
用 issue 号做 uid 会互相覆盖）。

阶段映射不靠 branch/url 启发式：记录带 `v2:<stage>` 标签，板配置把对应规则排在
`no_issue`／`branch_exists` 之前。`branches`/`assignee` 故意留空，避免被默认规则
误判成「残留分支」或「已派未动」。
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime

ISSUE_RE = re.compile(
    r"https?://github\.com/[\w.-]+/[\w.-]+/issues/(\d+)|(?<![\w#])#(\d+)"
)
TERMINAL = {"done", "cancelled", "failed"}
TASK_DONE = {"accepted", "abandoned"}
TASK_RUNNING = {"running"}
TASK_BLOCKED = {"blocked", "failed"}


def _issue_number(text: str) -> str | None:
    m = ISSUE_RE.search(text or "")
    if not m:
        return None
    return m.group(1) or m.group(2)


def _issue_url(text: str) -> str:
    m = re.search(r"https?://github\.com/[\w.-]+/[\w.-]+/issues/\d+", text or "")
    return m.group(0) if m else ""


def _phase_stage(phase: str) -> str:
    """V2 phase → 板阶段 key（与看板阶段映射表一致）。"""
    return {
        "queued": "queued",
        "planning": "flying",
        "design": "flying",
        "delegating": "flying",
        "reviewing": "review",
        "closing": "to_ship",
        "done": "closed",
        "blocked": "hold",
        "cancelled": "closed",
        "failed": "closed",
    }.get(phase or "", "hold")  # 未知 phase 不猜「排队」，按「需要人」处理


def _age_min(updated_at: str) -> int | None:
    """距上次更新的分钟数；解析不了返回 None（不猜 0）。"""
    if not updated_at:
        return None
    s = str(updated_at).strip().replace("T", " ")[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s if len(s) > 10 else str(updated_at)[:10], fmt)
            return max(0, int((datetime.now() - dt).total_seconds() // 60))
        except ValueError:
            continue
    return None


def _rel(path: str, repo_root: str) -> str:
    try:
        return os.path.relpath(path, repo_root).replace("\\", "/")
    except ValueError:
        return path


def _session_summary(state: dict) -> list[dict]:
    out = []
    sessions = state.get("sessions")
    if not isinstance(sessions, list):
        return out
    for s in sessions:
        if not isinstance(s, dict):
            continue
        out.append({
            "id": s.get("id") or "",
            "task_id": s.get("task_id") or "",
            "status": s.get("status") or "",
            "pid": s.get("pid") or 0,
        })
    return out


def _as_int(value, default: int = 0) -> int:
    """脏数据的 int：'x'/None/list 都归默认值，不让一条 run 静默消失。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _run_record(state: dict, run_id: str, repo_root: str) -> dict | None:
    phase = state.get("phase")
    if not phase:
        return None
    issue = str(state.get("issue") or "").strip()
    num = _issue_number(issue)
    tasks = state.get("tasks") or []
    statuses = [t.get("status") for t in tasks if isinstance(t, dict)]
    stage = _phase_stage(phase)
    updated_at = str(state.get("updated_at") or "")
    return {
        "uid": f"run:{run_id}",
        "ticket": f"#{num}" if num else run_id,
        "title": (issue[:120] if issue else run_id),
        "labels": [f"v2:{stage}"] + (["urgent"] if state.get("priority") == "urgent" else []),
        "closed": phase in TERMINAL,
        "last_comment": "",
        "table_note": "",
        "branches": [],          # 故意留空：避免 no_issue 把 V2 run 判成残留分支
        "assignee": "",          # 故意留空：避免 assignee_exists 抢先判阶段
        "milestone": "",
        "url": _issue_url(issue),
        "owner": state.get("fleet_id") or "",
        "persona": "",
        "planned": bool(tasks),
        "updated_at": updated_at,
        "source": "coding-runs",
        "kind": "task",
        # 扩展字段：不进 flight 表，供 Phase 2 的 coding 段使用
        "run_id": run_id,
        "issue": issue,
        "phase": phase,
        "stage": stage,
        "gates": _as_dict(state.get("gates")),
        "ship": _as_dict(state.get("ship")),
        "tasks_total": len(tasks),
        "tasks_done": sum(1 for x in statuses if x in TASK_DONE),
        "tasks_running": sum(1 for x in statuses if x in TASK_RUNNING),
        "tasks_blocked": sum(1 for x in statuses if x in TASK_BLOCKED),
        "next_action": (state.get("resume") or {}).get("next_action") or ""
        if isinstance(state.get("resume"), dict) else "",
        "priority": state.get("priority") or "normal",
        "fleet_id": state.get("fleet_id") or "",
        "ship_limit": _as_int(state.get("ship_limit")),
        "crew_limit": _as_int(state.get("crew_limit")),
        "branch": state.get("branch") or "",
        "worktree": _rel(str(state.get("worktree") or ""), repo_root) if state.get("worktree") else "",
        "sessions": _session_summary(state),
        "age_min": _age_min(updated_at),
    }


def _coding_row(rec: dict) -> dict:
    """从 flight 记录里摘出监工面字段（落 coding_run 表）。"""
    keys = ("run_id", "issue", "phase", "stage", "priority", "fleet_id",
            "ship_limit", "crew_limit", "gates", "tasks_total", "tasks_done",
            "tasks_running", "tasks_blocked", "sessions", "ship", "next_action",
            "updated_at", "age_min", "branch", "worktree")
    return {k: rec.get(k) for k in keys}


def collect(cfg: dict, ctx: dict) -> dict:
    repo_root = ctx["repo_root"]
    runs_dir = os.path.join(repo_root, ".coding", "runs")
    if not os.path.isdir(runs_dir):
        return {"flights": [], "coding": [], "schedules": [], "status": "absent",
                "detail": ".coding/runs 不存在（还没跑过 V2）"}

    flights, coding, bad, total, bad_names = [], [], 0, 0, []
    for child in sorted(os.listdir(runs_dir)):
        run_dir = os.path.join(runs_dir, child)
        state_path = os.path.join(run_dir, "state.json")
        if not os.path.isfile(state_path):
            continue
        total += 1
        try:
            with open(state_path, encoding="utf-8") as f:
                state = json.load(f)
            if not isinstance(state, dict):
                raise ValueError("state.json 不是对象")
            run_id = str(state.get("run_id") or child)
            rec = _run_record(state, run_id, repo_root)
            if rec is None:
                raise ValueError("state.json 缺 phase")
            flights.append(rec)
            coding.append(_coding_row(rec))
        except Exception as e:
            bad += 1
            bad_names.append(f"{child}: {e}")

    if total and not flights:
        return {"flights": [], "coding": [], "schedules": [], "status": "fail",
                "detail": f"{bad} 个 state.json 都读不了：{'; '.join(bad_names[:3])}"}
    detail = f"{len(flights)} 个 run"
    if bad:
        detail += f"（{bad} 个读不了：{'; '.join(bad_names[:2])}）"
    return {"flights": flights, "coding": coding, "schedules": [],
            "status": "ok", "detail": detail}
