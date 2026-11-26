#!/usr/bin/env python3
"""Add or show the local release gate pointer in gold/fleet skill docs.

Standalone maintainer script. Idempotent; does not touch installed library copies.
"""

from __future__ import annotations

import argparse
from pathlib import Path

BASE = "## 本地发布门禁（本地优先）"
TEXT = """## 本地发布门禁（本地优先）

合并推送不等于上线。涉及本地服务/数据库/密钥/公网的项目，在 `gate g2 approve` 前跑
`python <kai-mode>/scripts/local-release-gate.py --repo <项目> --target local`；红则不放行。
项目侧配置 `.coding/local-deploy.json` 记录 start/healthcheck/rollback/verify_cmds，
回执落 `.coding/release-gate/`。规则正本：`docs/adr/0040-local-first-release-gate.md`。
本门禁只在本机运行，不调用云部署/LLM；对外发布、花钱、不可逆仍按红线先问。
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="kai-mode repo root")
    ap.add_argument("--apply", action="store_true", help="write the pointer into gold/fleet SKILL.md")
    args = ap.parse_args()
    root = Path(args.root).resolve()
    targets = [
        root / "core" / "skills" / "gold" / "SKILL.md",
        root / "engine" / "skills" / "fleet" / "SKILL.md",
    ]
    if not args.apply:
        for p in targets:
            text = p.read_text(encoding="utf-8") if p.is_file() else ""
            print(f"{p}: {'has' if BASE in text else 'missing'}")
        return 0
    for p in targets:
        if not p.is_file():
            print(f"MISSING {p}")
            continue
        text = p.read_text(encoding="utf-8")
        if BASE in text:
            print(f"SKIP {p} (already present)")
            continue
        p.write_text(text.rstrip() + "\n\n" + TEXT, encoding="utf-8")
        print(f"ADD {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
