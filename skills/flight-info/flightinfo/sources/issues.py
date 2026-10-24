# -*- coding: utf-8 -*-
"""源：GitHub 票面（gh CLI）。

票面是**状态正本**。gh 不可用／未登录／超时一律降级，不让整页崩。
本模块只取票面字段，不拉评论（评论另有人读面需要时再加源）。
"""
from __future__ import annotations

import json
import subprocess

FIELDS = "number,title,state,labels,assignees,milestone,updatedAt,closedAt,url"


def _gh(args: list[str], cwd: str, timeout: int = 60) -> tuple[int, str, str]:
    try:
        r = subprocess.run(["gh"] + args, capture_output=True, text=True,
                           timeout=timeout, cwd=cwd, check=False)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return 127, "", "gh 不在 PATH"
    except subprocess.TimeoutExpired:
        return 124, "", f"gh 超时（{timeout}s）"
    except OSError as e:
        return 1, "", f"gh 起不来：{e}"


def collect(cfg: dict, ctx: dict) -> dict:
    if ctx.get("no_network"):
        return {"flights": [], "schedules": [], "status": "skipped",
                "detail": "--no-network：跳过票面（不冒充已读取）"}
    repo = cfg.get("repo") or ctx.get("repo") or ""
    if not repo:
        return {"flights": [], "schedules": [], "status": "skipped",
                "detail": "没有 repo slug（板配置 repo 或目标仓 git remote 解析不出）"}
    state = cfg.get("state") or "open"
    limit = int(cfg.get("limit") or 200)

    args = ["issue", "list", "--repo", repo, "--limit", str(limit),
            "--json", FIELDS]
    if state == "open":
        args += ["--state", "open"]
    elif state == "closed":
        args += ["--state", "closed"]
    elif state == "none":
        return {"flights": [], "schedules": [], "status": "skipped",
                "detail": "state=none，本板不读票面"}

    rc, out, err = _gh(args, ctx["repo_root"])
    if rc != 0:
        return {"flights": [], "schedules": [], "status": "fail",
                "detail": f"gh issue list 失败（rc={rc}）：{(err or out).strip()[:160]}"}
    try:
        rows = json.loads(out or "[]")
    except json.JSONDecodeError as e:
        return {"flights": [], "schedules": [], "status": "fail",
                "detail": f"gh 输出不是 JSON：{e}"}

    flights = []
    for it in rows:
        labels = [l.get("name", "") for l in (it.get("labels") or [])]
        who = (it.get("assignees") or [{}])[0].get("login", "") if it.get("assignees") else ""
        ms = it.get("milestone") or {}
        flights.append({
            "uid": f"issue:{it['number']}",
            "ticket": f"#{it['number']}",
            "title": it.get("title") or "",
            "labels": labels,
            "closed": (it.get("state") or "").upper() == "CLOSED",
            "last_comment": "",
            "table_note": "",
            "branches": [],
            "assignee": who,
            "milestone": ms.get("title") or "",
            "url": it.get("url") or "",
            "owner": "",
            "persona": "",
            "planned": False,
            "updated_at": it.get("updatedAt") or "",
            "closed_at": it.get("closedAt") or None,
            "source": "github-issues",
            "kind": "task",
        })
    return {"flights": flights, "schedules": [], "status": "ok",
            "detail": f"{len(flights)} 张票"}
