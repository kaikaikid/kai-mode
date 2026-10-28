#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""免票热修的机械闸（体检 M16）。

热修是「用户说了就能直接改」的道，四条门槛全靠自评——最自由的道最需要一道机检。
本脚本只查三件能机械判定的事，全过才许写 `verdict=pass`：

  1. 分支名合 `hotfix/ace-<YYYYMMDD>-<n>-<slug>`；
  2. 该分支最新提交的 subject 带热修标识 `H-<YYYY-MM-DD>-<n>`；
  3. 当日 `-ace.md` 里同一行同时有：分支名、`verdict=pass`、门禁读数（`rc=`）。

用法：
  python <本技能目录>/scripts/hotfix-lint.py --repo <仓根> --day-table <path> --branch <分支> [--json]

输出（每项一行）：`ok|fail\\t<项>\\t<读数>`，末行 `verdict=pass|fail`。
退出码：0 全过；1 有失败项；2 用法／仓根不可用。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BRANCH_RE = re.compile(r"^hotfix/ace-(\d{8})-(\d+)-[a-z0-9][a-z0-9-]*$")
MARKER_RE = re.compile(r"H-\d{4}-\d{2}-\d{2}-\d+")


def git(repo: str, *args: str) -> tuple[int, str]:
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "").strip()


def lint(repo: str, day_table: str, branch: str) -> list[dict]:
    rows = []

    m = BRANCH_RE.match(branch)
    rows.append({"check": "branch-name", "ok": bool(m),
                 "detail": branch if m else f"{branch} 不合 hotfix/ace-<YYYYMMDD>-<n>-<slug>"})

    rc, subject = git(repo, "log", "-1", "--format=%s", branch)
    if rc != 0:
        rows.append({"check": "commit-marker", "ok": False, "detail": f"读不到分支 {branch} 的提交"})
    else:
        hit = MARKER_RE.search(subject)
        rows.append({"check": "commit-marker", "ok": bool(hit),
                     "detail": subject if hit else f"最新提交缺热修标识 H-<日期>-<序号>：{subject}"})

    if not os.path.isfile(day_table):
        rows.append({"check": "day-table-row", "ok": False, "detail": f"日表不存在：{day_table}"})
    else:
        with open(day_table, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        cand = [ln for ln in lines if branch in ln]
        good = [ln for ln in cand if "verdict=pass" in ln and "rc=" in ln]
        if good:
            rows.append({"check": "day-table-row", "ok": True, "detail": good[0].strip()[:120]})
        elif cand:
            rows.append({"check": "day-table-row", "ok": False,
                         "detail": "行里缺 `verdict=pass` 或门禁读数 `rc=`：" + cand[0].strip()[:100]})
        else:
            rows.append({"check": "day-table-row", "ok": False,
                         "detail": "日表里没有这一行的分支名（热修必须逐行留痕）"})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="免票热修的机械闸")
    ap.add_argument("--repo", required=True, help="仓根（含 .git）")
    ap.add_argument("--day-table", required=True, help="当日 -ace.md 路径")
    ap.add_argument("--branch", required=True, help="热修分支名")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    repo = os.path.abspath(a.repo)
    if not os.path.exists(os.path.join(repo, ".git")):
        print(f"不是 git 仓：{repo}")
        return 2

    rows = lint(repo, a.day_table, a.branch)
    ok = all(r["ok"] for r in rows)
    if a.json:
        print(json.dumps({"verdict": "pass" if ok else "fail", "checks": rows},
                         ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print(f"{'ok' if r['ok'] else 'fail'}\t{r['check']}\t{r['detail']}")
        print(f"verdict={'pass' if ok else 'fail'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
