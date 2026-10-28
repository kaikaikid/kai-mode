#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
外部素材对账（docs/skill-sources/）—— 源件有没有更新、是不是到了对账日。
=========================================================================
素材索引正本：`docs/skill-sources/sources.json`（结构化，机器读）。
本脚本只读：不写索引、不碰源件、不联网。

用法：
  python scripts/source-check.py            # 人读
  python scripts/source-check.py --json     # 机器读
  python scripts/source-check.py --id <id>  # 只看某一个

判定：
  · 本地副本指纹 != 索引里的 sha256  → 「源件已更新，需对账」
  · 今天 >= next_diff_due            → 「到对账日」
  · 本地副本读不到（未安装/已卸载）  → 「副本缺失」

退出码：全部 ok ⇒ rc=0；有任何需处理项 ⇒ rc=1（自动化可据此中断）。
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
INDEX = os.path.join(ROOT, "docs", "skill-sources", "sources.json")


def load():
    if not os.path.isfile(INDEX):
        return None, f"没有素材索引：{os.path.relpath(INDEX, ROOT)}"
    try:
        with open(INDEX, encoding="utf-8") as f:
            return json.load(f), None
    except (OSError, ValueError) as exc:
        return None, f"索引解析失败：{exc!r}"


def expand(path: str) -> str:
    """展开 ~ 与 <magpie> 占位（占位未配置就原样返回，由调用方报缺失）。"""
    if path.startswith("~"):
        return os.path.expanduser(path)
    return path


def sha256(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except (OSError, ValueError):
        return None


def judge(item, today: dt.date):
    """返回 (状态, 说明)。"""
    path = expand(item.get("local_copy", ""))
    if not path or "<" in path or not os.path.isfile(path):
        return "副本缺失", f"读不到 {item.get('local_copy', '-')}"
    cur = sha256(path)
    tags = []
    if cur and item.get("sha256") and cur != item["sha256"]:
        tags.append("源件已更新，需对账")
    due = item.get("next_diff_due")
    if due:
        try:
            if today >= dt.date.fromisoformat(due):
                tags.append(f"到对账日（{due}）")
        except ValueError:
            tags.append(f"next_diff_due 非法：{due}")
    return ("需处理：" + "；".join(tags)) if tags else "ok", (cur or "")[:12]


def main() -> int:
    ap = argparse.ArgumentParser(description="外部素材对账")
    ap.add_argument("--json", action="store_true", help="机器读输出")
    ap.add_argument("--id", default=None, help="只看某个素材")
    a = ap.parse_args()

    data, err = load()
    if err:
        print(err)
        return 1
    today = dt.date.today()
    items = [x for x in data.get("sources", [])
             if a.id in (None, x.get("id"))]
    rows = []
    for it in items:
        status, fp = judge(it, today)
        rows.append({
            "id": it.get("id"), "name": it.get("name"), "status": status,
            "fingerprint": fp, "specialized_as": it.get("specialized_as", "-"),
            "next_diff_due": it.get("next_diff_due", "-"),
            "note": it.get("note", "-"),
        })

    todo = [r for r in rows if r["status"] != "ok"]
    if a.json:
        print(json.dumps({"today": today.isoformat(), "sources": rows}, ensure_ascii=False, indent=2))
        return 1 if todo else 0

    print(f"素材对账 —— {today} ｜ 共 {len(rows)} 条")
    for r in rows:
        print(f"  [{r['status']:<16}] {r['id']:<22} 指纹={r['fingerprint'] or '-':<12} "
              f"下次对账={r['next_diff_due']} 特化={r['specialized_as']}")
    print(f"总结：{len(rows)} 条 ｜ 需处理 {len(todo)} ｜ 对账命令：python scripts/source-check.py")
    return 1 if todo else 0


if __name__ == "__main__":
    raise SystemExit(main())
