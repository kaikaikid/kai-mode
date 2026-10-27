#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round —— 塔台一轮的机械部分：分批计划、轮次回执、门耗时判级。

只出计划与读数，不合并、不 push、不关票。

用法：
  python round.py plan --input tickets.json [--max-batch 5] [--json]
      输入：[{"ticket": 12, "files": ["a.py"], "urgent": false}, ...]
      输出：{batches: [{tickets, files}], skipped: []}
  python round.py report --shipped 3 --returned 1 --blocked 0 [--hotfix 1] [--json]
  python round.py budget --elapsed 348 --limit 600 [--json]

退出码：0 正常；1 预算超限；2 输入读不出。
"""
from __future__ import annotations

import argparse
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def load(path: str) -> list:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"输入读不出：{exc}")
    if isinstance(data, dict):
        data = data.get("tickets") or []
    if not isinstance(data, list):
        raise SystemExit("输入必须是票数组，或 {\"tickets\": [...]}")
    out = []
    for i, item in enumerate(data):
        if not isinstance(item, dict) or not item.get("ticket"):
            raise SystemExit(f"第 {i + 1} 条缺 ticket")
        files = item.get("files") or []
        if not isinstance(files, list):
            raise SystemExit(f"票 {item['ticket']} 的 files 不是数组")
        out.append({"ticket": item["ticket"], "files": [str(x) for x in files],
                    "urgent": bool(item.get("urgent"))})
    return out


def plan(tickets: list, max_batch: int) -> dict:
    urgent = [t for t in tickets if t.get("urgent")]
    normal = [t for t in tickets if not t.get("urgent")]
    batches, skipped = [], []

    def add(group):
        current = None
        for t in group:
            files = set(t.get("files") or [])
            if current and len(current["tickets"]) < max_batch and not (files & current["file_set"]):
                current["tickets"].append(t["ticket"])
                current["files"].update(files)
                current["file_set"] |= files
                continue
            if current and len(current["tickets"]) >= max_batch:
                batches.append(current)
                current = None
            if current is None:
                current = {"tickets": [t["ticket"]], "files": set(files), "file_set": set(files)}
            elif files & current["file_set"]:
                # 与当前批相交：单独成批，避免把冲突票硬塞进同一批
                batches.append(current)
                current = {"tickets": [t["ticket"]], "files": set(files), "file_set": set(files)}
        if current:
            batches.append(current)

    add(urgent)
    add(normal)
    out = []
    for b in batches:
        if not b["tickets"]:
            continue
        out.append({"tickets": b["tickets"], "files": sorted(b["files"])})
    if not out and tickets:
        skipped = [t["ticket"] for t in tickets]
    return {"batches": out, "skipped": skipped,
            "counts": {"tickets": len(tickets), "batches": len(out),
                       "urgent": len(urgent), "normal": len(normal)}}


def budget(elapsed: float, limit: float) -> dict:
    ratio = (elapsed / limit) if limit > 0 else 1.0
    if ratio > 1:
        status = "over"
    elif ratio >= 0.8:
        status = "warn"
    else:
        status = "ok"
    return {"elapsed": elapsed, "limit": limit, "ratio": round(ratio, 3),
            "status": status,
            "note": "门自身耗时不算被审对象的红；over 记「没跑成」并打印读数"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="塔台一轮的机械部分")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--input", required=True)
    p.add_argument("--max-batch", type=int, default=5)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn="plan")
    p = sub.add_parser("report")
    p.add_argument("--shipped", type=int, default=0)
    p.add_argument("--returned", type=int, default=0)
    p.add_argument("--blocked", type=int, default=0)
    p.add_argument("--hotfix", type=int, default=0)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn="report")
    p = sub.add_parser("budget")
    p.add_argument("--elapsed", type=float, required=True)
    p.add_argument("--limit", type=float, required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn="budget")
    a = ap.parse_args(argv)

    if a.fn == "plan":
        out = plan(load(a.input), max(1, a.max_batch))
        if a.json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            for i, b in enumerate(out["batches"], 1):
                print(f"批 {i}：票 {', '.join('#' + str(x) for x in b['tickets'])}"
                      f"（{len(b['files'])} 个文件）")
            print(f"合计：{out['counts']['tickets']} 张 / {out['counts']['batches']} 批")
        return 0

    if a.fn == "report":
        out = {"shipped": a.shipped, "returned": a.returned,
               "blocked": a.blocked, "hotfix": a.hotfix}
        out["total"] = a.shipped + a.returned + a.blocked + a.hotfix
        if a.json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            print(f"本轮：发货 {a.shipped} · 退回 {a.returned} · 卡点 {a.blocked} · "
                  f"热修 {a.hotfix} · 合计 {out['total']}")
        return 0

    out = budget(a.elapsed, a.limit)
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"门耗时 {a.elapsed:.1f}s / 上限 {a.limit:.1f}s（{out['ratio'] * 100:.0f}%）⇒ {out['status']}")
    return 1 if out["status"] == "over" else 0


if __name__ == "__main__":
    raise SystemExit(main())
