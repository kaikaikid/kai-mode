#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""车道代号：塔台排班的唯一开关。

代号：0=王牌(ace) 1=主机长(main) 2=副机长(deputy) 3=二副(second)
写法：`1+2`（默认）、`all`（＝1+2+3）、`1+2+3`；分隔符只认 `+`，全角数字与 `＋` 自动纠正。
落点：`<仓根>/<paths.state_dir>/tower-lanes.json`
优先级：本轮显式参数 > 状态文件 > 默认 `1+2`

塔台只排 1/2/3；0 只进集合，不产生日表（王牌日表由王牌写）。
停用道不建表、不补行；表里已有行不删，跑空即止。

用法：
  python lane_spec.py show [--repo R] [--json]
  python lane_spec.py set 1+2+3 [--repo R] [--source command|timer]
  python lane_spec.py parse "1+2"
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CODE_TO_LANE = {"0": "ace", "1": "main", "2": "deputy", "3": "second"}
LANE_TO_CODE = {lane: code for code, lane in CODE_TO_LANE.items()}
NORMAL_LANES = ("main", "deputy", "second")
ALL_LANES = ("ace", "main", "deputy", "second")
DEFAULT_SPEC = "1+2"
SETTING_NAME = "tower-lanes.json"
SETTING_SCHEMA = "kai-mode-tower-lanes/1"
INSTANCE_REL = os.path.join(".ai", "kai-mode.project.json")
# 中文输入法容易把代号打成全角：数字、加号、空格一起归一，别让一个全角字符废掉整条命令。
FULLWIDTH = str.maketrans("０１２３４５６７８９＋　", "0123456789+ ")


# ---------- 语法 ----------

def parse(spec: str) -> list[str]:
    """代号串 → 车道名（规范顺序 0,1,2,3）。认不出就抛 ValueError，不猜。"""
    raw = (spec or "").translate(FULLWIDTH).strip()
    if not raw:
        raise ValueError("空的车道代号：默认用 1+2，全部用 all")
    raw = raw.replace(" ", "")
    codes = []
    for token in raw.split("+"):
        # `all` 只展开 1/2/3；王牌要单独写（`all+0`）
        codes.extend(["1", "2", "3"] if token.lower() == "all" else [token])
    seen = []
    for code in codes:
        if code not in CODE_TO_LANE:
            raise ValueError(f"不认识的车道代号：{code}（只认 0/1/2/3，用 + 连接，或写 all）")
        lane = CODE_TO_LANE[code]
        if lane not in seen:
            seen.append(lane)
    return sorted(seen, key=ALL_LANES.index)


def canonical(lanes) -> str:
    """车道名 → 代号串（规范写法）。"""
    ordered = [lane for lane in ALL_LANES if lane in set(lanes)]
    return "+".join(LANE_TO_CODE[lane] for lane in ordered)


# ---------- 状态文件 ----------

def setting_path(state_dir: str) -> str:
    return os.path.join(state_dir, SETTING_NAME)


def read_setting(state_dir: str) -> dict | None:
    """读开关；缺失、读不出、schema 不认识 ⇒ None（回落默认，不硬失败）。"""
    path = setting_path(state_dir)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("schema") != SETTING_SCHEMA:
        return None
    if not isinstance(data.get("spec"), str) or not data["spec"].strip():
        return None
    return data


