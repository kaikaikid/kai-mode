# -*- coding: utf-8 -*-
"""源：日表（塔台写的排班视图，本模块只读）。

文件名约定 `YYYY-MM-DD-<lane>.md`。认两种行（同一文件里混用也行）：

1. markdown 列表行：
       - [ ] #12 一句话            未完成
       - [x] #12 一句话            已完成
       - #12 一句话 | 备注          无复选框，`|` 后是备注
2. markdown 表格行（表头 + 数据行），列名认中英两套：
       | 序 | 票号 | 里程碑 | 一句话 | 塔台备注 |

    0.24.13 补第 2 种：项目侧的塔台日表就是五列表格，旧版只认列表行，
    于是「22 行排班 / 0 张票」还报 ok——排班看得见、票全丢，失败不点名。

日表既是**排班快照**（schedule_row），也是**航班兜底来源**（票源不可用时的退化路径）。
"""
from __future__ import annotations

import fnmatch
import os
import re

LINE = re.compile(r"^\s*[-*]\s*(?:\[(?P<box>[ xX])\]\s*)?(?P<body>.+?)\s*$")
TICKET = re.compile(r"^(#(\d+)|H-\d{8}-\d+)\b")
DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
PIPE = re.compile(r"^\s*\|.*\|\s*$")
SEP = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
# 裸数字不是票号——日表第一列就是「序」。必须带 # 或 H- 前缀。
TICKET_CELL = re.compile(r"^(#(\d+)|H-\d{8}-\d+)$")

# 表格列名：表头里精确命中优先，其次包含
COLUMNS = {
    "ticket": ("票号", "编号", "ticket", "issue"),
    "milestone": ("里程碑", "milestone"),
    "summary": ("一句话", "事", "任务", "摘要", "title", "summary"),
    "note": ("塔台备注", "备注", "说明", "note", "notes"),
}


def _parse_line(body: str) -> tuple[str | None, str, str]:
    """→ (ticket, summary, note)"""
    body = body.strip()
    m = TICKET.match(body)
    num = _num(m) if m else None
    text = body[m.end():].strip() if m else body
    note = ""
    if "|" in text:
        text, note = text.split("|", 1)
        text, note = text.strip(), note.strip()
    return (f"#{num}" if num else None), text, note


def _num(m) -> str:
    """匹配到的票号格子 → 号码本体（H- 热修号保留原形，不带 #）。"""
    return m.group(2) or m.group(1)


def _cells(raw: str) -> list[str]:
    return [c.strip() for c in raw.strip().strip("|").split("|")]


def _header_map(cells: list[str]) -> dict[str, int]:
    """表头行 → {字段: 列号}。认不出的列不猜。"""
    m: dict[str, int] = {}
    for i, c in enumerate(cells):
        low = c.lower()
        for key, names in COLUMNS.items():
            if key in m:
                continue
            if any(n.lower() == low for n in names):
                m[key] = i
    for i, c in enumerate(cells):                  # 第二遍：包含匹配（如「塔台备注」）
        low = c.lower()
        for key, names in COLUMNS.items():
            if key not in m and any(len(n) > 1 and n.lower() in low for n in names):
                m[key] = i
    return m


def _parse_pipe_row(cells: list[str], hmap: dict[str, int]
                    ) -> tuple[str, str, str, str] | None:
    """表格数据行 → (ticket, summary, note, milestone)；不是数据行（表头/分隔）就 None。"""
    idx = hmap.get("ticket")
    num = None
    if idx is not None and idx < len(cells) and TICKET_CELL.match(cells[idx]):
        num = _num(TICKET_CELL.match(cells[idx]))
    else:
        for i, c in enumerate(cells):   # 回退扫描：同样只认带 # 或 H- 的格子
            if TICKET_CELL.match(c):
                num, idx = _num(TICKET_CELL.match(c)), i
                break
    if not num:
        return None

    def cell(key: str) -> str:
        i = hmap.get(key)
        return cells[i] if i is not None and i < len(cells) else ""

    milestone, summary, note = cell("milestone"), cell("summary"), cell("note")
    if not summary:                                # 没有表头映射：票号右侧第一格当摘要
        rest = [c for i, c in enumerate(cells)
                if i > (idx or 0) and c and i not in (hmap.get("milestone"), hmap.get("note"))]
        summary = rest[0] if rest else ""
    if not note and len(cells) > (idx or 0) + 2 and cells[-1] not in (summary, milestone):
        note = cells[-1]
    # 注意：H- 热修号也带 # 前缀（#H-20261027-1）——这是 2026-10-27 另一会话
    # 已立的契约（TestTasks.test_ace_hotfix_row），本文件不单方面改形。
    # 页面侧靠"只有 #纯数字 才配 GitHub 链接"避免死链，见 render._urgent_section。
    return f"#{num}", summary, note, milestone


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

    patterns = cfg.get("include") or ["*-main.md", "*-deputy.md", "*-ace.md"]
    lanes_cfg = cfg.get("lanes") or ctx["paths"].get("lanes") or ["main", "deputy", "ace"]

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
        hmap: dict[str, int] = {}
        for raw in lines:
            if PIPE.match(raw):
                if SEP.match(raw):
                    continue
                cells = _cells(raw)
                if not any(TICKET_CELL.match(c) for c in cells):
                    hmap = _header_map(cells)      # 表头行：只记列名，不出排班
                    continue
                parsed = _parse_pipe_row(cells, hmap)
                if not parsed:
                    continue
                ticket, summary, note, milestone = parsed
                done = False
            else:
                # 不清 hmap：塔台正文里的裸 `|` 会把一行表格撑破成几行正文，
                # 那是数据脏；清掉映射会让后面每一行都退回"扫第一格"，把「序」读成票号。
                m = LINE.match(raw)
                if not m:
                    continue
                ticket, summary, note = _parse_line(m.group("body"))
                milestone = ""
                done = (m.group("box") or "").lower() == "x"
            n += 1
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
                    "milestone": milestone,
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
