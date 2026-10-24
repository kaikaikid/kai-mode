#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给项目仓装 / 卸 git 钩子（post-commit ＋ post-merge）。

钩子只做一件事：把一个时间戳写进 `.git/flight-info-dirty`。
**不同步刷新**（联网的板一次几十秒，绝不能让 commit 等），也不调任何外部命令。
真正的刷新由 `refresh_if_dirty.py` 在闹钟或人工触发时做。

    python scripts/install_hook.py --repo-root <仓根>            # 干跑，只打印
    python scripts/install_hook.py --repo-root <仓根> --apply
    python scripts/install_hook.py --repo-root <仓根> --remove --apply

退出码：0 成功；2 参数/环境错；3 写不出或钩子已存在且不是本工具生成的。
"""
from __future__ import annotations

import argparse
import os
import stat
import sys

MARKER = "flight-info-dirty"
SIGN = "# managed by kai-mode skill: flight-info"

HOOK = """#!/bin/sh
{sign}
# 只打脏标记，不同步刷新，退出码恒 0 —— 绝不阻塞 commit / merge
root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
printf '%s\\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$root/.git/{marker}" 2>/dev/null
exit 0
""".format(sign=SIGN, marker=MARKER)

HOOKS = ("post-commit", "post-merge")


def _hook_path(repo_root: str, name: str) -> str:
    return os.path.join(repo_root, ".git", "hooks", name)


def main() -> int:
    ap = argparse.ArgumentParser(description="安装/卸载 flight-info 的 git 钩子")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--apply", action="store_true", help="真正落盘（默认干跑）")
    ap.add_argument("--remove", action="store_true", help="卸载本工具装的钩子")
    a = ap.parse_args()

    repo_root = os.path.abspath(a.repo_root)
    hooks_dir = os.path.join(repo_root, ".git", "hooks")
    if not os.path.isdir(hooks_dir):
        print(f"不是 git 仓或缺 .git/hooks：{repo_root}", file=sys.stderr)
        return 2

    rc = 0
    for name in HOOKS:
        p = _hook_path(repo_root, name)
        exists = os.path.isfile(p)
        mine = False
        if exists:
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    mine = SIGN in f.read()
            except OSError:
                mine = False

        if a.remove:
            if not exists:
                print(f"  {name}: 不存在，跳过")
            elif not mine:
                print(f"  {name}: 不是本工具装的，不动", file=sys.stderr)
                rc = 3
            elif a.apply:
                with open(p, "w", encoding="utf-8", newline="\n") as f:
                    f.write("#!/bin/sh\n# flight-info hook removed\n")
                print(f"  {name}: 已停用（保留文件，内容清空）")
            else:
                print(f"  {name}: [干跑] 会停用")
            continue

        if exists and not mine:
            print(f"  {name}: 已存在且不是本工具生成的，拒绝覆盖（请人工处理）", file=sys.stderr)
            rc = 3
            continue
        if a.apply:
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(HOOK)
            os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            print(f"  {name}: 已装")
        else:
            print(f"  {name}: [干跑] 会写入 {len(HOOK)} 字节")

    if a.apply and not a.remove:
        mp = os.path.join(repo_root, ".git", MARKER)
        if not os.path.exists(mp):
            with open(mp, "w", encoding="utf-8", newline="\n") as f:
                f.write("")
        print(f"  脏标记：.git/{MARKER}（内容空＝无脏）")
    if not a.apply:
        print("\n干跑结束；要落盘加 --apply")
    return rc


if __name__ == "__main__":
    sys.exit(main())
