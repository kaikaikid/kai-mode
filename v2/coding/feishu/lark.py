"""lark-cli 薄封装：所有出站调用都从这里走，构造参数集中一处。

测试时设 KAI_LARK_CLI 指向一个假脚本来替代真 CLI。
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any


def cli_cmd() -> list[str]:
    override = os.environ.get("KAI_LARK_CLI")
    if override:
        return [override]
    if os.name == "nt":
        return ["lark-cli.cmd"]
    return ["lark-cli"]


def no_window_kwargs() -> dict:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def base(profile: str = "") -> list[str]:
    cmd = cli_cmd()
    if profile:
        cmd += ["--profile", profile]
    return cmd


def run(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, **no_window_kwargs())


def send_text(profile: str, chat_id: str, text: str, idem: str = "",
              user_id: str = "") -> subprocess.CompletedProcess:
    target = ["--user-id", user_id] if user_id else ["--chat-id", chat_id]
    args = base(profile) + ["im", "+messages-send"] + target + ["--text", text]
    if idem:
        args += ["--idempotency-key", idem[:50]]
    return run(args)


def send_card(profile: str, chat_id: str, card: dict[str, Any], idem: str = "",
              user_id: str = "") -> subprocess.CompletedProcess:
    target = ["--user-id", user_id] if user_id else ["--chat-id", chat_id]
    args = base(profile) + ["im", "+messages-send"] + target + [
                            "--msg-type", "interactive", "--content",
                            json.dumps(card, ensure_ascii=False)]
    if idem:
        args += ["--idempotency-key", idem[:50]]
    return run(args)


def reply_text(profile: str, message_id: str, text: str, idem: str = "") -> subprocess.CompletedProcess:
    args = base(profile) + ["im", "+messages-reply", "--message-id", message_id, "--text", text]
    if idem:
        args += ["--idempotency-key", idem[:50]]
    return run(args)


def patch_card(profile: str, message_id: str, card: dict[str, Any]) -> subprocess.CompletedProcess:
    """原地更新卡片（仅 interactive，14 天内，内容 ≤30KB）。"""
    content = json.dumps(card, ensure_ascii=False)
    body = json.dumps({"content": content}, ensure_ascii=False)
    return run(base(profile) + ["im", "messages", "patch", "--message-id", message_id,
                                "--data", body, "--as", "bot", "--json"])


def pin(profile: str, message_id: str) -> subprocess.CompletedProcess:
    body = json.dumps({"message_id": message_id}, ensure_ascii=False)
    return run(base(profile) + ["im", "pins", "create", "--data", body, "--as", "bot", "--json"])


def unpin(profile: str, message_id: str) -> subprocess.CompletedProcess:
    """取消置顶：message_id 是路径参数，且属 high-risk，必须带 --yes。"""
    return run(base(profile) + ["im", "pins", "delete", "--message-id", message_id,
                                "--yes", "--as", "bot", "--json"])


def history(profile: str, chat_id: str, start_iso: str = "", limit: int = 50,
            timeout: int = 120) -> subprocess.CompletedProcess:
    """会话历史（机器人视角）。start 用 ISO 8601，只取之后的。"""
    args = base(profile) + ["im", "+chat-messages-list", "--chat-id", chat_id,
                            "--order", "asc", "--page-size", str(max(1, min(50, limit))),
                            "--as", "bot", "--json"]
    if start_iso:
        args += ["--start", start_iso]
    return run(args, timeout=timeout)


def _find_message_id(obj: Any) -> str:
    if isinstance(obj, dict):
        for k in ("message_id", "open_message_id"):
            v = obj.get(k)
            if isinstance(v, str) and v.startswith("om_"):
                return v
        for v in obj.values():
            found = _find_message_id(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_message_id(v)
            if found:
                return found
    return ""


def message_id_of(proc: subprocess.CompletedProcess) -> str:
    """从发送回执里取 message_id；取不到返回空串（如实降级，不猜）。"""
    if getattr(proc, "returncode", 1) != 0:
        return ""
    try:
        return _find_message_id(json.loads(proc.stdout or ""))
    except Exception:
        return ""


def _items(data: Any) -> "list[dict[str, Any]]":
    """在历史响应里找到消息列表：不同版本包在 items / messages / data.items 下。"""
    if isinstance(data, dict):
        for k in ("items", "messages"):
            v = data.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        for k in ("data", "result"):
            found = _items(data.get(k))
            if found:
                return found
    elif isinstance(data, list):
        return [x for x in data if isinstance(x, dict) and ("message_id" in x or "id" in x)]
    return []


def history_items(proc: subprocess.CompletedProcess) -> "list[dict[str, Any]] | None":
    """成功返回消息列表（可能为空）；读失败或结构认不出返回 None——

    两者必须分开：把「读失败」当成「没有消息」，补读会把水位推进过去，消息就永久丢了。
    """
    if getattr(proc, "returncode", 1) != 0:
        return None
    try:
        data = json.loads(proc.stdout or "")
    except Exception:
        return None
    if not isinstance(data, (dict, list)):
        return None
    return _items(data)


def consume_cmd(profile: str, event_key: str) -> list[str]:
    return base(profile) + ["event", "consume", event_key]


def chat_members(profile: str, chat_id: str) -> subprocess.CompletedProcess:
    return run(base(profile) + ["im", "+chat-members-list", "--chat-id", chat_id,
                                "--as", "bot", "--json"])


def chats(profile: str = "") -> subprocess.CompletedProcess:
    return run(base(profile) + ["im", "+chat-list", "--as", "bot", "--json"])


def version() -> subprocess.CompletedProcess:
    return run(cli_cmd() + ["--version"], timeout=20)
