# -*- coding: utf-8 -*-
"""源注册表：类型名 → 模块。

加新源只做两件事：在 sources/ 下加一个模块（实现 collect(cfg, ctx)），
再在下面 REGISTRY 加一行。板配置里写该类型名即可，不改其他任何地方。
"""
from __future__ import annotations

from . import board_cards, coding_runs, handoff, issues, tasks, tower_state, worktrees

REGISTRY = {
    "board-cards": board_cards,
    "tasks-table": tasks,
    "git-worktrees": worktrees,
    "github-issues": issues,
    "handoff-index": handoff,
    "ship-queue": tower_state,
    "coding-runs": coding_runs,
}

# tower-token 与 ship-queue 共用一个模块、两个入口：注册表按类型名分开指向
REGISTRY["tower-token"] = tower_state

TYPES = tuple(REGISTRY)


def get(type_: str):
    mod = REGISTRY.get(type_)
    if mod is None:
        raise KeyError(f"未知源类型 {type_!r}（只许 {'/'.join(TYPES)}）")
    return mod


def collect(type_: str, cfg: dict, ctx: dict) -> dict:
    """按类型名调对应采集函数：ship-queue / tower-token 同模块不同入口。"""
    mod = get(type_)
    if mod is tower_state:
        if type_ == "tower-token":
            return mod.collect_token(cfg, ctx)
        return mod.collect(cfg, ctx)
    return mod.collect(cfg, ctx)
