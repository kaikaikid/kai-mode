#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
handoff 看板（handoff/60-board/）操作脚本 —— 纯结构化、AI 读写、人不读。
=====================================================================
看板件 = 一坨 frontmatter（全部字段）+ 可选三行正文。认领/完成/归档一律靠**移动文件**，
移动是原子动作，天然防两个 agent 抢同一张活。任务**不依赖 GitHub issue**：开票的写
`ticket: "#12"`，没开票的热修/杂活写 `ticket: "-"`，靠 `id` 兜底追踪。

用法：
  python scripts/handoff-board.py new  --title "一句话" [--ticket "#12"] [--type task]
                                       [--role 机长] [--persona worker]
  python scripts/handoff-board.py list [--state open|claimed|done|all]
  python scripts/handoff-board.py show <id>
  python scripts/handoff-board.py claim <id> [--by 机长]
  python scripts/handoff-board.py close <id> --outcome "一句话结果"
  python scripts/handoff-board.py archive [--month YYYY-MM]

约定：
  id    = YYYYMMDD-NN（当日序号，脚本生成，全局唯一）
  文件名 = YYYY-MM-DD-NN-<type>.md
  状态   = open/  claimed/  done/  archive/YYYY-MM/
只读标准库、不装依赖；除本脚本写的卡件与索引外不碰别的盘上内容。
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
BOARD = os.path.join(ROOT, "handoff", "60-board")

STATES = ("open", "claimed", "done")
TYPES = ("task", "hotfix", "dispatch", "claim", "blocked")
# frontmatter 字段固定顺序（机器读，别乱序）
FIELDS = ("id", "slot", "type", "ticket", "title", "state", "role", "persona",
          "created_at", "claimed_by", "claimed_at", "closed_at", "outcome")


# ── frontmatter 读写 ────────────────────────────────────────────────────────
def fm_read(path):
    """读 frontmatter → dict（无 frontmatter 返回 {}）。"""
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return {}
    if not lines or lines[0].strip() != "---":
        return {}
    out = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def fm_write(fields: dict) -> str:
    """按 FIELDS 固定顺序渲染 frontmatter + 极简正文骨架。"""
    head = "\n".join(f"{k}: {fields.get(k, '-')}" for k in FIELDS)
    return (f"---\n{head}\n---\n\n"
            f"# {fields.get('title', '')}\n\n"
            f"<!-- 正文可选：卡点 / 结论 / 指针，控制在三行内 -->\n")


# ── 卡片定位 ────────────────────────────────────────────────────────────────
def cards(state=None):
    """返回 [(state, path, fields)]，state=None 表示扫 open/claimed/done（不含 archive）。"""
    out = []
    for st in (STATES if state in (None, "all") else (state,)):
        d = os.path.join(BOARD, st)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".md"):
                p = os.path.join(d, fn)
                out.append((st, p, fm_read(p)))
    return out


def find(card_id):
    for st, p, fm in cards():
        if fm.get("id") == card_id or os.path.basename(p).startswith(card_id.replace("-", "-")):
            return st, p, fm
    return None, None, {}


