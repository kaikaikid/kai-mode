# -*- coding: utf-8 -*-
"""源：GitHub 票面（gh CLI）。

票面是**状态正本**。gh 不可用／未登录／超时一律降级，不让整页崩。
本模块只取票面字段，不拉评论（评论另有人读面需要时再加源）。
"""
from __future__ import annotations

import json
import os
import subprocess

FIELDS = "number,title,state,labels,assignees,milestone,updatedAt,closedAt,url"


def _gh(args: list[str], cwd: str, timeout: int = 60) -> tuple[int, str, str]:
    # Windows 无控制台宿主（pythonw/计划任务）下不带旗标会闪黑窗
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        r = subprocess.run(["gh"] + args, capture_output=True, text=True,
                           timeout=timeout, cwd=cwd, check=False, creationflags=flags)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return 127, "", "gh 不在 PATH"
    except subprocess.TimeoutExpired:
        return 124, "", f"gh 超时（{timeout}s）"
    except OSError as e:
        return 1, "", f"gh 起不来：{e}"


def queries_for(state: str, limit: int, include_closed: bool,
                closed_limit: int | None = None) -> list[tuple[str, int]]:
    """→ [(--state 取值, 条数)]。include_closed ⇒ 顺带拉已关票。

    为什么需要：残留的 `exec/<票号>-*` 分支是「在飞」的硬证据，只有票已关这一条
    能把它压回「已收尾」；只拉 open 时，几十条历史分支会把板子说成「在飞 N 张」。
    """
    if state == "none":
        return []
    q = [(state, limit)]
    if state == "open" and include_closed:
        q.append(("closed", closed_limit or limit))
    return q


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
    queries = queries_for(state, limit, bool(cfg.get("include_closed")),
                          int(cfg["closed_limit"]) if cfg.get("closed_limit") else None)
    if not queries:
        return {"flights": [], "schedules": [], "status": "skipped",
                "detail": "state=none，本板不读票面"}

    picked: dict[int, dict] = {}
    for st, lim in queries:
        args = ["issue", "list", "--repo", repo, "--limit", str(lim),
                "--state", st, "--json", FIELDS]
        rc, out, err = _gh(args, ctx["repo_root"])
        if rc != 0:
            return {"flights": [], "schedules": [], "status": "fail",
                    "detail": f"gh issue list --state {st} 失败（rc={rc}）：{(err or out).strip()[:160]}"}
        try:
            for it in json.loads(out or "[]"):
                picked.setdefault(it["number"], it)
        except (json.JSONDecodeError, KeyError) as e:
            return {"flights": [], "schedules": [], "status": "fail",
                    "detail": f"gh 输出不是 JSON：{e}"}
    rows = list(picked.values())

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
