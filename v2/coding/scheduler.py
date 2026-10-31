"""调度：ready 判定、touchset 冲突、槽位分配。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import state as st

PER_RUN_SESSIONS = 1
FLEET_MAX_SHIPS = 3
FLEET_MAX_CREW = 5  # 每舰队最多 5 个子代理（crew）

TASK_TERMINAL = {"accepted", "abandoned"}
TASK_INFLIGHT = {"ready", "running", "review", "returned"}


def _norm(pattern: str) -> str:
    p = pattern.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.rstrip("/")


def _static_prefix(pattern: str) -> str:
    """取 glob 的静态前缀，用于粗判重叠。"""
    out = []
    for part in _norm(pattern).split("/"):
        if any(ch in part for ch in "*?["):
            break
        out.append(part)
    return "/".join(out)


def touchsets_overlap(a: list[str], b: list[str]) -> bool:
    for x in a:
        px = _static_prefix(x)
        nx = _norm(x)
        for y in b:
            py = _static_prefix(y)
            ny = _norm(y)
            if nx == ny:
                return True
            # 目录前缀关系
            if px and py and (px == py or px.startswith(py + "/") or py.startswith(px + "/")):
                return True
            if px and ny.startswith(px + "/"):
                return True
            if py and nx.startswith(py + "/"):
                return True
    return False


def deps_done(task: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> bool:
    return all(by_id.get(d, {}).get("status") in TASK_TERMINAL for d in task.get("deps", []))


def inflight_touchsets(run: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for t in run.get("tasks", []):
        if t.get("status") in {"running", "review"}:
            out.extend(t.get("touchset", []))
    return out


def other_runs_touchsets(run: dict[str, Any], root: Path | None = None) -> list[tuple[str, list[str]]]:
    out = []
    for r in st.list_runs(root):
        if r["run_id"] == run["run_id"] or r.get("phase") in st.TERMINAL_PHASES:
            continue
        out.append((r["run_id"], inflight_touchsets(r)))
    return out


def ready_tasks(run: dict[str, Any], root: Path | None = None) -> list[dict[str, Any]]:
    by_id = {t["id"]: t for t in run.get("tasks", [])}
    others = other_runs_touchsets(run, root)
    out = []
    for t in run.get("tasks", []):
        if t.get("status") not in {"pending", "returned"}:
            continue
        if not deps_done(t, by_id):
            continue
        if t.get("status") == "returned" and t.get("attempts", 0) >= 3:
            continue
        if touchsets_overlap(t.get("touchset", []), inflight_touchsets(run)):
            continue
        if any(touchsets_overlap(t.get("touchset", []), ts) for _, ts in others):
            continue
        out.append(t)
    return out


def _fleet_id(run: dict[str, Any]) -> str:
    return run.get("fleet_id") or "default"


def slot_usage(root: Path | None = None, fleet_id: str | None = None) -> dict[str, int]:
    # ship_limit 从该舰队的 run 里取（默认 2）
    # 槽位上限按舰队（fleet）独立计：不同舰桥/agent 框架互不抢占槽位，
    # 但 touchset 冲突检测仍全局生效（文件冲突与舰队无关）。
    if fleet_id is None:
        import os as _os
        fleet_id = _os.environ.get("TRAVEL_FLEET_ID", "default")
    normal = urgent = sessions = 0
    for r in st.list_runs(root):
        if r.get("phase") in st.TERMINAL_PHASES:
            continue
        if r.get("phase") == "queued":
            continue
        if _fleet_id(r) != fleet_id:
            continue
        if r.get("priority") == "urgent":
            urgent += 1
        else:
            normal += 1
        sessions += sum(1 for t in r.get("tasks", []) if t.get("status") == "running")
    return {"normal": normal, "urgent": urgent, "sessions": sessions}


def can_start(run: dict[str, Any], root: Path | None = None) -> tuple[bool, str]:
    # 舰船数：同一舰队（fleet_id）在飞 run 数达到 ship_limit（1–3，默认 2）就排队。
    # 曲速 / 跃迁共用同一配额，可混搭（warp-2 + jump-1）。
    ship_limit = max(1, min(FLEET_MAX_SHIPS, int(run.get("ship_limit") or 2)))
    u = slot_usage(root, fleet_id=run.get("fleet_id"))
    if u["normal"] + u["urgent"] >= ship_limit:
        return False, "fleet ship limit reached"
    for dep in run.get("depends_on_runs", []):
        try:
            d = st.load(dep, root)
        except FileNotFoundError:
            return False, f"dependency {dep} missing"
        if d.get("phase") != "done":
            return False, f"dependency {dep} not done ({d.get('phase')})"
    return True, "ok"


def can_spawn(run: dict[str, Any], task: dict[str, Any], root: Path | None = None) -> tuple[bool, str]:
    # 每舰船 1 个子代理；舰队船员上限（1–5，默认 5）跨舰船共享。
    running = sum(1 for t in run.get("tasks", []) if t.get("status") == "running")
    if running >= PER_RUN_SESSIONS:
        return False, "per-ship crew limit (1)"
    crew_limit = int(run.get("crew_limit") or FLEET_MAX_CREW)
    crew_limit = max(1, min(FLEET_MAX_CREW, crew_limit))
    if slot_usage(root, fleet_id=run.get("fleet_id"))["sessions"] >= crew_limit:
        return False, "fleet crew limit reached"
    return True, "ok"
