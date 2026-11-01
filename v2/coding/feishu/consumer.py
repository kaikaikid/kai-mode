"""事件消费：启动 lark-cli 的常驻事件流，把 NDJSON 行归一化成内部信封。

lark-cli 负责长连接与重连；这里只做「读一行、归一化、交给桥」，
以及断线后的退避重启。设计上**不**自己实现 WebSocket。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Iterable

from . import lark, policy


def parse_line(line: str, event_key: str, bot: str = "") -> "dict[str, Any] | None":
    line = (line or "").strip()
    if not line:
        return None
    try:
        raw = json.loads(line)
    except Exception:
        return None
    return policy.normalize(raw, event_key, bot)


def iter_events(lines: Iterable[str], event_key: str, bot: str = "") -> "Iterable[dict[str, Any]]":
    for line in lines:
        ev = parse_line(line, event_key, bot)
        if ev:
            yield ev


class Consumer(threading.Thread):
    """一个 EventKey 一条常驻流；退出后按 1/2/5/10/30 秒退避重启。"""

    KEY_MESSAGE = "im.message.receive_v1"
    KEY_CARD = "card.action.trigger"

    def __init__(self, bot: str, profile: str, event_key: str,
                 on_event: Callable[[dict[str, Any]], None], stop: threading.Event,
                 log_dir: "str | None" = None):
        super().__init__(daemon=True, name=f"feishu-consumer-{bot}-{event_key}")
        self.bot, self.profile, self.event_key = bot, profile, event_key
        self.on_event, self.stop, self.log_dir = on_event, stop, log_dir

    def run(self) -> None:
        backoff = [1, 2, 5, 10, 30]
        i = 0
        while not self.stop.is_set():
            cmd = lark.consume_cmd(self.profile, self.event_key)
            try:
                # stderr 落文件：用 PIPE 又不读会在大量日志后把子进程写阻塞。
                err = subprocess.DEVNULL
                if self.log_dir:
                    from pathlib import Path as _P
                    _P(self.log_dir).mkdir(parents=True, exist_ok=True)
                    err = open(_P(self.log_dir) / f"{self.bot}-{self.event_key}.log",
                               "a", encoding="utf-8")
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err,
                                        text=True, encoding="utf-8", errors="replace",
                                        **lark.no_window_kwargs())
            except Exception as e:
                print(f"[feishu.warn] cannot start consumer {self.event_key}: {e}", file=sys.stderr)
                if self.stop.wait(backoff[min(i, len(backoff) - 1)]):
                    return
                i += 1
                continue
            try:
                for ev in iter_events(proc.stdout or [], self.event_key, self.bot):
                    if self.stop.is_set():
                        break
                    try:
                        self.on_event(ev)
                    except Exception as e:
                        print(f"[feishu.warn] handler failed for {ev.get('dedup_key')}: {e}",
                              file=sys.stderr)
            finally:
                try:
                    proc.terminate()
                except Exception:
                    pass
            if self.stop.wait(backoff[min(i, len(backoff) - 1)]):
                return
            i += 1


def pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        if os.name == "nt":
            r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True,
                               **lark.no_window_kwargs())
            return str(pid) in (r.stdout or "")
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def write_pid(path, pid: int) -> None:
    from pathlib import Path
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(pid), encoding="utf-8")


def read_pid(path) -> int:
    from pathlib import Path
    p = Path(path)
    try:
        return int(p.read_text(encoding="utf-8").strip())
    except Exception:
        return 0
