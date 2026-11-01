"""桥的主循环：起消费者、收事件、按间隔播报。一次性模式便于自检与测试。

出站一律走队列：先落库再发，发不出去的靠下一轮退避重试，不静默丢。
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

from . import bridge as fbridge, config as fcfg, consumer
from .wake import make_wake

EXIT_ALREADY_RUNNING = 3


def _report(stats: "dict[str, int]") -> "dict[str, int]":
    dead = int(stats.get("dead") or 0)
    if dead:
        print(f"[feishu.warn] {dead} 条出站消息重试用尽，进死信；"
              f"看 `travel feishu outbox`，要重发用 `travel feishu outbox --retry`。",
              file=sys.stderr)
    return stats


def _acquire(root: Path) -> "tuple[Path | None, int]":
    """单实例：两个桥进程会各自 flush，同一行被发两次、attempts 每轮 +2。"""
    pid_path = root / ".coding" / "feishu" / "bridge.pid"
    other = consumer.read_pid(pid_path)
    if other and other != os.getpid() and consumer.pid_alive(other):
        return None, other
    consumer.write_pid(pid_path, os.getpid())
    return pid_path, 0


def run(root: "Path | str", once: bool = False) -> int:
    root = Path(root)
    cfg = fcfg.load(root)
    problems = fcfg.problems(cfg)
    for p in problems:
        print(f"[feishu] {p}", file=sys.stderr)
    if not cfg.get("enabled"):
        print("[feishu] enabled=false，不启动。改 <数据根>/kai-mode/feishu.json 后重试。", file=sys.stderr)
        return 2

    pid_path, other = _acquire(root)
    if pid_path is None:
        print(f"[feishu] 已经有一个桥在跑（pid {other}），不再起第二个；先停掉它。", file=sys.stderr)
        return EXIT_ALREADY_RUNNING

    try:
        return _run(root, cfg, once)
    finally:
        try:
            pid_path.unlink()
        except OSError:
            pass


def _run(root: Path, cfg: "dict[str, Any]", once: bool) -> int:
    b = fbridge.Bridge(root, cfg, wake_fn=make_wake(cfg, root))
    days = int((cfg.get("retention") or {}).get("outbox_days") or 14)
    if days > 0:
        b.ledger.purge_outbox(b.now() - days * 86400)

    if once:
        _report(b.publish())
        return 0

    stop = threading.Event()
    threads = []
    for bot in cfg.get("bots") or []:
        name = str(bot.get("name") or "default")
        prof = str(bot.get("profile") or "")

        def on_event(ev: dict[str, Any]) -> None:
            # 事件线程只顺手发一小把：积压的旧行留给主循环，别把 WS 读取卡住。
            b.enqueue(b.handle(ev))
            _report(b.flush(limit=5))

        for key in (consumer.Consumer.KEY_MESSAGE, consumer.Consumer.KEY_CARD):
            t = consumer.Consumer(name, prof, key, on_event, stop,
                                  log_dir=str(root / ".coding" / "feishu" / "logs"))
            t.start()
            threads.append(t)

    interval = max(5, int((cfg.get("notify") or {}).get("poll_s") or 15))
    try:
        while not stop.is_set():
            time.sleep(interval)
            try:
                # publish 内部会顺手 flush 一轮：上一轮没发出去的在这里续上。
                _report(b.publish())
            except Exception as e:          # noqa: BLE001 —— 常驻进程不能因一轮失败就死
                print(f"[feishu.warn] 这一轮播报失败，下轮再试：{type(e).__name__}: {e}",
                      file=sys.stderr)
    except KeyboardInterrupt:
        stop.set()
    finally:
        stop.set()
        for t in threads:
            t.join(timeout=5)
    return 0
