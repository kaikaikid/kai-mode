"""飞书桥配置：机器级一份，项目级可选覆盖。

机器级：`<KAI_AGENT_DATA_ROOT>/kai-mode/feishu.json`（没设变量时 `~/.kai-mode/feishu.json`）
项目级：`<项目根>/.coding/feishu.json`（gitignored）

为什么分两层：app 绑定、open_id 白名单、chat_id、token 变量名都是**机器事实**，
不该跟着仓库走；项目级只回答「这个仓接不接、发到哪个群」。
"""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "enabled": False,
    # 多机器人：一个应用一个 profile；name 只用于日志与看板。
    "bots": [{"name": "default", "profile": "", "app_id": "", "chat_id": ""}],
    "allow": {"users": [], "chats": [], "dm": True, "require_mention": True},
    "serve": {"url": "http://127.0.0.1:8765", "token_env": "KAI_TRAVEL_TOKEN"},
    "notify": {"poll_s": 15, "debounce_s": 10, "gate_reminder_min": 20, "max_reminders": 3},
    # 对话模式：同一条飞书会话续同一个宿主会话；默认开启（不带命令的话默认就是聊）。
    "chat": {"enabled": True, "idle_min": 45, "max_turns": 20,
             "budget_tokens": 60000, "daily_budget_tokens": 200000},
    "wake": {"adapter": "", "tier": "light", "cooldown_s": 0, "timeout_s": 600, "max_tokens": 120000},
    "retention": {"inbox_days": 30, "raw_days": 7, "audit_days": 90, "outbox_days": 14},
}


def machine_dir() -> Path:
    root = os.environ.get("KAI_AGENT_DATA_ROOT")
    return Path(root) / "kai-mode" if root else Path.home() / ".kai-mode"


def machine_path() -> Path:
    return machine_dir() / "feishu.json"


def project_path(project_root: "Path | str") -> Path:
    return Path(project_root) / ".coding" / "feishu.json"


def _read(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[travel.warn] {path} is not valid JSON ({e}); ignored", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    """深合并：字典逐键递归，列表与标量整体覆盖。"""
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def _norm_bots(cfg: dict[str, Any]) -> dict[str, Any]:
    bots = cfg.get("bots")
    if isinstance(bots, dict):          # 单机器人简写
        bots = [bots]
    if not isinstance(bots, list) or not bots:
        bots = [{"name": "default"}]
    clean = []
    for i, b in enumerate(bots):
        if not isinstance(b, dict):
            continue
        clean.append({
            "name": str(b.get("name") or f"bot{i + 1}"),
            "profile": str(b.get("profile") or ""),
            "app_id": str(b.get("app_id") or ""),
            "chat_id": str(b.get("chat_id") or ""),
        })
    cfg["bots"] = clean or [{"name": "default", "profile": "", "app_id": "", "chat_id": ""}]
    return cfg


def load(project_root: "Path | str | None" = None) -> dict[str, Any]:
    # 深拷贝：否则调用方改 cfg["chat"] 会改到 DEFAULTS 本身，污染后续所有实例。
    cfg = _merge(copy.deepcopy(DEFAULTS), _read(machine_path()))
    if project_root:
        cfg = _merge(cfg, _read(project_path(project_root)))
    return _norm_bots(cfg)


def save_machine(cfg: dict[str, Any]) -> Path:
    p = machine_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def bot_for(cfg: dict[str, Any], name_or_chat: str = "") -> dict[str, Any]:
    """按名字或 chat_id 找机器人；找不到退回第一个。"""
    for b in cfg.get("bots") or []:
        if name_or_chat and name_or_chat in {b.get("name"), b.get("chat_id")}:
            return b
    return (cfg.get("bots") or [{}])[0]


def problems(cfg: dict[str, Any]) -> list[str]:
    """配置自检：缺什么直接说，不猜。"""
    out = []
    if not cfg.get("enabled"):
        out.append("enabled=false：桥不会启动")
    allow = cfg.get("allow") or {}
    if not (allow.get("users") or []):
        out.append("allow.users 为空：谁都不会被受理（默认全拒）")
    if not (allow.get("chats") or []):
        out.append("allow.chats 为空：群消息不会被受理")
    for b in cfg.get("bots") or []:
        if not b.get("chat_id"):
            out.append(f"机器人 {b.get('name')} 没有 chat_id：看板与通知没有落点")
    return out
