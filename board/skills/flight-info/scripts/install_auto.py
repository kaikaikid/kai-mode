#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键接上「活的航班信息板」自动更新（Windows；零 token、无黑窗）。

把三件事按依赖顺序收齐：
  ① git 钩子（post-commit / post-merge）：写进仓的 *有效* hooksPath——
     默认 .git/hooks；本仓设了 core.hooksPath＝.githooks，就写 .githooks。
     钩子只往 .git/flight-info-dirty 写时间戳，不同步刷、不阻塞 git
     （退出码恒 0，fail-open）。
  ② 定时任务（schtasks，仅登录时运行、隐藏窗口）：每 `interval` 分钟调
     refresh_if_dirty.py。用**当前用户上下文**、不存密码、不讨凭证 = 无 token；
     代价＝登出/关机时不刷。git 钩子打的脏标记由它消费。
  ③ 人工入口 refresh.vbs：复制到板目录，页面「刷新」按钮指向它（无黑窗重建）。

为什么是这套（不是别的）：
  - 不用 (cmd … &) 丢后台：钩子一退出子进程就被回收，板根本没刷。
  - 不硬刷在钩子里：联网板刷一次几十秒，会卡死 commit。
  - 不用「无论是否登录都运行」：那要存密码 = token，用户明确不要。

    python scripts/install_auto.py --repo-root <仓根> --config <board.config.json>  # 干跑
    python scripts/install_auto.py --repo-root <仓根> --config <board.config.json> --apply
    python scripts/install_auto.py --repo-root <仓根> --config <board.config.json> --remove --apply

