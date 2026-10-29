#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""唤醒门卫：定时器拉起塔台会话之前的零 token 判据。

解决的问题：定时器每次到点都拉起一整轮会话（加载塔台技能全文）、上一轮还在跑也照拉、
没货也照跑。门卫在**模型会话之外**先跑，只有真有活才放行。

用法（定时器 prompt 的薄壳第一句）：
  python <本技能目录>/scripts/wake-gate.py [--repo <仓根>] [--json]

判据顺序（任一成立即放行，其余跳过；可执行正本＝本脚本，技能正文与定时器 prompt 不复述；
裁决理由见框架仓决策记录）：
  1. 令牌：他人持牌且心跳在「本轮上限」内 ⇒ 上一轮大概率还在跑 ⇒ SKIP（治「下一个塔台白跑」）；
     心跳超过本轮上限 ⇒ 死牌，不阻塞（塔台进去后按 $tower-token acquire 接管）。
  2. 待发货：`ship-queue.py peek` 的 pending／hotfix／invalid 任一非空 ⇒ WAKE。
  3. 日表：**启用道**的正常日表任一缺失或行数低于下限 ⇒ WAKE（没人补日表，机长会饿）。
     启用道从 `lane_spec.py` 读（显式参数 > 状态文件 > 默认 `1+2`）；停用道不参与判定。
  4. 探测失败（ship-queue rc=3）⇒ WAKE（失败不等于零票，保守放行）。

本轮上限 = `tower_cron.interval_min + 5` 分钟（走满一个轮巡周期还没收工，算还在飞）。

退出码：0＝WAKE（放行，读技能跑一轮）；10＝SKIP（只回一行就结束，不读任何技能）；
2＝缺件（按三格打印，不猜路径）。
`--json` 输出 `{"wake": bool, "reason": "...", "detail": {...}}`。
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

INSTANCE_REL = os.path.join(".ai", "kai-mode.project.json")
TOKEN_NAME = "tower-token.json"
DEFAULT_INTERVAL_MIN = 60
ROUND_SLACK_MIN = 5
MIN_ROWS = 5  # 协议 §一 持有帽下限；区间数值正本在协议，本处只做「表是否见底」的粗判
TICKET_ROW_RE = re.compile(r"^\|\s*[^|]*\|\s*(\d+)\s*\|")

HERE = os.path.dirname(os.path.abspath(__file__))
SHIP_QUEUE = os.path.join(HERE, "ship-queue.py")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import lane_spec  # noqa: E402  车道代号的唯一语法与优先级


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
    """返回 (cfg, state_dir_abs) 或 (None, 错误码)。"""
    if not repo or not os.path.isdir(repo):
        return None, missing("项目仓根（--repo / KAI_REPO_ROOT / git 根三条都没解析出）",
                             "定时器门卫（不知道去哪读令牌与日表）",
                             "在项目仓内跑，或显式 --repo <仓根>")
    inst = os.path.join(repo, INSTANCE_REL)
    if not os.path.isfile(inst):
        return None, missing(f"项目配置实例 {INSTANCE_REL}",
                             "定时器门卫（令牌、日表、轮巡周期都从它读）",
                             "在框架仓跑 scripts/init-project.py --repo <本仓> 生成实例")
    try:
        with open(inst, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as exc:
        return None, missing(f"读不出的项目配置实例（{exc}）", "定时器门卫", "修好该 JSON 或重新生成实例")
    state_dir = ((cfg.get("paths") or {}).get("state_dir") or "").strip()
    if not state_dir:
        return None, missing("实例里的 paths.state_dir（值为空）",
                             "定时器门卫（令牌要落在这个框架自有命名空间里）",
                             "把 paths.state_dir 填成仓内相对路径，例如 .git/<框架名>")
    return cfg, os.path.join(repo, *state_dir.split("/"))


# ---------- 1. 令牌 ----------

def check_token(state_dir: str, interval_min: int) -> dict:
    path = os.path.join(state_dir, TOKEN_NAME)
    try:
        with open(path, encoding="utf-8") as f:
            token = json.load(f)
    except (OSError, ValueError):
        return {"state": "free"}
    if not isinstance(token, dict) or not token.get("holder"):
        return {"state": "free"}
    raw = token.get("heartbeat_at")
    try:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(raw)).total_seconds() / 60.0
    except (TypeError, ValueError):
        return {"state": "free"}
    limit = interval_min + ROUND_SLACK_MIN
    return {"state": "running" if age <= limit else "stale",
            "holder": token.get("holder"), "age_min": round(age, 1),
            "limit_min": limit}


# ---------- 2. 待发货 ----------

