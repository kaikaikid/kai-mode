"""白名单、事件归一化与卡片动作签名。

铁律：**默认全拒**。白名单空 = 谁都不认；卡片 token 不是身份凭证。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from typing import Any

MENTION_RE = re.compile(r"@_user_\d+")

# 事件 key 与归一化后的 kind 的对应（key 会随 lark-cli 版本变化，用后缀匹配）
KIND_BY_SUFFIX = (("message.receive", "message"), ("card.action", "card_action"),
                  ("member.bot.added", "bot_added"))


def kind_of(event_key: str) -> str:
    for suffix, kind in KIND_BY_SUFFIX:
        if suffix in (event_key or ""):
            return kind
    return "unknown"


def _first(d: dict, *names: str) -> str:
    for n in names:
        v = d.get(n)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict):
            inner = v.get("open_id") or v.get("id") or v.get("chat_id")
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
    return ""


def normalize(raw: dict[str, Any], event_key: str, bot: str = "") -> "dict[str, Any] | None":
    """把 lark-cli 的事件 JSON 归一化成桥的内部信封；认不出来返回 None。

    去重键按事件类型分：消息用 message_id（lark-cli schema 明确 event_id 不可作消息去重键），
    卡片动作用 nonce，其它用投递 id。
    """
    if not isinstance(raw, dict):
        return None
    kind = kind_of(event_key)
    ev: dict[str, Any] = {
        "event_key": event_key, "kind": kind, "bot": bot,
        "event_id": _first(raw, "event_id", "id"),
        "chat_id": _first(raw, "chat_id", "open_chat_id") or _first(raw.get("chat") or {}, "chat_id"),
        "chat_type": _first(raw, "chat_type") or "group",
        "sender": _first(raw, "sender_id", "sender", "operator_id", "user_id"),
        "message_id": _first(raw, "message_id", "open_message_id", "id"),
        "thread_id": _first(raw, "thread_id", "root_id"),
        "text": _first(raw, "content", "text"),
    }
    raw_mentions = raw.get("mentions") or []
    ev["mentions"] = [m for m in raw_mentions if isinstance(m, dict)]
    ev["mentions"] = [m.get("id") or m.get("open_id") for m in ev["mentions"]]
    ev["mentions"] = [m for m in ev["mentions"] if isinstance(m, str)]

    if kind == "card_action":
        # lark-cli 1.0.93 的卡片事件是扁平结构：action_value 是 JSON 字符串，
        # 没有 action 字典、也没有顶层 nonce（见 lark-cli event schema card.action.trigger）。
        action = raw.get("action")
        if not isinstance(action, dict):
            action = {}
        value = raw.get("action_value")
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    action = {**parsed, **action}
            except Exception:
                pass
        ev["action"] = action
        ev["nonce"] = str(action.get("nonce") or raw.get("nonce") or "")
        ev["update_token"] = str(raw.get("token") or "")
        ev["text"] = ""
        dedup = f"card:{ev['nonce'] or ev['event_id']}"
    elif kind == "message":
        dedup = f"msg:{ev['message_id'] or ev['event_id']}"
    else:
        dedup = f"evt:{ev['event_id'] or ev['message_id']}"
    if dedup.endswith(":"):
        return None
    ev["dedup_key"] = dedup
    return ev


def strip_mentions(text: str) -> str:
    return MENTION_RE.sub("", text or "").strip()


def mentioned_me(ev: dict[str, Any], bot_open_id: str = "") -> bool:
    """require_mention 的判定：有 @ 就够（bot 自己的 open_id 取不到时按有 @ 算）。"""
    if not ev.get("mentions"):
        return False
    if not bot_open_id:
        return True
    return bot_open_id in ev["mentions"]


def allowed(cfg: dict[str, Any], ev: dict[str, Any], bot_open_id: str = "") -> bool:
    allow = cfg.get("allow") or {}
    users = set(allow.get("users") or [])
    chats = set(allow.get("chats") or [])
    if not users:
        return False                      # 默认全拒
    if ev.get("sender") not in users:
        return False
    if ev.get("chat_type") == "p2p":
        return bool(allow.get("dm", True))
    if not chats or ev.get("chat_id") not in chats:
        return False                      # 空 chats 同样拒绝：默认全拒
    if allow.get("require_mention", True) and ev.get("kind") == "message":
        # 补读的历史消息如果本来就带了 mentions，照常按 @ 判定；只有历史里没给 mentions
        # 时才放行——否则账号在重启后会把「没对机器人说的」命令形态旧消息也执行了。
        if ev.get("backfilled") and not ev.get("mentions"):
            return True
        return mentioned_me(ev, bot_open_id)
    return True


# ── 卡片动作签名（防伪造按钮回调）────────────────────────────────
def canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(secret: str, payload: dict[str, Any]) -> str:
    return hmac.new(secret.encode("utf-8"), canonical(payload), hashlib.sha256).hexdigest()


def verify(secret: str, payload: dict[str, Any], sig: str) -> bool:
    if not secret or not sig:
        return False
    try:
        return hmac.compare_digest(sign(secret, payload), str(sig))
    except Exception:
        return False


def binding_key(ev: dict[str, Any]) -> str:
    """会话绑定键：私聊按人，群按 chat（有话题就带 thread）。"""
    bot = ev.get("bot") or ""
    if ev.get("chat_type") == "p2p":
        return f"{bot}|dm|{ev.get('sender')}"
    thread = str((ev.get("action") or {}).get("thread_id") or ev.get("thread_id") or "")
    return f"{bot}|chat|{ev.get('chat_id')}|{thread}"
