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


def consume_cmd(profile: str, event_key: str) -> list[str]:
    return base(profile) + ["event", "consume", event_key]


def chat_members(profile: str, chat_id: str) -> subprocess.CompletedProcess:
    return run(base(profile) + ["im", "+chat-members-list", "--chat-id", chat_id,
                                "--as", "bot", "--json"])


def chats(profile: str = "") -> subprocess.CompletedProcess:
    return run(base(profile) + ["im", "+chat-list", "--as", "bot", "--json"])


def version() -> subprocess.CompletedProcess:
    return run(cli_cmd() + ["--version"], timeout=20)