def next_id(today: dt.date) -> str:
    """当日序号：扫 open/claimed/done/archive 找出当天最大 NN，+1。"""
    stem = today.strftime("%Y%m%d")
    maxn = 0
    for base, _d, files in os.walk(BOARD):
        for fn in files:
            m = re.match(rf"^{today.strftime('%Y-%m-%d')}-(\d{{2}})-", fn)
            if m and os.path.basename(base) != "templates":
                maxn = max(maxn, int(m.group(1)))
    return f"{stem}-{maxn + 1:02d}"


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def move(path, dest_dir, **updates):
    """移动卡片并回写 frontmatter 字段（移动＝原子认领）。"""
    os.makedirs(dest_dir, exist_ok=True)
    fm = fm_read(path)
    fm.update(updates)
    dst = os.path.join(dest_dir, os.path.basename(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write(fm_write(fm))
    shutil.move(path, dst)
    return dst


# ── 子命令 ──────────────────────────────────────────────────────────────────
def cmd_new(a):
    if not os.path.isdir(BOARD):
        return f"没有看板目录：{os.path.relpath(BOARD, ROOT)}"
    today, cid = dt.date.today(), None
    cid = next_id(today)
    fields = {
        "id": cid, "slot": "60-board", "type": a.type, "ticket": a.ticket,
        "title": a.title, "state": "open", "role": a.role, "persona": a.persona,
        "created_at": now(), "claimed_by": "-", "claimed_at": "-",
        "closed_at": "-", "outcome": "-",
    }
    fn = f"{today.strftime('%Y-%m-%d')}-{cid.split('-')[1]}-{a.type}.md"
    p = os.path.join(BOARD, "open", fn)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(fm_write(fields))
    return f"新建卡片 {cid} → {os.path.relpath(p, ROOT)}"


def cmd_list(a):
    rows = cards(None if a.state in (None, "all") else a.state)
    if not rows:
        return "看板为空"
    lines = [f"{len(rows)} 张卡片："]
    for st, p, fm in rows:
        lines.append(f"  [{st}] {fm.get('id','?'):<12} {fm.get('type','?'):<8} "
                     f"票={fm.get('ticket','-')} 领={fm.get('claimed_by','-')} "
                     f"｜ {fm.get('title','')}")
    return "\n".join(lines)


def cmd_show(a):
    st, p, fm = find(a.id)
    if not p:
        return f"找不到卡片 {a.id}"
    return "\n".join(f"{k}: {fm.get(k, '-')}" for k in FIELDS)


def cmd_claim(a):
    st, p, fm = find(a.id)
    if not p:
        return f"找不到卡片 {a.id}"
    if st != "open":
        return f"卡片 {a.id} 当前在 {st}/，只有 open/ 的能认领"
    dst = move(p, os.path.join(BOARD, "claimed"),
               state="claimed", claimed_by=a.by, claimed_at=now())
    return f"已认领 {a.id}（认领人 {a.by}）→ {os.path.relpath(dst, ROOT)}"


def cmd_close(a):
    st, p, fm = find(a.id)
    if not p:
        return f"找不到卡片 {a.id}"
    if st != "claimed":
        return f"卡片 {a.id} 当前在 {st}/，只有 claimed/ 的能完成"
    dst = move(p, os.path.join(BOARD, "done"),
               state="done", closed_at=now(), outcome=a.outcome)
    return f"已完成 {a.id} → {os.path.relpath(dst, ROOT)}"


def cmd_archive(a):
    """done/ → archive/YYYY-MM/，并生成该月生命周期索引（结构化表格，脚本产出人不写）。"""
    month = a.month or dt.date.today().strftime("%Y-%m")
    rows = [r for r in cards("done")]
    if not rows:
        return f"done/ 为空，无可归档（月={month}）"
    dest = os.path.join(BOARD, "archive", month)
    os.makedirs(dest, exist_ok=True)
    moved, recs = [], []
    for st, p, fm in rows:
        m = (fm.get("closed_at", "-") or "-")[:7] or month
        if a.month and m != month:
            continue
        d = os.path.join(BOARD, "archive", m)
        os.makedirs(d, exist_ok=True)
        shutil.move(p, os.path.join(d, os.path.basename(p)))
        moved.append(fm.get("id", "?"))
        recs.append((m, fm))
    if not moved:
        return f"done/ 里没有属于 {month} 的卡片"
    # 月度生命周期索引
    for m in sorted({r[0] for r in recs}):
        idx = os.path.join(BOARD, "archive", f"{m}.md")
        lines = [f"# 看板生命周期索引 {m}", "",
                 "| id | type | ticket | title | role | 创建 | 认领 | 完成 | 结果 |",
                 "|---|---|---|---|---|---|---|---|---|"]
        for mm, fm in sorted([r for r in recs if r[0] == m], key=lambda x: x[1].get("id", "")):
            lines.append(f"| {fm.get('id','-')} | {fm.get('type','-')} | {fm.get('ticket','-')} | "
                         f"{fm.get('title','-')} | {fm.get('role','-')} | {fm.get('created_at','-')} | "
                         f"{fm.get('claimed_at','-')} | {fm.get('closed_at','-')} | {fm.get('outcome','-')} |")
        with open(idx, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return f"已归档 {len(moved)} 张（{', '.join(moved)}）→ handoff/60-board/archive/{month}/，索引已生成"


def main() -> int:
    ap = argparse.ArgumentParser(description="handoff 看板（60-board）结构化操作")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new", help="新建卡片")
    p.add_argument("--title", required=True)
    p.add_argument("--ticket", default="-", help='票号，如 "#12"；没开票就留 -')
    p.add_argument("--type", default="task", choices=TYPES)
    p.add_argument("--role", default="-", help="角色（岗位）：地勤/塔台/机长/副机长")
    p.add_argument("--persona", default="-", help="人格（委派能力）：worker 等")
    p.set_defaults(fn=cmd_new)

    p = sub.add_parser("list", help="列卡片（结构化）")
    p.add_argument("--state", default="all", choices=("all",) + STATES)
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("show", help="看单张全部字段")
    p.add_argument("id")
    p.set_defaults(fn=cmd_show)

    p = sub.add_parser("claim", help="认领（open→claimed）")
    p.add_argument("id")
    p.add_argument("--by", default="agent", help="认领者标识")
    p.set_defaults(fn=cmd_claim)

    p = sub.add_parser("close", help="完成（claimed→done）")
    p.add_argument("id")
    p.add_argument("--outcome", required=True)
    p.set_defaults(fn=cmd_close)

    p = sub.add_parser("archive", help="归档 done→archive/YYYY-MM 并生成月度索引")
    p.add_argument("--month", default=None, help="YYYY-MM，默认全部按 closed_at 归月")
    p.set_defaults(fn=cmd_archive)

    a = ap.parse_args()
    print(a.fn(a))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
