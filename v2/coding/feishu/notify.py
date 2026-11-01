"""出站：读本地 run 状态 → 算出该发哪张卡；通过 lark 发送（带幂等键）。

状态真相永远是 `.coding/runs/*/state.json`；这里只读，不写。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from . import cards


def run_rows(root: "Path | str") -> "list[dict[str, Any]]":
    base = Path(root) / ".coding" / "runs"
    rows: list[dict[str, Any]] = []
    if not base.is_dir():
        return rows
    for d in sorted(base.iterdir()):
        f = d / "state.json"
        if not f.is_file():
            continue
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(s, dict):
            continue
        tasks = [t for t in (s.get("tasks") or []) if isinstance(t, dict)]
        done = sum(1 for t in tasks if t.get("status") in {"accepted", "abandoned"})
        rows.append({
            "run_id": s.get("run_id") or d.name,
            "phase": s.get("phase") or "",
            "gates": s.get("gates") or {},
            "tasks_total": len(tasks),
            "tasks_done": done,
            "progress": f"{done}/{len(tasks)}" if tasks else "—",
            "next_action": (s.get("resume") or {}).get("next_action", "") if isinstance(s.get("resume"), dict) else "",
            "updated_at": s.get("updated_at") or s.get("created_at") or 0,
            "branch": s.get("branch") or "",
        })
    return rows


def fingerprint(row: dict[str, Any]) -> str:
    keep = {k: row.get(k) for k in ("run_id", "phase", "progress", "next_action", "updated_at",
                                    "gates", "tasks_total", "tasks_done")}
    return hashlib.sha256(json.dumps(keep, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def load_snapshots(path: "Path | str") -> dict[str, str]:
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_snapshots(path: "Path | str", snap: dict[str, str]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")


def transitions(previous: dict[str, str], rows: "list[dict[str, Any]]") -> "list[dict[str, Any]]":
    """返回「状态稳定后需要发卡」的 run：指纹变了、且进入需要通知的阶段。"""
    out = []
    for r in rows:
        fp = fingerprint(r)
        if previous.get(r["run_id"]) == fp:
            continue
        phase = str(r.get("phase") or "")
        if phase in {"done", "blocked"} or _gate_waiting(r):
            out.append({"row": r, "fingerprint": fp, "kind": _kind(r)})
    return out


def _gate_waiting(row: dict[str, Any]) -> bool:
    gates = row.get("gates") or {}
    return any(v == "pending" for v in gates.values() if isinstance(v, str))


def _kind(row: dict[str, Any]) -> str:
    phase = str(row.get("phase") or "")
    if phase == "done":
        return "done"
    if phase == "blocked":
        return "blocked"
    return "gate"


def render(kind: str, row: dict[str, Any], nonce: str = "") -> dict[str, Any]:
    rid = row.get("run_id", "")
    if kind == "done":
        return cards.done(rid, commit="", tasks=int(row.get("tasks_done") or 0))
    if kind == "blocked":
        return cards.blocked(rid, str(row.get("next_action") or ""))
    gate = ""
    for g, v in (row.get("gates") or {}).items():
        if v == "pending":
            gate = g
            break
    return cards.gate_request(rid, gate or "g2", str(row.get("next_action") or "到门点了，等你拍板。"), nonce)
