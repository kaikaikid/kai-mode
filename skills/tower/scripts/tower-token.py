#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""塔台岗位互斥锁：抢牌／续约／释放／问谁在飞。

判据住这里，不住技能正文：落点＝项目配置实例 `paths.state_dir` 下的 `tower-token.json`；
过期阈值＝`tower_cron.interval_min × 2 + 5` 分钟（错过两个轮巡周期算死牌）；写入原子（临时文件 + os.replace）。
本锁只回答「这一轮谁是塔台」；票的领取仍只靠日表，不在锁里登记。

用法（<本技能目录> ＝ 装到宿主后的本技能根）：
  python <本技能目录>/scripts/tower-token.py acquire  --holder <会话或任务名> [--repo <仓根>]
  python <本技能目录>/scripts/tower-token.py heartbeat --holder <同上> [--repo <仓根>]
  python <本技能目录>/scripts/tower-token.py release  --holder <同上> [--repo <仓根>]
  python <本技能目录>/scripts/tower-token.py who [--repo <仓根>]

退出码：0 成；1 抢不到牌／不是持牌人（退位，不写任何东西）；2 缺件（仓根、实例或 state_dir 读不到）。
缺件一律按三格打印：缺什么／谁需要／怎么补，不猜路径。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

INSTANCE_REL = os.path.join(".ai", "kai-mode.project.json")
TOKEN_NAME = "tower-token.json"
DEFAULT_INTERVAL_MIN = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def missing(what: str, who: str, how: str) -> int:
    print(f"[缺件] 缺什么：{what}")
    print(f"        谁需要：{who}")
    print(f"        怎么补：{how}")
    return 2


def resolve_repo(cli_value: str | None) -> str | None:
    if cli_value:
        return os.path.abspath(cli_value)
    env = os.environ.get("KAI_REPO_ROOT")
    if env:
        return os.path.abspath(env)
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    top = out.stdout.strip()
    return os.path.abspath(top) if out.returncode == 0 and top else None


def load_context(repo: str | None):
    """返回 (token 路径, 过期分钟数) 或 (None, 错误码)。逐层如实报缺件。"""
    if not repo or not os.path.isdir(repo):
        return None, missing("项目仓根（--repo / KAI_REPO_ROOT / git 根三条都没解析出）",
                             "塔台（抢牌要知道锁住哪一棵树）",
                             "在项目仓内跑，或显式 --repo <仓根>")
    inst = os.path.join(repo, INSTANCE_REL)
    if not os.path.isfile(inst):
        return None, missing(f"项目配置实例 {INSTANCE_REL}",
                             "塔台（令牌落点与轮巡周期都从它读）",
                             "在框架仓跑 scripts/init-project.py --repo <本仓> 生成实例")
    try:
        with open(inst, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as exc:
        return None, missing(f"读不出的项目配置实例（{exc}）", "塔台", "修好该 JSON 或重新生成实例")
    state_dir = ((cfg.get("paths") or {}).get("state_dir") or "").strip()
    if not state_dir:
        return None, missing("实例里的 paths.state_dir（值为空）",
                             "塔台（令牌要落在这个框架自有命名空间里）",
                             "把 paths.state_dir 填成仓内相对路径，例如 .git/<框架名>")
    interval = (cfg.get("tower_cron") or {}).get("interval_min") or DEFAULT_INTERVAL_MIN
    try:
        interval = int(interval)
    except (TypeError, ValueError):
        interval = DEFAULT_INTERVAL_MIN
    return os.path.join(repo, *state_dir.split("/"), TOKEN_NAME), interval * 2 + 5


def read_token(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("holder") else None


def age_minutes(token: dict, key: str) -> float | None:
    raw = token.get(key)
    if not isinstance(raw, str):
        return None
    try:
        return (_now() - _parse(raw)).total_seconds() / 60.0
    except ValueError:
        return None


def write_token(path: str, token: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tower-token-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            json.dump(token, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def describe(token: dict, ttl_min: int) -> str:
    hb = age_minutes(token, "heartbeat_at")
    state = "过期" if hb is None or hb > ttl_min else "在飞"
    hb_txt = f"{hb:.0f} 分钟前" if hb is not None else "无心跳"
    return f"持牌人={token.get('holder')} 状态={state} 心跳={hb_txt} 取得={token.get('acquired_at')}"


def cmd_acquire(args, path: str, ttl_min: int) -> int:
    token = read_token(path)
    if token and token.get("holder") != args.holder:
        hb = age_minutes(token, "heartbeat_at")
        if hb is not None and hb <= ttl_min:
            print(f"HELD {describe(token, ttl_min)}")
            print("本轮退位：不读票、不排班、不发货，只播报这一行即收。")
            return 1
        print(f"TAKEOVER 接管过期牌：{describe(token, ttl_min)}（阈值 {ttl_min} 分钟）")
        print("在当日日报留一行「谁接谁的班」。")
    fresh = {"holder": args.holder,
             "acquired_at": _stamp(_now()),
             "heartbeat_at": _stamp(_now()),
             "ttl_min": ttl_min}
    existed = token is not None and token.get("holder") == args.holder
    write_token(path, fresh)
    print(f"{'REACQUIRED' if existed else 'ACQUIRED'} holder={args.holder} ttl_min={ttl_min}")
    return 0


def cmd_heartbeat(args, path: str, ttl_min: int) -> int:
    token = read_token(path)
    if not token or token.get("holder") != args.holder:
        print(f"NOT_HOLDER {describe(token, ttl_min) if token else '无令牌'}")
        print("不是持牌人就不续约；要上岗先 acquire。")
        return 1
    token["heartbeat_at"] = _stamp(_now())
    token["ttl_min"] = ttl_min
    write_token(path, token)
    print(f"HEARTBEAT holder={args.holder} at={token['heartbeat_at']}")
    return 0


def cmd_release(args, path: str, ttl_min: int) -> int:
    token = read_token(path)
    if not token:
        print("RELEASED 无令牌可释放")
        return 0
    if token.get("holder") != args.holder:
        print(f"NOT_HOLDER {describe(token, ttl_min)}")
        print("不删别人的牌；确需强制接管等它心跳过期，或由持牌人自己 release。")
        return 1
    os.remove(path)
    print(f"RELEASED holder={args.holder}")
    return 0


def cmd_who(args, path: str, ttl_min: int) -> int:
    token = read_token(path)
    if not token:
        print(f"FREE 无令牌（阈值 {ttl_min} 分钟）——谁先 acquire 谁是塔台")
        return 0
    print(describe(token, ttl_min))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="塔台岗位互斥锁")
    ap.add_argument("action", choices=("acquire", "heartbeat", "release", "who"))
    ap.add_argument("--holder", default=None, help="持牌人标识（会话名或定时任务名）")
    ap.add_argument("--repo", default=None, help="项目仓根（缺省按 KAI_REPO_ROOT → git 根解析）")
    a = ap.parse_args()
    if a.action != "who" and not a.holder:
        print("[缺件] 缺什么：--holder（持牌人标识）／谁需要：塔台／怎么补：给一个能区分会话的名字")
        return 2
    path, ttl = load_context(a.repo)
    if path is None:
        return ttl
    handlers = {"acquire": cmd_acquire, "heartbeat": cmd_heartbeat, "release": cmd_release, "who": cmd_who}
    return handlers[a.action](a, path, ttl)


if __name__ == "__main__":
    raise SystemExit(main())