退出码：0 成功；2 参数/环境错；3 写不出或钩子非本工具生成。
"""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SKILL_ROOT not in sys.path:
    sys.path.insert(0, SKILL_ROOT)

from flightinfo import config  # noqa: E402

MARKER = "flight-info-dirty"
SIGN = "# managed by kai-mode skill: flight-info"
SCHTASK_PREFIX = "flight-info-"
HOOKS = ("post-commit", "post-merge")

# 现有 .githooks/post-commit / post-merge 是退役残 stub（指向已删的「技能/航班信息」
# 和 .design/航班信息）。本工具会识别并覆盖它们；非本工具生成则拒绝。
STUB_SIGN = ("kai-mode 板工坊", "skills/航班信息", ".design/航班信息",
             "实现委托给 post-commit（同一套 fail-open 规矩）")

HOOK = """#!/bin/sh
{sign}
# 只打脏标记，不同步刷新，退出码恒 0 —— 绝不阻塞 commit / merge
root="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
printf '%s\\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$root/.git/{marker}" 2>/dev/null
exit 0
""".format(sign=SIGN, marker=MARKER)


def active_hooks_dir(repo_root: str) -> str:
    """→ 仓当前生效的 hooks 目录（读 core.hooksPath，缺省 .git/hooks）。"""
    try:
        out = subprocess.run(["git", "-C", repo_root, "config", "--get", "core.hooksPath"],
                             capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        out = subprocess.CompletedProcess([], 0, "", "")
    hp = (out.stdout or "").strip()
    if hp:
        return hp if os.path.isabs(hp) else os.path.join(repo_root, hp)
    return os.path.join(repo_root, ".git", "hooks")


def _is_stub(text: str) -> bool:
    return any(s in text for s in STUB_SIGN)


def install_hooks(repo_root: str, hooks_dir: str, apply: bool) -> int:
    rc = 0
    for name in HOOKS:
        p = os.path.join(hooks_dir, name)
        exists = os.path.isfile(p)
        mine = stub = False
        if exists:
            try:
                text = open(p, encoding="utf-8", errors="replace").read()
                mine = SIGN in text
                stub = _is_stub(text)
            except OSError:
                pass
        if mine or stub or not exists:
            if apply:
                os.makedirs(hooks_dir, exist_ok=True)
                with open(p, "w", encoding="utf-8", newline="\n") as f:
                    f.write(HOOK)
                os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
                print(f"  {name}: 已装到 {hooks_dir}")
            else:
                print(f"  {name}: [干跑] 会写入 {hooks_dir}")
        else:
            print(f"  {name}: 已存在且非本工具生成，拒绝覆盖（请人工处理）", file=sys.stderr)
            rc = 3
    if apply:
        mp = os.path.join(repo_root, ".git", MARKER)
        if not os.path.exists(mp):
            open(mp, "w", encoding="utf-8", newline="\n").close()
        print(f"  脏标记：.git/{MARKER}（内容空＝无脏）")
    return rc


def _write_task_bat(board_dir: str, repo_root: str, cfg_path: str, apply: bool) -> str | None:
    """写一个 start /min 隐藏窗口的刷新 bat，返回其路径（无 apply 时返回预定路径）。"""
    py = os.path.join(SKILL_ROOT, "scripts", "refresh_if_dirty.py")
    bat = os.path.join(board_dir, "refresh_task.bat")
    body = (
        "@echo off\n"
        f'start "" /min python "{py}" --repo-root "{repo_root}" '
        f'--config "{cfg_path}" --quiet\n'
    )
    if apply:
        os.makedirs(board_dir, exist_ok=True)
        with open(bat, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(body)
        print(f"  定时任务入口 bat：{bat}（start /min 隐藏窗口）")
    else:
        print(f"  定时任务入口 bat：[干跑] 会写 {bat}")
    return bat


def install_task(repo_root: str, cfg_path: str, board_name: str, interval: int,
                 apply: bool, bat_path: str | None = None) -> int:
    task = SCHTASK_PREFIX + board_name
    # 动作指向上面那个 .bat（start /min 隐藏窗口），bat 里调 python 跑刷新——
    # schtasks 的 /TR 不用嵌引号，窗口必然隐藏，零黑窗。
    # 无 token：/ru 用当前用户、/rp 不写（schtasks 默认 interactive，不存密码）；
    # 代价＝登出/关机时不刷。
    action = bat_path or ""
    create = [
        "schtasks", "/Create", "/TN", task, "/TR", f'"{action}"',
        "/SC", "MINUTE", "/MO", str(interval),
        "/RU", os.environ.get("USERNAME", ""),       # 当前用户，不写 /RP ⇒ 无密码/无 token
        "/RL", "LIMITED",
    ]
    if apply:
        subprocess.run(["schtasks", "/Delete", "/TN", task, "/F"],
                       capture_output=True, text=True, check=False)
        cr = subprocess.run(create, capture_output=True, text=True, check=False)
        if cr.returncode != 0:
            # 本机安全策略可能禁止创建任务（实测 Windows「Access is denied」）。
            # 这不是致命错：钩子＋手动刷新（refresh.vbs / 页面按钮）仍能更新板，
            # 只是少了「无人操作时的周期刷新」。降级为告警，不阻断整次安装。
            print(f"  ⚠ 定时任务 {task} 创建被拒（rc={cr.returncode}）："
                  f"{(cr.stderr or cr.stdout).strip()[:160]}。"
                  f"钩子与手动刷新仍可用；要周期刷新请在能建任务的环境重跑本命令。",
                  file=sys.stderr)
            return 0
        print(f"  定时任务 {task}：每 {interval} 分钟（仅登录时、隐藏窗口、无 token）")
    else:
        print(f"  定时任务 {task}：[干跑] 会创建（每 {interval} 分钟，仅登录时，无 token）")
    return 0


def install_vbs(board_dir: str, apply: bool) -> int:
    src = os.path.join(SKILL_ROOT, "scripts", "refresh.vbs")
    dst = os.path.join(board_dir, "refresh.vbs")
    if not os.path.isfile(src):
        print(f"  缺 refresh.vbs 源：{src}", file=sys.stderr)
        return 3
    if apply:
        try:
            shutil.copyfile(src, dst)
            print(f"  人工入口：{dst}（双击或页面按钮触发无黑窗重建）")
        except OSError as e:
            print(f"  复制 refresh.vbs 失败：{e}", file=sys.stderr)
            return 3
    else:
        print(f"  人工入口：[干跑] 会复制 {dst}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="接上航班信息板自动更新（钩子＋定时任务＋人工入口）")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--config", required=True, help="板配置 board.config.json")
    ap.add_argument("--interval", type=int, default=15, help="定时任务间隔（分钟，默认 15）")
    ap.add_argument("--apply", action="store_true", help="真正落盘（默认干跑）")
    ap.add_argument("--remove", action="store_true", help="卸载（钩子停用、定时任务删除；vbs 保留）")
    a = ap.parse_args()

    repo_root = os.path.abspath(a.repo_root)
    if not os.path.isdir(repo_root) or not os.path.isdir(os.path.join(repo_root, ".git")):
        print(f"不是 git 仓：{repo_root}", file=sys.stderr)
        return 2
    if not os.path.isfile(a.config):
        print(f"板配置不存在：{a.config}", file=sys.stderr)
        return 2
    cfg = config.load(a.config)
    problems = config.validate(cfg)
    if problems:
        print("板配置不合规：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2
    board_dir = config.board_dir(repo_root, cfg)
    task_name = cfg.get("name") or "flight"
    hooks_dir = active_hooks_dir(repo_root)

    print(f"生效 hooks 目录：{hooks_dir}")
    print(f"板目录：{board_dir}")
    rc = 0
    rc |= install_hooks(repo_root, hooks_dir, a.apply)
    if not a.remove:
        bat = _write_task_bat(board_dir, repo_root, os.path.abspath(a.config), a.apply)
        rc |= install_task(repo_root, os.path.abspath(a.config), task_name, a.interval, a.apply, bat)
        rc |= install_vbs(board_dir, a.apply)
    else:
        t = SCHTASK_PREFIX + task_name
        if a.apply:
            r = subprocess.run(["schtasks", "/Delete", "/TN", t, "/F"],
                               capture_output=True, text=True, check=False)
            print(f"  定时任务 {t}：{'已删除' if r.returncode == 0 else '删除失败'}")
        else:
            print(f"  定时任务 {t}：[干跑] 会删除")
    if not a.apply:
        print("\n干跑结束；要落盘加 --apply")
    return rc


if __name__ == "__main__":
    sys.exit(main())
