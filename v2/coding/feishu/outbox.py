"""出站可靠投递：先落库再发，失败退避重试，超限进死信。

为什么必须持久化：门点卡发不出去 = 用户永远不知道要拍板。lark-cli 超时、网络抖动、
机器人被移出群，以前只是 stderr 一行警告，消息就此消失；现在每一条待发消息在任何
发送动作之前就已经在 sqlite 里，进程重启也还在。

幂等键随行一起存（`kaimode:<dedup_key>` / `kaimode:<run>:<指纹>`），所以重试不会
在群里刷出重复卡片。
"""

from __future__ import annotations

import json
from typing import Any, Callable

from . import config as fcfg

RETRY_BASE_S = 30
RETRY_CAP_S = 900
MAX_ATTEMPTS = 8


def backoff(attempts: int) -> float:
    """第 n 次失败后等多久：30s、1m、2m… 封顶 15 分钟。"""
    n = max(1, int(attempts or 1))
    return float(min(RETRY_CAP_S, RETRY_BASE_S * (2 ** (n - 1))))


def _payload(row: dict[str, Any]) -> "dict[str, Any] | None":
    try:
        data = json.loads(str(row.get("payload") or ""))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _profile_for(cfg: dict[str, Any], bot: str) -> str:
    """按机器人名找回它自己的 profile：多机器人时各自用各自的身份发。"""
    return str(fcfg.bot_for(cfg, bot).get("profile") or "")


def flush(ledger, deliver: Callable[[dict[str, Any], str], "tuple[bool, str]"],
          cfg: dict[str, Any], now: float, limit: int = 20) -> "dict[str, int]":
    """把到点的行逐条发出去，返回本轮的记账。"""
    stats = {"sent": 0, "retried": 0, "dead": 0}
    for row in ledger.due(now, limit):
        payload = _payload(row)
        if payload is None:
            ledger.bury(row["id"], "payload 不是合法 JSON")
            stats["dead"] += 1
            continue
        if not (payload.get("chat_id") or payload.get("user_id")):
            # 没有落点的行永远发不出去，别让它一直占着队列重试。
            ledger.bury(row["id"], "没有落点（chat_id 与 user_id 都为空）")
            stats["dead"] += 1
            continue
        ok, err = _attempt(deliver, payload, _profile_for(cfg, str(row.get("bot") or "")))
        if ok:
            ledger.mark_sent(row["id"])
            stats["sent"] += 1
            continue
        attempts = int(row.get("attempts") or 0) + 1
        if attempts >= MAX_ATTEMPTS:
            ledger.bury(row["id"], err or "unknown error")
            stats["dead"] += 1
        else:
            ledger.reschedule(row["id"], err or "unknown error", now + backoff(attempts))
            stats["retried"] += 1
    return stats


def _attempt(deliver: Callable[[dict[str, Any], str], "tuple[bool, str]"],
             payload: dict[str, Any], profile: str) -> "tuple[bool, str]":
    """发送一次。异常一律折成失败：lark-cli 卡住会抛 TimeoutExpired，CLI 缺失会抛
    FileNotFoundError——这两种正是本模块要兜住的场景，不能让它穿出去掀翻主循环。"""
    try:
        ok, err = deliver(payload, profile)
        return bool(ok), str(err or "")
    except Exception as e:                     # noqa: BLE001 —— 兜底，失败要记账不是要崩
        return False, f"{type(e).__name__}: {e}"[:400]
