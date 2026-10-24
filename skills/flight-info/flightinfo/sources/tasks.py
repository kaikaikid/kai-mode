# -*- coding: utf-8 -*-
"""源：日表（塔台写的排班视图，本模块只读）。

文件名约定 `YYYY-MM-DD-<lane>.md`，行是 markdown 列表：
    - [ ] #12 一句话            未完成
    - [x] #12 一句话            已完成
    - #12 一句话 | 备注          无复选框，`|` 后是备注

日表既是**排班快照**（schedule_row），也是**航班兜底来源**（票源不可用时的退化路径）。
"""
from __future__ import annotations

import fnmatch
import os
import re

LINE = re.compile(r"^\s*[-*]\s*(?:\[(?P<box>[ xX])\]\s*)?(?P<body>.+?)\s*$")
TICKET = re.compile(r"^#?(\d+)\b")
DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _parse_line(body: str) -> tuple[str | None, str, str]:
    """→ (ticket, summary, note)"""
    body = body.strip()
    m = TICKET.match(body)
    num = m.group(1) if m else None
    text = body[m.end():].strip() if m else body
    note = ""
    if "|" in text:
        text, note = text.split("|", 1)
        text, note = text.strip(), note.strip()
    return (f"#{num}" if num else None), text, note


def collect(cfg: dict, ctx: dict) -> dict:
    repo_root = ctx["repo_root"]
    rel = cfg.get("path") or ctx["paths"].get("day_tables_dir")
    if not rel:
        return {"flights": [], "schedules": [], "status": "absent",
                "detail": "板配置没写 path，项目配置实例也没有 paths.day_tables_dir"}
    base = os.path.join(repo_root, rel)
    if not os.path.isdir(base):
        return {"flights": [], "schedules": [], "status": "absent",
                "detail": f"日表目录不存在：{rel}"}

    patterns = cfg.get("include") or ["*-main.md", "*-copilot.md"]
    lanes_cfg = cfg.get("lanes") or ctx["paths"].get("lanes") or ["main", "copilot"]

    schedules, flights, seen = [], [], set()
    for fn in sorted(os.listdir(base)):
        if not fn.endswith(".md"):
            continue
        if not any(fnmatch.fnmatch(fn, p) for p in patterns):
            continue
        dm = DATE.search(fn)
        table_date = dm.group(1) if dm else ""
        lane = next((l for l in lanes_cfg if f"-{l}.md" in fn), "unknown")
        try:
            with open(os.path.join(base, fn), encoding="utf-8") as f:
                lines = f.read().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        n = 0
        for raw in lines:
            m = LINE.match(raw)
            if not m:
                continue
            n += 1
            ticket, summary, note = _parse_line(m.group("body"))
            done = (m.group("box") or "").lower() == "x"
            schedules.append({"lane": lane, "table_date": table_date, "line_no": n,
                              "ticket": ticket, "summary": summary, "note": note})
            if ticket and ticket not in seen:
                seen.add(ticket)
                flights.append({
                    "uid": f"issue:{ticket.lstrip('#')}",
                    "ticket": ticket,
                    "title": summary or ticket,
                    "labels": [],
                    "closed": done,
                    "last_comment": "",
                    "table_note": note,
                    "branches": [],
                    "assignee": "",
                    "milestone": "",
                    "url": "",
                    "owner": lane,
                    "persona": "",
                    "planned": True,
                    "updated_at": table_date,
                    "source": "tasks-table",
                    "kind": "task",
                })

    if not schedules:
        return {"flights": [], "schedules": [], "status": "absent",
                "detail": f"{rel} 下没有匹配 {patterns} 的日表"}
    return {"flights": flights, "schedules": schedules, "status": "ok",
            "detail": f"{len(schedules)} 行排班 / {len(flights)} 张票"}
