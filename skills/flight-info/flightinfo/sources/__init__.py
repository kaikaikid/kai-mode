# -*- coding: utf-8 -*-
"""源注册表：类型名 → 模块。

加新源只做两件事：在 sources/ 下加一个模块（实现 collect(cfg, ctx)），
再在下面 REGISTRY 加一行。板配置里写该类型名即可，不改其他任何地方。
"""
from __future__ import annotations

from . import board_cards, issues, tasks, worktrees

REGISTRY = {
    "board-cards": board_cards,
    "tasks-table": tasks,
    "git-worktrees": worktrees,
    "github-issues": issues,
}

TYPES = tuple(REGISTRY)


def get(type_: str):
    mod = REGISTRY.get(type_)
    if mod is None:
        raise KeyError(f"未知源类型 {type_!r}（只许 {'/'.join(TYPES)}）")
    return mod
