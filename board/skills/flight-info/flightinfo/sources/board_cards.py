# -*- coding: utf-8 -*-
"""源：handoff/60-board 看板卡片（跨 agent 传话的数据层）。

一张卡片 → 一条记录。有票的卡片 uid 用 `issue:<号>`，与 issues 源天然合并；
无票热修／杂活用 `card:<id>`，靠 id 追踪。

卡片格式见 handoff/60-board/README.md；本模块只认 frontmatter 的顶层 `key: value`，
不解析嵌套结构（卡片本来就没有）。
"""
from __future__ import annotations

import os
import re

FM_KEY = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$")
STATES = ("open", "claimed", "done")


def _parse_frontmatter(text: str) -> dict:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = FM_KEY.match(line)
        if m:
            v = m.group(2).strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            out[m.group(1)] = "" if v in ("-", "~", "null") else v
    return out


def _ticket_num(raw: str) -> str | None:
    """'#12' / '12' → '12'；'-' 或空 → None。"""
    if not raw:
        return None
    m = re.search(r"(\d+)", raw)
    return m.group(1) if m else None


def collect(cfg: dict, ctx: dict) -> dict:
    """返回 {flights, schedules, status, detail}。"""
    repo_root = ctx["repo_root"]
    rel = cfg.get("path") or ctx["paths"].get("handoff_dir") or "handoff"
    base = os.path.join(repo_root, rel, "60-board")
    if not os.path.isdir(base):
        return {"flights": [], "schedules": [], "status": "absent",
                "detail": f"看板目录不存在：{rel}/60-board/"}

    records, bad = [], 0
    for state in STATES:
        d = os.path.join(base, state)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".md"):
                continue
            try:
                with open(os.path.join(d, fn), encoding="utf-8") as f:
                    fm = _parse_frontmatter(f.read())
            except (OSError, UnicodeDecodeError):
                bad += 1
                continue
            if not fm.get("id"):
                bad += 1
                continue
            num = _ticket_num(fm.get("ticket", ""))
            uid = f"issue:{num}" if num else f"card:{fm['id']}"
            records.append({
                "uid": uid,
                "ticket": f"#{num}" if num else None,
                "title": fm.get("title") or fm["id"],
                "labels": [x.strip() for x in (fm.get("type") or "").split(",") if x.strip()],
                "closed": state == "done",
                "last_comment": fm.get("outcome") or "",
                "table_note": "",
                "branches": [],
                "assignee": fm.get("claimed_by") or "",
                "milestone": "",
                "url": "",
                "owner": fm.get("role") or "",
                "persona": fm.get("persona") or "",
                "planned": False,
                "updated_at": (fm.get("closed_at") or fm.get("claimed_at")
                               or fm.get("created_at") or ""),
                "source": "board-cards",
                "kind": fm.get("type") or "task",
            })

    if not records:
        return {"flights": [], "schedules": [], "status": "absent",
                "detail": f"看板为空（{rel}/60-board/{{open,claimed,done}}/ 无卡片）"}
    detail = f"{len(records)} 张卡片" + (f"（{bad} 张读不动已跳过）" if bad else "")
    return {"flights": records, "schedules": [], "status": "ok", "detail": detail}
