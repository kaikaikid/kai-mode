#!/usr/bin/env python3
"""把 agents/ 下的子代理模板装到目标目录。

默认项目级：<项目仓>/.claude/agents/（adapters/README.md §8 的规定落点）。
--host-root：宿主级，$CLAUDE_CONFIG_DIR/agents/；未设该变量则 ~/.claude/agents/。
                宿主级是显式例外：同名项优先级低于项目级，且盖不掉内置代理。

只新增或备份后覆盖，不删除目标里多出来的文件。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / "agents"
SKIP = {"README.md"}


def host_root() -> Path:
    env = os.environ.get("CLAUDE_CONFIG_DIR", "").strip()
    return Path(env) if env else Path.home() / ".claude"


def plan(target: Path, force: bool) -> dict:
    actions = {"copy": [], "overwrite": [], "skip": [], "conflict": []}
    for src in sorted(SOURCE.glob("*.md")):
        if src.name in SKIP:
            continue
        dst = target / src.name
        if not dst.exists():
            actions["copy"].append(src.name)
        elif dst.read_bytes() == src.read_bytes():
            actions["skip"].append(src.name)
        elif force:
            actions["overwrite"].append(src.name)
        else:
            actions["conflict"].append(src.name)
    return actions


def apply(target: Path, actions: dict) -> Path | None:
    target.mkdir(parents=True, exist_ok=True)
    backup = None
    if actions["overwrite"]:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = target / ".backups" / stamp
        backup.mkdir(parents=True, exist_ok=True)
        for name in actions["overwrite"]:
            shutil.copy2(target / name, backup / name)
    for name in actions["copy"] + actions["overwrite"]:
        shutil.copy2(SOURCE / name, target / name)
    return backup


def main() -> int:
    parser = argparse.ArgumentParser(description="安装子代理模板")
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument("--project", metavar="REPO", help="项目仓根，装到 <REPO>/.claude/agents/")
    target_group.add_argument("--host-root", action="store_true", help="装到宿主配置根（显式例外）")
    parser.add_argument("--force", action="store_true", help="同名不同内容时先备份再覆盖")
    parser.add_argument("--dry-run", action="store_true", help="只报告将做什么，不写盘")
    parser.add_argument("--json", action="store_true", help="机器可读回执")
    args = parser.parse_args()

    if not SOURCE.is_dir():
        print(f"缺模板源：{SOURCE}", file=sys.stderr)
        return 2

    if args.host_root:
        target = host_root() / "agents"
        scope = "host"
    else:
        target = Path(args.project).resolve() / ".claude" / "agents"
        scope = "project"

    actions = plan(target, args.force)
    backup = None
    if not args.dry_run:
        backup = apply(target, actions)

    receipt = {
        "scope": scope,
        "source": str(SOURCE),
        "target": str(target),
        "dry_run": args.dry_run,
        "backup": str(backup) if backup else None,
        **actions,
    }
    if args.json:
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
    else:
        print(f"范围：{scope}")
        print(f"源：{SOURCE}")
        print(f"目标：{target}")
        for key, label in (("copy", "新增"), ("overwrite", "备份后覆盖"),
                           ("skip", "已一致"), ("conflict", "冲突未动")):
            names = actions[key]
            print(f"{label}（{len(names)}）：{', '.join(names) if names else '—'}")
        if backup:
            print(f"备份：{backup}")
        if args.dry_run:
            print("dry-run：未写盘")
        if actions["conflict"]:
            print("冲突用 --force 处理；装完起新会话才重新加载。", file=sys.stderr)
    return 1 if actions["conflict"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
