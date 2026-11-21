#!/usr/bin/env python3
"""CC 桌面 solo 投影冒烟（只读）。

检查一个 Claude Code 桌面项目落点是否与框架正本一致：
  1. 项目指令入口 CLAUDE.md 存在且非空；
  2. .claude/agents 有 7 份可派发契约 ＋ _primary.md；
  3. 契约正文没有 `## personality` 标题（契约＝无人格投影）；
  4. 每份契约头部 `kai-role` 指纹与 `render-roles.py contracts` 现渲逐字一致。

约束：只读文件、只起本地渲染器子进程；不调用模型、不发网络请求、不写盘。

用法：
  python scripts/smoke-solo-projection.py --json
  python scripts/smoke-solo-projection.py --root <项目目录> --json
未给 --root 时按顺序找：仓库上一级 → git 公共目录上一级的上一级 → 当前目录 → 当前目录上一级，
取第一个含 .claude/agents 的目录。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

try:  # Windows 控制台中文输出
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROLES = ("researcher", "architect", "engineer", "designer", "writer", "reviewer")
PRIMARY = "_primary.md"
FP_RX = re.compile(r"<!--\s*(kai-role\s+[^>]*?)\s*-->")
PERSONALITY_RX = re.compile(r"^\s*##\s+personality\b", re.IGNORECASE | re.MULTILINE)


def find_framework_root() -> str:
    """脚本所在仓根（scripts/ 的上一级）。"""
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def git_common_parent(framework_root: str) -> str | None:
    """worktree 场景：git 公共目录 → 仓根 → 上一级（工作区）。"""
    try:
        out = subprocess.run(
            ["git", "-C", framework_root, "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    common = out.stdout.strip()
    if not os.path.isabs(common):
        common = os.path.abspath(os.path.join(framework_root, common))
    return os.path.dirname(os.path.dirname(common))


def default_projection_root(framework_root: str) -> str | None:
    candidates = [
        os.path.dirname(framework_root),
        git_common_parent(framework_root),
        os.getcwd(),
        os.path.dirname(os.getcwd()),
    ]
    for cand in candidates:
        if cand and os.path.isdir(os.path.join(cand, ".claude", "agents")):
            return os.path.abspath(cand)
    return None


def fresh_fingerprint(framework_root: str, role: str) -> tuple[str | None, str | None]:
    """现渲该角色契约，取 kai-role 指纹。返回 (fingerprint, error)。"""
    renderer = os.path.join(framework_root, "scripts", "render-roles.py")
    if not os.path.isfile(renderer):
        return None, f"渲染器不存在：{renderer}"
    try:
        out = subprocess.run(
            [sys.executable, renderer, "contracts", "--role", role, "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60, cwd=framework_root,
        )
    except Exception as exc:  # 子进程本身失败
        return None, f"渲染器调用失败：{exc}"
    if out.returncode != 0:
        return None, f"渲染器退出 {out.returncode}：{(out.stderr or out.stdout).strip()[:200]}"
    try:
        data = json.loads(out.stdout)
    except Exception:
        return None, "渲染器输出不是 JSON"
    prompt = data.get("prompt") or ""
    match = FP_RX.search(prompt)
    if not match:
        return None, "现渲契约里没有 kai-role 指纹"
    return match.group(1).strip(), None


def projection_fingerprint(path: str) -> tuple[str | None, str | None]:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError as exc:
        return None, f"读不到：{exc}"
    match = FP_RX.search(text)
    if not match:
        return None, "文件里没有 kai-role 指纹"
    return match.group(1).strip(), None


def check(root: str, framework_root: str) -> dict:
    checks: list[dict] = []

    def add(check_id: str, ok: bool, detail: str) -> None:
        checks.append({"id": check_id, "ok": bool(ok), "detail": detail})

    # 1. CLAUDE.md 入口
    entry = os.path.join(root, "CLAUDE.md")
    if os.path.isfile(entry) and os.path.getsize(entry) > 0:
        add("entry", True, "CLAUDE.md 存在且非空")
    else:
        add("entry", False, "缺 CLAUDE.md 或为空")

    # 2. 目录与 8 份文件（7 契约 + _primary）
    agents_dir = os.path.join(root, ".claude", "agents")
    if not os.path.isdir(agents_dir):
        add("agents-dir", False, "缺 .claude/agents")
        return {"root": root, "framework_root": framework_root, "checks": checks}
    missing = [role for role in ROLES if not os.path.isfile(os.path.join(agents_dir, f"{role}.md"))]
    add("agents-contracts", not missing,
        "7 份契约齐全" if not missing else f"缺契约：{', '.join(missing)}")
    has_primary = os.path.isfile(os.path.join(agents_dir, PRIMARY))
    add("agents-primary", has_primary, "_primary.md 存在" if has_primary else "缺 _primary.md")

    # 3. 契约无人格标题
    with_personality = []
    for role in ROLES:
        path = os.path.join(agents_dir, f"{role}.md")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            with_personality.append(f"{role}(读失败)")
            continue
        if PERSONALITY_RX.search(text):
            with_personality.append(role)
    add("no-personality", not with_personality,
        "契约无 ## personality" if not with_personality
        else f"出现 ## personality：{', '.join(with_personality)}")

    # 4. 指纹与现渲一致
    mismatches = []
    unreadable = []
    for role in ROLES:
        path = os.path.join(agents_dir, f"{role}.md")
        if not os.path.isfile(path):
            continue
        have, err = projection_fingerprint(path)
        if err:
            unreadable.append(f"{role}: {err}")
            continue
        want, render_err = fresh_fingerprint(framework_root, role)
        if render_err:
            unreadable.append(f"{role}: {render_err}")
            continue
        if have != want:
            mismatches.append(role)
    if unreadable:
        add("fingerprints", False, "指纹读不到：" + "；".join(unreadable))
    elif mismatches:
        add("fingerprints", False, f"指纹与现渲不一致：{', '.join(mismatches)}")
    else:
        add("fingerprints", True, "7 份契约指纹与现渲逐字一致")

    return {"root": root, "framework_root": framework_root, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description="CC 桌面 solo 投影冒烟（只读）")
    parser.add_argument("--root", default=None, help="投影项目根（默认自动定位）")
    parser.add_argument("--json", action="store_true", help="机器可读输出")
    args = parser.parse_args()

    framework_root = find_framework_root()
    root = os.path.abspath(args.root) if args.root else default_projection_root(framework_root)

    if not root:
        payload = {
            "ok": False,
            "error": "找不到含 .claude/agents 的投影根；用 --root 指定",
            "framework_root": framework_root,
            "checks": [],
        }
    else:
        result = check(root, framework_root)
        checks = result["checks"]
        failed = [c for c in checks if not c["ok"]]
        payload = {
            "ok": not failed,
            "root": result["root"],
            "framework_root": result["framework_root"],
            "checks": checks,
            "summary": {
                "passed": sum(1 for c in checks if c["ok"]),
                "failed": len(failed),
                "total": len(checks),
            },
        }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"投影根：{payload.get('root') or '(未定位)'}")
        for item in payload.get("checks", []):
            mark = "PASS" if item["ok"] else "FAIL"
            print(f"[{mark}] {item['id']}: {item['detail']}")
        if payload.get("error"):
            print(f"[FAIL] {payload['error']}")
        summary = payload.get("summary")
        if summary:
            print(f"总结：{summary['passed']}/{summary['total']} 通过，{summary['failed']} 失败")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
