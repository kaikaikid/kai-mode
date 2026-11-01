"""桥的主循环：起消费者、收事件、按间隔播报。一次性模式便于自检与测试。"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from typing import Any

from . import bridge as fbridge, config as fcfg, consumer, notify
from .wake import make_wake


def _deliver(b: fbridge.Bridge, outs: "list[dict[str, Any]]", profile: str) -> None:
    for out in outs:
        if not out.get("chat_id") and not out.get("user_id"):
            continue
        ok, err = b.deliver(out, profile)
        if not ok:
            print(f"[feishu.warn] deliver failed: {err}", file=sys.stderr)


def run(root: "Path | str", once: bool = False) -> int:
    root = Path(root)
    cfg = fcfg.load(root)
    problems = fcfg.problems(cfg)
    for p in problems:
        print(f"[feishu] {p}", file=sys.stderr)
    if not cfg.get("enabled"):
        print("[feishu] enabled=false，不启动。改 <数据根>/kai-mode/feishu.json 后重试。", file=sys.stderr)
        return 2

    b = fbridge.Bridge(root, cfg, wake_fn=make_wake(cfg, root))
    default = fcfg.bot_for(cfg)
    profile = str(default.get("profile") or "")

    if once:
        outs = b.tick()
        _deliver(b, outs, profile)
        return 0

    stop = threading.Event()
    threads = []
    for bot in cfg.get("bots") or []:
        name = str(bot.get("name") or "default")
        prof = str(bot.get("profile") or "")

        def on_event(ev: dict[str, Any], _prof: str = prof) -> None:
            _deliver(b, b.handle(ev), _prof)

        for key in (consumer.Consumer.KEY_MESSAGE, consumer.Consumer.KEY_CARD):
            t = consumer.Consumer(name, prof, key, on_event, stop,
                                  log_dir=str(root / ".coding" / "feishu" / "logs"))
            t.start()
            threads.append(t)

    interval = max(5, int((cfg.get("notify") or {}).get("poll_s") or 15))
    # 通知投递统一走默认机器人的 profile（状态卡没有「谁问的」这回事）。
    try:
        while not stop.is_set():
            time.sleep(interval)
            _deliver(b, b.tick(), profile)
    except KeyboardInterrupt:
        stop.set()
    finally:
        stop.set()
        for t in threads:
            t.join(timeout=5)
    return 0