def check_queue(repo: str) -> dict:
    """委托 ship-queue.py peek（零 token），不在这里重写一遍判据。"""
    if not os.path.isfile(SHIP_QUEUE):
        return {"state": "error", "detail": f"ship-queue.py 不在 {HERE}"}
    try:
        p = subprocess.run([sys.executable, SHIP_QUEUE, "peek", "--repo", repo, "--json"],
                           capture_output=True, text=True, timeout=180,
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        return {"state": "error", "detail": str(exc)}
    if p.returncode == 2:
        return {"state": "missing", "detail": (p.stdout or "").strip()}
    if p.returncode != 0:
        return {"state": "error", "detail": (p.stdout or p.stderr or "").strip()[:300]}
    try:
        data = json.loads(p.stdout or "{}")
    except ValueError:
        return {"state": "error", "detail": "ship-queue 的 --json 输出读不出"}
    pending = data.get("pending") or {}
    hotfix = data.get("hotfix") or []
    invalid = data.get("invalid") or []
    live = [k for k, v in pending.items() if not (v or {}).get("held")]
    return {"state": "has_work" if (live or hotfix or invalid) else "empty",
            "pending": len(pending), "ready": len(live),
            "hotfix": len(hotfix), "invalid": len(invalid)}


# ---------- 3. 日表 ----------

def check_day_tables(repo: str, cfg: dict, state_dir: str) -> dict:
    paths = cfg.get("paths") or {}
    tables = (paths.get("day_tables_dir") or "").strip()
    if not tables:
        return {"state": "missing", "detail": "实例没有 paths.day_tables_dir"}
    base = os.path.join(repo, *tables.split("/"))
    pattern = (paths.get("day_table_pattern") or "YYYY-MM-DD-{lane}.md").strip()
    try:
        resolved = lane_spec.resolve(cfg, state_dir)
    except ValueError as exc:
        return {"state": "error", "detail": f"车道代号读不出：{exc}"}
    lanes = resolved["normal"]
    today = datetime.now().strftime("%Y-%m-%d")
    short, absent = [], []
    for lane in lanes:
        name = pattern.replace("{lane}", lane).replace("YYYY-MM-DD", today)
        path = os.path.join(base, name)
        if not os.path.isfile(path):
            # 当天没有就看最近一份，判断「表见底」而不是「还没开表」
            found = sorted(glob.glob(os.path.join(base, pattern.replace("{lane}", lane)
                                                  .replace("YYYY-MM-DD", "*"))))
            if not found:
                absent.append(lane)
                continue
            path = found[-1]
        try:
            with open(path, encoding="utf-8") as f:
                rows = sum(1 for line in f if TICKET_ROW_RE.match(line))
        except OSError:
            absent.append(lane)
            continue
        if rows < MIN_ROWS:
            short.append(f"{lane}={rows}")
    state = "short" if (short or absent) else "full"
    return {"state": state, "short": short, "absent": absent, "min_rows": MIN_ROWS,
            "spec": resolved["spec"], "lanes": lanes}


# ---------- 汇总 ----------

def decide(repo: str, cfg: dict, state_dir: str) -> dict:
    interval = (cfg.get("tower_cron") or {}).get("interval_min") or DEFAULT_INTERVAL_MIN
    try:
        interval = int(interval)
    except (TypeError, ValueError):
        interval = DEFAULT_INTERVAL_MIN

    token = check_token(state_dir, interval)
    if token["state"] == "running":
        return {"wake": False,
                "reason": f"held 上一轮还在跑（{token['holder']} 心跳 {token['age_min']} 分钟，"
                          f"本轮上限 {token['limit_min']}）",
                "detail": {"token": token}}

    queue = check_queue(repo)
    if queue["state"] == "has_work":
        return {"wake": True,
                "reason": f"pending={queue['ready']} hotfix={queue['hotfix']} invalid={queue['invalid']}",
                "detail": {"token": token, "queue": queue}}

    tables = check_day_tables(repo, cfg, state_dir)
    if tables["state"] == "error":
        return {"wake": True, "reason": f"日表判据失败（{tables.get('detail', '')}）",
                "detail": {"token": token, "queue": queue, "day_tables": tables}}
    if tables["state"] == "short":
        bits = []
        if tables["short"]:
            bits.append("低于下限 " + "、".join(tables["short"]))
        if tables["absent"]:
            bits.append("缺表 " + "、".join(tables["absent"]))
        return {"wake": True, "reason": f"日表（启用道 {tables.get('spec', '?')}）：" + "；".join(bits),
                "detail": {"token": token, "queue": queue, "day_tables": tables}}

    if queue["state"] in ("error", "missing"):
        return {"wake": True, "reason": f"待发货探测失败（{queue.get('detail', '')}）",
                "detail": {"token": token, "queue": queue, "day_tables": tables}}

    return {"wake": False, "reason": "零待发货且日表已满",
            "detail": {"token": token, "queue": queue, "day_tables": tables}}


def main() -> int:
    ap = argparse.ArgumentParser(description="定时器唤醒塔台前的零 token 门卫")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    repo = resolve_repo(a.repo)
    cfg, state_dir = load_context(repo)
    if cfg is None:
        return state_dir

    try:
        verdict = decide(repo, cfg, state_dir)
    except Exception as exc:  # 门卫自己坏了也不许静默吞掉一轮
        print(f"WAKE reason=gate-error（{exc}）")
        print("门卫出错按放行处理：宁可跑一轮，不可漏活。")
        return 0

    if a.json:
        print(json.dumps(verdict, ensure_ascii=False, indent=2))
    elif verdict["wake"]:
        print(f"WAKE reason={verdict['reason']}")
    else:
        print(f"SKIP reason={verdict['reason']}")
        print("本轮到此为止：不读技能、不扫评论、不排班。")
    return 0 if verdict["wake"] else 10


if __name__ == "__main__":
    raise SystemExit(main())
