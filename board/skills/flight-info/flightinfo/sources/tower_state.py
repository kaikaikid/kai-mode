# -*- coding: utf-8 -*-
"""源：塔台待发货队列 ＋ 塔台令牌（运行态，本地文件，零网络）。

两个源都读**框架自有命名空间**（项目配置 `paths.state_dir`）：
- `ship-queue`    → `<state_dir>/ship-queue.json`，正本写者是塔台（ship-queue.py sync）；
- `tower-token`   → `<state_dir>/tower-token.json`，正本写者是塔台（tower-token.py）。

它们都不产生航班记录：票面事实仍以 Issue 为准，这两个源只出「运行态读数」，
由渲染层挂在板子上（待发货队列区块、状态条塔台灯）。读不到 ⇒ 降级点名，不猜。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

QUEUE_FILE = "ship-queue.json"
TOKEN_FILE = "tower-token.json"


def _state_dir(ctx: dict) -> str | None:
    paths = ctx.get("paths") or {}
    sd = (paths.get("state_dir") or "").strip()
    if not sd:
        return None
    return os.path.join(ctx.get("repo_root") or "", *sd.split("/"))


def _read_json(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def collect(cfg: dict, ctx: dict) -> dict:
    """待发货队列：pending/hotfix 计数与逐票行，供板子的「待发货队列」区块用。"""
    base = _state_dir(ctx)
    if not base:
        return {"flights": [], "schedules": [], "queue": None, "status": "skipped",
                "detail": "项目配置实例缺 paths.state_dir，读不到队列"}
    path = os.path.join(base, QUEUE_FILE)
    if not os.path.isfile(path):
        return {"flights": [], "schedules": [], "queue": {"pending": 0, "hotfix": 0,
                                                          "invalid": 0, "rows": []},
                "status": "absent",
                "detail": "尚无 ship-queue.json（塔台还没跑过 sync）"}
    data = _read_json(path) or {}
    pending = data.get("pending") if isinstance(data.get("pending"), dict) else {}
    rows = []
    for key, e in pending.items():
        e = e or {}
        rows.append({"ticket": key, "ac": e.get("ac") or "", "sha": e.get("sha") or "",
                     "branch": e.get("branch") or "", "urgent": bool(e.get("urgent")),
                     "held": e.get("held") or "", "verified": e.get("verified") or ""})
    rows.sort(key=lambda r: (not r["urgent"], r["ticket"]))
    return {"flights": [], "schedules": [],
            "queue": {"pending": len(rows), "hotfix": 0, "invalid": 0,
                      "cursor": data.get("cursor_updated_at") or "", "rows": rows},
            "status": "ok",
            "detail": f"待发货 {len(rows)} 张（队列由塔台写，改后下一轮才刷新）"}


def collect_token(cfg: dict, ctx: dict) -> dict:
    """塔台令牌：持牌人、心跳年龄。只出一行读数，不产生改判。"""
    base = _state_dir(ctx)
    if not base:
        return {"flights": [], "schedules": [], "tower": None, "status": "skipped",
                "detail": "项目配置实例缺 paths.state_dir，读不到令牌"}
    token = _read_json(os.path.join(base, TOKEN_FILE))
    interval = 60
    try:
        inst = _read_json(os.path.join(ctx.get("repo_root") or "", ".ai",
                                       "kai-mode.project.json")) or {}
        interval = int((inst.get("tower_cron") or {}).get("interval_min") or 60)
    except (TypeError, ValueError):
        interval = 60
    if not isinstance(token, dict) or not token.get("holder"):
        return {"flights": [], "schedules": [],
                "tower": {"state": "free", "holder": "", "age_min": None,
                          "limit_min": interval + 5},
                "status": "ok", "detail": "无令牌（谁先 acquire 谁是塔台）"}
    raw = token.get("heartbeat_at")
    try:
        age = (datetime.now(timezone.utc)
               - datetime.fromisoformat(str(raw))).total_seconds() / 60.0
    except (TypeError, ValueError):
        age = None
    limit = interval + 5
    state = "running" if age is not None and age <= limit else "stale"
    return {"flights": [], "schedules": [],
            "tower": {"state": state, "holder": token.get("holder") or "",
                      "age_min": round(age, 1) if age is not None else None,
                      "limit_min": limit},
            "status": "ok",
            "detail": (f"{token.get('holder')} 心跳 "
                       + (f"{age:.0f} 分钟前" if age is not None else "读不出"))}
