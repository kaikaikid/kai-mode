#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""有脏才刷：给系统闹钟或人工调用的幂等入口。

git 钩子只写 `.git/flight-info-dirty`；本脚本读它：空＝跳过（零开销），
非空＝跑一次刷新，然后把标记清空（写空串，不删文件——环境常拦删除）。

    python scripts/refresh_if_dirty.py --repo-root <仓根> --config <board.config.json> [--force]

--force 无视标记，强制刷一次。
退出码：0 无脏/刷成功；2 配置错；3 写不出。
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import refresh as refresh_mod  # noqa: E402

MARKER = "flight-info-dirty"


def main() -> int:
    ap = argparse.ArgumentParser(description="脏标记驱动的幂等刷新")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--force", action="store_true", help="无视脏标记强制刷")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    repo_root = os.path.abspath(a.repo_root)
    mark = os.path.join(repo_root, ".git", MARKER)
    stamp = ""
    try:
        with open(mark, encoding="utf-8") as f:
            stamp = (f.read() or "").strip()
    except OSError:
        stamp = ""

    if not stamp and not a.force:
        if not a.quiet:
            print(f"无脏（.git/{MARKER} 为空），跳过")
        return 0

    res = refresh_mod.run_refresh(repo_root, a.config,
                                  quiet=a.quiet, no_network=False)
    if not res["ok"]:
        print(res.get("error", "刷新失败"), file=sys.stderr)
        return res["rc"]

    try:
        with open(mark, "w", encoding="utf-8", newline="\n") as f:
            f.write("")
    except OSError as e:
        print(f"标记清空失败（下次会再刷一次，不影响正确性）：{e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