def write_setting(state_dir: str, lanes, source: str) -> str:
    """原子写开关；只由塔台在显式参数下调用。"""
    os.makedirs(state_dir, exist_ok=True)
    path = setting_path(state_dir)
    data = {
        "schema": SETTING_SCHEMA,
        "spec": canonical(lanes),
        "lanes": [lane for lane in ALL_LANES if lane in set(lanes)],
        "set_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
    }
    fd, tmp = tempfile.mkstemp(prefix=".tower-lanes.", suffix=".tmp", dir=state_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    except OSError:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return path


# ---------- 解析与优先级 ----------

def inventory(cfg: dict) -> list[str]:
    """项目实例 paths.lanes＝这道项目有哪些车道（不是现在排哪几道）。"""
    raw = ((cfg.get("paths") or {}).get("lanes") or [])
    known = [x for x in raw if isinstance(x, str) and x in LANE_TO_CODE]
    return known or list(ALL_LANES)


def resolve(cfg: dict, state_dir: str, explicit: str | None = None) -> dict:
    """优先级：显式参数 > 状态文件 > 默认。返回规范化后的启用道。

    只保留项目实例里存在的道；一个可排班的机长道都没有 ⇒ 抛 ValueError。
    """
    if explicit is not None and str(explicit).strip():
        spec, source = str(explicit), "arg"
    else:
        data = read_setting(state_dir)
        spec = (data or {}).get("spec") or DEFAULT_SPEC
        source = "state" if data else "default"
    lanes = parse(spec)
    inv = inventory(cfg)
    kept = [lane for lane in lanes if lane in inv]
    dropped = [lane for lane in lanes if lane not in inv]
    normal = [lane for lane in kept if lane in NORMAL_LANES]
    if not normal:
        raise ValueError("启用道里没有可排班的机长道：1/2/3 至少留一个（0 是王牌道，塔台不排）")
    return {
        "spec": canonical(kept),
        "lanes": kept,
        "normal": normal,
        "dropped": dropped,
        "source": source,
    }


# ---------- 仓根与实例 ----------

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


def load_instance(repo: str) -> tuple:
    """返回 (cfg, state_dir_abs)；读不出返回 (None, 错误说明)。"""
    path = os.path.join(repo, INSTANCE_REL)
    if not os.path.isfile(path):
        return None, f"项目配置实例 {INSTANCE_REL} 不在 {repo}"
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, ValueError) as exc:
        return None, f"项目配置实例读不出：{exc}"
    state_dir = ((cfg.get("paths") or {}).get("state_dir") or "").strip()
    if not state_dir:
        return None, "实例里的 paths.state_dir 为空（车道开关要落在框架自有命名空间）"
    return cfg, os.path.join(repo, *state_dir.split("/"))


# ---------- 命令行 ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="车道代号（塔台排班开关）")
    sub = ap.add_subparsers(dest="mode", required=True)
    for name in ("show", "set", "parse"):
        p = sub.add_parser(name)
        if name != "parse":
            p.add_argument("--repo", default=None)
            p.add_argument("--json", action="store_true")
        if name == "set":
            p.add_argument("spec")
            p.add_argument("--source", default="command", choices=["command", "timer"])
        if name == "parse":
            p.add_argument("spec")
    a = ap.parse_args()

    if a.mode == "parse":
        try:
            lanes = parse(a.spec)
        except ValueError as exc:
            print(f"[缺件] {exc}")
            return 2
        print(f"spec={canonical(lanes)} lanes={','.join(lanes)}")
        return 0

    repo = resolve_repo(a.repo)
    if not repo:
        print("[缺件] 项目仓根解析不出（--repo / KAI_REPO_ROOT / git 根都没有）")
        return 2
    cfg, state_dir = load_instance(repo)
    if cfg is None:
        print(f"[缺件] {state_dir}")
        return 2

    if a.mode == "set":
        try:
            lanes = parse(a.spec)
            resolved = resolve(cfg, state_dir, explicit=a.spec)
        except ValueError as exc:
            print(f"[缺件] {exc}")
            return 2
        write_setting(state_dir, resolved["lanes"], a.source)
        print(f"已设启用道 spec={resolved['spec']} lanes={','.join(resolved['lanes'])}"
              f"（可排班：{','.join(resolved['normal'])}）")
        return 0

    try:
        resolved = resolve(cfg, state_dir)
    except ValueError as exc:
        print(f"[缺件] {exc}")
        return 2
    if a.json:
        print(json.dumps(resolved, ensure_ascii=False, indent=2))
    else:
        print(f"spec={resolved['spec']} lanes={','.join(resolved['lanes'])}"
              f" normal={','.join(resolved['normal'])} source={resolved['source']}")
        if resolved["dropped"]:
            print(f"（项目实例里没有这些道，已忽略：{','.join(resolved['dropped'])}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
