# -*- coding: utf-8 -*-
"""源：交接日报索引（handoff/ 下的纸条层）。

只读 `handoff/<槽位>/<YYYY-MM>/<文件>.md` 的**文件名与首行标题**，产出索引行
（槽位 / 相对路径 / 标题 / 日期），不读正文、不搬内容——正文正本在文件里。
板只做「最近交接在哪、点开看」这一层入口。

槽位可选：cfg.slots（缺省认 10-session/20-plan/30-research/40-review，
README 与 templates 目录天然不是月目录，会自动跳过）。
日期取自文件名前缀 YYYY-MM-DD；没有就退回目录名里的 YYYY-MM。
"""
from __future__ import annotations

import os
import re

DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
MONTH = re.compile(r"^(\d{4})-(\d{2})$")
DEFAULT_SLOTS = ("10-session", "20-plan", "30-research", "40-review")


def collect(cfg: dict, ctx: dict) -> dict:
    repo_root = ctx["repo_root"]
    rel = cfg.get("path") or ctx["paths"].get("handoff_dir") or "handoff"
    base = os.path.join(repo_root, rel)
    if not os.path.isdir(base):
        return {"handoffs": [], "status": "absent",
                "detail": f"交接目录不存在：{rel}"}

    slots = cfg.get("slots") or DEFAULT_SLOTS
    limit = int(cfg.get("limit") or 8)
    rows = []
    for slot in slots:
        sdir = os.path.join(base, slot)
        if not os.path.isdir(sdir):
            continue
        for month in os.listdir(sdir):
            mdir = os.path.join(sdir, month)
            if not os.path.isdir(mdir) or not MONTH.match(month):
                continue                    # templates/ 之类不是月目录
            for fn in os.listdir(mdir):
                if not fn.endswith(".md"):
                    continue
                dm = DATE.match(fn)
                if dm:
                    doc_date = dm.group(1)
                else:
                    mm = MONTH.match(month)
                    doc_date = f"{mm.group(1)}-{mm.group(2)}-01"
                rows.append({"slot": slot,
                             "rel_path": f"{rel}/{slot}/{month}/{fn}",
                             "doc_date": doc_date,
                             "title": _first_heading(os.path.join(mdir, fn)) or fn})

    if not rows:
        return {"handoffs": [], "status": "absent",
                "detail": f"{rel} 下没找到交接件（槽位 {list(slots)}）"}
    rows.sort(key=lambda r: (r["doc_date"], r["rel_path"]), reverse=True)
    rows = rows[:limit]
    for i, r in enumerate(rows):
        r["ord"] = i
    return {"handoffs": rows, "status": "ok",
            "detail": f"{len(rows)} 份交接（最近 {rows[0]['doc_date']}）"}


def _first_heading(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line.startswith("# "):
                    return line[2:].strip()
                if line and not line.startswith(("#", ">", "---", "|")):
                    return line[:120]
    except OSError:
        pass
    return ""
