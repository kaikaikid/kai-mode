#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开票归属守卫：`gh issue create` / `gh pr create` 缺显式 `--repo` 就拒。

判据住这里，不住技能正文与 AGENTS.md：
- 触发点＝宿主 PreToolUse / BeforeShell 钩子；本脚本**只判不写**，reject 时退出码 2。
- 想要的仓从项目配置实例读（`issue.repo` / `issue.pr_repo`，同一把键）；
  实例读不到 → 只要求命令带 `--repo`，不猜仓库。
- 豁免：命令里已有 `--repo` / `-R`；`--help`；非开票类 gh 命令一律放行（rc=0）。

用法（两种，同一份判据）：
  python <本技能目录>/scripts/issue-guard.py --command "<命令文本>"
  python <本技能目录>/scripts/issue-guard.py            # 宿主钩子：从 stdin 读 JSON，取 tool_input.command
  python <本技能目录>/scripts/issue-guard.py --self-test

退出码：0 放行；1 放行但提示（实例读不到，只能要求 --repo）；2 拒绝（缺 --repo）。
钩子接法（Claude Code 的 PreToolUse，matcher=Bash）见 `adapters/claude.md`；写入 settings.json 的动作
只在 set-kai-mode 安装步骤里发生，本脚本不写任何宿主配置。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

INSTANCE_REL = os.path.join(".ai", "kai-mode.project.json")
CREATE_RE = re.compile(r"\bgh\s+(?:issue|pr)\s+create\b")
REPO_FLAG_RE = re.compile(r"(?:^|\s)(?:--repo|-R)(?:=|\s+\S+)")
HELP_RE = re.compile(r"(?:^|\s)(?:--help|-h)(?:\s|$)")


def desired_repo(argv: list, repo_root: str | None) -> tuple[str | None, str]:
    """(想要的仓, 说明)。仓库只从项目配置实例的 issue 段读，读不到就 None。"""
    for i, arg in enumerate(argv):
        if arg in ("--repo", "-R") and i + 1 < len(argv):
            return argv[i + 1], "命令自带"
        if arg.startswith("--repo=") or arg.startswith("-R="):
            return arg.split("=", 1)[1], "命令自带"
    if not repo_root:
        return None, "实例读不到"
    try:
        with open(os.path.join(repo_root, INSTANCE_REL), encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError):
        return None, "实例读不到"
    issue = cfg.get("issue") or {}
    value = issue.get("repo") or issue.get("pr_repo")
    return (str(value), "实例") if isinstance(value, str) and value.strip() else (None, "实例没有 issue.repo")


def main() -> int:
    ap = argparse.ArgumentParser(description="开票归属守卫（缺 --repo 即拒）")
    ap.add_argument("--command", default=None, help="宿主给的命令文本")
    ap.add_argument("--repo", dest="repo_root", default=None, help="项目仓根（缺省按 KAI_REPO_ROOT / git 根）")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return _self_test()

    command = a.command or _stdin_command()
    if not command:
        print("放行：没有命令文本可判（不拦空输入）")
        return 0
    if not CREATE_RE.search(command) or HELP_RE.search(command):
        return 0

    repo_root = a.repo_root or os.environ.get("KAI_REPO_ROOT") or _git_root()

    if REPO_FLAG_RE.search(command):
        want, how = desired_repo(command.split(), repo_root)
        print(f"放行：命令已带 --repo（{how}）" + (f"，目标仓 {want}" if want else ""))
        return 0

    want, how = desired_repo([], repo_root)
    if want:
        print(f"拒绝：gh issue/pr create 必须显式带 --repo {want}（从{how}读）。", file=sys.stderr)
        print(f"       改成：gh issue create --repo {want} ...；在项目仓里跑 gh 会按 cwd 落仓，不得靠推断。",
              file=sys.stderr)
        return 2
    print("拒绝：gh issue/pr create 必须显式带 --repo <owner/name>；项目配置实例里也没有 issue.repo。",
          file=sys.stderr)
    print("       先补实例（见配置模板 issue 段），或这次直接写全 --repo <owner/name>。", file=sys.stderr)
    return 2


def _stdin_command() -> str | None:
    """宿主钩子形状：stdin 一段 JSON，取 `tool_input.command`（Claude Code / Qoder 同形状）。"""
    if sys.stdin is None or sys.stdin.isatty():
        return None
    try:
        raw = sys.stdin.read()
    except (OSError, UnicodeDecodeError):
        return None
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return raw.strip()
    if isinstance(data, dict):
        tool_input = data.get("tool_input") or data.get("toolInput") or {}
        if isinstance(tool_input, dict) and isinstance(tool_input.get("command"), str):
            return tool_input["command"]
    return None


def _git_root() -> str | None:
    try:
        import subprocess
        p = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=15)
    except (OSError, Exception):
        return None
    top = (p.stdout or "").strip()
    return os.path.abspath(top) if p.returncode == 0 and top else None


def _self_test() -> int:
    cases = [
        ("gh issue create --title x --body y", 2),
        ("gh issue create --repo a/b --title x", 0),
        ("gh pr create -R a/b --title x", 0),
        ("gh issue create --repo=a/b --title x", 0),
        ("gh issue list --state open", 0),
        ("gh issue create --help", 0),
        ("echo gh issue create", 2),
        ("git status", 0),
    ]
    fails = []
    for cmd, want in cases:
        rc = 0
        if CREATE_RE.search(cmd) and not HELP_RE.search(cmd):
            rc = 0 if REPO_FLAG_RE.search(cmd) else 2
        if rc != want:
            fails.append(f"{cmd!r} 期望 rc={want} 实得 rc={rc}")
    print("SELFTEST", "ok" if not fails else "FAIL")
    for f in fails:
        print("  -", f)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
