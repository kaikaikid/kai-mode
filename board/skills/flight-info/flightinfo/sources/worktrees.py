# -*- coding: utf-8 -*-
"""源：git worktree / 分支（在飞证据）。

有 `exec/<票号>-*` 分支 = 这张票有人正在施工。这是**最硬的在飞证据**：
不依赖任何平台 API，只看本地 git。
"""
from __future__ import annotations

import re
import subprocess

EXEC = re.compile(r"^(?P<prefix>.+?)/(?P<num>\d+)(?:[-_].*)?$")


def _worktrees(repo_root: str) -> list[str]:
    """→ 分支名列表（detached 的跳过）。"""
    try:
        out = subprocess.run(
            ["git", "-C", repo_root, "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if out.returncode != 0:
        return []
    branches = []
    for line in out.stdout.splitlines():
        if line.startswith("branch refs/heads/"):
            branches.append(line[len("branch refs/heads/"):].strip())
    return branches


def _local_branches(repo_root: str) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", repo_root, "for-each-ref", "--format=%(refname:short)",
             "refs/heads"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [l.strip() for l in out.stdout.splitlines() if l.strip()] if out.returncode == 0 else []


def _branch_dates(repo_root: str) -> dict[str, str]:
    """分支名 → 最后一次提交时间（ISO）。

    没有这一发，残留分支的票会被写成「本轮刚刚更新」，停滞判定就永远看不见它——
    2026-10-26 口径刀就是为这个补的。一次 for-each-ref 全取，不按分支逐发。
    """
    try:
        out = subprocess.run(
            ["git", "-C", repo_root, "for-each-ref",
             "--format=%(refname:short)%09%(committerdate:iso8601-strict)",
             "refs/heads"],
            capture_output=True, text=True, timeout=20, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return {}
    if out.returncode != 0:
        return {}
    dates: dict[str, str] = {}
    for line in out.stdout.splitlines():
        name, _, when = line.partition("\t")
        if name.strip():
            dates[name.strip()] = when.strip()
    return dates


def collect(cfg: dict, ctx: dict) -> dict:
    repo_root = ctx["repo_root"]
    raw = cfg.get("branch_prefixes")
    if raw is None:
        raw = cfg.get("branch_prefix") or "exec/"
    prefixes = [raw] if isinstance(raw, str) else [str(x) for x in raw]
    names = set(_worktrees(repo_root)) | set(_local_branches(repo_root))
    if not names:
        return {"flights": [], "schedules": [], "status": "fail",
                "detail": "git 不可用或读不到分支（该源只在本地生效）"}
    dates = _branch_dates(repo_root)

    hit = [b for b in sorted(names) if any(b.startswith(x) for x in prefixes)]
    flights = []
    for b in hit:
        m = EXEC.match(b)
        if not m:
            continue
        num = m.group("num")
        flights.append({
            "uid": f"issue:{num}",
            "ticket": f"#{num}",
            "title": "",          # 由其他源补；这里只贡献证据
            "labels": [],
            "closed": False,
            "last_comment": "",
            "table_note": "",
            "branches": [b],
            "assignee": "",
            "milestone": "",
            "url": "",
            "owner": "",
            "persona": "",
            "planned": False,
            "updated_at": dates.get(b, ""),   # 分支最后提交＝这张票真正动过的时刻
            "source": "git-worktrees",
            "kind": "task",
        })
    return {"flights": flights, "schedules": [], "status": "ok",
            "detail": f"{len(hit)} 个在飞分支" if hit else "无在飞分支"}
