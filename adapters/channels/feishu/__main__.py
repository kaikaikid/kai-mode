"""飞书桥命令行：python -m adapters.channels.feishu <run|triage|status>。

放这里而不是 engine/：engine 不许出现 feishu/lark 字样（engine/tests/test_purity.py）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 以 `python adapters/channels/feishu/...` 直跑时，仓根不在路径上。
_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from adapters.channels.feishu import config as fcfg, runner, triage  # noqa: E402


def main(argv: "list[str] | None" = None) -> int:
    p = argparse.ArgumentParser(prog="feishu-bridge", description="飞书桥（长连接，无公网回调）")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="起桥（常驻；--once 只跑一轮播报）")
    r.add_argument("--project", default=".", help="项目根（默认当前目录）")
    r.add_argument("--once", action="store_true")

    t = sub.add_parser("triage", help="只预览分诊结果，不执行、不写库")
    t.add_argument("text", nargs="+")

    s = sub.add_parser("status", help="打印配置自检（不含密钥）")
    s.add_argument("--project", default=".")

    a = p.parse_args(argv)
    if a.cmd == "run":
        return runner.run(a.project, once=a.once)
    if a.cmd == "triage":
        print(json.dumps(triage.decide(" ".join(a.text)), ensure_ascii=False))
        return 0
    if a.cmd == "status":
        cfg = fcfg.load(a.project)
        print(json.dumps({"enabled": bool(cfg.get("enabled")),
                          "problems": fcfg.problems(cfg),
                          "bots": [b.get("name") for b in cfg.get("bots") or []]},
                         ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
