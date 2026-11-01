"""唤醒：一条消息 → 一次宿主会话（可续接），带预算与超时。

复用宿主适配器（见 v2/skills/travel/host-adapter.md）：适配器声明 `resume` 才续接，
不支持就每次新会话，如实降级。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .. import adapters


def _usage_tokens(report: dict[str, Any]) -> int:
    usage = report.get("usage") or {}
    total = 0
    for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens",
              "cache_read_input_tokens"):
        try:
            total += int(usage.get(k) or 0)
        except Exception:
            continue
    return total


def _answer(text: str, report: dict[str, Any]) -> str:
    notes = str(report.get("notes") or "")
    if notes and notes != "report not parseable; read diff" and "not parseable" not in notes:
        return str(report.get("answer") or report.get("summary") or notes)
    return (text or "").strip()


def make_wake(cfg: dict[str, Any], root: "Path | str", spawn=None, wait=None, read=None):
    """返回 wake(brief, cwd, resume) -> {text, session_id, tokens, adapter, rc}。

    spawn/wait/read 可注入（测试用）；默认真实走适配器。
    """
    wake_cfg = cfg.get("wake") or {}
    root = Path(root)

    def wake(brief: str, cwd: str, resume: "str | None" = None) -> dict[str, Any]:
        if spawn is not None:
            handle = spawn(brief, cwd, resume)
            rc, text = wait(handle), read(handle)
            adapter_name = str(handle.get("adapter") or "injected")
            report: dict[str, Any] = adapters.parse_report(text)
        else:
            adapter = adapters.pick(wake_cfg.get("adapter") or None, root)
            caps = adapters.capabilities(adapter)
            if resume and not caps.get("resume"):
                resume = None                     # 宿主不支持续接：如实降级
            sid = f"wake-{int(time.time() * 1000)}"
            sdir = root / ".coding" / "feishu" / "wake" / sid
            # 对话面不该有写盘与提交权限：用只读工具面起会话。
            handle = adapter.spawn(brief, Path(cwd), sdir,
                                   tier=str(wake_cfg.get("tier") or "light"),
                                   timeout=int(wake_cfg.get("timeout_s") or 600),
                                   read_only=True, resume=resume)
            rc = adapter.wait(handle, int(wake_cfg.get("timeout_s") or 600))
            text = adapter.read(handle)
            report = adapters.parse_report(text)
            adapter_name = adapter.name

        session_id = str(report.get("session_id") or resume or "")
        tokens = _usage_tokens(report)
        limit = int(wake_cfg.get("max_tokens") or 0)
        return {"text": _answer(text, report), "session_id": session_id,
                "tokens": tokens, "adapter": adapter_name, "rc": rc,
                "over_budget": bool(limit and tokens > limit)}

    return wake
