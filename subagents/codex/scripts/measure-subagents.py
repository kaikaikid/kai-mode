"""Measure how the Codex subagent set actually behaves on this machine.

Read-only against ~/.codex/state_5.sqlite (never written by this script).
Turns the contract's prose obligations into numbers, so "did the discipline land?"
is answerable instead of arguable. Exit code 1 when a gate goes red.

Usage: python scripts/measure-subagents.py [--since 2026-10-23T01:38] [--json]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOCAL = timezone(timedelta(hours=8))
DB = Path.home() / ".codex" / "state_5.sqlite"

# Gates. Keep in sync with contracts/routing.md 收口三条 + contracts/roles.yaml tiers.
GATE_OPEN_RATE = 0.10  # unclosed agents eat the concurrency budget (max_concurrent=3)
GATE_NULL_ROLE_RATE = 0.0  # an untagged spawn cannot be routed to its tier at all


def edges(db: Path) -> list[dict]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            """select e.status, t.agent_role, t.model, t.reasoning_effort, t.created_at
               from thread_spawn_edges e join threads t on t.id = e.child_thread_id
               order by t.created_at"""
        ).fetchall()
    finally:
        con.close()
    return [
        dict(zip(("status", "role", "model", "effort", "ts"), r)) for r in rows
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None, help="ISO local time; default: whole history")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not DB.is_file():
        print(f"missing {DB}", file=sys.stderr)
        return 2
    cutoff = None
    if args.since:
        cutoff = datetime.fromisoformat(args.since).replace(tzinfo=LOCAL).timestamp()

    all_edges = edges(DB)
    scope = [e for e in all_edges if cutoff is None or e["ts"] >= cutoff]
    if not scope:
        print("no spawns in this window")
        return 1

    n = len(scope)
    open_n = sum(e["status"] == "open" for e in scope)
    null_role = sum(e["role"] is None for e in scope)
    roles = Counter(str(e["role"]) for e in scope)
    models = Counter(str(e["model"]) for e in scope)
    per_role_model = {
        r: Counter(str(e["model"]) for e in scope if str(e["role"]) == r).most_common()
        for r in sorted(roles)
    }
    open_rate = open_n / n
    null_rate = null_role / n

    report = {
        "window": args.since or "all",
        "spawns": n,
        "open": open_n,
        "open_rate": round(open_rate, 3),
        "null_role": null_role,
        "null_role_rate": round(null_rate, 3),
        "roles_used": dict(roles),
        "models_used": dict(models),
        "model_per_role": per_role_model,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"window={report['window']}  spawns={n}  open={open_n} ({open_rate:.0%})  "
              f"null_role={null_role} ({null_rate:.0%})")
        print("roles used:", dict(roles))
        print("models used:", dict(models))
        for r, ms in per_role_model.items():
            print(f"  {r:16s} -> {ms}")

    red = []
    if open_rate > GATE_OPEN_RATE:
        red.append(f"open_rate {open_rate:.0%} > {GATE_OPEN_RATE:.0%} (unclosed agents)")
    if null_rate > GATE_NULL_ROLE_RATE:
        red.append(f"null_role {null_rate:.0%} > {GATE_NULL_ROLE_RATE:.0%} (untagged spawns)")
    for line in red:
        print("RED:", line)
    if red:
        return 1
    print("all gates green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
