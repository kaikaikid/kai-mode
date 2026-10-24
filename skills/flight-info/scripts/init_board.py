#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""建一块板：校验配置 → 建目录 → 留档配置 → 出第一版板。

    python scripts/init_board.py --repo-root <仓根> [--config <json>] [--name <板名>] [--force]

退出码：0 建好；2 配置/参数错或同名板已存在；3 写不出。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SKILL_ROOT not in sys.path:
    sys.path.insert(0, SKILL_ROOT)

from flightinfo import config  # noqa: E402

DEFAULT_CFG = os.path.join(SKILL_ROOT, "templates", "board.config.example.json")


def main() -> int:
    ap = argparse.ArgumentParser(description="建一块 flight-info 板")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--config", default=DEFAULT_CFG)
    ap.add_argument("--name", default=None, help="覆盖配置里的板名")
    ap.add_argument("--force", action="store_true", help="同名板已存在时覆盖配置与产物")
    a = ap.parse_args()

    repo_root = os.path.abspath(a.repo_root)
    if not os.path.isdir(repo_root):
        print(f"仓根不存在：{repo_root}", file=sys.stderr)
        return 2
    if not os.path.isfile(a.config):
        print(f"板配置不存在：{a.config}", file=sys.stderr)
        return 2

    cfg = config.load(a.config)
    if a.name:
        cfg["name"] = a.name
    problems = config.validate(cfg)
    if problems:
        print("板配置不合规：", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 2

    bdir = config.board_dir(repo_root, cfg)
    if os.path.isdir(bdir) and os.listdir(bdir) and not a.force:
        print(f"同名板已存在：{bdir}（要覆盖加 --force）", file=sys.stderr)
        return 2
    os.makedirs(bdir, exist_ok=True)

    saved = os.path.join(bdir, "board.config.json")
    try:
        with open(saved, "w", encoding="utf-8", newline="\n") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except OSError as e:
        print(f"写配置失败：{e}", file=sys.stderr)
        return 3

    print(f"板目录：{bdir}")
    print(f"配置留档：{saved}")

    from flightinfo import collect, db, render
    ctx = config.build_ctx(repo_root, cfg)
    conn = db.connect(db.db_path(bdir))
    try:
        db.migrate(conn, os.path.join(SKILL_ROOT, "schema"))
        run_id = db.new_run_id()
        stats = collect.run_sources(cfg, ctx, conn, run_id)
        payload = render.build_summary(conn, cfg)
        paths = render.write_outputs(bdir, payload, cfg)
        db.record_board_run(conn, run_id, payload["kpi"], payload["sources"],
                            paths["board.json"]["sha256"], paths["index.html"]["sha256"])
        db.commit(conn)
    except OSError as e:
        print(f"出板失败：{e}", file=sys.stderr)
        conn.close()
        return 3
    finally:
        try:
            conn.close()
        except Exception:
            pass

    print(f"首版已出：{stats['flights']} 航班 / {stats['schedules']} 排班")
    for sid, v in stats["sources"].items():
        print(f"  [{v['status']}] {sid}：{v['detail']}")
    print(f"人读面：{paths['index.html']['path']}")
    print(f"机读面：{paths['board.json']['path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
