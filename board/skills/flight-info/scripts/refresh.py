#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""刷一块板：采集 → 落 SQLite → 出 board.json ＋ index.html。

用法：
    python scripts/refresh.py --repo-root <仓根> --config <board.config.json> [--quiet] [--no-network]

退出码：
    0  板已生成（**含降级**；数据好坏看 board.json 的 sources，不看退出码）
    2  配置/参数错（逐条打印错在哪）
    3  写盘失败
"""
from __future__ import annotations

import argparse
import os
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SKILL_ROOT not in sys.path:
    sys.path.insert(0, SKILL_ROOT)

from flightinfo import collect, config, db, render  # noqa: E402


def run_refresh(repo_root: str, config_path: str, quiet: bool = False,
                no_network: bool = False) -> dict:
    """核心：采集 → 落库 → 出板。供 refresh.py 与 refresh_if_dirty.py 共用。

    返回 {"ok": bool, "rc": int, "stats": ..., "paths": ..., "board_dir": ...}
    """
    repo_root = os.path.abspath(repo_root)
    if not os.path.isdir(repo_root):
        return {"ok": False, "rc": 2, "error": f"仓根不存在：{repo_root}"}
    if not os.path.isfile(config_path):
        return {"ok": False, "rc": 2, "error": f"板配置不存在：{config_path}"}

    cfg = config.load(config_path)
    problems = config.validate(cfg)
    if problems:
        return {"ok": False, "rc": 2, "error": "板配置不合规：" + "；".join(problems)}

    bdir = config.board_dir(repo_root, cfg)
    ctx = config.build_ctx(repo_root, cfg)
    ctx["no_network"] = no_network

    conn = db.connect(db.db_path(bdir))
    try:
        db.migrate(conn, os.path.join(SKILL_ROOT, "schema"))
        run_id = db.new_run_id()
        stats = collect.run_sources(cfg, ctx, conn, run_id)
        payload = render.build_summary(conn, cfg, bdir)
        # 趋势线：本轮 KPI 先落 history.jsonl，再把（含本轮的）近 N 轮塞回 payload
        if render.append_history(bdir, run_id, payload["kpi"], payload["sources"],
                                 coding_trend=payload.get("coding", {}).get("counts")):
            payload["trend"] = render.read_trend(bdir)
        paths = render.write_outputs(bdir, payload, cfg)
        db.record_board_run(conn, run_id, payload["kpi"], payload["sources"],
                            paths["board.json"]["sha256"], paths["index.html"]["sha256"])
        db.commit(conn)
    except OSError as e:
        return {"ok": False, "rc": 3, "error": f"写盘失败：{e}"}
    finally:
        conn.close()

    if not quiet:
        print(f"板：{cfg['name']}  →  {bdir}")
        print(f"航班 {stats['flights']} 张，排班 {stats['schedules']} 行，库 run_id={run_id}")
        for sid, v in stats["sources"].items():
            print(f"  [{v['status']}] {sid}：{v['detail']}")
        for k in ("board.json", "index.html"):
            print(f"  {k}  {paths[k]['bytes']} B  sha256={paths[k]['sha256'][:12]}")
    else:
        bad = sum(1 for v in stats["sources"].values() if v["status"] != "ok")
        print(f"[{cfg['name']}] {stats['flights']} 航班 / {stats['schedules']} 排班"
              f" / 降级 {bad} 源")
    return {"ok": True, "rc": 0, "stats": stats, "paths": paths,
            "board_dir": bdir, "config": cfg}


def main() -> int:
    ap = argparse.ArgumentParser(description="刷新一块 flight-info 板")
    ap.add_argument("--repo-root", required=True, help="项目仓根")
    ap.add_argument("--config", required=True, help="板配置 board.config.json")
    ap.add_argument("--quiet", action="store_true", help="只打一行汇总")
    ap.add_argument("--no-network", action="store_true", help="不发任何网络请求")
    a = ap.parse_args()

    res = run_refresh(a.repo_root, a.config, quiet=a.quiet, no_network=a.no_network)
    if not res["ok"]:
        print(res.get("error", "刷新失败"), file=sys.stderr)
    return res["rc"]


if __name__ == "__main__":
    sys.exit(main())
