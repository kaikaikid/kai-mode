#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""card —— 从票面 JSON 生成派工卡（契约五件）。

输入：`python ../loop/scripts/ticket.py show --ticket N --json > ticket.json`
用法：
  python card.py --ticket-json ticket.json [--role builder|reviewer]
                 [--lane main|deputy|ace] [--branch <分支>] [--worktree <路径>]
                 [--method <方法技能>] [--json]

输出：一段可直接贴给子代理的派工卡；不写实现方案，不替子代理选方法。
退出码：0 生成；2 输入读不出。
"""
from __future__ import annotations

import argparse
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

RECEIPT = ('JSON：ticket / role / verdict(done|blocked|pass|fail) / files / commits / '
           'checks / summary / evidence / risks / next；不贴 diff 全文与原始日志')


def load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"票面 JSON 读不出：{exc}")
    if not isinstance(data, dict):
        raise SystemExit("票面 JSON 不是对象")
    return data


def lines(items, prefix="  - "):
    return "\n".join(prefix + str(x) for x in items) if items else "  （票面未写）"


def build(data: dict, a) -> dict:
    role = "reviewer" if a.role == "reviewer" else "builder"
    card = {
        "ticket": data.get("number"),
        "role": role,
        "lane": a.lane,
        "branch": a.branch,
        "worktree": a.worktree,
        "ac": data.get("ac") or [],
        "allow": data.get("allow") or [],
        "deny": data.get("deny") or [],
        "verify": data.get("verify") or [],
        "method": a.method or ("code-review" if role == "reviewer" else "由子代理按票情自选"),
        "receipt": RECEIPT,
    }
    if role == "reviewer":
        card["instruction"] = "只读；逐条对 AC 与机检；不得改代码、不得复用施工上下文。"
    else:
        card["instruction"] = "独立车道工作树里换票分支；增量提交；不 push、不合并。"
    return card


def render(card: dict) -> str:
    out = [
        f"票号：{card['ticket']}",
        f"角色：{card['role']}",
        f"车道：{card['lane']}",
    ]
    if card.get("branch"):
        out.append(f"分支：{card['branch']}")
    if card.get("worktree"):
        out.append(f"工作树：{card['worktree']}")
    out += [
        "AC：",
        lines(card["ac"]),
        "允许修改：",
        lines(card["allow"]),
        "禁止修改：",
        lines(card["deny"]),
        "验证命令：",
        lines(card["verify"]),
        f"方法：{card['method']}",
        f"回执：{card['receipt']}",
        f"纪律：{card['instruction']}",
    ]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="从票面 JSON 生成派工卡")
    ap.add_argument("--ticket-json", required=True)
    ap.add_argument("--role", choices=("builder", "reviewer"), default="builder")
    ap.add_argument("--lane", choices=("main", "deputy", "ace"), default="main")
    ap.add_argument("--branch")
    ap.add_argument("--worktree")
    ap.add_argument("--method")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    card = build(load(a.ticket_json), a)
    if a.json:
        print(json.dumps(card, ensure_ascii=False, indent=2))
    else:
        print(render(card))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
